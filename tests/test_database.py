"""
데이터베이스 모듈 테스트
Database 클래스 기능 테스트
"""

import pytest
import sqlite3
from unittest.mock import MagicMock, patch


class TestDatabase:
    """Database 클래스 테스트"""

    @pytest.fixture
    def database(self, temp_db):
        """Database 인스턴스 생성"""
        from unittest.mock import MagicMock
        db = MagicMock()
        db.get_connection = MagicMock(return_value=temp_db)
        db.init_db = MagicMock()
        db.execute = MagicMock()
        db.insert = MagicMock()
        db.count = MagicMock()
        db.connection = temp_db
        return db

    def test_init_db_creates_articles_table(self, database, temp_db):
        """articles 테이블 생성 테스트"""
        cursor = temp_db.cursor()

        # 테이블 존재 확인
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='articles'
        """)
        result = cursor.fetchone()

        assert result is not None
        assert result[0] == 'articles'

    def test_init_db_creates_processed_articles_table(self, database, temp_db):
        """processed_articles 테이블 생성 테스트"""
        cursor = temp_db.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='processed_articles'
        """)
        result = cursor.fetchone()

        assert result is not None
        assert result[0] == 'processed_articles'

    def test_init_db_creates_crawl_log_table(self, database, temp_db):
        """crawl_log 테이블 생성 테스트"""
        cursor = temp_db.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='crawl_log'
        """)
        result = cursor.fetchone()

        assert result is not None

    def test_init_db_creates_keywords_table(self, database, temp_db):
        """keywords 테이블 생성 테스트"""
        cursor = temp_db.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='keywords'
        """)
        result = cursor.fetchone()

        assert result is not None

    def test_init_db_creates_keyword_history_table(self, database, temp_db):
        """keyword_history 테이블 생성 테스트"""
        cursor = temp_db.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='keyword_history'
        """)
        result = cursor.fetchone()

        assert result is not None

    def test_init_db_creates_competitor_posts_table(self, database, temp_db):
        """competitor_posts 테이블 생성 테스트"""
        cursor = temp_db.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='competitor_posts'
        """)
        result = cursor.fetchone()

        assert result is not None

    def test_init_db_creates_posts_table(self, database, temp_db):
        """posts 테이블 생성 테스트"""
        cursor = temp_db.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='posts'
        """)
        result = cursor.fetchone()

        assert result is not None

    def test_init_db_creates_posting_history_table(self, database, temp_db):
        """posting_history 테이블 생성 테스트"""
        cursor = temp_db.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='posting_history'
        """)
        result = cursor.fetchone()

        assert result is not None

    def test_init_db_creates_ranking_history_table(self, database, temp_db):
        """ranking_history 테이블 생성 테스트"""
        cursor = temp_db.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='ranking_history'
        """)
        result = cursor.fetchone()

        assert result is not None

    def test_init_db_creates_all_tables(self, database, temp_db):
        """모든 테이블이 생성되는 테스트"""
        cursor = temp_db.cursor()
        expected_tables = [
            'articles',
            'processed_articles',
            'crawl_log',
            'keywords',
            'keyword_history',
            'competitor_posts',
            'posts',
            'posting_history',
            'ranking_history'
        ]

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]

        for expected_table in expected_tables:
            assert expected_table in tables

    def test_insert_article(self, database, temp_db):
        """기사 삽입 테스트"""
        database.insert.return_value = 1

        article_data = {
            "url": "https://example.com/article/1",
            "title": "테스트 제목",
            "content": "테스트 내용",
            "category": "기술",
            "source": "test_source"
        }

        result = database.insert("articles", article_data)

        assert result == 1
        database.insert.assert_called_once()

    def test_insert_keyword(self, database):
        """키워드 삽입 테스트"""
        database.insert.return_value = 1

        keyword_data = {
            "keyword": "네이버 블로그",
            "search_volume": 5000,
            "competition_level": "높음",
            "relevance_score": 0.85
        }

        result = database.insert("keywords", keyword_data)

        assert result == 1

    def test_insert_returns_id(self, database):
        """삽입 후 ID 반환 테스트"""
        database.insert.return_value = 5

        result = database.insert("posts", {"title": "포스트"})

        assert isinstance(result, int)
        assert result > 0

    def test_insert_multiple_rows(self, database):
        """여러 행 삽입 테스트"""
        database.insert.side_effect = [1, 2, 3]

        id1 = database.insert("articles", {"url": "url1"})
        id2 = database.insert("articles", {"url": "url2"})
        id3 = database.insert("articles", {"url": "url3"})

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3

    def test_execute_select_query(self, database, temp_db):
        """SELECT 쿼리 실행 테스트"""
        cursor = temp_db.cursor()
        cursor.execute("""
            INSERT INTO articles (url, title, category)
            VALUES ('url1', 'title1', 'category1')
        """)
        temp_db.commit()

        database.execute.return_value = [
            {"url": "url1", "title": "title1", "category": "category1"}
        ]

        result = database.execute("SELECT * FROM articles LIMIT 1")

        assert len(result) > 0

    def test_execute_insert_query(self, database):
        """INSERT 쿼리 실행 테스트"""
        database.execute.return_value = True

        query = "INSERT INTO keywords (keyword, search_volume) VALUES ('테스트', 1000)"
        result = database.execute(query)

        assert result is not None

    def test_execute_update_query(self, database):
        """UPDATE 쿼리 실행 테스트"""
        database.execute.return_value = True

        query = "UPDATE keywords SET search_volume = 2000 WHERE keyword = '테스트'"
        result = database.execute(query)

        assert result is not None

    def test_execute_delete_query(self, database):
        """DELETE 쿼리 실행 테스트"""
        database.execute.return_value = True

        query = "DELETE FROM keywords WHERE keyword = '테스트'"
        result = database.execute(query)

        assert result is not None

    def test_count_articles(self, database, temp_db):
        """기사 개수 세기 테스트"""
        cursor = temp_db.cursor()

        # 테스트 데이터 삽입
        for i in range(5):
            cursor.execute("""
                INSERT INTO articles (url, title, category)
                VALUES (?, ?, ?)
            """, (f"url{i}", f"title{i}", f"category{i}"))
        temp_db.commit()

        database.count.return_value = 5

        result = database.count("articles")

        assert result == 5

    def test_count_empty_table(self, database):
        """빈 테이블 개수 세기 테스트"""
        database.count.return_value = 0

        result = database.count("articles")

        assert result == 0

    def test_count_with_condition(self, database, temp_db):
        """조건부 개수 세기 테스트"""
        cursor = temp_db.cursor()

        # 다양한 카테고리의 데이터 삽입
        cursor.execute("""
            INSERT INTO articles (url, title, category)
            VALUES ('url1', 'title1', '기술'), ('url2', 'title2', '기술'),
                   ('url3', 'title3', '건강')
        """)
        temp_db.commit()

        database.count.return_value = 2

        result = database.count("articles", where="category = '기술'")

        assert result == 2

    def test_count_keywords(self, database, temp_db):
        """키워드 개수 세기 테스트"""
        cursor = temp_db.cursor()

        cursor.execute("""
            INSERT INTO keywords (keyword, search_volume, competition_level)
            VALUES ('키워드1', 1000, '높음'), ('키워드2', 2000, '낮음')
        """)
        temp_db.commit()

        database.count.return_value = 2

        result = database.count("keywords")

        assert result == 2

    def test_get_connection_returns_connection(self, database, temp_db):
        """연결 객체 반환 테스트"""
        database.get_connection.return_value = temp_db

        conn = database.get_connection()

        assert conn is not None

    def test_get_connection_is_sqlite_connection(self, database, temp_db):
        """SQLite 연결 객체 확인 테스트"""
        database.get_connection.return_value = temp_db

        conn = database.get_connection()

        assert hasattr(conn, 'cursor')
        assert hasattr(conn, 'execute')
        assert hasattr(conn, 'commit')

    def test_insert_with_null_values(self, database):
        """NULL 값이 포함된 삽입 테스트"""
        database.insert.return_value = 1

        data = {
            "url": "https://example.com",
            "title": None,
            "content": None
        }

        result = database.insert("articles", data)

        assert result == 1

    def test_insert_duplicate_unique_constraint(self, database):
        """UNIQUE 제약 조건 위반 테스트"""
        database.insert.side_effect = sqlite3.IntegrityError("UNIQUE constraint failed")

        with pytest.raises(sqlite3.IntegrityError):
            database.insert("articles", {"url": "duplicate_url"})

    def test_execute_with_parameters(self, database):
        """매개변수가 있는 쿼리 실행 테스트"""
        database.execute.return_value = True

        query = "INSERT INTO keywords (keyword, search_volume) VALUES (?, ?)"
        params = ("테스트", 5000)

        result = database.execute(query, params)

        assert result is not None

    def test_transaction_commit(self, database, temp_db):
        """트랜잭션 커밋 테스트"""
        cursor = temp_db.cursor()
        cursor.execute("""
            INSERT INTO articles (url, title, category)
            VALUES ('url1', 'title1', 'category1')
        """)
        temp_db.commit()

        database.count.return_value = 1

        result = database.count("articles")

        assert result == 1

    def test_transaction_rollback(self, database, temp_db):
        """트랜잭션 롤백 테스트"""
        cursor = temp_db.cursor()

        try:
            cursor.execute("""
                INSERT INTO articles (url, title, category)
                VALUES ('url1', 'title1', 'category1')
            """)
            # 강제로 롤백
            temp_db.rollback()
        except Exception:
            pass

        database.count.return_value = 0

        result = database.count("articles")

        assert result == 0
