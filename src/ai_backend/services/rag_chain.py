from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import settings
from ..prompts.chat import CODE_KEYWORDS, PROMPT_TEMPLATE, THINKING_PROMPT_TEMPLATE
from .embeddings import get_embeddings
from .vectorstore import SupabaseStore
from .chat_logger import ChatLogger


class RAGChain:
    def __init__(self):
        self._embeddings = get_embeddings()
        self._store = SupabaseStore(self._embeddings)
        self._llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=settings.gemini_temperature,
            top_p=settings.gemini_top_p,
            max_output_tokens=settings.gemini_max_tokens,
        )
        self._prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        self._thinking_llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0.7,
            top_p=0.9,
            max_output_tokens=settings.gemini_max_tokens * 4,
            thinking_budget=8192,
        )
        self._thinking_prompt = ChatPromptTemplate.from_template(THINKING_PROMPT_TEMPLATE)
        self._logger = ChatLogger(self._store.client)

    @property
    def store(self) -> SupabaseStore:
        return self._store

    @staticmethod
    def _is_code_query(question: str) -> bool:
        q = question.lower()
        return any(kw in q for kw in CODE_KEYWORDS)

    def query(
        self,
        question: str,
        thinking: bool = False,
        user_id: str | None = None,
    ) -> dict:
        try:
            return self._query(question, thinking=thinking, user_id=user_id)
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                return {
                    "question": question,
                    "answer": (
                        "현재 API 호출 한도에 도달했습니다. "
                        "약 1분 후에 다시 질문해 주세요.\n\n"
                        "> Gemini 무료 플랜은 분당 요청 수가 제한되어 있습니다."
                    ),
                    "retrieved_documents": [],
                }
            raise

    def _query(
        self,
        question: str,
        thinking: bool = False,
        user_id: str | None = None,
    ) -> dict:
        search_filter = None if self._is_code_query(question) else {"content_type": "prose"}
        docs_with_scores = self._store.similarity_search_with_score(
            question, k=settings.retriever_k, filter=search_filter
        )

        if not docs_with_scores:
            answer = "저장된 문서가 없습니다. /ingest 명령으로 문서를 먼저 로드해주세요."
            return {
                "question": question,
                "answer": answer,
                "retrieved_documents": [],
            }

        seen = set()
        section_keys = []
        for doc, score in docs_with_scores:
            sn = doc.metadata.get("section_number", "")
            src = doc.metadata.get("source", "")
            if sn and (sn, src) not in seen:
                seen.add((sn, src))
                section_keys.append((sn, src))

        if section_keys:
            context_parts = []
            for sn, src in section_keys:
                section_docs = self._store.fetch_by_section_number(sn, source=src)
                section_content = "\n\n".join(d.page_content for d in section_docs)
                if section_content:
                    context_parts.append(section_content)
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = "\n\n".join(doc.page_content for doc, _ in docs_with_scores)

        llm = self._thinking_llm if thinking else self._llm
        prompt = self._thinking_prompt if thinking else self._prompt
        chain = prompt | llm
        response = chain.invoke({"context": context, "question": question})
        answer = response.content

        retrieved = []
        for i, (doc, score) in enumerate(docs_with_scores):
            retrieved.append(
                {
                    "rank": i + 1,
                    "score": float(score),
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                }
            )

        result = {
            "question": question,
            "answer": answer,
            "retrieved_documents": retrieved,
        }

        try:
            self._logger.log(
                question, answer, retrieved,
                thinking_mode=thinking, user_id=user_id,
            )
        except Exception as e:
            result["log_error"] = str(e)

        return result
