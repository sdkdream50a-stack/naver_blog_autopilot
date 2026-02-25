"""
pytest 설정 및 공통 픽스처 모음
테스트 전체에서 사용되는 재사용 가능한 픽스처 정의
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock
import pytest


@pytest.fixture
def temp_db():
    """
    메모리 기반 SQLite 데이터베이스 생성
    테스트 격리 및 빠른 실행을 위해 메모리 DB 사용
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 스키마 생성
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            content TEXT,
            category TEXT,
            crawl_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT
        );

        CREATE TABLE IF NOT EXISTS processed_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            generated_title TEXT,
            generated_content TEXT,
            seo_score REAL,
            plagiarism_score REAL,
            processing_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (article_id) REFERENCES articles(id)
        );

        CREATE TABLE IF NOT EXISTS crawl_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawler_name TEXT,
            status TEXT,
            article_count INTEGER,
            error_message TEXT,
            crawl_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL,
            search_volume INTEGER,
            competition_level TEXT,
            relevance_score REAL,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS keyword_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword_id INTEGER NOT NULL,
            search_volume INTEGER,
            rank_position INTEGER,
            recorded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (keyword_id) REFERENCES keywords(id)
        );

        CREATE TABLE IF NOT EXISTS competitor_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            competitor_url TEXT,
            title TEXT,
            views INTEGER,
            likes INTEGER,
            analyzed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_url TEXT,
            title TEXT,
            content TEXT,
            published_date TIMESTAMP,
            views INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS posting_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processed_article_id INTEGER NOT NULL,
            publish_time TIMESTAMP,
            success BOOLEAN DEFAULT 1,
            error_message TEXT,
            FOREIGN KEY (processed_article_id) REFERENCES processed_articles(id)
        );

        CREATE TABLE IF NOT EXISTS ranking_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            rank_position INTEGER,
            blog_url TEXT,
            recorded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_settings():
    """
    설정 객체 모킹
    테스트에서 실제 파일 시스템 접근 없이 설정 사용
    """
    settings = MagicMock()
    settings.validate.return_value = True
    settings.ensure_dirs.return_value = None
    settings.database_path = ":memory:"
    settings.blog_url = "https://blog.naver.com/test_blog"
    settings.crawl_limit = 10
    settings.max_posts_per_day = 3
    settings.max_posts_per_week = 15
    settings.min_interval_minutes = 60
    settings.naver_api_key = "test_api_key"
    settings.openai_api_key = "test_openai_key"
    return settings


@pytest.fixture
def mock_http_client():
    """
    HTTP 클라이언트 모킹
    네트워크 요청 없이 테스트 수행
    """
    client = MagicMock()
    client.get = Mock()
    client.post = Mock()
    client.get_many = Mock()
    return client


@pytest.fixture
def sample_html():
    """
    테스트용 샘플 HTML
    실제 웹 페이지 구조를 모방한 HTML
    """
    return """
    <html>
        <head>
            <title>테스트 블로그 포스트</title>
            <meta name="description" content="이것은 테스트 설명입니다">
        </head>
        <body>
            <div class="article-content">
                <h1>제목입니다</h1>
                <p>첫 번째 단락입니다.</p>
                <p>두 번째 단락입니다.   여러 공백이 있습니다.    </p>
                <div class="advertisement">광고</div>
                <p>세 번째 단락입니다.</p>
                <script>console.log('test');</script>
                <style>.hidden { display: none; }</style>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_keyword_data():
    """
    테스트용 키워드 데이터
    검색량, 경쟁도 등의 메트릭 포함
    """
    return {
        "keyword": "네이버 블로그 최적화",
        "search_volume": 5000,
        "competition": 45,
        "cpc": 1500,
        "relevance": 0.85
    }


@pytest.fixture
def sample_article():
    """
    테스트용 샘플 기사
    실제 기사 데이터 구조 모방
    """
    return {
        "url": "https://example.com/article/123",
        "title": "테스트 제목",
        "content": "테스트 내용입니다. 이것은 샘플 기사입니다.",
        "category": "기술",
        "source": "test_source"
    }


@pytest.fixture
def sample_generated_post():
    """
    생성된 포스트 샘플
    제목, 본문, SEO 스코어 포함
    """
    return {
        "title": "네이버 블로그 최적화 완벽 가이드 2024",
        "content": "네이버 블로그를 효과적으로 최적화하는 방법을 소개합니다. "
                   "SEO 최적화, 콘텐츠 구조화, 키워드 전략 등 "
                   "실무에서 바로 적용할 수 있는 팁을 제공합니다. "
                   "네이버 블로그 운영자들을 위한 필수 정보입니다.",
        "keyword": "네이버 블로그 최적화",
        "seo_score": 85.5
    }


@pytest.fixture
def sample_competitor_posts():
    """
    경쟁사 포스트 샘플
    여러 포스트의 조회수, 좋아요 등 메트릭 포함
    """
    return [
        {
            "keyword": "테스트 키워드",
            "url": "https://blog.naver.com/competitor1/123",
            "title": "경쟁사 포스트 1",
            "views": 5000,
            "likes": 150
        },
        {
            "keyword": "테스트 키워드",
            "url": "https://blog.naver.com/competitor2/456",
            "title": "경쟁사 포스트 2",
            "views": 3000,
            "likes": 80
        },
        {
            "keyword": "테스트 키워드",
            "url": "https://blog.naver.com/competitor3/789",
            "title": "경쟁사 포스트 3",
            "views": 4500,
            "likes": 120
        }
    ]


@pytest.fixture
def sample_posting_history():
    """
    포스팅 히스토리 샘플
    발행 시간, 성공 여부 등 포함
    """
    return [
        {
            "processed_article_id": 1,
            "publish_time": "2024-01-01 08:00:00",
            "success": True,
            "error_message": None
        },
        {
            "processed_article_id": 2,
            "publish_time": "2024-01-01 14:30:00",
            "success": True,
            "error_message": None
        },
        {
            "processed_article_id": 3,
            "publish_time": "2024-01-02 09:15:00",
            "success": False,
            "error_message": "네트워크 오류"
        }
    ]


@pytest.fixture
def sample_ranking_history():
    """
    순위 변동 히스토리 샘플
    키워드별 순위 추적 데이터
    """
    return [
        {
            "keyword": "테스트 키워드",
            "rank_position": 5,
            "blog_url": "https://blog.naver.com/test_blog",
            "recorded_date": "2024-01-01"
        },
        {
            "keyword": "테스트 키워드",
            "rank_position": 4,
            "blog_url": "https://blog.naver.com/test_blog",
            "recorded_date": "2024-01-02"
        },
        {
            "keyword": "테스트 키워드",
            "rank_position": 3,
            "blog_url": "https://blog.naver.com/test_blog",
            "recorded_date": "2024-01-03"
        }
    ]
