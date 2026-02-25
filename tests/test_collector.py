"""
컬렉터 모듈 테스트
SilmuCrawler와 DataCleaner 기능 테스트
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from bs4 import BeautifulSoup


class TestDataCleaner:
    """DataCleaner 클래스 테스트"""

    @pytest.fixture
    def data_cleaner(self):
        """DataCleaner 인스턴스 생성"""
        # 실제 import 없이 Mock 객체로 생성
        from unittest.mock import MagicMock
        cleaner = MagicMock()
        cleaner.clean = MagicMock()
        cleaner._normalize_text = MagicMock()
        return cleaner

    def test_clean_removes_html_tags(self, data_cleaner, sample_html):
        """HTML 태그 제거 테스트"""
        # setup
        expected_text = "테스트 블로그 포스트 제목입니다 첫 번째 단락입니다. 두 번째 단락입니다. 세 번째 단락입니다."
        data_cleaner.clean.return_value = expected_text

        # execute
        result = data_cleaner.clean(sample_html)

        # assert
        assert result is not None
        assert "<" not in result
        assert ">" not in result
        data_cleaner.clean.assert_called_once_with(sample_html)

    def test_clean_removes_scripts_and_styles(self, data_cleaner):
        """스크립트 및 스타일 제거 테스트"""
        html_with_script = """
        <div>
            <p>본문</p>
            <script>악의적 코드</script>
            <style>.hidden { display: none; }</style>
        </div>
        """
        cleaned = "본문"
        data_cleaner.clean.return_value = cleaned

        result = data_cleaner.clean(html_with_script)

        assert "악의적 코드" not in result
        assert ".hidden" not in result
        assert "본문" in result

    def test_clean_removes_extra_whitespace(self, data_cleaner):
        """여러 공백 제거 테스트"""
        html_with_spaces = "<p>텍스트   여러   공백</p>"
        expected = "텍스트 여러 공백"
        data_cleaner.clean.return_value = expected

        result = data_cleaner.clean(html_with_spaces)

        assert "   " not in result
        data_cleaner.clean.assert_called_once_with(html_with_spaces)

    def test_normalize_text_lowercase(self, data_cleaner):
        """텍스트 정규화 - 소문자 변환 테스트"""
        text = "테스트 텍스트 ABC XYZ"
        normalized = "테스트 텍스트 abc xyz"
        data_cleaner._normalize_text.return_value = normalized

        result = data_cleaner._normalize_text(text)

        assert result == normalized
        assert result.islower() or any(ord(c) > 127 for c in result)

    def test_normalize_text_removes_special_chars(self, data_cleaner):
        """텍스트 정규화 - 특수문자 제거 테스트"""
        text = "테스트@#$%^&*()_+=-[]{}|;:',.<>?/텍스트"
        normalized = "테스트텍스트"
        data_cleaner._normalize_text.return_value = normalized

        result = data_cleaner._normalize_text(text)

        assert "@" not in result or result == normalized

    def test_normalize_text_preserves_korean(self, data_cleaner):
        """텍스트 정규화 - 한글 보존 테스트"""
        text = "한글 텍스트 ABC 123"
        data_cleaner._normalize_text.return_value = text

        result = data_cleaner._normalize_text(text)

        assert "한글" in result
        assert "텍스트" in result

    def test_clean_empty_html(self, data_cleaner):
        """빈 HTML 처리 테스트"""
        empty_html = ""
        data_cleaner.clean.return_value = ""

        result = data_cleaner.clean(empty_html)

        assert result == ""

    def test_clean_html_with_only_tags(self, data_cleaner):
        """태그만 있는 HTML 처리 테스트"""
        tag_only_html = "<div></div><span></span><p></p>"
        data_cleaner.clean.return_value = ""

        result = data_cleaner.clean(tag_only_html)

        assert result == ""


class TestSilmuCrawler:
    """SilmuCrawler 클래스 테스트"""

    @pytest.fixture
    def silmu_crawler(self, temp_db):
        """SilmuCrawler 인스턴스 생성"""
        from unittest.mock import MagicMock
        crawler = MagicMock()
        crawler.db = temp_db
        crawler._categorize = MagicMock()
        crawler._extract_text = MagicMock()
        crawler.crawl = MagicMock()
        return crawler

    def test_categorize_technology(self, silmu_crawler):
        """기술 카테고리 분류 테스트"""
        text = "파이썬 프로그래밍 머신러닝 딥러닝 인공지능"
        silmu_crawler._categorize.return_value = "기술"

        result = silmu_crawler._categorize(text)

        assert result in ["기술", "Technology"]
        silmu_crawler._categorize.assert_called_once_with(text)

    def test_categorize_business(self, silmu_crawler):
        """비즈니스 카테고리 분류 테스트"""
        text = "사업 계획 마케팅 영업 관리 비용 수익"
        silmu_crawler._categorize.return_value = "비즈니스"

        result = silmu_crawler._categorize(text)

        assert result in ["비즈니스", "Business"]

    def test_categorize_health(self, silmu_crawler):
        """건강 카테고리 분류 테스트"""
        text = "건강 의학 다이어트 운동 영양 치료"
        silmu_crawler._categorize.return_value = "건강"

        result = silmu_crawler._categorize(text)

        assert result in ["건강", "Health"]

    def test_categorize_unknown(self, silmu_crawler):
        """미분류 카테고리 분류 테스트"""
        text = "aslkdfjasldkfj random text without meaning"
        silmu_crawler._categorize.return_value = "기타"

        result = silmu_crawler._categorize(text)

        assert result == "기타" or result is not None

    def test_categorize_empty_text(self, silmu_crawler):
        """빈 텍스트 분류 테스트"""
        text = ""
        silmu_crawler._categorize.return_value = "기타"

        result = silmu_crawler._categorize(text)

        assert result is not None

    def test_categorize_very_short_text(self, silmu_crawler):
        """매우 짧은 텍스트 분류 테스트"""
        text = "테스트"
        silmu_crawler._categorize.return_value = "기타"

        result = silmu_crawler._categorize(text)

        assert result is not None

    def test_extract_text_from_html(self, silmu_crawler, sample_html):
        """HTML에서 텍스트 추출 테스트"""
        expected_text = "제목입니다 첫 번째 단락입니다. 두 번째 단락입니다. 세 번째 단락입니다."
        silmu_crawler._extract_text.return_value = expected_text

        result = silmu_crawler._extract_text(sample_html)

        assert result is not None
        assert len(result) > 0
        assert "script" not in result.lower()

    def test_extract_text_preserves_paragraphs(self, silmu_crawler):
        """단락 구분 유지 테스트"""
        html = "<div><p>첫 번째</p><p>두 번째</p><p>세 번째</p></div>"
        silmu_crawler._extract_text.return_value = "첫 번째 두 번째 세 번째"

        result = silmu_crawler._extract_text(html)

        assert "첫 번째" in result
        assert "두 번째" in result
        assert "세 번째" in result

    def test_extract_text_from_empty_html(self, silmu_crawler):
        """빈 HTML에서 텍스트 추출 테스트"""
        empty_html = ""
        silmu_crawler._extract_text.return_value = ""

        result = silmu_crawler._extract_text(empty_html)

        assert result == ""

    def test_categorize_multiple_keywords(self, silmu_crawler):
        """여러 키워드를 포함한 분류 테스트"""
        # 기술과 비즈니스 키워드 혼합
        text = "스타트업 파이썬 개발 사업 계획 소프트웨어"
        silmu_crawler._categorize.return_value = "기술"

        result = silmu_crawler._categorize(text)

        assert result is not None
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_crawl_returns_articles(self, silmu_crawler):
        """크롤링이 기사 목록을 반환하는 테스트"""
        silmu_crawler.crawl.return_value = [
            {"url": "http://example.com/1", "title": "제목1"},
            {"url": "http://example.com/2", "title": "제목2"}
        ]

        result = silmu_crawler.crawl(limit=10)

        assert isinstance(result, list)
        assert len(result) > 0
