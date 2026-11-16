import os
import sys
import json
import logging
import readline
from typing import List, Dict
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import mcp_server

load_dotenv()

# 터미널 대화창을 어지럽히는 HTTP 통신 로그(httpx) 숨김 처리
logging.getLogger("httpx").setLevel(logging.WARNING)

# 컨테이너 표준 입출력을 UTF-8 및 에러 무시(replace) 모드로 재설정
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ==========================================
# [설정 영역] 수정 가능한 변수 및 매개변수
# ==========================================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
MAX_HISTORY_TURNS = 3  # 기억할 최근 대화 턴 수

# 이전 대화 문맥 결합이 필요한 지시어 및 생략형 키워드 목록
FOLLOWUP_TRIGGERS = [
    "그중", "그 중", "그사람", "그 사람", "그 고객", "그 상품", "거기", "해당",
    "중에서", "중에", "그러면", "그럼", "반대로", "제외", "말고", "아닌", "외에"
]


def clean_user_input(raw_text: str) -> str:
    """터미널 한글 입력 과정에서 발생할 수 있는 깨진 서로게이트 바이트를 제거합니다."""
    if not raw_text:
        return ""
    return raw_text.encode("utf-8", errors="ignore").decode("utf-8").strip()


class ConversationalSQLAgent:
    """
    직전 질문과 실행된 SQL 조건을 함께 기억(Structured Memory)하여,
    '그 중에', '그 사람' 같은 대명사 후속 질문을 완벽한 조건문으로 변환하는 에이전트입니다.
    """

    def __init__(self):
        self.llm = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_MODEL,
            temperature=0.0
        )
        # 각 턴의 {'question': 변환된 질문, 'sql': 실행된 SQL, 'answer': 답변} 저장
        self.history_records: List[Dict[str, str]] = []
        self._init_agent_chains()

    def _init_agent_chains(self) -> None:
        """
        1) 의도 분류 체인 (Router)
        2) SQL 문맥 기반 대명사 치환 체인 (Contextualizer)
        3) 일상 대화 응답 체인 (General Chat)
        """
        router_prompt = ChatPromptTemplate.from_template("""
사용자의 [질문]을 분석하여 DB_QUERY, SCHEMA, CHAT 중 알맞은 단어 하나만 출력하세요.

[분류 기준]
- DB_QUERY : 고객, 상품, 주문, 인원수, 이름, 이메일, 가격 등 데이터를 조회하거나 계산하는 모든 질문
- SCHEMA : 데이터베이스의 테이블 목록이나 컬럼 구조 자체를 물어보는 질문
- CHAT : 인사말, 자기소개 등 데이터와 무관한 일상 대화

[질문]: {question}
결과:
""")
        self.router_chain = router_prompt | self.llm | StrOutputParser()

        # MessagesPlaceholder 대신 직전 질문과 직전 SQL을 명시적으로 주입하는 Few-Shot 프롬프트
        contextualize_prompt = ChatPromptTemplate.from_template("""
당신은 사용자의 [현재 질문]에 있는 대명사('그중에', '그 사람', '그 고객' 등)나 생략된 표현을 [직전 질문]의 조건으로 치환하는 전문가입니다.

[작성 규칙]
1. 출력 문장에는 '그중에', '그 중에서', '그 사람', '그사람' 같은 대명사가 절대 남아있으면 안 됩니다.
2. [직전 질문]과 [직전 SQL]의 조건(WHERE 절)을 확인하여 대명사를 구체적인 한국어 조건으로 풀어서 한 문장으로 작성하세요.
3. 부연 설명 없이 오직 치환된 질문 한 문장만 출력하세요.

[예시 1]
- 직전 질문: VIP 고객은 몇명이야?
- 직전 SQL: SELECT COUNT(*) FROM customers WHERE membership_tier = 'VIP'
- 현재 질문: VIP 가 아닌 고객은?
- 치환된 질문: VIP 등급이 아닌 고객은 몇 명이야?

[예시 2]
- 직전 질문: VIP 등급이 아닌 고객은 몇 명이야?
- 직전 SQL: SELECT COUNT(*) FROM customers WHERE membership_tier != 'VIP'
- 현재 질문: 그 중에 서울에 사는 사람은?
- 치환된 질문: VIP 등급이 아닌 고객 중에서 서울에 사는 사람은 몇 명이야?

[예시 3]
- 직전 질문: VIP가 아니면서 서울에 사는 사람은 몇 명이야?
- 직전 SQL: SELECT COUNT(*) FROM customers WHERE membership_tier != 'VIP' AND city = '서울'
- 현재 질문: 그사람의 이름과 메일을 알려줘.
- 치환된 질문: VIP가 아니면서 서울에 사는 고객의 이름과 이메일을 알려줘.

[실제 입력]
- 직전 질문: {last_question}
- 직전 SQL: {last_sql}
- 현재 질문: {question}
- 치환된 질문:
""")
        self.contextualize_chain = contextualize_prompt | self.llm | StrOutputParser()

        chat_prompt = ChatPromptTemplate.from_template("""
당신은 미니 커머스 데이터 분석을 돕는 친절한 AI 코딩 파트너입니다.
사용자의 말에 간결하고 친절하게 한국어로 답변하세요.

[사용자 입력]: {question}
답변:
""")
        self.chat_chain = chat_prompt | self.llm | StrOutputParser()

    def _needs_contextualization(self, user_input: str) -> bool:
        """현재 질문이 이전 대화의 문맥(대명사 치환 또는 생략 복원)을 필요로 하는지 판별합니다."""
        if not self.history_records:
            return False

        # 1. 대명사나 연결어가 포함된 경우
        if any(trigger in user_input for trigger in FOLLOWUP_TRIGGERS):
            return True

        # 2. 서술어가 생략된 짧은 질문인 경우 (예: '서울에 사는 사람은?', '골드 등급은?')
        short_endings = ("고객은?", "사람은?", "상품은?", "주문은?", "고객은", "사람은")
        if len(user_input) <= 18 and user_input.endswith(short_endings):
            return True

        return False

    def _ensure_pronoun_resolved(self, user_input: str, rewritten: str, last_q: str, last_sql: str) -> str:
        """
        만일 소형 LLM이 대명사('그중', '그사람' 등)를 치환하지 못하고 그대로 남겼을 경우,
        직전 질문의 맥락을 명시적으로 결합하여 SQL 생성기가 조건을 놓치지 않게 보장합니다.
        """
        unresolved_pronouns = ["그중", "그 중", "그사람", "그 사람", "그 고객", "거기"]
        has_unresolved = any(p in rewritten for p in unresolved_pronouns)

        if has_unresolved or rewritten == user_input:
            return f"직전 질문('{last_q}', 조건 SQL: {last_sql})의 대상 중에서, {user_input}"
        return rewritten

    def _parse_intent(self, raw_intent: str, question: str) -> str:
        """LLM의 라우팅 응답과 질문 키워드를 결합하여 오분류를 방지합니다."""
        cleaned = raw_intent.strip().upper()
        first_token = cleaned.split()[0] if cleaned else ""

        schema_keywords = ["스키마", "테이블", "컬럼", "구조", "schema", "table"]
        has_schema_keyword = any(k in question.lower() for k in schema_keywords)

        if first_token == "DB_QUERY" or "DB_QUERY" in cleaned:
            return "DB_QUERY"
        if (first_token == "SCHEMA" or "SCHEMA" in cleaned) and has_schema_keyword:
            return "SCHEMA"
        if first_token == "CHAT" or "CHAT" in cleaned:
            return "CHAT"
        return "DB_QUERY"

    def chat(self, user_input: str) -> dict:
        """
        사용자 입력 정제 -> 문맥 기반 질문 재구성 -> 의도 분류 -> MCP 도구 실행 -> 구조화 메모리 저장을 수행합니다.
        """
        user_input = clean_user_input(user_input)
        standalone_question = user_input
        query_for_mcp = user_input

        # 1단계: 후속 질문이거나 대명사가 포함된 경우 직전 질문 & SQL 조건을 바탕으로 치환
        if self._needs_contextualization(user_input):
            last_turn = self.history_records[-1]
            last_q = last_turn["question"]
            last_sql = last_turn["sql"]

            rewritten = self.contextualize_chain.invoke({
                "last_question": last_q,
                "last_sql": last_sql,
                "question": user_input
            }).strip()
            rewritten = clean_user_input(rewritten)

            standalone_question = self._ensure_pronoun_resolved(user_input, rewritten, last_q, last_sql)
            # SQL 생성기가 이전 WHERE 절을 100% 참고할 수 있도록 참고용 직전 SQL 힌트 부착
            query_for_mcp = f"{standalone_question} (참고할 직전 조건 SQL: {last_sql})"

        # 2단계: 질문 의도 분류 (DB_QUERY / SCHEMA / CHAT)
        raw_intent = self.router_chain.invoke({"question": standalone_question})
        intent = self._parse_intent(raw_intent, standalone_question)

        # 3단계: 의도에 따른 도구 호출 및 응답 생성
        executed_sql = None
        if intent == "SCHEMA":
            schema_text = mcp_server.get_ecommerce_schema()
            answer = f"현재 미니 커머스 데이터베이스의 스키마 정보입니다:\n\n{schema_text}"
        elif intent == "CHAT":
            answer = self.chat_chain.invoke({"question": user_input}).strip()
        else:
            mcp_json_str = mcp_server.query_ecommerce_db(question=query_for_mcp, include_summary=True)
            mcp_result = json.loads(mcp_json_str)
            executed_sql = mcp_result.get("executed_sql")
            answer = mcp_result.get("answer", "")

            # 4단계: 성공한 DB 질의의 '변환된 질문'과 '실행된 SQL'을 메모리에 저장
            if mcp_result.get("success") and executed_sql:
                self.history_records.append({
                    "question": standalone_question,
                    "sql": executed_sql,
                    "answer": answer
                })
                if len(self.history_records) > MAX_HISTORY_TURNS:
                    self.history_records = self.history_records[-MAX_HISTORY_TURNS:]

        return {
            "user_input": user_input,
            "standalone_question": standalone_question,
            "intent": intent,
            "executed_sql": executed_sql,
            "answer": answer
        }


