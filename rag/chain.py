from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from config import settings
from embeddings import get_embeddings
from vectorstore import SupabaseStore
from utils import ChatLogger

CODE_KEYWORDS = (
    "코드", "구현", "인터페이스", "타입", "함수", "컴포넌트",
    "typescript", "mermaid", "소스", "다이어그램", "흐름도",
)

PROMPT_TEMPLATE = """\
너는 제공된 문서의 정보만을 사용하여 질문에 답변하는 전문가야.
- 문서에 없는 내용은 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답해.
- 가능하면 문서의 구체적인 내용을 인용해.
- 가능하면 전체적인 관점에서 내용을 조합해.
- 답변은 간결하게 해.
- 옆의 설명은 간결하게 해.

<context>
{context}
</context>

질문: {question}

답변:"""

THINKING_PROMPT_TEMPLATE = """\
너는 제공된 문서의 정보만을 사용하여 질문에 심도 있게 답변하는 전문가야.

## 기본 원칙
- 반드시 문서에 있는 내용만 사용해. 문서에 없는 내용은 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답해.
- 가능하면 문서의 구체적인 내용을 인용해.

## 심층 분석 지침
- 관련 용어나 개념이 있으면 먼저 간략히 설명해.
- 답변을 단계별로 구조화해서 작성해.
- 문서의 여러 섹션에 걸친 내용이면 관련 섹션들을 연결해서 종합적으로 분석해.
- 핵심 포인트를 정리해서 제공해.

<context>
{context}
</context>

질문: {question}

답변:"""


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

    def query(self, question: str, thinking: bool = False) -> dict:
        try:
            return self._query(question, thinking=thinking)
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

    def _query(self, question: str, thinking: bool = False) -> dict:
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

        # Extract unique (section_number, source) pairs from top-k results
        seen = set()
        section_keys = []
        for doc, score in docs_with_scores:
            sn = doc.metadata.get("section_number", "")
            src = doc.metadata.get("source", "")
            if sn and (sn, src) not in seen:
                seen.add((sn, src))
                section_keys.append((sn, src))

        # Fetch full sections and assemble context
        if section_keys:
            context_parts = []
            for sn, src in section_keys:
                section_docs = self._store.fetch_by_section_number(sn, source=src)
                section_content = "\n\n".join(d.page_content for d in section_docs)
                if section_content:
                    context_parts.append(section_content)
            context = "\n\n---\n\n".join(context_parts)
        else:
            # Fallback: no section_number available, use top-k as-is
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
            self._logger.log(question, answer, retrieved)
        except Exception as e:
            result["log_error"] = str(e)

        return result
