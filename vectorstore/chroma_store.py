from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from config import settings


class ChromaStore:
    def __init__(self, embeddings: Embeddings):
        self._embeddings = embeddings
        self._store: Chroma | None = None

    @property
    def store(self) -> Chroma:
        if self._store is None:
            settings.chroma_db_path.mkdir(parents=True, exist_ok=True)
            self._store = Chroma(
                collection_name=settings.chroma_collection_name,
                embedding_function=self._embeddings,
                persist_directory=str(settings.chroma_db_path),
            )
        return self._store

    def similarity_search(self, query: str, k: int = 3) -> list[Document]:
        return self.store.similarity_search(query, k=k)

    def similarity_search_with_score(
        self, query: str, k: int = 20
    ) -> list[tuple[Document, float]]:
        return self.store.similarity_search_with_score(query, k=k)

    def add_documents(self, documents: list[Document]) -> list[str]:
        return self.store.add_documents(documents)

    def add_texts(
        self, texts: list[str], metadatas: list[dict] | None = None
    ) -> list[str]:
        return self.store.add_texts(texts, metadatas=metadatas)

    def get_collection_count(self) -> int:
        return self.store._collection.count()

    def reset_collection(self) -> bool:
        try:
            self.store._client.delete_collection(settings.chroma_collection_name)
            self._store = None
            return True
        except Exception:
            return False

    def delete_by_source(self, source: str) -> int:
        collection = self.store._collection
        results = collection.get(where={"source": source})
        ids = results.get("ids", [])
        if ids:
            collection.delete(ids=ids)
        return len(ids)
