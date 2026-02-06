from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # Gemini API
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    gemini_temperature: float = field(default_factory=lambda: float(os.getenv("GEMINI_TEMPERATURE", "0")))
    gemini_top_p: float = field(default_factory=lambda: float(os.getenv("GEMINI_TOP_P", "0.95")))
    gemini_max_tokens: int = field(default_factory=lambda: int(os.getenv("GEMINI_MAX_TOKENS", "1024")))

    # 임베딩
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001"))

    # Supabase
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_key: str = field(default_factory=lambda: os.getenv("SUPABASE_KEY", ""))

    # 청킹
    chunk_size: int = 1500
    chunk_overlap: int = 100

    # 검색
    retriever_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVER_K", "3")))

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / "logs"

    @property
    def chat_log_file(self) -> Path:
        return self.logs_dir / "chat_logs.json"

    @property
    def raw_data_dir(self) -> Path:
        return self.base_dir / "raw_data"
