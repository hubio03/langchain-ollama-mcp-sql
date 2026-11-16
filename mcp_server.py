import sys
import json
import contextlib
from mcp.server.mcpserver import MCPServer

from src.text_to_sql_chain import TextToSQLService

# ==========================================
# [설정 영역] 수정 가능한 변수 및 매개변수
# ==========================================
MCP_SERVER_NAME = "Ecommerce-TextToSQL-MCP"  # 외부 클라이언트에 표시될 MCP 서버 이름
DEFAULT_INCLUDE_SUMMARY = True               # 도구 호출 시 AI 한국어 요약 기본 포함 여부

# 1. MCP 2.x 표준 MCPServer 인스턴스 초기화
mcp = MCPServer(MCP_SERVER_NAME)

# 2. 내부 출력이 MCP stdio 통신을 방해하지 않도록 stderr로 우회하여 서비스 초기화
with contextlib.redirect_stdout(sys.stderr):
    sql_service = TextToSQLService()
    sql_service.db_manager.init_sample_db()


@mcp.tool()
def get_ecommerce_schema() -> str:
    """
    미니 커머스 데이터베이스(customers, products, orders)의 테이블 스키마(DDL)와
    각 테이블의 샘플 데이터를 조회합니다.
    데이터베이스 구조를 먼저 파악해야 할 때 이 도구를 호출하세요.
    """
    with contextlib.redirect_stdout(sys.stderr):
        return sql_service.db_manager.get_schema_context()


@mcp.tool()
def query_ecommerce_db(question: str, include_summary: bool = DEFAULT_INCLUDE_SUMMARY) -> str:
    """
    미니 커머스 데이터베이스에 대해 한국어 자연어로 질문하면,
    안전한 SELECT SQL 쿼리로 자동 변환하여 실행한 뒤 결과 데이터와 요약 답변을 반환합니다.

    Args:
        question: 조회하고 싶은 자연어 질문 (예: 'VIP 고객의 이름과 도시를 알려줘', '배송완료 주문의 총 결제금액은?')
        include_summary: 조회 결과에 대한 한국어 자연어 요약 포함 여부 (기본값: True)
    """
    with contextlib.redirect_stdout(sys.stderr):
        result = sql_service.ask(question=question, include_summary=include_summary)

    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 표준 입출력(stdio) 모드로 MCP 서버 실행
    mcp.run()
