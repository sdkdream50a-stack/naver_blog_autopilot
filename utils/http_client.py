"""
비동기 HTTP 클라이언트 (aiohttp 기반)
동시 요청 제한, 재시도, 타임아웃 지원
"""

import asyncio
import aiohttp
from utils.logger import get_logger

logger = get_logger()


class AsyncHTTPClient:
    """비동기 HTTP 클라이언트"""

    def __init__(
        self,
        max_concurrent: int = 10,
        timeout: int = 30,
        user_agent: str = "",
        retries: int = 3,
    ):
        self.max_concurrent = max_concurrent
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.user_agent = user_agent
        self.retries = retries
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        headers = {}
        if self.user_agent:
            headers["User-Agent"] = self.user_agent
        self._session = aiohttp.ClientSession(
            timeout=self.timeout,
            headers=headers,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def get(self, url: str, **kwargs) -> dict:
        """GET 요청 (재시도 포함)"""
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> dict:
        """POST 요청 (재시도 포함)"""
        return await self._request("POST", url, **kwargs)

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        """HTTP 요청 실행 (세마포어 + 재시도)"""
        async with self._semaphore:
            last_error = None
            for attempt in range(1, self.retries + 1):
                try:
                    async with self._session.request(method, url, **kwargs) as resp:
                        text = await resp.text()
                        return {
                            "status": resp.status,
                            "text": text,
                            "url": str(resp.url),
                            "headers": dict(resp.headers),
                        }
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    last_error = e
                    logger.warning(f"요청 실패 (시도 {attempt}/{self.retries}): {url} - {e}")
                    if attempt < self.retries:
                        await asyncio.sleep(2 ** attempt)

            logger.error(f"요청 최종 실패: {url} - {last_error}")
            return {"status": 0, "text": "", "url": url, "error": str(last_error)}

    async def get_many(self, urls: list[str], delay: float = 0) -> list[dict]:
        """여러 URL 동시 요청"""
        tasks = []
        for i, url in enumerate(urls):
            if delay and i > 0:
                await asyncio.sleep(delay)
            tasks.append(self.get(url))
        return await asyncio.gather(*tasks, return_exceptions=True)
