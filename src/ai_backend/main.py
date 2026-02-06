from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api.v1 import chat as chat_route
from .api.v1 import logs as logs_route
from .api.v1 import rag as rag_route
from .api.v1.router import router as v1_router
from .services.rag_chain import RAGChain
from .services.data_loader import DataLoader
from .services.chat_logger import ChatLogger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    rag = RAGChain()
    loader = DataLoader(rag.store)
    logger = ChatLogger(rag.store.client)

    chat_route.init_rag(rag)
    rag_route.init_rag(rag, loader)
    logs_route.init_logger(logger)

    app.state.rag = rag
    app.state.loader = loader
    app.state.logger = logger

    yield

    # Shutdown (nothing to clean up)


app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/")
async def root():
    return {
        "service": settings.app_title,
        "version": settings.app_version,
        "model": settings.gemini_model,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
