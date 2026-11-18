import unittest
import tempfile
from pathlib import Path
import pandas as pd

from src.db_manager import DatabaseManager
from src.sql_guard import SQLGuard, SQLGuardError


class TestCoreEngineCI(unittest.TestCase):
    """GitHub Actions CI 환경에서 코어 모듈과 보안 가드레일을 빠르게 검증하는 단위 테스트입니다."""

    def setUp(self):
        # 매 테스트마다 독립된 임시 DB 경로 생성
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = str(Path(self.temp_dir.name) / "test_ecommerce.db")
        self.db_manager = DatabaseManager(db_path=self.test_db_path)
        self.db_manager.init_sample_db()
        self.sql_guard = SQLGuard(default_limit=100)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_sample_db_initialization_and_readonly_query(self):
        """샘플 DB 초기화 및 읽기 전용 SELECT 쿼리가 정상 동작하는지 검증합니다."""
        rows = self.db_manager.execute_readonly_query(
            "SELECT name, city FROM customers WHERE membership_tier = 'VIP';"
        )
        self.assertEqual(len(rows), 2)
        schema_text = self.db_manager.get_schema_context()
        self.assertIn("customers", schema_text)
        self.assertIn("products", schema_text)
        self.assertIn("orders", schema_text)

    def test_02_sql_guard_clean_and_auto_limit(self):
        """마크다운 코드 블록 제거 및 LIMIT 100 자동 부착 기능을 검증합니다."""
        raw_sql = "```sql\nSELECT * FROM products WHERE price > 50000\n```"
        secured = self.sql_guard.validate_and_secure(raw_sql)
        self.assertEqual(secured, "SELECT * FROM products WHERE price > 50000 LIMIT 100;")

    def test_03_sql_guard_block_forbidden_keywords(self):
        """DELETE, DROP 등 위험한 데이터 조작 쿼리가 100% 차단되는지 검증합니다."""
        dangerous_queries = [
            "DELETE FROM orders WHERE status = '주문취소';",
            "DROP TABLE customers;",
            "SELECT * FROM customers; DROP TABLE orders;"
        ]
        for query in dangerous_queries:
            with self.assertRaises(SQLGuardError):
                self.sql_guard.validate_and_secure(query)

    def test_04_csv_dynamic_table_import(self):
        """CSV 데이터프레임이 SQLite 신규 테이블로 정상 변환 및 조회되는지 검증합니다."""
        df = pd.DataFrame({
            "review id": [1, 2],
            "rating": [5, 4],
            "review text": ["좋아요", "만족합니다"]
        })
        info = self.db_manager.import_csv_to_table(df, "product reviews")
        self.assertEqual(info["table_name"], "product_reviews")
        self.assertEqual(info["row_count"], 2)

        rows = self.db_manager.execute_readonly_query("SELECT * FROM product_reviews WHERE rating = 5;")
        self.assertEqual(len(rows), 1)

    def test_05_module_imports(self):
        """전체 파이썬 모듈(체인, 에이전트, MCP 서버)이 문법 오류 없이 임포트되는지 검증합니다."""
        import src.text_to_sql_chain
        import src.chat_agent
        import mcp_server
        self.assertIsNotNone(src.text_to_sql_chain.TextToSQLService)
        self.assertIsNotNone(src.chat_agent.ConversationalSQLAgent)
        self.assertIsNotNone(mcp_server.mcp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
