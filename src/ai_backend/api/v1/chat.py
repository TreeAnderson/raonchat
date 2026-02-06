from fastapi import APIRouter, Header

from ...models.chat import ChatRequest, ChatResponse
from ...services.rag_chain import RAGChain

router = APIRouter(tags=["chat"])

_rag: RAGChain | None = None


def init_rag(rag: RAGChain) -> None:
    global _rag
    _rag = rag


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_user_id: str | None = Header(None),
):
    result = _rag.query(
        request.question,
        thinking=request.thinking,
        user_id=x_user_id,
    )
    return ChatResponse(**result)
