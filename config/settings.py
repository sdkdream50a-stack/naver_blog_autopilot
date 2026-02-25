"""
NaverBlogAutoPilot 설정 관리
환경변수(.env)에서 설정값을 로드합니다.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv as _load_dotenv

    def load_dotenv(path):
        """python-dotenv로 .env 로드 (override=True)"""
        _load_dotenv(path, override=True)

except ImportError:
    # python-dotenv가 없으면 수동으로 .env 파싱
    def load_dotenv(path):
        if path and Path(path).exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        os.environ[key.strip()] = value.strip()

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).resolve().parent.parent

# .env 로드
load_dotenv(BASE_DIR / ".env")


class Settings:
    """전역 설정"""

    # === 프로젝트 경로 ===
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    REPORTS_DIR: Path = BASE_DIR / "data" / "reports"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"

    # === 데이터베이스 ===
    DB_PATH: Path = Path(os.getenv("DB_PATH", str(BASE_DIR / "data" / "blog_autopilot.db")))

    # === Claude AI ===
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
    CLAUDE_MAX_TOKENS: int = int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))

    # === Google Gemini (이미지 생성) ===
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"  # 무료 이미지 생성 모델

    # === 네이버 검색광고 API (키워드 분석) ===
    NAVER_AD_API_KEY: str = os.getenv("NAVER_AD_API_KEY", "")
    NAVER_AD_SECRET_KEY: str = os.getenv("NAVER_AD_SECRET_KEY", "")
    NAVER_AD_CUSTOMER_ID: str = os.getenv("NAVER_AD_CUSTOMER_ID", "")

    # === 네이버 개발자 API (검색) ===
    NAVER_CLIENT_ID: str = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET: str = os.getenv("NAVER_CLIENT_SECRET", "")

    # === 네이버 블로그 ===
    NAVER_BLOG_ID: str = os.getenv("NAVER_BLOG_ID", "")
    NAVER_COOKIES_PATH: Path = BASE_DIR / "data" / "naver_cookies.json"

    # === 크롤링 설정 ===
    SILMU_BASE_URL: str = "https://silmu.kr"
    SILMU_SITEMAP_URL: str = "https://silmu.kr/sitemap.xml"
    CRAWL_DELAY: float = 1.0  # 크롤링 간 딜레이 (초)
    CRAWL_TIMEOUT: int = 30  # 요청 타임아웃 (초)

    # === 콘텐츠 생성 설정 ===
    MIN_POST_LENGTH: int = 2000  # 최소 글자수
    MAX_POST_LENGTH: int = 3000  # 최대 글자수
    MIN_SEO_SCORE: int = 70  # 최소 SEO 점수 (미만 시 재생성)
    MAX_REGENERATION: int = 3  # 최대 재생성 횟수
    TARGET_KEYWORD_DENSITY_MIN: float = 1.5  # 키워드 밀도 최소 (%)
    TARGET_KEYWORD_DENSITY_MAX: float = 2.5  # 키워드 밀도 최대 (%)
    PLAGIARISM_THRESHOLD: float = 0.30  # 표절 임계값 (30% 이하)

    # === 발행 설정 (어뷰징 방지) ===
    MIN_INTERVAL_HOURS: int = 4  # 최소 발행 간격 (시간)
    MAX_POSTS_PER_DAY: int = 2  # 일일 최대 발행 수
    MAX_POSTS_PER_WEEK: int = 5  # 주간 최대 발행 수
    PREFERRED_HOURS: list = [9, 15, 20]  # 선호 발행 시간대

    # === 모니터링 설정 ===
    MONITOR_HOUR: int = 18  # 순위 체크 시간 (18:00)
    REPORT_DAY: str = "monday"  # 주간 리포트 생성 요일

    # === 스케줄러 설정 ===
    SCHEDULE_CRAWL_HOUR: str = "08:00"
    SCHEDULE_PUBLISH_HOURS: list = ["09:00", "15:00"]
    SCHEDULE_MONITOR_HOUR: str = "18:00"

    # === 로깅 ===
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: Path = BASE_DIR / "logs"

    # === HTTP 클라이언트 ===
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    MAX_CONCURRENT_REQUESTS: int = 10

    # === 카테고리 매핑 ===
    CATEGORIES: dict = {
        "procurement": "계약/조달",
        "budget": "예산/회계",
        "service": "복무/급여",
        "general": "일반",
    }

    # === 카테고리 발행 순서 ===
    PUBLISH_CATEGORY_ORDER: list = ["계약/조달", "예산/회계", "복무/급여"]
    POSTS_PER_CATEGORY_ROTATE: int = 5  # 한 카테고리에 N개 발행 후 다음으로

    # === 크롤링 카테고리 → 발행 카테고리 매핑 ===
    CATEGORY_MAP: dict = {
        "조달/계약": "계약/조달",
        "예산/회계": "예산/회계",
        "공직생활": "복무/급여",
        "학교행정": "복무/급여",
    }

    @classmethod
    def validate(cls) -> list[str]:
        """필수 설정값 검증. 누락된 항목 리스트 반환."""
        missing = []
        if not cls.ANTHROPIC_API_KEY:
            missing.append("ANTHROPIC_API_KEY")
        if not cls.NAVER_CLIENT_ID:
            missing.append("NAVER_CLIENT_ID")
        if not cls.NAVER_CLIENT_SECRET:
            missing.append("NAVER_CLIENT_SECRET")
        if not cls.NAVER_BLOG_ID:
            missing.append("NAVER_BLOG_ID")
        return missing

    @classmethod
    def ensure_dirs(cls):
        """필요한 디렉토리 생성"""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
