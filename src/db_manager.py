import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()

# ==========================================
# [설정 영역] 수정 가능한 변수 및 매개변수
# ==========================================
DEFAULT_DB_PATH = os.getenv("DB_PATH", "data/ecommerce.db")
SAMPLE_ROWS_COUNT = 2  # LLM에게 스키마와 함께 보여줄 테이블당 샘플 행 개수


class DatabaseManager:
    """
    미니 커머스 SQLite 데이터베이스를 초기화하고,
    LangChain을 위한 스키마 추출 및 읽기 전용(Read-Only) 쿼리 실행을 담당하는 클래스입니다.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        # data/ 폴더가 없으면 자동 생성
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def init_sample_db(self) -> None:
        """
        고객(customers), 상품(products), 주문(orders) 3개 테이블을 생성하고
        데이터가 비어 있을 경우 미니 커머스 샘플 데이터를 삽입합니다.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 외래키 제약조건 활성화
        cursor.execute("PRAGMA foreign_keys = ON;")

        # 1. 고객(customers) 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                membership_tier TEXT NOT NULL, -- 'VIP', 'Gold', 'Silver'
                city TEXT NOT NULL,
                join_date TEXT NOT NULL        -- 'YYYY-MM-DD'
            );
        """)

        # 2. 상품(products) 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,        -- '전자기기', '주방용품', '도서' 등
                price INTEGER NOT NULL,
                stock_quantity INTEGER NOT NULL
            );
        """)

        # 3. 주문(orders) 테이블 생성 (customers, products와 외래키 연결)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                total_amount INTEGER NOT NULL,
                order_date TEXT NOT NULL,      -- 'YYYY-MM-DD'
                status TEXT NOT NULL,          -- '배송완료', '배송중', '주문취소'
                FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            );
        """)

        # 기존 데이터 존재 여부 확인 후 비어있을 때만 샘플 데이터 입력
        cursor.execute("SELECT COUNT(*) FROM customers;")
        if cursor.fetchone()[0] == 0:
            self._insert_seed_data(cursor)
            conn.commit()
            print(f"[INFO] 미니 커머스 샘플 데이터베이스가 생성되었습니다: {self.db_path}")
        else:
            print(f"[INFO] 기존 데이터베이스를 사용합니다: {self.db_path}")

        conn.close()

    def _insert_seed_data(self, cursor: sqlite3.Cursor) -> None:
        """실습용 미니 커머스 초기 데이터를 삽입합니다."""
        customers_data = [
            ("김민수", "minsu@example.com", "VIP", "서울", "2026-01-15"),
            ("이서연", "seoyeon@example.com", "Gold", "부산", "2026-03-22"),
            ("박지훈", "jihoon@example.com", "Silver", "서울", "2026-05-10"),
            ("최유진", "yujin@example.com", "VIP", "성남", "2026-06-01"),
        ]
        cursor.executemany(
            "INSERT INTO customers (name, email, membership_tier, city, join_date) VALUES (?, ?, ?, ?, ?);",
            customers_data,
        )

        products_data = [
            ("기계식 키보드 프로", "전자기기", 145000, 30),
            ("무선 노이즈캔슬링 헤드폰", "전자기기", 280000, 15),
            ("스테인리스 프라이팬 28cm", "주방용품", 42000, 50),
            ("핸드드립 커피 그라인더", "주방용품", 68000, 25),
            ("실전 파이썬 아키텍처 가이드", "도서", 32000, 100),
        ]
        cursor.executemany(
            "INSERT INTO products (product_name, category, price, stock_quantity) VALUES (?, ?, ?, ?);",
            products_data,
        )

        orders_data = [
            (1, 1, 1, 145000, "2026-10-05", "배송완료"),
            (1, 2, 1, 280000, "2026-10-12", "배송완료"),
            (2, 3, 2, 84000, "2026-10-18", "배송완료"),
            (3, 5, 1, 32000, "2026-11-01", "배송중"),
            (4, 2, 1, 280000, "2026-11-03", "배송완료"),
            (4, 4, 1, 68000, "2026-11-07", "주문취소"),
            (2, 5, 2, 64000, "2026-11-10", "배송완료"),
        ]
        cursor.executemany(
            "INSERT INTO orders (customer_id, product_id, quantity, total_amount, order_date, status) VALUES (?, ?, ?, ?, ?, ?);",
            orders_data,
        )

    def get_schema_context(self, sample_rows: int = SAMPLE_ROWS_COUNT) -> str:
        """
        LLM이 정확한 SQL을 생성할 수 있도록 테이블 생성문(DDL)과
        각 테이블의 샘플 데이터를 텍스트 형태로 조합하여 반환합니다.
        """
        if not self.db_path.exists():
            self.init_sample_db()

        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = cursor.fetchall()

        schema_parts = []
        for table_name, create_sql in tables:
            part = f"### 테이블: {table_name}\n[스키마 정의]\n{create_sql}\n"

            # 샘플 행 추출
            cursor.execute(f"SELECT * FROM {table_name} LIMIT {sample_rows};")
            col_names = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            part += f"[샘플 데이터 ({sample_rows}개 행)]\n컬럼: {', '.join(col_names)}\n"
            for row in rows:
                part += f"데이터: {row}\n"

            schema_parts.append(part)

        conn.close()
        return "\n".join(schema_parts)

    def execute_readonly_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """
        URI 읽기 전용 모드(?mode=ro)로 DB에 연결하여 SELECT 쿼리를 안전하게 실행하고,
        컬럼명과 값이 매핑된 딕셔너리 리스트를 반환합니다.
        """
        if not self.db_path.exists():
            self.init_sample_db()

        # mode=ro 옵션을 통해 INSERT, UPDATE, DELETE, DROP 등을 엔진 레벨에서 차단
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


if __name__ == "__main__":
    # 단독 실행 테스트: DB 초기화 -> 스키마 출력 -> 샘플 JOIN 쿼리 실행 테스트
    db = DatabaseManager()
    db.init_sample_db()

    print("\n================ [추출된 DB 스키마 정보] ================")
    print(db.get_schema_context())

    print("================ [읽기 전용 JOIN 쿼리 테스트] ================")
    test_sql = """
        SELECT c.name AS 고객명, p.product_name AS 상품명, o.total_amount AS 결제금액, o.status AS 주문상태
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN products p ON o.product_id = p.product_id
        WHERE o.status = '배송완료';
    """
    results = db.execute_readonly_query(test_sql)
    for row in results:
        print(row)