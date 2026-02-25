"""
SQLite 데이터베이스 관리
9개 테이블: articles, processed_articles, crawl_log,
           keywords, keyword_history, competitor_posts,
           posts, posting_history, ranking_history
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from utils.logger import get_logger

logger = get_logger()

# === 스키마 정의 ===
SCHEMA_SQL = """
-- Phase 1: Collector
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    html TEXT,
    category TEXT,
    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS processed_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    clean_text TEXT,
    summary TEXT,
    word_count INTEGER,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS crawl_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    status_code INTEGER,
    success BOOLEAN,
    error_message TEXT,
    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase 2: Researcher
CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT UNIQUE NOT NULL,
    cluster TEXT,
    monthly_search_volume INTEGER DEFAULT 0,
    competition_score FLOAT DEFAULT 0,
    relevance_score FLOAT DEFAULT 0,
    total_score FLOAT DEFAULT 0,
    related_keywords TEXT,  -- JSON array
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS keyword_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword_id INTEGER NOT NULL,
    monthly_search_volume INTEGER,
    competition_score FLOAT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (keyword_id) REFERENCES keywords(id)
);

CREATE TABLE IF NOT EXISTS competitor_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    post_url TEXT,
    post_title TEXT,
    char_count INTEGER,
    image_count INTEGER,
    has_table BOOLEAN DEFAULT 0,
    has_faq BOOLEAN DEFAULT 0,
    naver_rank INTEGER,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase 3: Generator
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER,
    keyword_id INTEGER,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    html_body TEXT,
    seo_score FLOAT DEFAULT 0,
    keyword_density FLOAT DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    generation_cost FLOAT DEFAULT 0,
    plagiarism_score FLOAT DEFAULT 0,
    publish_category TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',  -- draft, approved, published, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES articles(id),
    FOREIGN KEY (keyword_id) REFERENCES keywords(id)
);

-- Phase 4: Publisher
CREATE TABLE IF NOT EXISTS posting_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    blog_url TEXT,
    publish_status TEXT DEFAULT 'pending',  -- pending, success, failed
    error_message TEXT,
    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

-- Phase 5: Monitor
CREATE TABLE IF NOT EXISTS ranking_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,
    keyword TEXT NOT NULL,
    naver_rank INTEGER,
    blog_url TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

-- Phase 6: Legal Verification (법령 검증)
CREATE TABLE IF NOT EXISTS legal_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    law_name TEXT NOT NULL,              -- 법령명
    law_name_normalized TEXT,            -- 정규화된 법령명
    article_number TEXT,                 -- 조문 번호 (예: 제9조)
    citation_text TEXT,                  -- 인용 원문
    verification_status TEXT DEFAULT 'pending',  -- pending, verified, failed, warning
    error_message TEXT,
    last_verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS legal_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id INTEGER NOT NULL,
    check_type TEXT NOT NULL,            -- exists, article_valid, content_match
    result TEXT NOT NULL,                -- pass, fail, warning
    details TEXT,                        -- JSON 상세 정보
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reference_id) REFERENCES legal_references(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS legal_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    law_name TEXT NOT NULL,
    change_type TEXT NOT NULL,           -- amended, repealed, new
    change_date DATE,
    description TEXT,
    affected_posts_count INTEGER DEFAULT 0,
    notified BOOLEAN DEFAULT 0,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_keywords_keyword ON keywords(keyword);
CREATE INDEX IF NOT EXISTS idx_keywords_score ON keywords(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posting_history_status ON posting_history(publish_status);
CREATE INDEX IF NOT EXISTS idx_ranking_history_keyword ON ranking_history(keyword);
CREATE INDEX IF NOT EXISTS idx_legal_references_post ON legal_references(post_id);
CREATE INDEX IF NOT EXISTS idx_legal_references_law ON legal_references(law_name_normalized);
CREATE INDEX IF NOT EXISTS idx_legal_changes_law ON legal_changes(law_name);
"""


class Database:
    """SQLite 데이터베이스 매니저"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """컨텍스트 매니저로 DB 연결 관리"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        """데이터베이스 초기화 (테이블 생성)"""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
        logger.info(f"데이터베이스 초기화 완료: {self.db_path}")

    def execute(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """쿼리 실행 및 결과 반환"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def execute_many(self, query: str, params_list: list[tuple]):
        """여러 행 삽입"""
        with self.get_connection() as conn:
            conn.executemany(query, params_list)

    def insert(self, query: str, params: tuple = ()) -> int:
        """단일 행 삽입 후 ID 반환"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid

    def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        """테이블 행 수 반환"""
        query = f"SELECT COUNT(*) as cnt FROM {table}"
        if where:
            query += f" WHERE {where}"
        rows = self.execute(query, params)
        return rows[0]["cnt"] if rows else 0

    # ===== 멀티 블로그 관련 메서드 =====

    def get_blog(self, blog_id: int = None, blog_name: str = None) -> dict | None:
        """
        블로그 설정 조회

        Args:
            blog_id: 블로그 ID
            blog_name: 블로그 이름

        Returns:
            블로그 설정 딕셔너리 또는 None
        """
        if blog_id:
            rows = self.execute("SELECT * FROM blogs WHERE id = ?", (blog_id,))
        elif blog_name:
            rows = self.execute("SELECT * FROM blogs WHERE name = ?", (blog_name,))
        else:
            # 기본 블로그 (첫 번째)
            rows = self.execute("SELECT * FROM blogs WHERE active = 1 ORDER BY id LIMIT 1")

        return dict(rows[0]) if rows else None

    def list_blogs(self, active_only: bool = True) -> list[dict]:
        """
        모든 블로그 목록 조회

        Args:
            active_only: 활성화된 블로그만 조회

        Returns:
            블로그 목록
        """
        if active_only:
            rows = self.execute("SELECT * FROM blogs WHERE active = 1 ORDER BY id")
        else:
            rows = self.execute("SELECT * FROM blogs ORDER BY id")

        return [dict(row) for row in rows]

    def create_blog(self, blog_data: dict) -> int:
        """
        새 블로그 생성

        Args:
            blog_data: 블로그 데이터

        Returns:
            생성된 블로그 ID
        """
        import json

        query = """
            INSERT INTO blogs (
                name, display_name, domain, description, theme,
                system_prompt, categories, crawler_configs,
                verification_modules, monthly_budget, max_posts_per_day
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            blog_data["name"],
            blog_data["display_name"],
            blog_data.get("domain"),
            blog_data.get("description"),
            blog_data.get("theme", "default"),
            blog_data["system_prompt"],
            json.dumps(blog_data.get("categories", [])),
            json.dumps(blog_data.get("crawler_configs", {})),
            json.dumps(blog_data.get("verification_modules", [])),
            blog_data.get("monthly_budget", 5000),
            blog_data.get("max_posts_per_day", 2),
        )

        return self.insert(query, params)
