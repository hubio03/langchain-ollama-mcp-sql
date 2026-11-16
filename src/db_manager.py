import os
import re
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# [설정 영역] 수정 가능한 변수 및 매개변수
# ==========================================
DEFAULT_DB_PATH = os.getenv("DB_PATH", "data/ecommerce.db")
SAMPLE_ROWS_COUNT = 2   # LLM에게 스키마와 함께 보여줄 테이블당 샘플 행 개수
MAX_CSV_ROWS = 10000    # 업로드 허용할 CSV 최대 행 수 (과부하 방지)


class DatabaseManager:
    """
    미니 커머스 SQLite 데이터베이스를 초기화하고,
    CSV 동적 테이블 등록, 스키마 추출 및 읽기 전용(Read-Only) 쿼리 실행을 담당하는 클래스입니다.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def init_sample_db(self) -> None:
        """기본 3개 테이블(customers, products, orders)을 생성하고 초기 데이터를 삽입합니다."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                membership_tier TEXT NOT NULL,
                city TEXT NOT NULL,
                join_date TEXT NOT NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                price INTEGER NOT NULL,
                stock_quantity INTEGER NOT NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                total_amount INTEGER NOT NULL,
                order_date TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            );
        """)

        cursor.execute("SELECT COUNT(*) FROM customers;")
        if cursor.fetchone()[0] == 0:
            self._insert_seed_data(cursor)
            conn.commit()
        conn.close()

    def _insert_seed_data(self, cursor: sqlite3.Cursor) -> None:
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

    def import_csv_to_table(self, df: pd.DataFrame, raw_table_name: str) -> Dict[str, Any]:
        """
        업로드된 Pandas DataFrame을 SQLite의 새 테이블로 저장합니다.
        테이블명과 컬럼명의 공백/특수문자를 언더스코어(_)로 정제하여 SQL 호환성을 보장합니다.
        """
        if not self.db_path.exists():
            self.init_sample_db()

        if len(df) > MAX_CSV_ROWS:
            raise ValueError(f"CSV 행 수가 최대 허용치({MAX_CSV_ROWS}행)를 초과했습니다.")

        clean_table = re.sub(r"[^a-zA-Z0-9가-힣_]", "_", raw_table_name.strip()).strip("_").lower()
        if not clean_table or clean_table[0].isdigit():
            clean_table = f"custom_{clean_table}"

        df_clean = df.copy()
        df_clean.columns = [
            re.sub(r"[^a-zA-Z0-9가-힣_]", "_", str(col).strip()).strip("_")
            for col in df_clean.columns
        ]

        conn = sqlite3.connect(self.db_path)
        try:
            df_clean.to_sql(clean_table, conn, if_exists="replace", index=False)
            return {
                "table_name": clean_table,
                "row_count": len(df_clean),
                "columns": list(df_clean.columns)
            }
        finally:
            conn.close()

    def get_schema_context(self, sample_rows: int = SAMPLE_ROWS_COUNT) -> str:
        """모든 테이블(동적 추가된 CSV 테이블 포함)의 DDL과 샘플 행을 텍스트로 반환합니다."""
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
        """URI 읽기 전용 모드(?mode=ro)로 SELECT 쿼리를 실행합니다."""
        if not self.db_path.exists():
            self.init_sample_db()

        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
