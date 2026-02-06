from typing import Any

from pydantic import BaseModel


class LogEntry(BaseModel):
    id: str
    query: str
    response: str
    source_documents: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    thinking_mode: int = 0
    user_id: str | None = None
    created_at: str


class LogsResponse(BaseModel):
    logs: list[LogEntry]
    count: int


class LogsStatsResponse(BaseModel):
    total_logs: int
    thinking_mode_logs: int
    normal_mode_logs: int


class LogsDeleteResponse(BaseModel):
    deleted: int
    message: str
