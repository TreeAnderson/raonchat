from fastapi import APIRouter, Header, Query

from ...models.logs import LogEntry, LogsDeleteResponse, LogsResponse, LogsStatsResponse
from ...services.chat_logger import ChatLogger

router = APIRouter(prefix="/logs", tags=["logs"])

_logger: ChatLogger | None = None


def init_logger(logger: ChatLogger) -> None:
    global _logger
    _logger = logger


@router.get("", response_model=LogsResponse)
async def get_logs(
    n: int = Query(10, ge=1, le=100, description="조회할 로그 수"),
    x_user_id: str | None = Header(None),
):
    rows = _logger.get_recent(n=n, user_id=x_user_id)
    logs = [LogEntry(**row) for row in rows]
    return LogsResponse(logs=logs, count=len(logs))


@router.get("/stats", response_model=LogsStatsResponse)
async def get_stats(
    x_user_id: str | None = Header(None),
):
    stats = _logger.get_stats(user_id=x_user_id)
    return LogsStatsResponse(**stats)


@router.delete("", response_model=LogsDeleteResponse)
async def delete_logs(
    x_user_id: str | None = Header(None),
):
    deleted = _logger.clear(user_id=x_user_id)
    return LogsDeleteResponse(
        deleted=deleted,
        message="로그가 삭제되었습니다.",
    )
