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
        thinking_mode: bool = False,
        user_id: str | None = None,
    ) -> None:
        row: dict[str, Any] = {
            "query": query,
            "response": response,
            "source_documents": source_documents or [],
            "metadata": metadata or {},
            "thinking_mode": 1 if thinking_mode else 0,
        }
        if user_id:
            row["user_id"] = user_id

        response_obj = self._client.table("chat_logs").insert(row).execute()
        if not response_obj.data:
            raise RuntimeError(
                "chat_logs INSERT가 차단되었습니다. "
                "Supabase SQL Editor에서 실행: "
                "ALTER TABLE chat_logs DISABLE ROW LEVEL SECURITY; "
                "GRANT ALL ON chat_logs TO anon;"
            )

    def get_recent(
        self, n: int = 10, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = self._client.table("chat_logs").select("*")
        if user_id:
            query = query.eq("user_id", user_id)
        response = query.order("created_at", desc=True).limit(n).execute()
        rows = response.data or []
        rows.reverse()
        return rows

    def get_stats(self, user_id: str | None = None) -> dict[str, Any]:
        query = self._client.table("chat_logs").select("id", count="exact")
        if user_id:
            query = query.eq("user_id", user_id)
        response = query.execute()
        total = response.count or 0

        thinking_query = (
            self._client.table("chat_logs")
            .select("id", count="exact")
            .eq("thinking_mode", 1)
        )
        if user_id:
            thinking_query = thinking_query.eq("user_id", user_id)
        thinking_response = thinking_query.execute()
        thinking_count = thinking_response.count or 0

        return {
            "total_logs": total,
            "thinking_mode_logs": thinking_count,
            "normal_mode_logs": total - thinking_count,
        }

    def clear(self, user_id: str | None = None) -> int:
        query = self._client.table("chat_logs").delete()
        if user_id:
            query = query.eq("user_id", user_id)
        else:
            query = query.neq("id", "00000000-0000-0000-0000-000000000000")
        response = query.execute()
        return len(response.data) if response.data else 0
