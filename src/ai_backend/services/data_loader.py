import re
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import settings
from .vectorstore import SupabaseStore

_HEADING_RE = re.compile(r'^(#{2,4})\s+(\d[\d.]*)\s+(.*)')
_HEADING_NO_NUM_RE = re.compile(r'^(#{2,4})\s+(.*)')


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

    @staticmethod
    def _parse_heading(line: str) -> dict | None:
        m = _HEADING_RE.match(line.strip())
        if m:
            level = len(m.group(1))
            number = m.group(2).rstrip(".")
            title = m.group(3).strip()
            return {"level": level, "number": number, "title": title}
        m = _HEADING_NO_NUM_RE.match(line.strip())
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            return {"level": level, "number": "", "title": title}
        return None

    def _separate_code_blocks(self, sections: list[dict]) -> list[dict]:
        result: list[dict] = []
        code_pattern = re.compile(r"(```(\w*)\n.*?```)", re.DOTALL)

        for sec in sections:
            base_meta = {k: v for k, v in sec.items() if k != "content"}

            parts = code_pattern.split(sec["content"])
            i = 0
            while i < len(parts):
                if i + 2 < len(parts) and parts[i + 1] is not None and parts[i + 1].startswith("```"):
                    prose_text = parts[i].strip()
                    if prose_text:
                        result.append({
                            **base_meta,
                            "content": prose_text,
                            "content_type": "prose",
                        })
                    code_text = parts[i + 1].strip()
                    code_lang = parts[i + 2] or ""
                    if code_text:
                        result.append({
                            **base_meta,
                            "content": code_text,
                            "content_type": "code",
                            "code_language": code_lang,
                        })
                    i += 3
                else:
                    prose_text = parts[i].strip()
                    if prose_text:
                        result.append({
                            **base_meta,
                            "content": prose_text,
                            "content_type": "prose",
                        })
                    i += 1

        return result

    def _split_markdown_sections(self, text: str) -> list[dict]:
        lines = text.split("\n")
        sections: list[dict] = []

        current_h2 = ""
        current_h2_number = ""
        current_h2_title = ""
        current_h3 = ""
        current_h3_number = ""
        current_h3_title = ""
        current_h4 = ""
        current_h4_number = ""
        current_h4_title = ""
        current_lines: list[str] = []

        def _build_section_path() -> str:
            parts = []
            if current_h2:
                parts.append(current_h2)
            if current_h3:
                parts.append(current_h3)
            if current_h4:
                parts.append(current_h4)
            return " > ".join(parts)

        def _section_number() -> str:
            if current_h4_number:
                return current_h4_number
            if current_h3_number:
                return current_h3_number
            return current_h2_number

        def _flush():
            content = "\n".join(current_lines).strip()
            if not content:
                return
            meta = {
                "content": content,
                "section": _build_section_path(),
                "section_number": _section_number(),
                "h2": current_h2,
                "h2_number": current_h2_number,
                "h2_title": current_h2_title,
            }
            if current_h3:
                meta["h3"] = current_h3
                meta["h3_number"] = current_h3_number
                meta["h3_title"] = current_h3_title
            if current_h4:
                meta["h4"] = current_h4
                meta["h4_number"] = current_h4_number
                meta["h4_title"] = current_h4_title
            sections.append(meta)

        for line in lines:
            parsed = self._parse_heading(line)
            if parsed and parsed["level"] == 2:
                _flush()
                current_h2 = line.strip()
                current_h2_number = parsed["number"]
                current_h2_title = parsed["title"]
                current_h3 = ""
                current_h3_number = ""
                current_h3_title = ""
                current_h4 = ""
                current_h4_number = ""
                current_h4_title = ""
                current_lines = [line]
            elif parsed and parsed["level"] == 3:
                _flush()
                current_h3 = line.strip()
                current_h3_number = parsed["number"]
                current_h3_title = parsed["title"]
                current_h4 = ""
                current_h4_number = ""
                current_h4_title = ""
                current_lines = [line]
            elif parsed and parsed["level"] == 4:
                _flush()
                current_h4 = line.strip()
                current_h4_number = parsed["number"]
                current_h4_title = parsed["title"]
                current_lines = [line]
            else:
                current_lines.append(line)

        _flush()

        separated = self._separate_code_blocks(sections)

        result: list[dict] = []
        for sec in separated:
            if sec["content_type"] == "code" or len(sec["content"]) <= settings.chunk_size:
                result.append(sec)
            else:
                base_meta = {k: v for k, v in sec.items() if k != "content"}
                sub_chunks = self._splitter.split_text(sec["content"])
                for chunk in sub_chunks:
                    result.append({
                        **base_meta,
                        "content": chunk,
                    })

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
                meta = {
                    "source": str(file_path),
                    "filename": file_path.name,
                    "title": title,
                    "category": category,
                    "section": sec["section"],
                    "section_number": sec.get("section_number", ""),
                    "content_type": sec.get("content_type", "prose"),
                    "chunk_index": i,
                    "total_chunks": len(section_chunks),
                    "ingested_at": datetime.now().isoformat(),
                    "h2_number": sec.get("h2_number", ""),
                    "h2_title": sec.get("h2_title", ""),
                }
                if sec.get("h3"):
                    meta["h3_number"] = sec.get("h3_number", "")
                    meta["h3_title"] = sec.get("h3_title", "")
                if sec.get("h4"):
                    meta["h4_number"] = sec.get("h4_number", "")
                    meta["h4_title"] = sec.get("h4_title", "")
                if sec.get("code_language"):
                    meta["code_language"] = sec["code_language"]
                doc = Document(
                    page_content=prefix + sec["content"],
                    metadata=meta,
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
