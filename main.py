from pathlib import Path

from config import settings
from embeddings import get_embeddings
from vectorstore import ChromaStore
from data_loader import DataLoader
from rag import RAGChain
from utils import ChatLogger


def print_help():
    print(
        """
[raonChat 명령어]
  /ingest          raw_data 문서 로드
  /ingest --force  모든 파일 강제 재로드
  /reset           벡터DB 초기화
  /list            raw_data 파일 목록
  /count           저장된 문서 수 확인
  /add <텍스트>    텍스트 수동 추가
  /file <경로>     파일 수동 추가
  /logs            최근 대화 로그
  /clear           대화 로그 초기화
  /help            도움말
  /quit, /exit     종료
  일반 텍스트       RAG 질의
"""
    )


def main():
    print("raonChat - Gemini 전용 건설 프로젝트 관리 RAG 챗봇")
    print(f"모델: {settings.gemini_model} | 리랭킹: {'ON' if settings.reranker_enabled else 'OFF'}")
    print("'/help' 입력 시 명령어 목록을 확인할 수 있습니다.\n")

    rag = RAGChain()
    loader = DataLoader(rag.store)
    logger = ChatLogger()

    while True:
        try:
            user_input = input("질문> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if not user_input:
            continue

        if user_input in ("/quit", "/exit"):
            print("종료합니다.")
            break

        elif user_input == "/help":
            print_help()

        elif user_input.startswith("/ingest"):
            force = "--force" in user_input
            print("문서 로딩 중..." + (" (강제 재로드)" if force else ""))
            result = loader.ingest_all(force=force)
            print(
                f"완료: 전체 {result['total_files']}개 파일 중 "
                f"{result['ingested']}개 인제스트, "
                f"{result['skipped']}개 스킵, "
                f"총 {result['chunks']}개 청크 생성"
            )

        elif user_input == "/reset":
            confirm = input("벡터DB를 초기화하시겠습니까? (y/N): ").strip().lower()
            if confirm == "y":
                if rag.store.reset_collection():
                    print("벡터DB가 초기화되었습니다.")
                else:
                    print("초기화 실패.")
            else:
                print("취소되었습니다.")

        elif user_input == "/list":
            files = loader.list_files()
            if not files:
                print("raw_data/ 디렉토리에 파일이 없습니다.")
            else:
                print(f"총 {len(files)}개 파일:")
                for f in files:
                    rel = f.relative_to(settings.raw_data_dir)
                    print(f"  - {rel}")

        elif user_input == "/count":
            count = rag.store.get_collection_count()
            print(f"저장된 문서(청크) 수: {count}")

        elif user_input.startswith("/add "):
            text = user_input[5:].strip()
            if text:
                rag.store.add_texts([text])
                print("텍스트가 추가되었습니다.")
            else:
                print("추가할 텍스트를 입력해주세요.")

        elif user_input.startswith("/file "):
            path_str = user_input[6:].strip()
            file_path = Path(path_str)
            if not file_path.exists():
                print(f"파일을 찾을 수 없습니다: {path_str}")
            else:
                chunks = loader.ingest_file(file_path)
                print(f"파일 인제스트 완료: {chunks}개 청크 생성")

        elif user_input == "/logs":
            logs = logger.get_recent(10)
            if not logs:
                print("대화 로그가 없습니다.")
            else:
                for log in logs:
                    print(f"\n[{log['timestamp']}]")
                    print(f"  Q: {log['query']}")
                    answer_preview = log["response"][:100]
                    print(f"  A: {answer_preview}{'...' if len(log['response']) > 100 else ''}")

        elif user_input == "/clear":
            confirm = input("대화 로그를 초기화하시겠습니까? (y/N): ").strip().lower()
            if confirm == "y":
                logger.clear()
                print("대화 로그가 초기화되었습니다.")
            else:
                print("취소되었습니다.")

        elif user_input.startswith("/"):
            print(f"알 수 없는 명령어: {user_input}  ('/help'로 명령어 확인)")

        else:
            print("답변 생성 중...")
            result = rag.query(user_input)
            print(f"\n{result['answer']}\n")

            if result["retrieved_documents"]:
                print("--- 참고 문서 ---")
                for doc in result["retrieved_documents"]:
                    score = doc.get("rerank_score", doc.get("score", 0))
                    source = doc["metadata"].get("filename", "unknown")
                    print(f"  [{doc['rank']}] {source} (score: {score:.4f})")
                print()


if __name__ == "__main__":
    main()
