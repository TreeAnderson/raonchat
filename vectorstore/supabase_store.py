import time
import uuid

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from supabase import create_client, Client

from config import settings

EMBED_BATCH_SIZE = 20
EMBED_BATCH_DELAY = 15.0


class SupabaseStore:
    def __init__(self, embeddings: Embeddings):
        self._embeddings = embeddings
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = create_client(settings.supabase_url, settings.supabase_key)
        return self._client

    def similarity_search(
        self, query: str, k: int = 3, filter: dict | None = None
    ) -> list[Document]:
        results = self.similarity_search_with_score(query, k=k, filter=filter)
        return [doc for doc, _ in results]

    def similarity_search_with_score(
        self, query: str, k: int = 3, filter: dict | None = None
    ) -> list[tuple[Document, float]]:
        query_embedding = self._embeddings.embed_query(query)
        rpc_params = {"query_embedding": query_embedding, "match_count": k}
        if filter:
            rpc_params["filter"] = filter
        response = self.client.rpc(
            "match_documents",
            rpc_params,
        ).execute()

        results = []
        for row in response.data:
            doc = Document(
                page_content=row["content"],
                metadata=row.get("metadata", {}),
            )
            similarity = float(row.get("similarity", 0))
            results.append((doc, similarity))

        return results

    def add_documents(self, documents: list[Document]) -> list[str]:
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        return self.add_texts(texts, metadatas=metadatas)

    def add_texts(
        self, texts: list[str], metadatas: list[dict] | None = None
    ) -> list[str]:
        if not texts:
            return []

        ids = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            if start > 0:
                time.sleep(EMBED_BATCH_DELAY)

            end = min(start + EMBED_BATCH_SIZE, len(texts))
            batch_texts = texts[start:end]
            batch_embeddings = self._embeddings.embed_documents(batch_texts)

            rows = []
            for i, text in enumerate(batch_texts):
                doc_id = str(uuid.uuid4())
                ids.append(doc_id)
                rows.append({
                    "id": doc_id,
                    "content": text,
                    "embedding": batch_embeddings[i],
                    "metadata": metadatas[start + i] if metadatas else {},
                })

            self.client.table("documents").insert(rows).execute()

        return ids

    def get_collection_count(self) -> int:
        response = (
            self.client.table("documents")
            .select("id", count="exact")
            .execute()
        )
        return response.count or 0

    def reset_collection(self) -> bool:
        try:
            self.client.table("documents").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            return True
        except Exception:
            return False

    def delete_by_source(self, source: str) -> int:
        response = (
            self.client.table("documents")
            .delete()
            .eq("metadata->>source", source)
            .execute()
        )
        return len(response.data) if response.data else 0
