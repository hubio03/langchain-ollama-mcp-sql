# LangChain + Ollama Text-to-SQL MCP Module

[![CI](https://github.com/hubio03/langchain-ollama-mcp-sql/actions/workflows/ci.yml/badge.svg)](https://github.com/hubio03/langchain-ollama-mcp-sql/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-qwen2.5:3b-000000?logo=ollama&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-SDK_v2-4EAA25)

로컬 LLM(Ollama)과 LangChain을 활용하여 사용자의 자연어 질의를 안전한 SQLite 쿼리로 변환·실행하고, 이를 **MCP(Model Context Protocol)** 표준 도구 및 **Streamlit 웹 대시보드**로 제공하는 Docker 기반 크로스플랫폼 프로젝트입니다.

## 1. 주요 기능 및 아키텍처 특징
- **완전한 로컬 LLM 실행:** 외부 유료 API 없이 `qwen2.5:3b` (Ollama) 모델을 활용하여 비용 제로 및 데이터 프라이버시 보장
- **크로스플랫폼 Docker 환경:** Windows와 macOS 어디서든 동일한 컨테이너 환경에서 호스트 GPU 가속 연동 (`host.docker.internal`)
- **이중 SQL 보안 가드레일 (`SQLGuard`):** 정규식 기반 `SELECT` 전용 검증, 위험 키워드(`DELETE`, `DROP` 등) 원천 차단, 과부하 방지용 `LIMIT 100` 자동 부착 및 SQLite 읽기 전용 URI(`?mode=ro`) 적용
- **에러 자가 수정 (Self-Correction):** 잘못된 컬럼명이나 문법 오류 발생 시 SQLite 에러 메시지를 피드백하여 스스로 쿼리를 재작성하는 복구 루프 구현
- **표준 MCP 서버 래핑 (`MCPServer`):** 외부 AI 에이전트나 IDE에서 즉시 연결 가능한 2종의 MCP 도구(`get_ecommerce_schema`, `query_ecommerce_db`) 제공
- **구조화된 대화 메모리 에이전트 (`ConversationalSQLAgent`):** 직전 질의와 실행된 SQL 조건(`WHERE` 절)을 함께 기억하여 대명사(`그 중에`, `그 사람`) 후속 질문을 처리하는 멀티턴 라우팅 구현
- **대화형 웹 대시보드 및 동적 CSV 연동 (`Streamlit`):** 실시간 채팅 인터페이스와 데이터 표(`DataFrame`) 시각화는 물론, 사용자가 업로드한 CSV 파일을 즉시 SQLite 테이블로 변환하여 기존 테이블과 `JOIN` 분석하는 기능 제공
- **GitHub Actions CI 자동 검증:** 코드 푸시 시 DB 초기화, CSV 테이블 변환, `SQLGuard` 보안 차단 및 모듈 임포트를 자동 테스트하는 CI 파이프라인 구축

## 2. 디렉터리 구조
```text
langchain-ollama-mcp-sql/
├── .github/workflows/
│   └── ci.yml              # GitHub Actions CI 자동 테스트 워크플로우
├── .env.example            # 환경변수 템플릿
├── Dockerfile              # Python 3.11 컨테이너 이미지 정의
├── docker-compose.yml      # 컨테이너 볼륨, 포트(8501) 및 호스트 통신 설정
├── requirements.txt        # 파이썬 의존성 패키지 목록
├── data/
│   └── product_reviews.csv # 동적 테이블 업로드 테스트용 샘플 상품 리뷰 CSV
├── docs/
│   ├── POC_PLAN.md         # 프로젝트 PoC 계획서
│   └── TEST_REPORT.md      # 6대 시나리오 자동 검증 결과 리포트
├── src/
│   ├── db_manager.py       # DB 자동 초기화, CSV 동적 테이블 변환 및 읽기 전용 실행기
│   ├── sql_guard.py        # SELECT 전용 검증 및 LIMIT 자동 추가 보안 모듈
│   ├── text_to_sql_chain.py# LangChain + Ollama 핵심 파이프라인
│   └── chat_agent.py       # 멀티턴 SQL 메모리 및 의도 라우팅 에이전트 (확장 1단계)
├── tests/
│   ├── test_ci.py          # GitHub Actions CI 전용 고속 무결성 단위 테스트
│   └── test_runner.py      # LLM 연동 6대 시나리오 검증 및 리포트 생성 스크립트
├── mcp_server.py           # MCP SDK v2(MCPServer) 기반 도구 래핑 서버
└── app.py                  # Streamlit 웹 대시보드 및 CSV 업로더 UI (확장 2·3단계)
```

## 3. 진행 상황 (Progress)

### Part 1. 코어 엔진 PoC 검증 (`v0.1.0-poc`)
- [x] PoC 계획서 수립 및 프로젝트 초기 구조 세팅 ([docs/POC_PLAN.md](docs/POC_PLAN.md))
- [x] Phase 1: Docker 환경 및 샘플 DB 매니저 구축 (`src/db_manager.py`)
- [x] Phase 2: SQL 보안 가드레일 및 LangChain Text-to-SQL 체인 구현 (`src/sql_guard.py`, `src/text_to_sql_chain.py`)
- [x] Phase 3: 에러 자가 수정(Self-Correction) 및 테스트 러너 검증 ([docs/TEST_REPORT.md](docs/TEST_REPORT.md))
- [x] Phase 4: MCP 서버 래핑 및 외부 클라이언트 연동 (`mcp_server.py`)

### Part 2. 엔드투엔드 프로젝트 확장 (`v1.0.0` ~ `v1.0.1`)
- [x] 확장 1단계: 구조화된 SQL 메모리 및 의도 라우팅 기반 멀티턴 에이전트 구현 (`src/chat_agent.py`)
- [x] 확장 2단계: 실시간 채팅 및 데이터 표 시각화 Streamlit 웹 대시보드 구축 (`app.py`)
- [x] 확장 3단계: 사용자 CSV 파일 업로드 및 동적 SQLite 테이블 자동 변환·분석 구현 (`data/product_reviews.csv`)
- [x] CI/CD 구축: GitHub Actions 기반 코어 모듈 & 보안 가드레일 자동 테스트 파이프라인 구축 (`.github/workflows/ci.yml`)

## 4. 빠른 시작 (Quick Start)

### 1) 사전 준비 및 컨테이너 이미지 빌드
호스트 PC에 [Ollama](https://ollama.com/)와 [Docker Desktop](https://www.docker.com/)이 설치되어 있어야 합니다. (최초 실행 시 샘플 DB는 자동으로 생성 및 초기화됩니다.)
```bash
ollama pull qwen2.5:3b
cp .env.example .env
docker compose build
```

### 2) 코어 모듈 및 MCP 서버 검증 (PoC & CI)
```bash
# 코어 모듈 및 SQLGuard 보안 단위 테스트 (GitHub Actions CI 동일 테스트)
docker compose run --rm app python -m unittest tests/test_ci.py -v

# 6대 시나리오 LLM 자동 검증 및 리포트(docs/TEST_REPORT.md) 생성
docker compose run --rm app python -m tests.test_runner

# MCP 도구 단독 호출 테스트
docker compose run --rm app python -c "import mcp_server; print(mcp_server.query_ecommerce_db('가장 비싼 상품의 이름과 가격은?'))"

# MCP Inspector를 통한 대화형 웹 UI 테스트 (Node.js 필요)
npx @modelcontextprotocol/inspector docker compose run --rm -T app python mcp_server.py
```

### 3) 멀티턴 에이전트 및 웹 대시보드 실행 (확장 기능)
```bash
# 터미널 기반 멀티턴 에이전트 5턴 연속 질문 데모 실행
docker compose run --rm app python -m src.chat_agent

# 터미널 기반 멀티턴 에이전트 직접 대화 모드 실행 (종료: exit)
docker compose run --rm app python -m src.chat_agent --interactive

# Streamlit 웹 대시보드 및 CSV 업로더 실행 (브라우저에서 http://localhost:8501 접속)
docker compose run --rm --service-ports app streamlit run app.py --server.address=0.0.0.0
```
