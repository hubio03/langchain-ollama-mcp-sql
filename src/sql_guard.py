import re

# ==========================================
# [설정 영역] 수정 가능한 변수 및 매개변수
# ==========================================
DEFAULT_ROW_LIMIT = 100  # LIMIT 절이 없을 때 자동으로 붙일 최대 조회 행 수

# 차단할 위험 SQL 키워드 목록 (데이터 변경, 스키마 조작, 시스템 명령)
FORBIDDEN_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
    "TRUNCATE", "REPLACE", "CREATE", "ATTACH", "DETACH", "PRAGMA"
]


class SQLGuardError(Exception):
    """보안 정책에 위배되는 SQL 쿼리가 감지되었을 때 발생하는 예외입니다."""
    pass


class SQLGuard:
    """
    LLM이 생성한 SQL 쿼리를 정제하고,
    읽기 전용(SELECT) 여부 검증 및 LIMIT 자동 추가를 수행하는 보안 모듈입니다.
    """

    def __init__(self, default_limit: int = DEFAULT_ROW_LIMIT):
        self.default_limit = default_limit

    def clean_sql(self, raw_text: str) -> str:
        """
        LLM 출력에 포함될 수 있는 마크다운 코드 블록(`sql ... `)이나
        불필요한 설명 텍스트를 제거하고 순수 SQL 문장만 추출합니다.
        """
        if not raw_text:
            return ""

        text = raw_text.strip()

        # 1. `sql ... ` 코드 블록이 있다면 내부 텍스트만 추출
        code_block_match = re.search(r"`(?:sql)?\s*(.*?)\s*`", text, re.DOTALL | re.IGNORECASE)
        if code_block_match:
            text = code_block_match.group(1).strip()

        # 2. 만약 LLM이 앞에 설명을 붙였다면 첫 번째 SELECT 또는 WITH부터 추출
        select_match = re.search(r"\b(SELECT|WITH)\b.*", text, re.DOTALL | re.IGNORECASE)
        if select_match:
            text = select_match.group(0).strip()

        # 3. 끝부분의 세미콜론(;) 및 공백 제거
        text = text.rstrip(";").strip()
        return text

    def validate_and_secure(self, raw_sql: str) -> str:
        """
        1) 마크다운 정제
        2) 다중 쿼리(SQL Injection) 차단
        3) SELECT/WITH 시작 여부 확인
        4) 금지 키워드 검사
        5) LIMIT 절 자동 추가
        과정을 거쳐 안전한 최종 SQL을 반환합니다.
        """
        sql = self.clean_sql(raw_sql)

        if not sql:
            raise SQLGuardError("생성된 SQL 쿼리가 비어 있습니다.")

        # 1. 다중 쿼리 실행 차단 (중간에 세미콜론이 있으면 차단)
        if ";" in sql:
            raise SQLGuardError("보안 정책 위반: 한 번에 여러 개의 SQL 문장을 실행할 수 없습니다.")

        # 2. SELECT 또는 WITH로 시작하는지 검증
        if not re.match(r"^(SELECT|WITH)\b", sql, re.IGNORECASE):
            raise SQLGuardError(f"보안 정책 위반: 오직 SELECT 조회 쿼리만 허용됩니다. (입력된 쿼리: {sql})")

        # 3. 금지된 데이터 조작/삭제 키워드 검사 (단어 경계 \b 기준)
        for keyword in FORBIDDEN_KEYWORDS:
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, sql, re.IGNORECASE):
                raise SQLGuardError(f"보안 정책 위반: 금지된 키워드('{keyword}')가 감지되었습니다.")

        # 4. 과부하 방지를 위한 LIMIT 자동 부착
        if not re.search(r"\bLIMIT\s+\d+", sql, re.IGNORECASE):
            sql = f"{sql} LIMIT {self.default_limit}"

        return f"{sql};"


if __name__ == "__main__":
    guard = SQLGuard(default_limit=100)

    print("================ [SQLGuard 동작 테스트] ================")
    # 테스트 1: 마크다운 제거 및 LIMIT 100 자동 부착 확인
    sample_1 = "`sql\nSELECT name, city FROM customers WHERE membership_tier = 'VIP'\n`"
    print("[테스트 1 - 정상 쿼리 정제 결과]")
    print(guard.validate_and_secure(sample_1))

    # 테스트 2: 이미 LIMIT이 있는 경우 유지 확인
    sample_2 = "SELECT * FROM products LIMIT 5;"
    print("\n[테스트 2 - 기존 LIMIT 유지 결과]")
    print(guard.validate_and_secure(sample_2))

    # 테스트 3: 위험한 DELETE 쿼리 차단 확인
    sample_3 = "DELETE FROM orders WHERE status = '주문취소';"
    print("\n[테스트 3 - 위험 쿼리 차단 결과]")
    try:
        guard.validate_and_secure(sample_3)
    except SQLGuardError as e:
        print(f"정상 차단 완료 -> {e}")
