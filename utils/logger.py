import json
from datetime import datetime
from pathlib import Path
from typing import Any

from config import settings


class ChatLogger:
    def __init__(self, log_file: Path | None = None):
        self.log_file = log_file or settings.chat_log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_logs(self) -> list[dict[str, Any]]:
        if not self.log_file.exists():
            return []
        text = self.log_file.read_text(encoding="utf-8").strip()
        if not text:
            return []
        return json.loads(text)

    def _save_logs(self, logs: list[dict[str, Any]]) -> None:
        self.log_file.write_text(
            json.dumps(logs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def log(
        self,
        query: str,
        response: str,
        source_documents: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        logs = self._load_logs()
        logs.append(
            {
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "response": response,
                "source_documents": source_documents or [],
                "metadata": metadata or {},
            }
        )
        self._save_logs(logs)

    def get_recent(self, n: int = 10) -> list[dict[str, Any]]:
        logs = self._load_logs()
        return logs[-n:]

    def clear(self) -> None:
        self._save_logs([])
