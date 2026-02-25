"""
경쟁 분석 모듈 - Naver 블로그 경쟁 포스트 분석
"""

import re
import json
from typing import Optional
from bs4 import BeautifulSoup

from utils.database import Database
from utils.http_client import AsyncHTTPClient
from utils.logger import get_logger
from config.settings import settings

logger = get_logger()


class CompetitorScanner:
    """Naver 블로그 경쟁 분석 클래스"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database(settings.DB_PATH)
        self.search_endpoint = "https://openapi.naver.com/v1/search/blog.json"
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET

    async def analyze_competitors(self, keyword: str, top_n: int = 10) -> dict:
        """특정 키워드의 상위 경쟁 블로그 포스트 분석"""
        logger.info(f"경쟁 분석 시작: '{keyword}' (상위 {top_n}개)")

        result = {
            "keyword": keyword,
            "total_posts_analyzed": 0,
            "competition_score": 0.0,
            "average_char_count": 0,
            "average_image_count": 0,
            "posts": [],
        }

        async with AsyncHTTPClient(
            timeout=settings.CRAWL_TIMEOUT,
            user_agent=settings.USER_AGENT,
        ) as client:
            # 네이버 블로그 검색
            posts = await self._search_naver_blog(client, keyword, top_n)

            if not posts:
                logger.warning(f"'{keyword}' 검색 결과 없음")
                return result

            # 각 포스트 분석
            analyzed = []
            for rank, post in enumerate(posts, 1):
                try:
                    analysis = await self._analyze_post(client, post)
                    analysis["naver_rank"] = rank
                    analyzed.append(analysis)

                    # DB 저장
                    self._save_competitor_post(keyword, analysis)

                except Exception as e:
                    logger.error(f"포스트 분석 오류: {e}")

            # 통계 계산
            if analyzed:
                result["total_posts_analyzed"] = len(analyzed)
                result["average_char_count"] = int(
                    sum(p.get("char_count", 0) for p in analyzed) / len(analyzed)
                )
                result["average_image_count"] = int(
                    sum(p.get("image_count", 0) for p in analyzed) / len(analyzed)
                )
                result["competition_score"] = self._calculate_competition_score(analyzed)
                result["posts"] = analyzed

        logger.info(f"경쟁 분석 완료: '{keyword}' - {result['total_posts_analyzed']}개 분석")
        return result

    async def _search_naver_blog(self, client: AsyncHTTPClient, keyword: str, count: int) -> list[dict]:
        """네이버 블로그 검색 API 호출"""
        if not self.client_id or not self.client_secret:
            logger.warning("네이버 API 키 미설정 - 검색 건너뜀")
            return []

        try:
            response = await client.get(
                self.search_endpoint,
                headers={
                    "X-Naver-Client-Id": self.client_id,
                    "X-Naver-Client-Secret": self.client_secret,
                },
                params={
                    "query": keyword,
                    "display": min(count, 100),
                    "sort": "sim",
                },
            )

            if response.get("status") == 200:
                data = json.loads(response.get("text", "{}"))
                items = data.get("items", [])
                logger.info(f"블로그 검색 성공: '{keyword}' - {len(items)}개 결과")
                return items
            else:
                logger.error(f"블로그 검색 API 오류: status={response.get('status')}")
                return []

        except Exception as e:
            logger.error(f"블로그 검색 오류: {e}")
            return []

    async def _analyze_post(self, client: AsyncHTTPClient, post: dict) -> dict:
        """개별 포스트 분석 (검색 결과 메타데이터 기반)"""
        title = re.sub(r"<[^>]+>", "", post.get("title", ""))
        description = re.sub(r"<[^>]+>", "", post.get("description", ""))
        link = post.get("link", "")

        # 기본 분석 (검색 결과에서 추출 가능한 정보)
        char_count = len(description) * 10  # 설명 길이로 전체 글 길이 추정
        has_table = "표" in description or "비교" in description
        has_faq = "질문" in description or "FAQ" in description or "Q." in description

        return {
            "post_url": link,
            "post_title": title,
            "char_count": char_count,
            "image_count": 3,  # 기본 추정값
            "has_table": has_table,
            "has_faq": has_faq,
        }

    def _calculate_competition_score(self, posts: list[dict]) -> float:
        """경쟁도 점수 계산 (0.0~1.0)"""
        if not posts:
            return 0.0

        avg_char = sum(p.get("char_count", 0) for p in posts) / len(posts)
        avg_img = sum(p.get("image_count", 0) for p in posts) / len(posts)
        table_ratio = sum(1 for p in posts if p.get("has_table")) / len(posts)
        faq_ratio = sum(1 for p in posts if p.get("has_faq")) / len(posts)

        # 가중 점수 (높을수록 경쟁이 치열)
        score = (
            min(avg_char / 3000, 1.0) * 0.35
            + min(avg_img / 10, 1.0) * 0.25
            + table_ratio * 0.20
            + faq_ratio * 0.20
        )
        return round(score, 2)

    def _save_competitor_post(self, keyword: str, analysis: dict) -> None:
        """경쟁 포스트 분석 결과를 DB에 저장"""
        try:
            self.db.insert(
                """INSERT INTO competitor_posts
                   (keyword, post_url, post_title, char_count, image_count,
                    has_table, has_faq, naver_rank)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    keyword,
                    analysis.get("post_url", ""),
                    analysis.get("post_title", ""),
                    analysis.get("char_count", 0),
                    analysis.get("image_count", 0),
                    analysis.get("has_table", False),
                    analysis.get("has_faq", False),
                    analysis.get("naver_rank", 0),
                ),
            )
        except Exception as e:
            logger.error(f"경쟁 포스트 DB 저장 오류: {e}")
