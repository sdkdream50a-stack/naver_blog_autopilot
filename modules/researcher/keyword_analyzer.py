"""
키워드 분석 모듈 - Naver Search Ads API 연동
월간 검색량, 경쟁도, 관련성 등을 분석하여 키워드 점수를 산출합니다.
"""

import hmac
import hashlib
import json
from datetime import datetime
from typing import Optional
from base64 import b64encode

from utils.database import Database
from utils.http_client import AsyncHTTPClient
from utils.logger import get_logger
from config.settings import settings

logger = get_logger()


class KeywordAnalyzer:
    """Naver Search Ads API를 이용한 키워드 분석 클래스"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database(settings.DB_PATH)
        self.api_key = settings.NAVER_AD_API_KEY
        self.secret_key = settings.NAVER_AD_SECRET_KEY
        self.customer_id = settings.NAVER_AD_CUSTOMER_ID
        self.api_endpoint = "https://api.searchad.naver.com/keywordstool"

    async def analyze_keywords(self, keywords: list[str]) -> list[dict]:
        """키워드 목록을 분석하여 점수를 계산합니다."""
        logger.info(f"키워드 분석 시작: {len(keywords)}개 키워드")

        if not keywords:
            return []

        results = []

        async with AsyncHTTPClient(
            timeout=settings.CRAWL_TIMEOUT,
            user_agent=settings.USER_AGENT,
        ) as client:
            # 배치 처리 (API 제한: 한 번에 5개씩)
            batch_size = 5
            for i in range(0, len(keywords), batch_size):
                batch = keywords[i:i + batch_size]
                try:
                    volume_data = await self._get_search_volume(client, batch)

                    for keyword in batch:
                        if keyword in volume_data:
                            info = volume_data[keyword]
                            monthly_volume = info.get("monthlyPcQcCnt", 0) + info.get("monthlyMobileQcCnt", 0)
                            competition = info.get("compIdx", 0.5)
                            relevance = self._calculate_relevance_score(keyword, [])

                            total_score = self._calculate_score(monthly_volume, competition, relevance)

                            result = {
                                "keyword": keyword,
                                "monthly_search_volume": monthly_volume,
                                "competition_score": competition,
                                "relevance_score": relevance,
                                "total_score": total_score,
                                "related_keywords": [],
                            }
                            results.append(result)
                            self._save_keyword_to_db(result)
                        else:
                            # API 데이터 없으면 기본값으로 저장
                            logger.warning(f"키워드 '{keyword}' API 데이터 없음 - 기본값 사용")
                            result = {
                                "keyword": keyword,
                                "monthly_search_volume": 0,
                                "competition_score": 0.5,
                                "relevance_score": 0.5,
                                "total_score": self._calculate_score(0, 0.5, 0.5),
                                "related_keywords": [],
                            }
                            results.append(result)
                            self._save_keyword_to_db(result)

                except Exception as e:
                    logger.error(f"키워드 배치 분석 오류: {e}")
                    # 에러 시에도 기본값으로 키워드 저장
                    for keyword in batch:
                        result = {
                            "keyword": keyword,
                            "monthly_search_volume": 0,
                            "competition_score": 0.5,
                            "relevance_score": 0.5,
                            "total_score": self._calculate_score(0, 0.5, 0.5),
                            "related_keywords": [],
                        }
                        results.append(result)
                        self._save_keyword_to_db(result)

        logger.info(f"키워드 분석 완료: {len(results)}개 결과")
        return results

    async def _get_search_volume(self, client: AsyncHTTPClient, keywords: list[str]) -> dict:
        """Naver Search Ads API 호출로 검색량 데이터 조회"""
        if not self.api_key or not self.secret_key or not self.customer_id:
            logger.warning("네이버 검색광고 API 키가 설정되지 않음")
            return {}

        try:
            timestamp = str(int(datetime.now().timestamp() * 1000))
            method = "GET"
            uri = "/keywordstool"

            signature = self._generate_signature(timestamp, method, uri)

            headers = {
                "X-API-KEY": self.api_key,
                "X-Customer": self.customer_id,
                "X-Timestamp": timestamp,
                "X-Signature": signature,
            }

            response = await client.get(
                self.api_endpoint,
                headers=headers,
                params={
                    "hintKeywords": ",".join(keywords),
                    "showDetail": "1",
                },
            )

            if response.get("status") == 200:
                data = json.loads(response.get("text", "{}"))
                return self._parse_search_volume_response(data, keywords)
            else:
                logger.error(f"Naver Ads API 응답: status={response.get('status')}")
                return {}

        except Exception as e:
            logger.error(f"검색량 조회 오류: {e}")
            return {}

    def _generate_signature(self, timestamp: str, method: str, uri: str) -> str:
        """HMAC-SHA256 서명 생성"""
        message = f"{timestamp}.{method}.{uri}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return b64encode(signature).decode("utf-8")

    def _calculate_score(self, volume: int, competition: float, relevance: float) -> float:
        """
        키워드 점수 계산
        가중치: 검색량 25% + 경쟁도 20% + 관련성 30% + 신선도 15% + 검색의도 10%
        """
        max_volume = 100000
        volume_score = min(volume / max_volume, 1.0) * 100
        competition_score = (1 - min(competition, 1.0)) * 100
        relevance_score = relevance * 100
        freshness_score = 100
        intent_score = 80

        final = (
            volume_score * 0.25
            + competition_score * 0.20
            + relevance_score * 0.30
            + freshness_score * 0.15
            + intent_score * 0.10
        )
        return round(final, 2)

    def _calculate_relevance_score(self, keyword: str, related: list[str]) -> float:
        """관련성 점수 계산 (0.0 ~ 1.0)"""
        if not related:
            return 0.5
        return round(min(len(related) / 20, 1.0), 2)

    def _save_keyword_to_db(self, data: dict) -> None:
        """키워드 데이터를 SQLite에 저장"""
        try:
            related_json = json.dumps(data.get("related_keywords", []), ensure_ascii=False)
            self.db.insert(
                """INSERT OR REPLACE INTO keywords
                   (keyword, monthly_search_volume, competition_score,
                    relevance_score, total_score, related_keywords, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    data["keyword"],
                    data["monthly_search_volume"],
                    data["competition_score"],
                    data["relevance_score"],
                    data["total_score"],
                    related_json,
                ),
            )
        except Exception as e:
            logger.error(f"키워드 DB 저장 오류: {e}")

    def _parse_search_volume_response(self, api_response: dict, keywords: list[str]) -> dict:
        """Naver Ads API 응답 파싱"""
        parsed = {}
        keyword_list = api_response.get("keywordList", [])

        for item in keyword_list:
            kw = item.get("relKeyword", "")
            if kw in keywords:
                parsed[kw] = {
                    "monthlyPcQcCnt": item.get("monthlyPcQcCnt", 0) or 0,
                    "monthlyMobileQcCnt": item.get("monthlyMobileQcCnt", 0) or 0,
                    "compIdx": self._normalize_comp_idx(item.get("compIdx", "보통")),
                }

        return parsed

    def _normalize_comp_idx(self, comp_idx) -> float:
        """경쟁도 인덱스 정규화 (0.0~1.0)"""
        if isinstance(comp_idx, (int, float)):
            return min(comp_idx, 1.0)
        mapping = {"높음": 0.8, "보통": 0.5, "낮음": 0.2}
        return mapping.get(str(comp_idx), 0.5)
