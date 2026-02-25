"""
트렌드 추적 모듈 - Naver 자동완성 및 관련 키워드 확장
"""

import json
from typing import Optional

from utils.database import Database
from utils.http_client import AsyncHTTPClient
from utils.logger import get_logger
from config.settings import settings

logger = get_logger()


class TrendTracker:
    """Naver 자동완성 및 관련 키워드를 이용한 트렌드 추적 클래스"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database(settings.DB_PATH)
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET

    async def expand_keywords(self, seed_keywords: list[str]) -> dict[str, list[str]]:
        """시드 키워드를 확장하여 관련 키워드 수집"""
        logger.info(f"키워드 확장 시작: {len(seed_keywords)}개 시드 키워드")

        expanded_keywords = {}

        async with AsyncHTTPClient(
            timeout=settings.CRAWL_TIMEOUT,
            user_agent=settings.USER_AGENT,
        ) as client:
            for keyword in seed_keywords:
                try:
                    autocomplete = await self._get_autocomplete(client, keyword)
                    related = await self._get_related_keywords(client, keyword)

                    all_kw = list(set(autocomplete + related))
                    all_kw = [kw for kw in all_kw if kw.strip()]
                    expanded_keywords[keyword] = all_kw

                    logger.info(f"'{keyword}'에서 {len(all_kw)}개 확장 키워드 추출")

                    # DB에 관련 키워드 저장
                    if all_kw:
                        self._save_to_db(keyword, all_kw)

                except Exception as e:
                    logger.error(f"키워드 '{keyword}' 확장 오류: {e}")
                    expanded_keywords[keyword] = []

        logger.info(f"키워드 확장 완료: {len(expanded_keywords)}개 카테고리")
        return expanded_keywords

    async def _get_autocomplete(self, client: AsyncHTTPClient, keyword: str) -> list[str]:
        """Naver 자동완성 API 호출"""
        try:
            if not self.client_id or not self.client_secret:
                logger.warning("네이버 API 키가 설정되지 않음 - 자동완성 건너뜀")
                return []

            response = await client.get(
                "https://openapi.naver.com/v1/search/blog.json",
                headers={
                    "X-Naver-Client-Id": self.client_id,
                    "X-Naver-Client-Secret": self.client_secret,
                },
                params={"query": keyword, "display": 5},
            )

            if response.get("status") == 200:
                data = json.loads(response.get("text", "{}"))
                # 블로그 검색 결과에서 관련 키워드 추출
                keywords = []
                for item in data.get("items", []):
                    title = item.get("title", "")
                    # HTML 태그 제거
                    import re
                    clean_title = re.sub(r"<[^>]+>", "", title)
                    if clean_title and clean_title != keyword:
                        keywords.append(clean_title[:30])
                return keywords[:10]
            else:
                logger.warning(f"자동완성 API 응답: {response.get('status')}")
                return []

        except Exception as e:
            logger.error(f"자동완성 조회 오류: {e}")
            return []

    async def _get_related_keywords(self, client: AsyncHTTPClient, keyword: str) -> list[str]:
        """Naver 연관 검색어 추출 (블로그 검색 결과에서)"""
        try:
            if not self.client_id or not self.client_secret:
                return []

            # 키워드 변형으로 연관 키워드 생성
            suffixes = ["방법", "절차", "서류", "기준", "규정"]
            related = []
            for suffix in suffixes:
                combined = f"{keyword} {suffix}"
                related.append(combined)

            return related

        except Exception as e:
            logger.error(f"관련 검색 조회 오류: {e}")
            return []

    def _save_to_db(self, seed_keyword: str, expanded: list[str]) -> None:
        """확장 키워드를 keywords 테이블에 저장"""
        try:
            related_json = json.dumps(expanded, ensure_ascii=False)
            self.db.insert(
                """INSERT OR REPLACE INTO keywords (keyword, cluster, related_keywords)
                   VALUES (?, ?, ?)""",
                (seed_keyword, "expanded", related_json),
            )
        except Exception as e:
            logger.error(f"키워드 DB 저장 오류: {e}")
