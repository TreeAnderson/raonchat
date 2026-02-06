# raonChat 프로젝트 구조명세서

> Gemini 전용(LLM + 임베딩) 건설 프로젝트 관리 RAG 챗봇
> localAgent 프로젝트를 기반으로 Gemini 전용 구조로 재설계

---

## 1. 프로젝트 디렉토리 구조

```
raonChat/
├── config/
│   ├── __init__.py
│   └── settings.py             # @dataclass Settings (Gemini 전용 설정)
├── embeddings/
│   ├── __init__.py
│   └── gemini_embed.py         # GoogleGenerativeAIEmbeddings 래퍼
├── vectorstore/
│   ├── __init__.py
│   └── chroma_store.py         # ChromaDB 벡터스토어 래퍼
├── rag/
│   ├── __init__.py
│   ├── chain.py                # RAG 파이프라인 (Gemini 전용)
│   └── reranker.py             # CrossEncoder 리랭커
├── data_loader/
│   ├── __init__.py
│   └── loader.py               # 문서 인제스트 & 청킹
├── utils/
│   ├── __init__.py
│   └── logger.py               # JSON 기반 채팅 로거
├── raw_data/                   # 원본 문서 (md/txt)
│   └── 기획/                   # 카테고리별 하위 폴더
├── data/
│   └── chroma_db/              # ChromaDB 영구 저장소
├── logs/
│   └── chat_logs.json          # 대화 이력
├── main.py                     # CLI 진입점
├── app.py                      # Streamlit 웹 UI
├── pyproject.toml              # 의존성 정의 (uv)
├── .env.example                # 환경변수 템플릿
├── .env                        # 실제 환경변수 (gitignore)
├── .gitignore
├── .python-version             # 3.13
├── STRUCTURE.md                # 이 문서
└── README.md
```

---

## 2. 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                         사용자 질문                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  [1] 임베딩 (Gemini text-embedding-004)                         │
│      질문 → 벡터 변환 (API 호출)                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  [2] 벡터 검색 (ChromaDB)                                       │
│      상위 20개 문서 검색 (similarity_search_with_score)          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  [3] 리랭킹 (CrossEncoder - bge-reranker-v2-m3)                 │
│      query-doc 쌍 점수 계산 → 상위 3개 선별                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  [4] LLM 답변 생성 (Gemini)                                     │
│      선별된 문서를 컨텍스트로 답변 생성                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  [5] 로깅 (ChatLogger)                                          │
│      질문/답변/검색문서 → logs/chat_logs.json                    │
└─────────────────────────────────────────────────────────────────┘
```

### 데이터 인제스트 흐름

```
raw_data/ (md/txt 파일)
    │
    ▼
DataLoader.ingest_all()
    │
    ▼
RecursiveCharacterTextSplitter (500자 단위, 100자 오버랩)
    │
    ▼
ChromaStore.add_documents()
    │
    ▼
