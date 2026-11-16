# LangChain + Ollama Text-to-SQL MCP Module

로컬 LLM(Ollama)과 LangChain을 활용하여 사용자의 자연어 질의를 안전한 SQLite 쿼리로 변환·실행하고, 이를 **MCP(Model Context Protocol)** 표준 도구로 노출하는 Docker 기반 크로스플랫폼 프로젝트입니다.

## 1. 주요 기능 및 아키텍처 특징
- **완전한 로컬 LLM 실행:** 외부 유료 API 없이 `qwen2.5:3b` (Ollama) 모델을 활용하여 비용 제로 및 데이터 프라이버시 보장
- **크로스플랫폼 Docker 환경:** Windows와 macOS 어디서든 동일한 컨테이너 환경에서 호스트 GPU 가속 연동 (`host.docker.internal`)
- **이중 SQL 보안 가드레일 (`SQLGuard`):** 정규식 기반 `SELECT` 전용 검증, 위험 키워드(`DELETE`, `DROP` 등) 원천 차단, 과부하 방지용 `LIMIT 100` 자동 부착 및 SQLite 읽기 전용 URI(`?mode=ro`) 적용
- **에러 자가 수정 (Self-Correction):** 잘못된 컬럼명이나 문법 오류 발생 시 SQLite 에러 메시지를 피드백하여 스스로 쿼리를 재작성하는 복구 루프 구현
- **표준 MCP 서버 래핑 (`MCPServer`):** 외부 AI 에이전트나 IDE에서 즉시 연결 가능한 2종의 MCP 도구(`get_ecommerce_schema`, `query_ecommerce_db`) 제공

## 2. 디렉터리 구조
```text
langchain-ollama-mcp-sql/
├── .env.example            # 환경변수 템플릿
├── Dockerfile              # Python 3.11 컨테이너 이미지 정의
├── docker-compose.yml      # 컨테이너 볼륨 및 호스트 통신 설정
├── requirements.txt        # 파이썬 의존성 패키지 목록
├── docs/
│   ├── POC_PLAN.md         # 프로젝트 PoC 계획서
│   └── TEST_REPORT.md      # 6대 시나리오 자동 검증 결과 리포트
├── src/
│   ├── db_manager.py       # 미니 커머스 DB 초기화 및 읽기 전용 실행기
│   ├── sql_guard.py        # SELECT 전용 검증 및 LIMIT 자동 추가 보안 모듈
│   └── text_to_sql_chain.py# LangChain + Ollama 핵심 파이프라인
├── tests/
│   └── test_runner.py      # 시나리오별 자동 검증 및 리포트 생성 스크립트
└── mcp_server.py           # MCP SDK v2(MCPServer) 기반 도구 래핑 서버
```

## 3. 진행 상황 (Progress)
- [x] PoC 계획서 수립 및 프로젝트 초기 구조 세팅 ([docs/POC_PLAN.md](docs/POC_PLAN.md))
- [x] Phase 1: Docker 환경 및 샘플 DB 매니저 구축 (`src/db_manager.py`)
- [x] Phase 2: SQL 보안 가드레일 및 LangChain Text-to-SQL 체인 구현 (`src/sql_guard.py`, `src/text_to_sql_chain.py`)
- [x] Phase 3: 에러 자가 수정(Self-Correction) 및 테스트 러너 검증 ([docs/TEST_REPORT.md](docs/TEST_REPORT.md))
- [x] Phase 4: MCP 서버 래핑 및 외부 클라이언트 연동 (`mcp_server.py`)

## 4. 빠른 시작 (Quick Start)

### 1) 사전 준비
호스트 PC에 [Ollama](https://ollama.com/)와 [Docker Desktop](https://www.docker.com/)이 설치되어 있어야 합니다.
```bash
ollama pull qwen2.5:3b
cp .env.example .env
```

### 2) 모듈별 실행 및 자동 검증 테스트
```bash
# 샘플 미니 커머스 DB 초기화 및 스키마 확인
docker compose run --rm app python -m src.db_manager

# 6대 시나리오 자동 검증 및 리포트(docs/TEST_REPORT.md) 생성
docker compose run --rm app python -m tests.test_runner

# MCP 도구 단독 호출 테스트
docker compose run --rm app python -c "import mcp_server; print(mcp_server.query_ecommerce_db('가장 비싼 상품의 이름과 가격은?'))"

# MCP Inspector를 통한 대화형 웹 UI 테스트 (Node.js 필요)
npx @modelcontextprotocol/inspector docker compose run --rm -T app python mcp_server.py
```
