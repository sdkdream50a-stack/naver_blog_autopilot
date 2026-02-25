"""
Data Cleaner Module

크롤링된 HTML 기사를 정제하고 처리하는 모듈입니다.
HTML 태그를 제거하고, 텍스트를 정규화하며,
요약을 생성하고 단어 수를 계산합니다.
"""

import re
from typing import Dict

import trafilatura

from utils.logger import get_logger


logger = get_logger()


class DataCleaner:
    """
    크롤링된 HTML 기사를 정제하고 처리하는 클래스입니다.

    원본 HTML에서 본문 텍스트를 추출하고, 정규화된 텍스트를 생성하며,
    요약과 단어 수를 계산합니다.

    Attributes:
        SUMMARY_LENGTH (int): 요약의 최대 길이 (문자 단위)
    """

    SUMMARY_LENGTH = 200

    def __init__(self):
        """DataCleaner를 초기화합니다."""
        self.logger = logger

    def clean(self, html: str) -> Dict[str, any]:
        """
        HTML 문서를 정제하고 처리합니다.

        Trafilatura를 사용하여 본문을 추출한 후,
        텍스트를 정규화하여 깨끗한 결과물을 생성합니다.

        Args:
            html (str): 정제할 HTML 문자열

        Returns:
            dict: 정제된 기사 데이터
                {
                    "clean_text": str,  # 정제된 본문 텍스트
                    "summary": str,     # 첫 200자의 요약
                    "word_count": int   # 단어 개수
                }

        Example:
            >>> cleaner = DataCleaner()
            >>> result = cleaner.clean("<html><body><p>샘플 텍스트입니다.</p></body></html>")
            >>> print(result['word_count'])
            4
        """
        try:
            # Step 1: Trafilatura를 사용하여 본문 텍스트 추출
            extracted_text = trafilatura.extract(html)

            if not extracted_text:
                self.logger.warning("HTML에서 텍스트 추출 실패")
                return {
                    "clean_text": "",
                    "summary": "",
                    "word_count": 0,
                }

            # Step 2: 텍스트 정규화
            clean_text = self._normalize_text(extracted_text)

            # Step 3: 요약 생성 (첫 200자)
            summary = clean_text[: self.SUMMARY_LENGTH]
            if len(clean_text) > self.SUMMARY_LENGTH:
                summary = summary.rsplit(" ", 1)[0] + "..."

            # Step 4: 단어 개수 계산
            word_count = len(clean_text.split())

            self.logger.debug(
                f"데이터 정제 완료: {word_count}개 단어, "
                f"{len(clean_text)}자 길이"
            )

            return {
                "clean_text": clean_text,
                "summary": summary,
                "word_count": word_count,
            }

        except Exception as e:
            self.logger.error(f"데이터 정제 중 오류 발생: {str(e)}")
            return {
                "clean_text": "",
                "summary": "",
                "word_count": 0,
            }

    def _normalize_text(self, text: str) -> str:
        """
        추출된 텍스트를 정규화합니다.

        다음 작업을 수행합니다:
        - 연속된 공백을 하나의 공백으로 통합
        - 줄바꿈 문자를 공백으로 변환
        - 불필요한 특수 문자 제거
        - 문자열의 양쪽 공백 제거

        Args:
            text (str): 정규화할 텍스트

        Returns:
            str: 정규화된 텍스트

        Example:
            >>> cleaner = DataCleaner()
            >>> text = "텍스트  \\n  예시\\r\\n  샘플"
            >>> result = cleaner._normalize_text(text)
            >>> print(result)
            텍스트 예시 샘플
        """
        if not text:
            return ""

        # 연속된 공백 제거 (줄바꿈, 탭 등 포함)
        text = re.sub(r"\s+", " ", text)

        # 양쪽 공백 제거
        text = text.strip()

        # 불필요한 특수 문자 제거 (필요시 조정)
        # 한글, 영문, 숫자, 기본 구두점만 유지
        text = re.sub(r"[^\w\s.,!?\-()혣-힣]", "", text)

        # 다시 한 번 공백 정규화
        text = re.sub(r"\s+", " ", text).strip()

        return text


def process_article_html(html: str) -> Dict[str, any]:
    """
    주어진 HTML을 정제하는 유틸리티 함수입니다.

    DataCleaner를 직접 사용하지 않고,
    이 함수를 통해 간단하게 HTML을 정제할 수 있습니다.

    Args:
        html (str): 정제할 HTML 문자열

    Returns:
        dict: 정제된 기사 데이터

    Example:
        >>> result = process_article_html("<html><body><p>테스트</p></body></html>")
        >>> print(result['word_count'])
    """
    cleaner = DataCleaner()
    return cleaner.clean(html)


if __name__ == "__main__":
    # 테스트용 메인 함수
    sample_html = """
    <html>
        <head>
            <title>샘플 기사</title>
        </head>
        <body>
            <h1>제목</h1>
            <p>이것은   샘플   기사입니다.
            여러  줄로   나뉘어  있습니다.</p>
            <p>두 번째 문단입니다.</p>
        </body>
    </html>
    """

    cleaner = DataCleaner()
    result = cleaner.clean(sample_html)

    print("=== 데이터 정제 결과 ===")
    print(f"정제된 텍스트: {result['clean_text']}")
    print(f"요약: {result['summary']}")
    print(f"단어 수: {result['word_count']}")
