from typing import Any

from supabase import create_client, Client

from config import settings


class ChatLogger:
    def __init__(self):
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = create_client(settings.supabase_url, settings.supabase_key)
        return self._client

    def log(
        self,
        query: str,
        response: str,
        source_documents: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.client.table("chat_logs").insert({
            "query": query,
            "response": response,
            "source_documents": source_documents or [],
            "metadata": metadata or {},
        }).execute()

    def get_recent(self, n: int = 10) -> list[dict[str, Any]]:
        response = (
            self.client.table("chat_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(n)
            .execute()
        )
        rows = response.data or []
        rows.reverse()
        return rows

    def clear(self) -> None:
        self.client.table("chat_logs").delete().neq(
            "id", "00000000-0000-0000-0000-000000000000"
        ).execute()