def run_demo():
    """방금 테스트하셨던 5턴 연속 대화를 자동으로 검증하는 데모입니다."""
    print("=================================================================")
    print(" 5턴 연속 대명사 문맥 기억 에이전트 검증 데모 시작")
    print("=================================================================")
    agent = ConversationalSQLAgent()

    demo_turns = [
        "VIP 고객은 몇명이야?",
        "VIP 가 아닌 고객은?",
        "그 중에 서울에 사는 사람은?",
        "VIP가 아니면서 서울에 사는 사람은?",
        "그사람의 이름과 메일을 알려줘."
    ]

    for idx, msg in enumerate(demo_turns, start=1):
        print(f"\n[Turn {idx}] 질문 입력 >> {msg}")
        res = agent.chat(msg)
        if res["user_input"] != res["standalone_question"]:
            print(f"[문맥 반영 질문]: {res['standalone_question']}")
        if res["executed_sql"]:
            print(f"[실행된 SQL]: {res['executed_sql']}")
        print(f"[AI 답변]: {res['answer']}")


def run_interactive():
    """사용자가 직접 터미널에서 연속으로 질문할 수 있는 대화형 모드입니다."""
    print("=================================================================")
    print(" 미니 커머스 AI 에이전트 대화 시작 (종료하려면 'exit' 입력)")
    print("=================================================================")
    agent = ConversationalSQLAgent()

    while True:
        try:
            raw_input = input("\n질문 입력 >> ")
            user_input = clean_user_input(raw_input)
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "종료"):
                print("대화를 종료합니다.")
                break

            res = agent.chat(user_input)
            if res["user_input"] != res["standalone_question"]:
                print(f"[문맥 반영 질문]: {res['standalone_question']}")
            if res["executed_sql"]:
                print(f"[실행된 SQL]: {res['executed_sql']}")
            print(f"[AI 답변]: {res['answer']}")
        except (KeyboardInterrupt, EOFError):
            print("\n대화를 종료합니다.")
            break


if __name__ == "__main__":
    if "--interactive" in sys.argv:
        run_interactive()
    else:
        run_demo()
