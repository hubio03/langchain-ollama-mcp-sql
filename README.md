# LangChain + Ollama Text-to-SQL MCP Module

로컬 LLM(Ollama)과 LangChain을 활용하여 자연어를 SQL로 변환하고, 이를 MCP(Model Context Protocol) 도구로 제공하는 크로스플랫폼(Docker) 프로젝트입니다.

## 진행 상황 (Progress)
- [x] PoC 계획서 수립 및 프로젝트 초기 구조 세팅 ([docs/POC_PLAN.md](docs/POC_PLAN.md))
- [x] Phase 1: Docker 환경 및 샘플 DB 매니저 구축 (`src/db_manager.py`)
- [x] Phase 2: SQL 보안 가드레일 및 LangChain Text-to-SQL 체인 구현 (`src/sql_guard.py`, `src/text_to_sql_chain.py`)
- [x] Phase 3: 에러 자가 수정(Self-Correction) 및 테스트 러너 검증 ([docs/TEST_REPORT.md](docs/TEST_REPORT.md))
- [ ] Phase 4: FastMCP 서버 래핑 및 외부 클라이언트 연동
