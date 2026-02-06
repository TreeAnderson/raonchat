from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="질문 텍스트")
    thinking: bool = Field(False, description="사고 모드 활성화 여부")


class RetrievedDocument(BaseModel):
    rank: int
    score: float
    content: str
    metadata: dict


class ChatResponse(BaseModel):
    question: str
    answer: str
    retrieved_documents: list[RetrievedDocument] = []
    log_error: str | None = None
