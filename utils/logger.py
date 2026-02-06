from typing import Any

from supabase import Client


class ChatLogger:
    def __init__(self, client: Client):
        self._client = client

    def log(
        self,
        query: str,
        response: str,
        source_documents: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._client.table("chat_logs").insert({
            "query": query,
            "response": response,
            "source_documents": source_documents or [],
            "metadata": metadata or {},
        }).execute()

    def get_recent(self, n: int = 10) -> list[dict[str, Any]]:
        response = (
            self._client.table("chat_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(n)
            .execute()
        )
        rows = response.data or []
        rows.reverse()
        return rows

    def clear(self) -> None:
        self._client.table("chat_logs").delete().neq(
            "id", "00000000-0000-0000-0000-000000000000"
        ).execute()
