"""
네이버 블로그 OAuth API 클라이언트 (백업, 거의 사용 안 함)
Naver Blog OAuth API Client (Backup, rarely used)
"""

import aiohttp
import json
from typing import Dict, Optional
from utils.logger import get_logger
from config.settings import settings

logger = get_logger()


class NaverAPIClient:
    """
    네이버 블로그 OAuth API를 통한 포스트 발행 (백업 메서드)
    Publishes posts via Naver Blog OAuth API (backup method)
    """

    def __init__(self):
        """초기화 / Initialize API client"""
        self.client_id = getattr(settings, 'NAVER_CLIENT_ID', None)
        self.client_secret = getattr(settings, 'NAVER_CLIENT_SECRET', None)
        self.access_token = getattr(settings, 'NAVER_ACCESS_TOKEN', None)
        self.blog_id = settings.NAVER_BLOG_ID
        self.api_base_url = "https://openapi.naver.com/blog"
        self.session: Optional[aiohttp.ClientSession] = None

    async def publish_via_api(self, title: str, body: str) -> Dict:
        """
        네이버 블로그 API를 통해 포스트를 발행합니다
        Publish post via Naver Blog API

        Args:
            title (str): 포스트 제목 (post title)
            body (str): 포스트 본문 (post body)

        Returns:
            Dict: {success: bool, post_id: str, error: str or None}
        """
        try:
            if not self.access_token:
                logger.error("액세스 토큰이 없습니다 / Access token not available")
                return {
                    'success': False,
                    'post_id': None,
                    'error': '액세스 토큰이 없습니다 / Access token not available'
                }

            logger.info(f"API를 통한 포스트 발행 시작: {title} / Publishing via API: {title}")

            # 세션 생성
            if self.session is None:
                self.session = aiohttp.ClientSession()

            # 포스트 발행 API 호출
            url = f"{self.api_base_url}/v2/posts"
            headers = self._get_auth_headers()

            payload = {
                "title": title,
                "content": body,
                "visibility": 3  # 공개 / public
            }

            async with self.session.post(url, json=payload, headers=headers) as response:
                if response.status == 201:
                    data = await response.json()
                    post_id = data.get('id')
                    blog_url = f"https://blog.naver.com/{self.blog_id}/{post_id}"

                    logger.info(f"API 발행 성공: {blog_url} / API publish successful: {blog_url}")

                    return {
                        'success': True,
                        'post_id': post_id,
                        'blog_url': blog_url,
                        'error': None
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"API 발행 실패: {response.status} - {error_text} / API publish failed: {response.status} - {error_text}")

                    return {
                        'success': False,
                        'post_id': None,
                        'error': f"API Error: {response.status} - {error_text}"
                    }

        except Exception as e:
            logger.error(f"API 발행 오류: {e} / API publish error: {e}")

            return {
                'success': False,
                'post_id': None,
                'error': str(e)
            }

    def _get_auth_headers(self) -> Dict[str, str]:
        """
        인증 헤더를 생성합니다
        Generate authentication headers

        Returns:
            Dict[str, str]: 인증 헤더 (auth headers)
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }

            logger.debug("인증 헤더 생성 완료 / Auth headers generated")
            return headers

        except Exception as e:
            logger.error(f"인증 헤더 생성 오류: {e} / Auth header generation error: {e}")
            return {}

    async def refresh_access_token(self) -> bool:
        """
        액세스 토큰을 갱신합니다 (OAuth2 리프레시 토큰 사용)
        Refresh access token using OAuth2 refresh token

        Returns:
            bool: 갱신 성공 여부 (refresh success)
        """
        try:
            refresh_token = getattr(settings, 'NAVER_REFRESH_TOKEN', None)

            if not refresh_token:
                logger.warning("리프레시 토큰이 없습니다 / Refresh token not available")
                return False

            logger.info("액세스 토큰 갱신 중 / Refreshing access token")

            # 세션 생성
            if self.session is None:
                self.session = aiohttp.ClientSession()

            # 토큰 갱신 API 호출
            url = "https://nid.naver.com/oauth2.0/token"

            params = {
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': refresh_token
            }

            async with self.session.post(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data.get('access_token')

                    logger.info("액세스 토큰 갱신 성공 / Access token refreshed successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"토큰 갱신 실패: {response.status} - {error_text} / Token refresh failed: {response.status} - {error_text}")
                    return False

        except Exception as e:
            logger.error(f"토큰 갱신 오류: {e} / Token refresh error: {e}")
            return False

    async def close(self):
        """
        세션을 종료합니다
        Close the session
        """
        try:
            if self.session:
                await self.session.close()
                self.session = None
                logger.info("API 세션 종료 / API session closed")

        except Exception as e:
            logger.error(f"세션 종료 오류: {e} / Session close error: {e}")
