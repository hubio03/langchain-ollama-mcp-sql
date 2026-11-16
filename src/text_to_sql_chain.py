import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.db_manager import DatabaseManager
from src.sql_guard import SQLGuard, SQLGuardError

load_dotenv()

# ==========================================
# [설정 영역] 수정 가능한 변수 및 매개변수
# ==========================================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
MAX_RETRIES = 2  # SQL 문법 오류 발생 시 자가 수정 최대 재시도 횟수


class TextToSQLService:
    """
    자연어 질문을 받아 Ollama(qwen2.5:3b)를 통해 SQL을 생성하고,
    SQLGuard 검증 및 자가 수정(Self-Correction)을 거쳐 결과를 반환하는 핵심 모듈입니다.
    """

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.sql_guard = SQLGuard()
        self.llm = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_MODEL,
            temperature=LLM_TEMPERATURE,
        )
        self._init_chains()

    def _init_chains(self) -> None:
        sql_prompt = ChatPromptTemplate.from_template("""
당신은 SQLite 데이터베이스 전문가입니다.
아래 제공된 [데이터베이스 스키마]만을 참고하여 사용자의 [질문]에 답하기 위한 SQLite SELECT 쿼리를 작성하세요.

[작성 규칙]
1. 설명, 인사말, 마크다운 기호 없이 오직 실행 가능한 SQL 쿼리문만 출력하세요.
2. [데이터베이스 스키마]에 정의된 모든 테이블(기본 테이블 및 사용자가 업로드한 신규 테이블)과 컬럼명만 정확히 사용하세요.
3. 데이터를 삭제하거나 변경하는 쿼리(DROP, DELETE, UPDATE, INSERT)는 절대 작성하지 마세요.

[데이터베이스 스키마]
{schema}

[질문]
{question}

SQL 쿼리:
""")
        self.sql_gen_chain = sql_prompt | self.llm | StrOutputParser()

        fix_prompt = ChatPromptTemplate.from_template("""
당신은 SQLite 쿼리 디버깅 전문가입니다.
이전에 작성한 SQL 쿼리를 실행하던 중 [오류 메시지]가 발생했습니다.
[데이터베이스 스키마]를 다시 확인하여 오류가 수정된 올바른 SQLite SELECT 쿼리문을 작성하세요.

[작성 규칙]
1. 설명, 인사말, 마크다운 기호 없이 오직 수정된 SQL SELECT 쿼리문만 출력하세요.
2. 스키마에 실제로 존재하는 테이블명과 컬럼명만 정확히 사용하세요.

[데이터베이스 스키마]
{schema}

[사용자 질문]
{question}

[이전에 실패한 SQL]
{failed_sql}

[오류 메시지]
{error_msg}

수정된 SQL 쿼리:
""")
        self.sql_fix_chain = fix_prompt | self.llm | StrOutputParser()

        answer_prompt = ChatPromptTemplate.from_template("""
사용자의 [질문]에 대해 데이터베이스를 조회한 결과입니다.
아래 정보를 바탕으로 사용자에게 친절하고 명확한 한국어로 답변을 작성하세요.

[질문]: {question}
[실행된 SQL]: {sql}
[조회된 데이터]: {db_result}

답변:
""")
        self.answer_chain = answer_prompt | self.llm | StrOutputParser()

    def ask(self, question: str, include_summary: bool = True) -> Dict[str, Any]:
        schema_context = self.db_manager.get_schema_context()

        raw_sql = self.sql_gen_chain.invoke({
            "schema": schema_context,
            "question": question
        })

        attempt = 0
        last_error = ""
        current_raw_sql = raw_sql

        while attempt <= MAX_RETRIES:
            try:
                secured_sql = self.sql_guard.validate_and_secure(current_raw_sql)
                rows = self.db_manager.execute_readonly_query(secured_sql)

                summary = ""
                if include_summary:
                    summary = self.answer_chain.invoke({
                        "question": question,
                        "sql": secured_sql,
                        "db_result": str(rows)
                    }).strip()

                return {
                    "success": True,
                    "question": question,
                    "executed_sql": secured_sql,
                    "row_count": len(rows),
                    "data": rows,
                    "answer": summary,
                    "attempts": attempt + 1
                }

            except SQLGuardError as guard_err:
                return {
                    "success": False,
                    "question": question,
                    "executed_sql": current_raw_sql.strip(),
                    "error": str(guard_err),
                    "answer": f"보안 가드레일에 의해 요청이 차단되었습니다: {guard_err}",
                    "attempts": attempt + 1
                }

            except Exception as db_err:
                last_error = str(db_err)
                attempt += 1
                if attempt <= MAX_RETRIES:
                    print(f"[WARN] SQL 실행 오류 발생 (재시도 {attempt}/{MAX_RETRIES}): {last_error}")
                    current_raw_sql = self.sql_fix_chain.invoke({
                        "schema": schema_context,
                        "question": question,
                        "failed_sql": current_raw_sql,
                        "error_msg": last_error
                    })

        return {
            "success": False,
            "question": question,
            "executed_sql": current_raw_sql.strip(),
            "error": last_error,
            "answer": f"SQL 쿼리 생성 및 수정에 실패했습니다. 마지막 오류: {last_error}",
            "attempts": attempt
        }
