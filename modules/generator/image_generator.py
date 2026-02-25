"""
Gemini API를 활용한 이미지 자동 생성
무료 Gemini 2.5 Flash Image 모델 사용
"""

import asyncio
from pathlib import Path
from typing import Optional
from google import genai
from google.genai import types
from utils.logger import get_logger
from config.settings import settings


logger = get_logger()


class ImageGenerator:
    """
    Gemini 2.5 Flash Image 모델을 활용한 무료 이미지 생성

    생성 이미지:
    - 썸네일 (16:9)
    - 본문 이미지 (16:9)
    """

    def __init__(self):
        """이미지 생성기 초기화"""
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다")

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_IMAGE_MODEL
        self.save_dir = settings.DATA_DIR / "images"
        self.save_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"이미지 생성기 초기화 완료: model={self.model}")

    async def generate_thumbnail(self, keyword: str, title: str) -> Optional[Path]:
        """
        블로그 썸네일 이미지 생성

        Args:
            keyword: 타겟 키워드
            title: 블로그 제목

        Returns:
            생성된 이미지 파일 경로 (실패 시 None)
        """
        logger.info(f"썸네일 생성 시작: keyword={keyword}")

        # 이미지 생성 프롬프트
        prompt = self._create_thumbnail_prompt(keyword, title)

        try:
            image_path = await self._generate_image(
                prompt=prompt,
                aspect_ratio="16:9",
                filename_prefix=f"thumbnail_{keyword}"
            )
            logger.info(f"썸네일 생성 완료: {image_path}")
            return image_path
        except Exception as e:
            logger.error(f"썸네일 생성 실패: {e}")
            return None

    async def generate_body_image(self, keyword: str, context: str = "") -> Optional[Path]:
        """
        본문 삽입용 이미지 생성

        Args:
            keyword: 타겟 키워드
            context: 본문 맥락 (선택)

        Returns:
            생성된 이미지 파일 경로 (실패 시 None)
        """
        logger.info(f"본문 이미지 생성 시작: keyword={keyword}")

        # 이미지 생성 프롬프트
        prompt = self._create_body_image_prompt(keyword, context)

        try:
            image_path = await self._generate_image(
                prompt=prompt,
                aspect_ratio="16:9",
                filename_prefix=f"body_{keyword}"
            )
            logger.info(f"본문 이미지 생성 완료: {image_path}")
            return image_path
        except Exception as e:
            logger.error(f"본문 이미지 생성 실패: {e}")
            return None

    async def _generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        filename_prefix: str = "image"
    ) -> Path:
        """
        Gemini API로 이미지 생성 (내부 메서드)

        Args:
            prompt: 이미지 생성 프롬프트
            aspect_ratio: 종횡비 ("16:9", "9:16", "1:1" 등)
            filename_prefix: 파일명 접두사

        Returns:
            생성된 이미지 파일 경로
        """
        logger.debug(f"Gemini API 호출: prompt={prompt[:100]}...")

        # 비동기 → 동기 변환 (Gemini API는 동기 방식)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                    ),
                ),
            )
        )

        # 이미지 추출 및 저장
        for part in response.parts:
            if part.inline_data:
                image = part.as_image()

                # 파일명 생성 (타임스탬프 포함)
                import time
                timestamp = int(time.time())
                filename = f"{filename_prefix}_{timestamp}.png"
                filepath = self.save_dir / filename

                # 저장
                image.save(str(filepath))
                logger.info(f"이미지 저장 완료: {filepath}")
                return filepath

        raise ValueError("이미지 생성 실패: 응답에 이미지가 없음")

    def _create_thumbnail_prompt(self, keyword: str, title: str) -> str:
        """썸네일 이미지 생성 프롬프트"""
        return f"""Create a professional, clean illustration for a blog post about '{keyword}'.

Context: This is for a Korean government/school administration blog post titled "{title}".

Style requirements:
- Modern, clean, minimal design
- Professional and trustworthy atmosphere
- Soft colors (blue, green, gray tones)
- No text or Korean characters in the image
- Suitable for a thumbnail (clear and recognizable even when small)

Subject: Office worker or administrator reviewing documents or working at a desk, symbolizing '{keyword}' work.

Make it look professional yet approachable, suitable for Korean government employees."""

    def _create_body_image_prompt(self, keyword: str, context: str = "") -> str:
        """본문 이미지 생성 프롬프트"""
        context_hint = f"\n\nContext: {context[:200]}" if context else ""

        return f"""Create a professional infographic-style illustration related to '{keyword}'.

This image will be inserted in the middle of a blog post about Korean school/government administration.{context_hint}

Style requirements:
- Clean, modern, infographic style
- Professional color scheme (blue, green, neutral tones)
- Simple and easy to understand
- No text or Korean characters
- Suitable for blog content (informative and visually appealing)

Subject: Visual representation of '{keyword}' concept, such as process flow, checklist, or conceptual diagram.

Make it informative yet visually attractive."""

    def cleanup_old_images(self, days: int = 30):
        """오래된 이미지 파일 정리

        Args:
            days: 보관 기간 (일)
        """
        import time
        cutoff_time = time.time() - (days * 24 * 60 * 60)

        deleted_count = 0
        for img_file in self.save_dir.glob("*.png"):
            if img_file.stat().st_mtime < cutoff_time:
                img_file.unlink()
                deleted_count += 1

        logger.info(f"오래된 이미지 {deleted_count}개 삭제 (>{days}일)")
