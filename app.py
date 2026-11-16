import os
from pathlib import Path
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import mcp_server
from src.chat_agent import ConversationalSQLAgent

load_dotenv()

# ==========================================
# [설정 영역] 수정 가능한 변수 및 매개변수
# ==========================================
PAGE_TITLE = "미니 커머스 Text-to-SQL AI 에이전트"
PAGE_ICON = "🛒"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
EXPAND_DETAILS_DEFAULT = True
SUPPORTED_CSV_ENCODINGS = ["utf-8-sig", "utf-8", "cp949"]  # 한글 CSV 자동 인식 인코딩 순서

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")


def load_csv_with_fallback(uploaded_file) -> pd.DataFrame:
    """업로드된 CSV 파일의 인코딩(UTF-8, CP949 등)을 자동으로 감지하여 DataFrame으로 변환합니다."""
    for enc in SUPPORTED_CSV_ENCODINGS:
        try:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("지원되지 않는 파일 인코딩입니다. UTF-8 또는 CP949 형식의 CSV를 업로드해 주세요.")


def init_session_state() -> None:
    """Streamlit 세션에 에이전트 인스턴스와 화면 표시용 메시지 목록을 초기화합니다."""
    if "agent" not in st.session_state:
        st.session_state.agent = ConversationalSQLAgent()
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "안녕하세요! 미니 커머스 데이터 분석 에이전트입니다. 왼쪽 사이드바에서 새로운 CSV 파일을 업로드하여 테이블을 추가할 수도 있습니다.",
                "meta": None
            }
        ]


def render_sidebar() -> None:
    """왼쪽 사이드바에 모델 상태, CSV 업로더, 대화 초기화 버튼, DB 스키마 열람기를 표시합니다."""
    with st.sidebar:
        st.header("⚙️ 에이전트 설정 및 정보")
        st.info(f"**사용 중인 로컬 LLM:** `{OLLAMA_MODEL}`\n\n**보안 모드:** `Read-Only (SELECT 전용)`")

        if st.button("🔄 대화 메모리 초기화", use_container_width=True):
            st.session_state.agent = ConversationalSQLAgent()
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": "대화 메모리가 초기화되었습니다. 새로운 질문을 입력해 주세요!",
                    "meta": None
                }
            ]
            st.rerun()

        st.divider()
        st.subheader("📂 나만의 CSV 테이블 추가")
        uploaded_file = st.file_uploader(
            "분석할 CSV 파일을 업로드하세요",
            type=["csv"],
            help="예: data/product_reviews.csv 파일을 선택해 보세요."
        )

        if uploaded_file is not None:
            default_name = Path(uploaded_file.name).stem
            target_table = st.text_input("생성할 SQLite 테이블 이름", value=default_name)

            if st.button("📥 DB 테이블로 등록하기", use_container_width=True, type="primary"):
                try:
                    df_csv = load_csv_with_fallback(uploaded_file)
                    info = mcp_server.sql_service.db_manager.import_csv_to_table(df_csv, target_table)
                    st.success(
                        f"`{info['table_name']}` 테이블 등록 완료! "
                        f"(총 {info['row_count']}행, 컬럼: {', '.join(info['columns'])})"
                    )
                except Exception as e:
                    st.error(f"CSV 등록 중 오류 발생: {e}")

        st.divider()
        st.subheader("💡 추천 질문 예시")
        st.markdown(
            "**[기본 테이블 질문]**\n"
            "- `VIP 고객은 몇명이야?`\n"
            "- `그 사람들의 이름과 도시를 알려줘.`\n\n"
            "**[CSV(product_reviews) 업로드 후 질문]**\n"
            "- `등록된 리뷰 중에서 평점이 5점인 리뷰는 총 몇 개야?`\n"
            "- `상품별 평균 리뷰 평점과 상품명을 같이 보여줘.`"
        )

        st.divider()
        with st.expander("📊 현재 데이터베이스 스키마 보기", expanded=False):
            schema_str = mcp_server.get_ecommerce_schema()
            st.code(schema_str, language="sql")


def render_meta_details(meta: dict) -> None:
    """응답 하단에 의도 분류, 변환된 질문, 실행된 SQL, 조회 결과 표를 렌더링합니다."""
    if not meta:
        return

    with st.expander("🔍 에이전트 추론 과정 및 조회 데이터 확인", expanded=EXPAND_DETAILS_DEFAULT):
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f"**판별된 의도:** `{meta.get('intent')}`")
        with col2:
            if meta.get("user_input") != meta.get("standalone_question"):
                st.markdown(f"**문맥 반영 질문:** `{meta.get('standalone_question')}`")

        executed_sql = meta.get("executed_sql")
        if executed_sql:
            st.markdown("**실행된 SQL 쿼리:**")
            st.code(executed_sql, language="sql")

            rows = meta.get("rows")
            if rows is not None:
                st.markdown(f"**조회된 원본 데이터 ({len(rows)}건):**")
                if len(rows) > 0:
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.caption("조건에 해당하는 데이터가 없습니다.")


def main() -> None:
    init_session_state()
    render_sidebar()

    st.title(f"{PAGE_ICON} {PAGE_TITLE}")
    st.caption("LangChain + Ollama + MCP 기반 멀티턴 Text-to-SQL & 동적 CSV 분석 대시보드")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("meta"):
                render_meta_details(msg["meta"])

    user_input = st.chat_input("질문을 입력하세요 (예: 평점이 5점인 상품 리뷰 내용과 상품명을 알려줘)")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input, "meta": None})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("문맥 분석 및 SQL 실행 중..."):
                res = st.session_state.agent.chat(user_input)

                rows = None
                if res.get("executed_sql"):
                    try:
                        rows = mcp_server.sql_service.db_manager.execute_readonly_query(res["executed_sql"])
                    except Exception:
                        rows = []

                meta_info = {
                    "user_input": res.get("user_input"),
                    "standalone_question": res.get("standalone_question"),
                    "intent": res.get("intent"),
                    "executed_sql": res.get("executed_sql"),
                    "rows": rows
                }

                st.markdown(res["answer"])
                render_meta_details(meta_info)

        st.session_state.messages.append({
            "role": "assistant",
            "content": res["answer"],
            "meta": meta_info
        })


if __name__ == "__main__":
    main()
