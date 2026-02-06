from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # Gemini API
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    gemini_temperature: float = field(default_factory=lambda: float(os.getenv("GEMINI_TEMPERATURE", "0.3")))
    gemini_max_tokens: int = field(default_factory=lambda: int(os.getenv("GEMINI_MAX_TOKENS", "1024")))

    # 임베딩
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001"))

    # ChromaDB
    chroma_collection_name: str = "raonchat_docs"

    # 청킹
    chunk_size: int = 500
    chunk_overlap: int = 100

    # 리랭킹
    reranker_enabled: bool = field(
        default_factory=lambda: os.getenv("RERANKER_ENABLED", "true").lower() == "true"
    )
    reranker_model_name: str = field(
        default_factory=lambda: os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    )
    retrieval_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_K", "20")))
    rerank_top_k: int = field(default_factory=lambda: int(os.getenv("RERANK_TOP_K", "3")))
    retriever_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVER_K", "3")))
    reranker_max_length: int = field(default_factory=lambda: int(os.getenv("RERANKER_MAX_LENGTH", "512")))
    reranker_device: str = field(default_factory=lambda: os.getenv("RERANKER_DEVICE", "cpu"))

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
    def chroma_db_path(self) -> Path:
        return self.data_dir / "chroma_db"

    @property
    def chat_log_file(self) -> Path:
        return self.logs_dir / "chat_logs.json"

    @property
    def raw_data_dir(self) -> Path:
        return self.base_dir / "raw_data"
