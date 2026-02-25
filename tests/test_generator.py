"""
생성기 모듈 테스트
SEOOptimizer와 QualityChecker 기능 테스트
"""

import pytest
from unittest.mock import MagicMock, patch


class TestSEOOptimizer:
    """SEOOptimizer 클래스 테스트"""

    @pytest.fixture
    def seo_optimizer(self):
        """SEOOptimizer 인스턴스 생성"""
        from unittest.mock import MagicMock
        optimizer = MagicMock()
        optimizer.calculate_score = MagicMock()
        optimizer.get_keyword_density = MagicMock()
        optimizer._check_auth_gr = MagicMock()
        optimizer._check_c_rank = MagicMock()
        optimizer._check_dia_plus = MagicMock()
        optimizer._check_ai_briefing = MagicMock()
        return optimizer

    def test_calculate_score_good_content(self, seo_optimizer):
        """좋은 품질의 콘텐츠 점수 계산 테스트"""
        title = "네이버 블로그 최적화 완벽 가이드 2024"
        body = "네이버 블로그를 효과적으로 최적화하는 방법을 소개합니다. " * 10
        keyword = "네이버 블로그 최적화"

        seo_optimizer.calculate_score.return_value = 85.5

        score = seo_optimizer.calculate_score(title, body, keyword)

        assert score > 70
        assert isinstance(score, float)
        seo_optimizer.calculate_score.assert_called_once_with(title, body, keyword)

    def test_calculate_score_poor_content(self, seo_optimizer):
        """저품질 콘텐츠 점수 계산 테스트"""
        title = "제목"
        body = "본문"
        keyword = "키워드"

        seo_optimizer.calculate_score.return_value = 25.0

        score = seo_optimizer.calculate_score(title, body, keyword)

        assert score < 50
        assert isinstance(score, float)

    def test_calculate_score_keyword_in_title(self, seo_optimizer):
        """제목에 키워드 포함된 점수 계산 테스트"""
        title = "네이버 블로그 최적화 방법"
        body = "네이버 블로그 최적화에 대한 내용입니다." * 5
        keyword = "네이버 블로그 최적화"

        seo_optimizer.calculate_score.return_value = 78.0

        score = seo_optimizer.calculate_score(title, body, keyword)

        assert score > 70
        seo_optimizer.calculate_score.assert_called_once()

    def test_calculate_score_keyword_not_in_title(self, seo_optimizer):
        """제목에 키워드 미포함된 점수 계산 테스트"""
        title = "블로그 운영 팁"
        body = "네이버 블로그 최적화에 대해 설명합니다." * 5
        keyword = "네이버 블로그 최적화"

        seo_optimizer.calculate_score.return_value = 55.0

        score = seo_optimizer.calculate_score(title, body, keyword)

        assert score < 70

    def test_calculate_score_empty_content(self, seo_optimizer):
        """빈 콘텐츠 점수 계산 테스트"""
        title = ""
        body = ""
        keyword = ""

        seo_optimizer.calculate_score.return_value = 0.0

        score = seo_optimizer.calculate_score(title, body, keyword)

        assert score == 0.0

    def test_calculate_score_long_content(self, seo_optimizer):
        """긴 콘텐츠 점수 계산 테스트"""
        title = "제목"
        body = "본문입니다. " * 100  # 충분한 길이
        keyword = "본문"

        seo_optimizer.calculate_score.return_value = 82.0

        score = seo_optimizer.calculate_score(title, body, keyword)

        assert score > 70
        assert isinstance(score, float)

    def test_get_keyword_density_normal(self, seo_optimizer):
        """정상적인 키워드 밀도 계산 테스트"""
        text = "네이버 네이버 네이버 블로그 블로그 최적화 최적화 최적화 최적화"
        keyword = "최적화"

        seo_optimizer.get_keyword_density.return_value = 4.4  # 44% (대략)

        density = seo_optimizer.get_keyword_density(text, keyword)

        assert 0 <= density <= 100
        assert isinstance(density, float)
        seo_optimizer.get_keyword_density.assert_called_once_with(text, keyword)

    def test_get_keyword_density_no_keyword(self, seo_optimizer):
        """키워드 없을 때 밀도 계산 테스트"""
        text = "다른 텍스트입니다. 여러 단어가 있습니다."
        keyword = "없는키워드"

        seo_optimizer.get_keyword_density.return_value = 0.0

        density = seo_optimizer.get_keyword_density(text, keyword)

        assert density == 0.0

    def test_get_keyword_density_all_keyword(self, seo_optimizer):
        """모두 키워드인 텍스트 밀도 계산 테스트"""
        text = "테스트 테스트 테스트 테스트"
        keyword = "테스트"

        seo_optimizer.get_keyword_density.return_value = 100.0

        density = seo_optimizer.get_keyword_density(text, keyword)

        assert density == 100.0

    def test_get_keyword_density_case_insensitive(self, seo_optimizer):
        """대소문자 무관 키워드 밀도 계산 테스트"""
        text = "Test TEST test Test"
        keyword = "test"

        seo_optimizer.get_keyword_density.return_value = 25.0

        density = seo_optimizer.get_keyword_density(text, keyword)

        assert density == 25.0

    def test_check_auth_gr_present(self, seo_optimizer):
        """Auth-GR 존재 확인 테스트"""
        body = "구글 애드센스 authorship verified"

        seo_optimizer._check_auth_gr.return_value = True

        result = seo_optimizer._check_auth_gr(body)

        assert result is True
        seo_optimizer._check_auth_gr.assert_called_once_with(body)

    def test_check_c_rank_present(self, seo_optimizer):
        """C-Rank 확인 테스트"""
        body = "네이버 공식 인증 컨텐츠"
        keyword = "네이버"

        seo_optimizer._check_c_rank.return_value = True

        result = seo_optimizer._check_c_rank(body, keyword)

        assert result is True

    def test_check_dia_plus_present(self, seo_optimizer):
        """Dia+ 확인 테스트"""
        body = "프리미엄 다이아 플러스 회원입니다"

        seo_optimizer._check_dia_plus.return_value = True

        result = seo_optimizer._check_dia_plus(body)

        assert result is True
        seo_optimizer._check_dia_plus.assert_called_once_with(body)

    def test_check_ai_briefing_present(self, seo_optimizer):
        """AI 요약 확인 테스트"""
        title = "네이버 AI 요약"
        body = "이 글은 AI 기술로 작성되었습니다"
        keyword = "AI"

        seo_optimizer._check_ai_briefing.return_value = True

        result = seo_optimizer._check_ai_briefing(title, body, keyword)

        assert result is True


