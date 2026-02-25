"""
Silmu.kr Article Crawler Module

silmu.kr 사이트에서 기사를 수집하는 모듈입니다.
Sitemap.xml을 파싱하여 기사 URL을 발견하고, 각 기사를 크롤링한 후
카테고리별로 자동 분류하여 SQLite 데이터베이스에 저장합니다.
"""

import asyncio
import xml.etree.ElementTree as ET
from typing import Optional
from datetime import datetime

from bs4 import BeautifulSoup
import trafilatura

from utils.database import Database
from utils.http_client import AsyncHTTPClient
from utils.logger import get_logger
from config.settings import settings

logger = get_logger()


class SilmuCrawler:
    """
    Silmu.kr 기사 크롤러

    Attributes:
        db (Database): SQLite 데이터베이스 인스턴스
    """

    # 카테고리 매칭용 키워드 사전
    CATEGORY_KEYWORDS = {
        "조달/계약": ["조달", "계약", "입찰", "낙찰", "수의", "경쟁", "계약금", "보증금"],
        "예산/회계": ["예산", "회계", "결산", "세출", "세입", "기금", "지출", "수익", "이월"],
        "학교행정": ["학교", "교육청", "수학여행", "학교행사", "교직원", "학생", "교실", "학급"],
        "공직생활": ["공무원", "직급", "승진", "퇴직", "근무", "휴가", "복무", "규정", "지침"],
    }

    def __init__(self, db: Optional[Database] = None):
        """
        Args:
            db (Database, optional): 데이터베이스 인스턴스 (None이면 settings 기본값 사용)
        """
        self.db = db or Database(settings.DB_PATH)

    async def crawl(self, limit: Optional[int] = None) -> int:
        """
        Silmu.kr에서 기사를 크롤링합니다.

        Args:
            limit (int, optional): 크롤링할 최대 기사 수

        Returns:
            int: 크롤링된 기사 수
        """
        logger.info("Silmu.kr 크롤링 시작")

        async with AsyncHTTPClient(
            max_concurrent=settings.MAX_CONCURRENT_REQUESTS,
            timeout=settings.CRAWL_TIMEOUT,
            user_agent=settings.USER_AGENT,
        ) as client:
            # Sitemap에서 URL 목록 가져오기
            urls = await self._fetch_sitemap(client)
            logger.info(f"Sitemap에서 {len(urls)}개의 URL 발견")

            if limit:
                urls = urls[:limit]
                logger.info(f"크롤링 제한: 최대 {limit}개")

            # 이미 크롤링한 URL 제외
            existing = self.db.execute("SELECT url FROM articles")
            existing_urls = {row["url"] for row in existing}
            new_urls = [u for u in urls if u not in existing_urls]
            logger.info(f"새로운 URL: {len(new_urls)}개 (기존 {len(existing_urls)}개 제외)")

            crawled_count = 0

            for idx, url in enumerate(new_urls, 1):
                try:
                    logger.info(f"({idx}/{len(new_urls)}) {url} 크롤링 중...")
                    article_data = await self._crawl_article(client, url)

                    if article_data:
                        self._save_article(article_data)
                        crawled_count += 1
                        logger.info(f"기사 저장: {article_data['title']}")
                    else:
                        logger.warning(f"기사 파싱 실패: {url}")
                        self._log_crawl(url, None, False, "파싱 실패")

                    # 크롤링 딜레이
                    await asyncio.sleep(settings.CRAWL_DELAY)

                except Exception as e:
                    logger.error(f"크롤링 오류: {url} - {e}")
                    self._log_crawl(url, None, False, str(e))
                    continue

        logger.info(f"크롤링 완료: {crawled_count}개 기사 저장")
        return crawled_count

    async def _fetch_sitemap(self, client: AsyncHTTPClient) -> list[str]:
        """Sitemap.xml에서 기사 URL 목록 추출"""
        logger.info(f"Sitemap 다운로드: {settings.SILMU_SITEMAP_URL}")

        response = await client.get(settings.SILMU_SITEMAP_URL)

        if response.get("status") != 200:
            logger.error(f"Sitemap 다운로드 실패: status={response.get('status')}")
            return []

        xml_text = response.get("text", "")

        try:
            root = ET.fromstring(xml_text)
            namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = [
                loc.text
                for loc in root.findall(".//ns:loc", namespace)
                if loc.text
            ]
            logger.info(f"Sitemap에서 {len(urls)}개 URL 추출")
            return urls

        except ET.ParseError as e:
            logger.error(f"Sitemap XML 파싱 실패: {e}")
            return []

    async def _crawl_article(self, client: AsyncHTTPClient, url: str) -> Optional[dict]:
        """
        개별 기사 크롤링

        Returns:
            dict: {"url", "title", "html", "clean_text", "category"} 또는 None
        """
        response = await client.get(url)

        if response.get("status") != 200:
            return None

        html = response.get("text", "")
        if not html:
            return None

        # BeautifulSoup으로 제목 추출
        soup = BeautifulSoup(html, "html.parser")

        title = None
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]
        else:
            title_tag = soup.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else "제목 없음"

        # trafilatura로 본문 추출
        clean_text = self._extract_text(html)

        # 카테고리 분류
        category = self._categorize(clean_text)

        # 크롤링 성공 로그
        self._log_crawl(url, 200, True, None)

        return {
            "url": url,
            "title": title,
            "html": html,
            "clean_text": clean_text,
            "category": category,
        }

    def _categorize(self, text: str) -> str:
        """텍스트 기반 카테고리 자동 분류"""
        if not text:
            return "일반"

        category_scores = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            category_scores[category] = score

        max_score = max(category_scores.values())
        if max_score > 0:
            return max(category_scores, key=category_scores.get)

        return "일반"

    def _extract_text(self, html: str) -> str:
        """HTML에서 본문 텍스트 추출 (trafilatura)"""
        try:
            extracted = trafilatura.extract(html)
            return extracted if extracted else ""
        except Exception as e:
            logger.error(f"텍스트 추출 오류: {e}")
            return ""

    def _save_article(self, article_data: dict) -> None:
        """기사를 DB에 저장 (articles + processed_articles)"""
        try:
            # articles 테이블
            article_id = self.db.insert(
                """INSERT OR IGNORE INTO articles (url, title, html, category)
                   VALUES (?, ?, ?, ?)""",
                (
                    article_data["url"],
                    article_data["title"],
                    article_data["html"],
                    article_data["category"],
                ),
            )

            # processed_articles 테이블
            if article_id and article_data.get("clean_text"):
                clean_text = article_data["clean_text"]
                summary = clean_text[:200] + "..." if len(clean_text) > 200 else clean_text
                word_count = len(clean_text)

                self.db.insert(
                    """INSERT INTO processed_articles (article_id, clean_text, summary, word_count)
                       VALUES (?, ?, ?, ?)""",
                    (article_id, clean_text, summary, word_count),
                )

        except Exception as e:
            logger.error(f"DB 저장 오류: {e}")

    def _log_crawl(self, url: str, status_code: Optional[int], success: bool, error_message: Optional[str]) -> None:
        """크롤링 결과를 crawl_log 테이블에 기록"""
        try:
            self.db.insert(
                """INSERT INTO crawl_log (url, status_code, success, error_message)
                   VALUES (?, ?, ?, ?)""",
                (url, status_code, success, error_message),
            )
        except Exception as e:
            logger.error(f"크롤링 로그 기록 오류: {e}")