ChromaDB 벡터 저장 (Gemini text-embedding-004 임베딩)
```

---

## 3. 각 파일/폴더 역할

### 3.1 `config/settings.py` - 중앙 설정 관리

`@dataclass` 기반 설정 클래스. 모든 환경변수를 로드하고 경로를 관리한다.

**주요 필드:**

| 필드명 | 타입 | 기본값 | 설명 |
|--------|------|--------|------|
| `google_api_key` | `str` | env `GOOGLE_API_KEY` | Gemini API 키 |
| `gemini_model` | `str` | `"gemini-2.0-flash"` | Gemini LLM 모델명 |
| `gemini_temperature` | `float` | `0.3` | 생성 온도 |
| `gemini_max_tokens` | `int` | `1024` | 최대 토큰 수 |
| `embedding_model` | `str` | `"models/text-embedding-004"` | Gemini 임베딩 모델명 |
| `chroma_collection_name` | `str` | `"raonchat_docs"` | ChromaDB 컬렉션명 |
| `chunk_size` | `int` | `500` | 청크 크기 (문자) |
| `chunk_overlap` | `int` | `100` | 청크 오버랩 (문자) |
| `reranker_enabled` | `bool` | `true` | 리랭킹 활성화 여부 |
| `reranker_model_name` | `str` | `"BAAI/bge-reranker-v2-m3"` | 리랭커 모델명 |
| `retrieval_k` | `int` | `20` | 초기 벡터 검색 개수 |
| `rerank_top_k` | `int` | `3` | 리랭킹 후 선택 개수 |
| `retriever_k` | `int` | `3` | 리랭킹 미사용 시 검색 개수 |
| `reranker_max_length` | `int` | `512` | 리랭커 최대 시퀀스 길이 |
| `reranker_device` | `str` | `"cpu"` | 리랭커 실행 장치 |

**경로 프로퍼티:**

| 프로퍼티 | 경로 | 설명 |
|----------|------|------|
| `base_dir` | 프로젝트 루트 | 기준 디렉토리 |
| `data_dir` | `{base_dir}/data` | 데이터 디렉토리 |
| `logs_dir` | `{base_dir}/logs` | 로그 디렉토리 |
| `chroma_db_path` | `{data_dir}/chroma_db` | ChromaDB 저장 경로 |
| `chat_log_file` | `{logs_dir}/chat_logs.json` | 채팅 로그 파일 |

### 3.2 `embeddings/gemini_embed.py` - Gemini 임베딩

`langchain-google-genai`의 `GoogleGenerativeAIEmbeddings`를 사용한 임베딩 래퍼.

```python
from langchain_google_genai import GoogleGenerativeAIEmbeddings

def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=settings.google_api_key,
    )
```

**핵심:**
- API 기반이므로 로컬 모델 다운로드/캐시 불필요
- `text-embedding-004`: 768차원, 다국어 지원

### 3.3 `vectorstore/chroma_store.py` - ChromaDB 래퍼

localAgent와 동일한 인터페이스. Lazy initialization 패턴.

**주요 메서드:**

| 메서드 | 반환값 | 설명 |
|--------|--------|------|
| `similarity_search(query, k)` | `List[Document]` | 유사 문서 검색 |
| `similarity_search_with_score(query, k)` | `List[(Document, float)]` | 점수 포함 검색 |
| `add_documents(documents)` | `List[str]` | 문서 추가 |
| `add_texts(texts, metadatas)` | `List[str]` | 텍스트 추가 |
| `get_collection_count()` | `int` | 문서 수 조회 |
| `reset_collection()` | `bool` | 컬렉션 초기화 |
| `delete_by_source(source)` | `int` | 소스별 삭제 |

### 3.4 `rag/chain.py` - RAG 파이프라인

Gemini 전용 RAG 체인. 프롬프트 템플릿은 Gemini 형식만 사용.

**프롬프트 템플릿:**
```
너는 제공된 문서의 정보만을 사용하여 질문에 답변하는 전문가야.
- 문서에 없는 내용은 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답해.
- 답변은 간결하고 정확하게 해.
- 가능하면 문서의 구체적인 내용을 인용해.

<context>
{context}
</context>

질문: {question}

