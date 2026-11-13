# [PoC 계획서] Docker 기반 크로스플랫폼 Text-to-SQL MCP 모듈 구축

## 1. 프로젝트 개요 (Overview)
* **프로젝트명:** Local LLM(Ollama) & LangChain 기반 Text-to-SQL MCP 서버 모듈
* **목적:** 사용자의 자연어 질의를 안전한 SQL 쿼리로 변환하여 실행하고, 이를 MCP(Model Context Protocol) 표준 도구로 노출하는 독립 모듈의 기술적 타당성(PoC)을 검증한다.
* **핵심 가치:**
  1. **완전한 로컬 실행:** 외부 유료 API 없이 Ollama를 활용하여 데이터 프라이버시 보장 및 비용 제로화
  2. **크로스플랫폼 호환성:** Docker를 활용해 macOS와 Windows 환경을 오가며 동일한 개발/실행 환경 유지
  3. **모듈화 및 확장성:** 핵심 LangChain 로직과 MCP 서버 계층을 분리하여 어디서든 재사용 가능한 구조 확보

## 2. 목표 및 성공 지표 (KPIs)
| 평가 항목 | 목표 기준 | 검증 방법 |
| :--- | :--- | :--- |
| **환경 일관성** | Mac 및 Windows에서 동일한 docker compose 명령으로 오류 없이 컨테이너 기동 | 두 OS 환경에서 빌드 및 호스트 Ollama 통신 테스트 |
| **SQL 생성 정확도** | 단순 조회, 집계(GROUP BY), 테이블 결합(JOIN) 질의에 대해 실행 가능한 SQL 생성 | 테스트 질문 10개 중 8개 이상 정상 실행 |
| **보안 가드레일** | 데이터 변경/삭제(DROP, DELETE, UPDATE, INSERT) 질의 100% 사전 차단 | 악의적 프롬프트 주입 시 차단 메시지 반환 확인 |
| **자가 수정(Self-Correction)** | 잘못된 컬럼명/문법 오류 발생 시 에러 로그를 바탕으로 최대 2회 자동 재시도 후 복구 | 의도적 스키마 오타 유도 후 자동 수정 여부 확인 |

## 3. 시스템 아키텍처 및 폴더 구조
### 3.1 크로스플랫폼 Docker 통신 구조
* **호스트 OS (Mac / Windows):** 각각의 하드웨어 가속을 살려 Ollama 서버를 네이티브로 구동 (localhost:11434)
* **Docker 컨테이너 (Linux 기반 Python 환경):** LangChain 모듈, SQLite DB, FastMCP 서버를 구동하며, host.docker.internal:11434 주소를 통해 호스트의 Ollama와 통신

### 3.2 디렉터리 구조
- docs/POC_PLAN.md : 프로젝트 PoC 계획서
- data/ : SQLite DB 파일 저장 경로
- src/db_manager.py : 샘플 DB 초기화 및 스키마 추출 모듈
- src/sql_guard.py : 읽기 전용(SELECT) 검증 보안 모듈
- src/text_to_sql_chain.py : LangChain + Ollama 핵심 파이프라인
- tests/test_runner.py : 시나리오별 자동 검증 스크립트
- mcp_server.py : FastMCP 기반 도구(Tool) 래핑 서버

## 4. 단계별 개발 일정 (Development Phases)
* **Phase 1 (기반 구축):** Docker 크로스플랫폼 환경 설정 및 SQLite 샘플 DB 생성/스키마 로드 모듈(db_manager.py) 구현
* **Phase 2 (코어 로직):** SQL 보안 검증기(sql_guard.py) 및 LangChain 구조화 출력 기반 Text-to-SQL 체인(text_to_sql_chain.py) 구현
* **Phase 3 (고도화 및 검증):** SQL 실행 오류 발생 시 에러 피드백 루프(자가 수정) 구현 및 테스트 시나리오 검증(test_runner.py)
* **Phase 4 (MCP 연동):** 완성된 모듈을 FastMCP 서버(mcp_server.py)에 등록하고 MCP Inspector로 최종 연동 테스트
