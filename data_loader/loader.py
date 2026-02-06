import re
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import settings
from vectorstore import ChromaStore


class DataLoader:
    SEPARATORS = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]
    EXTENSIONS = {".md", ".txt"}

    def __init__(self, store: ChromaStore):
        self._store = store
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=self.SEPARATORS,
        )

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