답변:
```

**실행 모드:**
1. **리랭킹 모드** (기본): 벡터 검색 20개 → CrossEncoder 리랭킹 → 상위 3개 → LLM
2. **단순 모드**: 벡터 검색 3개 → LLM

**반환 구조:**
```python
{
    "question": str,
    "answer": str,
    "reranking_enabled": bool,
    "retrieved_documents": [
        {
            "rank": int,
            "rerank_score": float,      # 리랭킹 모드
            "vector_score": float,       # 리랭킹 모드
            # 또는
            "score": float,             # 단순 모드
            "content": str,
            "metadata": dict,
        }
    ]
}
```

### 3.5 `rag/reranker.py` - CrossEncoder 리랭커

localAgent와 동일. `sentence-transformers`의 `CrossEncoder` 사용.

- 모델: `BAAI/bge-reranker-v2-m3` (다국어, 한국어 지원, ~568MB)
- Lazy loading으로 초기화 지연
- 점수: 높을수록 관련성 높음 (0~1)

### 3.6 `data_loader/loader.py` - 문서 로더

`raw_data/` 하위 md/txt 파일을 청킹하여 벡터스토어에 저장.

**청킹 설정:**

| 설정 | 값 | 이유 |
|------|-----|------|
| `chunk_size` | **500** | Gemini 대용량 컨텍스트 활용 |
| `chunk_overlap` | **100** | 넉넉한 오버랩으로 문맥 보존 |
| `separators` | `["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]` | 마크다운 헤더 우선 분리 |

**메타데이터 구조:**
```python
{
    "source": str,          # 파일 전체 경로
    "filename": str,        # 파일명
    "title": str,           # # 헤더에서 추출한 제목
    "category": str,        # 하위 폴더명 (예: "기획")
    "chunk_index": int,     # 현재 청크 인덱스
    "total_chunks": int,    # 전체 청크 수
    "ingested_at": str,     # ISO 포맷 타임스탬프
}
```

### 3.7 `utils/logger.py` - 채팅 로거

JSON 파일 기반 대화 이력 관리.

**저장 형식:**
```json
{
    "timestamp": "2025-01-01T12:00:00",
    "query": "질문 내용",
    "response": "답변 내용",
    "source_documents": [...],
    "metadata": {}
}
```

### 3.8 `main.py` - CLI 인터페이스

**지원 명령어:**

| 명령어 | 설명 |
|--------|------|
| `/ingest` | raw_data 문서 로드 |
| `/ingest --force` | 모든 파일 강제 재로드 |
| `/reset` | 벡터DB 초기화 |
| `/list` | raw_data 파일 목록 |
| `/count` | 저장된 문서 수 확인 |
| `/add <텍스트>` | 텍스트 수동 추가 |
| `/file <경로>` | 파일 수동 추가 |
| `/logs` | 최근 대화 로그 |
| `/clear` | 대화 로그 초기화 |
| `/help` | 도움말 |
| `/quit`, `/exit` | 종료 |
| 일반 텍스트 | RAG 질의 |

**실행:** `uv run python main.py`

### 3.9 `app.py` - Streamlit 웹 UI

사이드바(설정, 데이터 관리) + 메인 영역(채팅) 구조.

- `@st.cache_resource`로 임베딩/LLM/벡터스토어 캐싱
- 리랭킹 활성화 상태 표시
- 검색된 문서 및 점수 표시

**실행:** `uv run streamlit run app.py`

---

## 4. 의존성

```toml
[project]
name = "raonchat"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "langchain>=0.3.0",
    "langchain-community>=0.3.0",
    "langchain-google-genai>=2.0.0",       # Gemini LLM + Embedding
    "chromadb>=0.5.0",
    "sentence-transformers>=3.0.0",         # Reranker 전용 (CrossEncoder)
    "langchain-text-splitters>=0.3.0",
    "python-dotenv>=1.0.0",
    "streamlit>=1.40.0",
]
```

**제거된 의존성 (localAgent 대비):**
- ~~`langchain-huggingface`~~ → Gemini 임베딩 사용
- ~~`llama-cpp-python`~~ → 로컬 LLM 제거
- ~~`huggingface-hub`~~ → 로컬 모델 다운로드 불필요

---

## 5. 환경변수 (`.env`)

```bash
# Gemini API
GOOGLE_API_KEY=                     # 필수: Google AI Studio에서 발급
GEMINI_MODEL=gemini-2.0-flash       # LLM 모델
GEMINI_TEMPERATURE=0.3
GEMINI_MAX_TOKENS=1024

# 임베딩 (Gemini API)
EMBEDDING_MODEL=models/text-embedding-004

# RAG
RETRIEVER_K=3                       # 리랭킹 미사용 시 검색 개수

# 리랭킹
RERANKER_ENABLED=true
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RETRIEVAL_K=20                      # 초기 벡터 검색 개수
RERANK_TOP_K=3                      # 리랭킹 후 선택 개수
RERANKER_MAX_LENGTH=512
RERANKER_DEVICE=cpu
```

---

## 6. localAgent 대비 변경 비교표

| 항목 | localAgent | raonChat | 변경 이유 |
|------|-----------|----------|----------|
| **LLM** | EXAONE(로컬) + Gemini(API) 선택 | **Gemini만** | API 전용으로 단순화 |
| **LLM 모듈** | `models/` (factory 패턴, 3파일) | 제거 (`chain.py`에서 직접 생성) | 단일 LLM이므로 모듈 불필요 |
| **임베딩** | KURE-v1 (로컬 SentenceTransformer) | **Gemini text-embedding-004** (API) | API 전용으로 통일 |
| **임베딩 파일** | `embeddings/embedder.py` | `embeddings/gemini_embed.py` | Gemini 전용 |
| **chunk_size** | 300 | **500** | Gemini 대용량 컨텍스트 활용 |
| **chunk_overlap** | 50 | **100** | 더 넓은 문맥 보존 |
| **프롬프트** | EXAONE/Gemini 분기 | **Gemini 전용** | 단일 프롬프트 |
| **컬렉션명** | `localagent_docs` | `raonchat_docs` | 프로젝트 분리 |
| **Streamlit** | `streamlit_app.py` | `app.py` | 파일명 단순화 |
| **로컬 모델 디렉토리** | `huggingface_models/` | 제거 | 로컬 모델 불필요 |
| **설정 분기** | `llm_type` 분기 로직 | 제거 | Gemini 단일 |

### 제거된 요소

| 제거 항목 | 이유 |
|-----------|------|
| `models/` 디렉토리 | 로컬 LLM(EXAONE) 제거, Gemini 직접 호출 |
| `models/__init__.py` (get_llm factory) | 단일 LLM이므로 factory 불필요 |
| `models/local_llm.py` | EXAONE GGUF 제거 |
| `models/gemini_llm.py` | chain.py에서 직접 ChatGoogleGenerativeAI 생성 |
| `huggingface_models/` 디렉토리 | 로컬 모델 캐시 불필요 |
| `llama-cpp-python` 의존성 | 로컬 GGUF 추론 제거 |
| `langchain-huggingface` 의존성 | HuggingFace 임베딩 제거 |
| `huggingface-hub` 의존성 | 모델 다운로드 제거 |
| `HF_TOKEN` 환경변수 | HuggingFace 인증 불필요 |
| `LLM_TYPE` 환경변수 | Gemini 전용이므로 분기 불필요 |
| EXAONE 프롬프트 템플릿 | 로컬 LLM 제거 |
| `RAG_SPECIFICATION.md` | 이 STRUCTURE.md로 대체 |

---

## 7. 기술 스택 요약

| 구분 | 도구 | 모델/버전 |
|------|------|-----------|
| LLM | Google Gemini API | `gemini-2.0-flash` |
| 임베딩 | Google Gemini API | `text-embedding-004` (768차원) |
| 벡터DB | ChromaDB | `langchain-community` |
| 리랭커 | CrossEncoder | `BAAI/bge-reranker-v2-m3` |
| 텍스트 분할 | LangChain | `RecursiveCharacterTextSplitter` |
| 프레임워크 | LangChain | `>=0.3.0` |
| UI | Streamlit | `>=1.40.0` |
| 패키지 관리 | uv | - |
| Python | - | `>=3.13` |

---

## 8. 점수 해석

### ChromaDB 벡터 점수
- **낮을수록 유사** (L2 거리 기반)
- 동일 문서 = 0.0

### CrossEncoder 리랭크 점수
- **높을수록 관련성 높음** (0~1 스케일)
- query-document 쌍의 의미적 관련성 직접 평가

### 안전한 점수 접근 패턴
```python
# 리랭킹 ON/OFF 모두 대응
score = d.get("rerank_score", d.get("score", 0))
```
