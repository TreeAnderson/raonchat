from fastapi import APIRouter

from . import chat, logs, rag

router = APIRouter(prefix="/api/v1")
router.include_router(chat.router)
router.include_router(rag.router)
router.include_router(logs.router)
