from fastapi import APIRouter

from ...models.rag import (
    IngestResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    StoreInfoResponse,
    StoreResetResponse,
)
from ...services.data_loader import DataLoader
from ...services.rag_chain import RAGChain

router = APIRouter(prefix="/rag", tags=["rag"])

_rag: RAGChain | None = None
_loader: DataLoader | None = None


def init_rag(rag: RAGChain, loader: DataLoader) -> None:
    global _rag, _loader
    _rag = rag
    _loader = loader


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    results = _rag.store.similarity_search_with_score(
        request.query, k=request.k,
    )
    return SearchResponse(
        query=request.query,
        results=[
            SearchResult(
                content=doc.page_content,
                metadata=doc.metadata,
                similarity=score,
            )
            for doc, score in results
        ],
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest():
    result = _loader.ingest_all(force=True)
    return IngestResponse(**result)


@router.get("/store", response_model=StoreInfoResponse)
async def store_info():
    count = _rag.store.get_collection_count()
    files = _loader.list_files()
    return StoreInfoResponse(
        document_count=count,
        files=[str(f) for f in files],
    )


@router.delete("/store", response_model=StoreResetResponse)
async def store_reset():
    success = _rag.store.reset_collection()
    return StoreResetResponse(
        success=success,
        message="벡터DB가 초기화되었습니다." if success else "초기화 실패.",
    )
