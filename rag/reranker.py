from langchain_core.documents import Document

from config import settings


class Reranker:
    def __init__(self):
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                settings.reranker_model_name,
                max_length=settings.reranker_max_length,
                device=settings.reranker_device,
            )
        return self._model

    def rerank(
        self,
        query: str,
        documents: list[tuple[Document, float]],
        top_k: int | None = None,
    ) -> list[dict]:
        top_k = top_k or settings.rerank_top_k

        pairs = [(query, doc.page_content) for doc, _ in documents]
        scores = self.model.predict(pairs)

        ranked = []
        for i, score in enumerate(scores):
            doc, vector_score = documents[i]
            ranked.append(
                {
                    "document": doc,
                    "rerank_score": float(score),
                    "vector_score": float(vector_score),
                }
            )

        ranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:top_k]
