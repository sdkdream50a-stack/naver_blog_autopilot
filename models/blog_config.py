"""
BlogConfig 모델
멀티 블로그 설정을 관리하는 데이터 클래스
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json


@dataclass
class BlogConfig:
    """블로그 설정 모델"""

    # 기본 정보
    id: int
    name: str  # 식별자 (예: "silmu", "tech-blog")
    display_name: str  # 표시명 (예: "실무 블로그")
    domain: Optional[str] = None
    description: Optional[str] = None
    theme: str = "default"

    # 콘텐츠 설정
    system_prompt: str = ""
    categories: List[str] = field(default_factory=list)

    # 크롤러 설정
    crawler_configs: Dict[str, bool] = field(default_factory=dict)
    crawler_urls: List[str] = field(default_factory=list)

    # 검증 설정
    verification_modules: List[str] = field(default_factory=list)

    # 예산/스케줄
    monthly_budget: int = 5000
    max_posts_per_day: int = 2
    max_posts_per_week: int = 5
    min_interval_hours: int = 4

    # 스케줄
    schedule_crawl_hour: int = 3
    schedule_publish_hours: List[int] = field(default_factory=lambda: [9, 15])
    schedule_monitor_hour: int = 23

    # 품질 기준
    min_seo_score: int = 70
    plagiarism_threshold: float = 0.3
    max_regeneration: int = 3

    # API 키
    api_keys: Dict[str, str] = field(default_factory=dict)

    # 상태
    active: bool = True

    @classmethod
    def from_db_row(cls, row: dict) -> "BlogConfig":
        """
        DB 행에서 BlogConfig 객체 생성

        Args:
            row: sqlite3.Row 객체 (dict로 변환 가능)

        Returns:
            BlogConfig 인스턴스
        """
        # JSON 필드 파싱
        categories = json.loads(row.get("categories", "[]"))
        crawler_configs = json.loads(row.get("crawler_configs", "{}"))
        crawler_urls = json.loads(row.get("crawler_urls", "[]"))
        verification_modules = json.loads(row.get("verification_modules", "[]"))
        schedule_publish_hours = json.loads(row.get("schedule_publish_hours", "[9, 15]"))
        api_keys = json.loads(row.get("api_keys", "{}"))

        return cls(
            id=row["id"],
            name=row["name"],
            display_name=row["display_name"],
            domain=row.get("domain"),
            description=row.get("description"),
            theme=row.get("theme", "default"),
            system_prompt=row["system_prompt"],
            categories=categories,
            crawler_configs=crawler_configs,
            crawler_urls=crawler_urls,
            verification_modules=verification_modules,
            monthly_budget=row.get("monthly_budget", 5000),
            max_posts_per_day=row.get("max_posts_per_day", 2),
            max_posts_per_week=row.get("max_posts_per_week", 5),
            min_interval_hours=row.get("min_interval_hours", 4),
            schedule_crawl_hour=row.get("schedule_crawl_hour", 3),
            schedule_publish_hours=schedule_publish_hours,
            schedule_monitor_hour=row.get("schedule_monitor_hour", 23),
            min_seo_score=row.get("min_seo_score", 70),
            plagiarism_threshold=row.get("plagiarism_threshold", 0.3),
            max_regeneration=row.get("max_regeneration", 3),
            api_keys=api_keys,
            active=bool(row.get("active", 1)),
        )

    def to_dict(self) -> dict:
        """BlogConfig를 딕셔너리로 변환"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "domain": self.domain,
            "description": self.description,
            "theme": self.theme,
            "system_prompt": self.system_prompt,
            "categories": self.categories,
            "crawler_configs": self.crawler_configs,
            "crawler_urls": self.crawler_urls,
            "verification_modules": self.verification_modules,
            "monthly_budget": self.monthly_budget,
            "max_posts_per_day": self.max_posts_per_day,
            "max_posts_per_week": self.max_posts_per_week,
            "min_interval_hours": self.min_interval_hours,
            "schedule_crawl_hour": self.schedule_crawl_hour,
            "schedule_publish_hours": self.schedule_publish_hours,
            "schedule_monitor_hour": self.schedule_monitor_hour,
            "min_seo_score": self.min_seo_score,
            "plagiarism_threshold": self.plagiarism_threshold,
            "max_regeneration": self.max_regeneration,
            "active": self.active,
        }

    def has_verification_module(self, module_name: str) -> bool:
        """특정 검증 모듈이 활성화되어 있는지 확인"""
        return module_name in self.verification_modules

    def is_crawler_enabled(self, crawler_name: str) -> bool:
        """특정 크롤러가 활성화되어 있는지 확인"""
        return self.crawler_configs.get(crawler_name, False)
