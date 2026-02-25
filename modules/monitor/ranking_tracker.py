"""
Naver 검색 순위 추적 모듈
"""

import asyncio
from datetime import datetime
from typing import Optional

from utils.database import Database
from utils.http_client import AsyncHTTPClient
from utils.logger import get_logger
from config.settings import settings


logger = get_logger()


class RankingTracker:
    """Naver 검색 순위 추적 클래스"""

    def __init__(self, db: Optional[Database] = None):
        """초기화"""
        self.db = db or Database(settings.DB_PATH)
        self.naver_api_url = "https://openapi.naver.com/v1/search/blog.json"
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET

    async def check_rankings(self) -> list[dict]:
        """모든 발행된 포스트의 순위를 확인합니다."""
        try:
            posts = self._get_published_posts()
            logger.info(f"발행된 포스트 {len(posts)}개 발견")

            ranking_results = []

            async with AsyncHTTPClient() as client:
                for post in posts:
                    post_id = post["id"]
                    keyword = post["keyword"]
                    blog_url = post["blog_url"]

                    try:
                        search_results = await self._search_naver(client, keyword)
                        rank = self._find_my_rank(search_results, blog_url)

                        self._save_ranking(post_id, keyword, rank, blog_url)

                        ranking_results.append({
                            "post_id": post_id,
                            "keyword": keyword,
                            "rank": rank,
                            "blog_url": blog_url,
                            "checked_at": datetime.now(),
                        })

                        logger.info(f"포스트 {post_id} 키워드 '{keyword}' 순위: {rank or '검색 결과 없음'}")

                        # API 레이트 제한
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.error(f"포스트 {post_id} 순위 확인 실패: {e}")
                        ranking_results.append({
                            "post_id": post_id,
                            "keyword": keyword,
                            "rank": None,
                            "blog_url": blog_url,
                            "checked_at": datetime.now(),
                            "error": str(e),
                        })

            return ranking_results

        except Exception as e:
            logger.error(f"순위 확인 중 오류 발생: {e}")
            raise

    async def _search_naver(self, client: AsyncHTTPClient, keyword: str) -> list[dict]:
        """Naver 검색 API를 호출하여 검색 결과를 가져옵니다."""
        try:
            headers = {
                "X-Naver-Client-Id": self.client_id,
                "X-Naver-Client-Secret": self.client_secret,
            }

            url = f"{self.naver_api_url}?query={keyword}&display=100&start=1&sort=sim"

            response = await client.get(url, headers=headers)

            if response.get("status") == 200:
                import json
                try:
                    data = json.loads(response.get("text", "{}"))
                    items = data.get("items", [])
                    logger.debug(f"키워드 '{keyword}' 검색 결과: {len(items)}개")
                    return items
                except json.JSONDecodeError:
                    logger.error(f"검색 결과 JSON 파싱 실패")
                    return []
            else:
                logger.error(f"Naver API 오류 (상태 코드: {response.get('status')})")
                return []

        except Exception as e:
            logger.error(f"Naver 검색 API 호출 실패: {e}")
            return []

    def _find_my_rank(self, results: list[dict], blog_url: str) -> Optional[int]:
        """검색 결과에서 내 블로그의 순위를 찾습니다."""
        try:
            for rank, result in enumerate(results, start=1):
                link = result.get("link", "")
                normalized_link = self._normalize_url(link)
                normalized_blog_url = self._normalize_url(blog_url)

                if normalized_link.startswith(normalized_blog_url):
                    logger.debug(f"블로그 순위 발견: {rank}위")
                    return rank

            return None

        except Exception as e:
            logger.error(f"순위 찾기 중 오류: {e}")
            return None

    def _normalize_url(self, url: str) -> str:
        """URL을 정규화합니다."""
        url = url.lower()
        url = url.replace("https://", "").replace("http://", "")
        url = url.replace("www.", "")
        url = url.rstrip("/")
        return url

    def _save_ranking(self, post_id: int, keyword: str, rank: Optional[int], blog_url: str) -> None:
        """순위를 데이터베이스에 저장합니다."""
        try:
            self.db.insert(
                """INSERT INTO ranking_history (post_id, keyword, naver_rank, blog_url, checked_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (post_id, keyword, rank, blog_url, datetime.now().isoformat()),
            )
            logger.debug(f"순위 저장 완료: post_id={post_id}, keyword={keyword}, rank={rank}")

        except Exception as e:
            logger.error(f"순위 저장 실패: {e}")

    def _get_published_posts(self) -> list[dict]:
        """발행된 모든 포스트를 조회합니다."""
        try:
            results = self.db.execute(
                """SELECT DISTINCT p.id, p.title, ph.blog_url
                   FROM posts p
                   INNER JOIN posting_history ph ON p.id = ph.post_id
                   WHERE ph.publish_status = 'success'
                   ORDER BY ph.published_at DESC"""
            )

            posts = []
            for row in results:
                # keywords 테이블에서 키워드 조회
                kw_rows = self.db.execute(
                    "SELECT keyword FROM keywords WHERE id = ?",
                    (row["id"],),
                )
                keyword = kw_rows[0]["keyword"] if kw_rows else row["title"]

                posts.append({
                    "id": row["id"],
                    "keyword": keyword,
                    "blog_url": row["blog_url"] or "",
                })

            logger.debug(f"발행된 포스트 조회: {len(posts)}개")
            return posts

        except Exception as e:
            logger.error(f"발행된 포스트 조회 실패: {e}")
            return []
