from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from config import settings
from embeddings import get_embeddings
from vectorstore import SupabaseStore
from utils import ChatLogger

PROMPT_TEMPLATE = """\
너는 제공된 문서의 정보만을 사용하여 질문에 답변하는 전문가야.
- 문서에 없는 내용은 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답해.
- 답변은 간결하고 정확하게 해.
- 가능하면 문서의 구체적인 내용을 인용해.

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
            max_output_tokens=settings.gemini_max_tokens,
        )
        self._prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        self._logger = ChatLogger(self._store.client)

    @property
    def store(self) -> SupabaseStore:
        return self._store

    def query(self, question: str) -> dict:
        docs_with_scores = self._store.similarity_search_with_score(
            question, k=settings.retriever_k
        )

        if not docs_with_scores:
            answer = "저장된 문서가 없습니다. /ingest 명령으로 문서를 먼저 로드해주세요."
            return {
                "question": question,
                "answer": answer,
                "retrieved_documents": [],
            }

        context = "\n\n".join(doc.page_content for doc, _ in docs_with_scores)
        chain = self._prompt | self._llm
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
