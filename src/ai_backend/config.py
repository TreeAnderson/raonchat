from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini API
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0
    gemini_top_p: float = 0.95
    gemini_max_tokens: int = 1024

    # 임베딩
    embedding_model: str = "models/gemini-embedding-001"

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # 청킹
    chunk_size: int = 1500
    chunk_overlap: int = 100

    # 검색
    retriever_k: int = 3

    # FastAPI
    app_title: str = "raonChat API"
    app_version: str = "0.1.0"
    cors_origins: list[str] = ["*"]

    @property
    def base_dir(self) -> Path:
        # src/ai_backend/config.py → parent×3 = project root
        return Path(__file__).resolve().parent.parent.parent

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


settings = Settings()
