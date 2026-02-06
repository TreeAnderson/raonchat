import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path 최상위에 추가 (패키지명 충돌 방지)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

# Streamlit Cloud: st.secrets → 환경변수 주입 (config import 전에 실행)
_SECRET_KEYS = [
    "GOOGLE_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "GEMINI_MODEL",
    "GEMINI_TEMPERATURE",
    "GEMINI_MAX_TOKENS",
    "EMBEDDING_MODEL",
    "RETRIEVER_K",
]
for key in _SECRET_KEYS:
    if key not in os.environ:
        try:
            os.environ[key] = st.secrets[key]
        except (KeyError, FileNotFoundError):
            pass

from config import settings
from data_loader import DataLoader
from rag import RAGChain


@st.cache_resource
def init_rag() -> RAGChain:
    return RAGChain()


@st.cache_resource
def init_loader(_rag: RAGChain) -> DataLoader:
    return DataLoader(_rag.store)


def main():
    st.set_page_config(page_title="laonChat", page_icon="🏗️", layout="wide")
    st.title("라온 챗봇 테스트")
    st.caption("ConTech-DX 플랫폼 도우미 - 테스트 버전")

    # 사용자 API 키 반영 (cache_resource 생성 전에 실행)
    if "default_api_key" not in st.session_state:
        st.session_state["default_api_key"] = settings.google_api_key

    custom_key = st.session_state.get("custom_api_key", "")
    settings.google_api_key = custom_key if custom_key else st.session_state["default_api_key"]

    rag = init_rag()
    loader = init_loader(rag)

    # 벡터DB가 비어있으면 자동으로 문서 로드
    if rag.store.get_collection_count() == 0:
        with st.spinner("기본 문서를 로드하고 있습니다..."):
            loader.ingest_all()
        st.rerun()

    # --- 사이드바 ---
    with st.sidebar:
        st.header("설정")
        st.text(f"모델: {settings.gemini_model}")
        st.text(f"임베딩: {settings.embedding_model}")

        def _on_api_key_change():
            new_key = st.session_state.get("api_key_input", "").strip()
            if new_key != st.session_state.get("custom_api_key", ""):
                st.session_state["custom_api_key"] = new_key
                st.cache_resource.clear()

        using_custom = bool(st.session_state.get("custom_api_key"))
        st.text_input(
            "Google API Key (선택)",
            type="password",
            key="api_key_input",
            placeholder="무료 한도 초과 시 본인 키 입력",
            on_change=_on_api_key_change,
            help="입력하면 기본 키 대신 사용됩니다. 비우면 기본 키로 복원됩니다.",
        )
        if using_custom:
            st.caption("✅ 사용자 API 키 사용 중")

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
                        score = doc.get("score", 0)
                        source = doc["metadata"].get("filename", "unknown")
                        st.markdown(f"**[{doc['rank']}] {source}** (score: {score:.4f})")
                        st.text(doc["content"][:300])
                        st.divider()

    # --- 빠른 질문 (입력창 바로 위 고정) ---
    QUICK_QUESTIONS = [
        ("🏢 플랫폼 소개", "ConTech-DX 플랫폼에 대해 소개해주세요"),
        ("⚙️ 주요 기능", "이 플랫폼의 주요 기능은 무엇인가요?"),
        ("🚀 시작 가이드", "플랫폼을 처음 사용하려면 어떻게 시작하면 되나요?"),
        ("📋 공정계획 소개", "공정계획 기능에 대해 설명해주세요"),
    ]

    cols = st.columns(len(QUICK_QUESTIONS))
    for i, (label, q) in enumerate(QUICK_QUESTIONS):
        if cols[i].button(label, use_container_width=True, key=f"quick_{i}"):
            st.session_state["pending_question"] = q
            st.rerun()

    question = st.chat_input("질문을 입력하세요")
    if "pending_question" in st.session_state:
        question = st.session_state.pop("pending_question")

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("답변 생성 중..."):
                try:
                    result = rag.query(question)
                except Exception as e:
                    if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                        result = {
                            "answer": (
                                "현재 API 호출 한도에 도달했습니다. "
                                "약 1분 후에 다시 질문해 주세요.\n\n"
                                "> Gemini 무료 플랜은 분당 요청 수가 제한되어 있습니다."
                            ),
                            "retrieved_documents": [],
                        }
                    else:
                        raise

            st.markdown(result["answer"])

            if "log_error" in result:
                st.error(f"로그 기록 실패: {result['log_error']}")

            if result["retrieved_documents"]:
                with st.expander("참고 문서"):
                    for doc in result["retrieved_documents"]:
                        score = doc.get("score", 0)
                        source = doc["metadata"].get("filename", "unknown")
                        st.markdown(f"**[{doc['rank']}] {source}** (score: {score:.4f})")
                        st.text(doc["content"][:300])
                        st.divider()

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": result["answer"],
                "documents": result.get("retrieved_documents", []),
            }
        )


if __name__ == "__main__":
    main()
