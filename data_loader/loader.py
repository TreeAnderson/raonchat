import re
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import settings
from vectorstore import SupabaseStore


class DataLoader:
    SEPARATORS = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]
    EXTENSIONS = {".md", ".txt"}

    def __init__(self, store: SupabaseStore):
        self._store = store
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=self.SEPARATORS,
        )

    def _split_markdown_sections(self, text: str) -> list[dict]:
        """마크다운을 ### 헤딩 기준으로 분할하고, 부모 ## 경로를 프리픽스로 추가한다.

        Returns:
            list of {"content": str, "section": str}
        """
        lines = text.split("\n")
        sections: list[dict] = []
        current_h2 = ""
        current_h3 = ""
        current_lines: list[str] = []

        def _flush():
            content = "\n".join(current_lines).strip()
            if not content:
                return
            section_path = current_h2
            if current_h3:
                section_path = f"{current_h2} > {current_h3}" if current_h2 else current_h3
            sections.append({"content": content, "section": section_path})

        for line in lines:
            if re.match(r"^## ", line):
                _flush()
                current_h2 = line.strip()
                current_h3 = ""
                current_lines = [line]
            elif re.match(r"^### ", line):
                _flush()
                current_h3 = line.strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        _flush()

        # 2차 분할: max_chunk_size 초과 시 RecursiveCharacterTextSplitter 적용
        result: list[dict] = []
        for sec in sections:
            if len(sec["content"]) <= settings.chunk_size:
                result.append(sec)
            else:
                sub_chunks = self._splitter.split_text(sec["content"])
                for chunk in sub_chunks:
                    result.append({"content": chunk, "section": sec["section"]})

        return result

    def list_files(self) -> list[Path]:
        raw_dir = settings.raw_data_dir
        if not raw_dir.exists():
            return []
        return sorted(
            f for f in raw_dir.rglob("*") if f.is_file() and f.suffix in self.EXTENSIONS
        )

    def ingest_all(self, force: bool = False) -> dict:
        files = self.list_files()
        result = {"total_files": len(files), "ingested": 0, "skipped": 0, "chunks": 0}

        for file_path in files:
            chunks = self._ingest_file(file_path, force=force)
            if chunks > 0:
                result["ingested"] += 1
                result["chunks"] += chunks
            else:
                result["skipped"] += 1

        return result

    def ingest_file(self, file_path: Path) -> int:
        return self._ingest_file(file_path, force=True)

    def _ingest_file(self, file_path: Path, force: bool = False) -> int:
        if force:
            self._store.delete_by_source(str(file_path))

        text = file_path.read_text(encoding="utf-8")
        if not text.strip():
            return 0

        title = self._extract_title(text, file_path.stem)
        category = self._extract_category(file_path)

        if file_path.suffix == ".md":
            section_chunks = self._split_markdown_sections(text)
            if not section_chunks:
                return 0
            documents = []
            for i, sec in enumerate(section_chunks):
                prefix = f"[{sec['section']}]\n\n" if sec["section"] else ""
                doc = Document(
                    page_content=prefix + sec["content"],
                    metadata={
                        "source": str(file_path),
                        "filename": file_path.name,
                        "title": title,
                        "category": category,
                        "section": sec["section"],
                        "chunk_index": i,
                        "total_chunks": len(section_chunks),
                        "ingested_at": datetime.now().isoformat(),
                    },
                )
                documents.append(doc)
        else:
            chunks = self._splitter.split_text(text)
            if not chunks:
                return 0
            documents = []
            for i, chunk in enumerate(chunks):
                doc = Document(
                    page_content=chunk,
                    metadata={
                        "source": str(file_path),
                        "filename": file_path.name,
                        "title": title,
                        "category": category,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "ingested_at": datetime.now().isoformat(),
                    },
                )
                documents.append(doc)

        self._store.add_documents(documents)
        return len(documents)

    def _extract_title(self, text: str, default: str) -> str:
        match = re.match(r"^#\s+(.+)", text.strip())
        return match.group(1).strip() if match else default

    def _extract_category(self, file_path: Path) -> str:
        try:
            rel = file_path.relative_to(settings.raw_data_dir)
            parts = rel.parts
            return parts[0] if len(parts) > 1 else ""
        except ValueError:
            return ""
