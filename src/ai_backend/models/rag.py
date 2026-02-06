from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="검색 쿼리")
    k: int = Field(3, ge=1, le=20, description="반환할 문서 수")


class SearchResult(BaseModel):
    content: str
    metadata: dict
    similarity: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class IngestResponse(BaseModel):
    total_files: int
    ingested: int
    skipped: int
    chunks: int


class StoreInfoResponse(BaseModel):
    document_count: int
    files: list[str]


class StoreResetResponse(BaseModel):
    success: bool
    message: str