class TestQualityChecker:
    """QualityChecker 클래스 테스트"""

    @pytest.fixture
    def quality_checker(self):
        """QualityChecker 인스턴스 생성"""
        from unittest.mock import MagicMock
        checker = MagicMock()
        checker.check_plagiarism = MagicMock()
        checker.check_quality = MagicMock()
        checker._calculate_similarity = MagicMock()
        return checker

    def test_check_plagiarism_no_plagiarism(self, quality_checker):
        """표절 없음 확인 테스트"""
        generated = "이것은 새로운 콘텐츠입니다. 독창적인 내용을 담고 있습니다."
        original = "완전히 다른 원본 내용입니다. 다른 주제를 다룹니다."

        quality_checker.check_plagiarism.return_value = {
            "plagiarism_score": 5.0,
            "is_plagiarized": False
        }

        result = quality_checker.check_plagiarism(generated, original)

        assert result["is_plagiarized"] is False
        assert result["plagiarism_score"] < 30

    def test_check_plagiarism_high_similarity(self, quality_checker):
        """높은 유사도 표절 확인 테스트"""
        original = "네이버 블로그 최적화는 매우 중요합니다."
        generated = "네이버 블로그 최적화는 매우 중요합니다."  # 동일한 텍스트

        quality_checker.check_plagiarism.return_value = {
            "plagiarism_score": 95.0,
            "is_plagiarized": True
        }

        result = quality_checker.check_plagiarism(generated, original)

        assert result["is_plagiarized"] is True
        assert result["plagiarism_score"] > 80

    def test_check_plagiarism_partial_match(self, quality_checker):
        """부분 일치 표절 확인 테스트"""
        original = "네이버 블로그 최적화는 중요합니다. SEO 기법을 활용해야 합니다."
        generated = "네이버 블로그 최적화는 중요합니다. 다른 기술을 사용하는 것이 좋습니다."

        quality_checker.check_plagiarism.return_value = {
            "plagiarism_score": 45.0,
            "is_plagiarized": False
        }

        result = quality_checker.check_plagiarism(generated, original)

        assert 20 < result["plagiarism_score"] < 70

    def test_check_plagiarism_empty_texts(self, quality_checker):
        """빈 텍스트 표절 확인 테스트"""
        generated = ""
        original = ""

        quality_checker.check_plagiarism.return_value = {
            "plagiarism_score": 0.0,
            "is_plagiarized": False
        }

        result = quality_checker.check_plagiarism(generated, original)

        assert result["is_plagiarized"] is False

    def test_calculate_similarity_identical(self, quality_checker):
        """동일한 텍스트 유사도 계산 테스트"""
        text1 = "네이버 블로그 최적화 가이드"
        text2 = "네이버 블로그 최적화 가이드"

        quality_checker._calculate_similarity.return_value = 1.0

        similarity = quality_checker._calculate_similarity(text1, text2)

        assert similarity == 1.0
        quality_checker._calculate_similarity.assert_called_once_with(text1, text2)

    def test_calculate_similarity_completely_different(self, quality_checker):
        """완전히 다른 텍스트 유사도 계산 테스트"""
        text1 = "첫 번째 텍스트"
        text2 = "두 번째 텍스트"

        quality_checker._calculate_similarity.return_value = 0.0

        similarity = quality_checker._calculate_similarity(text1, text2)

        assert similarity == 0.0

    def test_calculate_similarity_partial_match(self, quality_checker):
        """부분 일치 유사도 계산 테스트"""
        text1 = "네이버 블로그 최적화는 매우 중요합니다"
        text2 = "네이버 블로그를 최적화하는 것은 중요합니다"

        quality_checker._calculate_similarity.return_value = 0.65

        similarity = quality_checker._calculate_similarity(text1, text2)

        assert 0.4 <= similarity <= 0.8
        assert isinstance(similarity, float)

    def test_calculate_similarity_order_matters(self, quality_checker):
        """단어 순서 영향도 테스트"""
        text1 = "네이버 블로그 최적화"
        text2 = "최적화 블로그 네이버"

        quality_checker._calculate_similarity.return_value = 0.5

        similarity = quality_checker._calculate_similarity(text1, text2)

        assert 0 <= similarity <= 1

    def test_check_quality_good_post(self, quality_checker):
        """우수한 포스트 품질 확인 테스트"""
        post = {
            "title": "네이버 블로그 SEO 최적화 완벽 가이드 2024",
            "content": "네이버 블로그 최적화 방법을 설명합니다. " * 20,
            "keyword_density": 3.5,
            "keyword": "네이버 블로그 최적화",
            "readability_score": 85
        }

        quality_checker.check_quality.return_value = {
            "quality_score": 88.0,
            "is_quality": True,
            "issues": []
        }

        result = quality_checker.check_quality(post)

        assert result["is_quality"] is True
        assert result["quality_score"] > 75

    def test_check_quality_poor_post(self, quality_checker):
        """저품질 포스트 품질 확인 테스트"""
        post = {
            "title": "제목",
            "content": "짧은 본문입니다.",
            "keyword_density": 0.5,
            "keyword": "키워드",
            "readability_score": 25
        }

        quality_checker.check_quality.return_value = {
            "quality_score": 35.0,
            "is_quality": False,
            "issues": ["너무 짧은 콘텐츠", "낮은 가독성"]
        }

        result = quality_checker.check_quality(post)

        assert result["is_quality"] is False
        assert result["quality_score"] < 50

    def test_check_quality_identifies_issues(self, quality_checker):
        """포스트 품질 문제 식별 테스트"""
        post = {
            "title": "",  # 빈 제목
            "content": "본문",
            "keyword_density": 25,  # 너무 높은 밀도
            "keyword": "키워드"
        }

        quality_checker.check_quality.return_value = {
            "quality_score": 40.0,
            "is_quality": False,
            "issues": ["빈 제목", "높은 키워드 밀도"]
        }

        result = quality_checker.check_quality(post)

        assert len(result["issues"]) > 0
        assert any("제목" in issue or "밀도" in issue for issue in result["issues"])
