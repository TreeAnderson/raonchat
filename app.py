import streamlit as st

from config import settings
from embeddings import get_embeddings
from vectorstore import ChromaStore
from data_loader import DataLoader
from rag import RAGChain


@st.cache_resource
def init_rag() -> RAGChain:
    return RAGChain()


@st.cache_resource
def init_loader(_rag: RAGChain) -> DataLoader:
    return DataLoader(_rag.store)


def main():
    st.set_page_config(page_title="raonChat", page_icon="🏗️", layout="wide")
    st.title("raonChat")
    st.caption("Gemini 전용 건설 프로젝트 관리 RAG 챗봇")

    rag = init_rag()
    loader = init_loader(rag)

    # --- 사이드바 ---
    with st.sidebar:
        st.header("설정")
        st.text(f"모델: {settings.gemini_model}")
        st.text(f"임베딩: {settings.embedding_model}")
        st.text(f"리랭킹: {'ON' if settings.reranker_enabled else 'OFF'}")

        st.divider()
        st.header("데이터 관리")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("문서 로드", use_container_width=True):
                with st.spinner("문서 인제스트 중..."):
                    result = loader.ingest_all()
                st.success(
                    f"완료: {result['ingested']}개 파일, {result['chunks']}개 청크"
                )
        with col2:
            if st.button("강제 재로드", use_container_width=True):
                with st.spinner("전체 재인제스트 중..."):
                    result = loader.ingest_all(force=True)
                st.success(
                    f"완료: {result['ingested']}개 파일, {result['chunks']}개 청크"
                )

        count = rag.store.get_collection_count()
        st.metric("저장된 문서(청크)", count)

        files = loader.list_files()
        if files:
            with st.expander(f"원본 파일 목록 ({len(files)}개)"):
                for f in files:
                    rel = f.relative_to(settings.raw_data_dir)
                    st.text(str(rel))

        st.divider()
        if st.button("벡터DB 초기화", type="secondary", use_container_width=True):
            rag.store.reset_collection()
            st.cache_resource.clear()
            st.rerun()

    # --- 채팅 영역 ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "documents" in msg:
                with st.expander("참고 문서"):
                    for doc in msg["documents"]:
                        score = doc.get("rerank_score", doc.get("score", 0))
                        source = doc["metadata"].get("filename", "unknown")
                        st.markdown(f"**[{doc['rank']}] {source}** (score: {score:.4f})")
                        st.text(doc["content"][:300])
                        st.divider()

    if question := st.chat_input("질문을 입력하세요"):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("답변 생성 중..."):
                result = rag.query(question)

            st.markdown(result["answer"])

            if result["retrieved_documents"]:
                with st.expander("참고 문서"):
                    for doc in result["retrieved_documents"]:
                        score = doc.get("rerank_score", doc.get("score", 0))
                        source = doc["metadata"].get("filename", "unknown")
                        st.markdown(f"**[{doc['rank']}] {source}** (score: {score:.4f})")
                        st.text(doc["content"][:300])
                        st.divider()

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": result["answer"],
                "documents": result["retrieved_documents"],
            }
        )


if __name__ == "__main__":
    main()
