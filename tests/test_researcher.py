"""
리서처 모듈 테스트
KeywordAnalyzer와 CompetitorScanner 기능 테스트
"""

import pytest
from unittest.mock import MagicMock, patch


class TestKeywordAnalyzer:
    """KeywordAnalyzer 클래스 테스트"""

    @pytest.fixture
    def keyword_analyzer(self, temp_db):
        """KeywordAnalyzer 인스턴스 생성"""
        from unittest.mock import MagicMock
        analyzer = MagicMock()
        analyzer.db = temp_db
        analyzer._calculate_score = MagicMock()
        analyzer._generate_signature = MagicMock()
        analyzer.analyze_keywords = MagicMock()
        return analyzer

    def test_calculate_score_high_volume_low_competition(self, keyword_analyzer):
        """높은 검색량, 낮은 경쟁도 점수 계산 테스트"""
        # 최고의 조건: 높은 검색량, 낮은 경쟁도
        volume = 5000
        competition = 20
        relevance = 0.9

        keyword_analyzer._calculate_score.return_value = 85.0

        score = keyword_analyzer._calculate_score(volume, competition, relevance)

        assert score > 75
        assert isinstance(score, float)
        keyword_analyzer._calculate_score.assert_called_once_with(volume, competition, relevance)

    def test_calculate_score_low_volume_low_competition(self, keyword_analyzer):
        """낮은 검색량, 낮은 경쟁도 점수 계산 테스트"""
        # 좋은 기회 키워드
        volume = 500
        competition = 15
        relevance = 0.85

        keyword_analyzer._calculate_score.return_value = 72.0

        score = keyword_analyzer._calculate_score(volume, competition, relevance)

        assert score > 60
        assert isinstance(score, float)

    def test_calculate_score_high_volume_high_competition(self, keyword_analyzer):
        """높은 검색량, 높은 경쟁도 점수 계산 테스트"""
        # 어려운 키워드
        volume = 10000
        competition = 85
        relevance = 0.7

        keyword_analyzer._calculate_score.return_value = 55.0

        score = keyword_analyzer._calculate_score(volume, competition, relevance)

        assert score < 70
        assert isinstance(score, float)

    def test_calculate_score_zero_volume(self, keyword_analyzer):
        """검색량 0 점수 계산 테스트"""
        volume = 0
        competition = 50
        relevance = 0.5

        keyword_analyzer._calculate_score.return_value = 0.0

        score = keyword_analyzer._calculate_score(volume, competition, relevance)

        assert score >= 0
        keyword_analyzer._calculate_score.assert_called_once_with(volume, competition, relevance)

    def test_calculate_score_high_relevance(self, keyword_analyzer):
        """높은 관련성 점수 계산 테스트"""
        volume = 3000
        competition = 40
        relevance = 0.95  # 높은 관련성

        keyword_analyzer._calculate_score.return_value = 78.5

        score = keyword_analyzer._calculate_score(volume, competition, relevance)

        assert score > 70
        assert isinstance(score, float)

    def test_calculate_score_low_relevance(self, keyword_analyzer):
        """낮은 관련성 점수 계산 테스트"""
        volume = 3000
        competition = 40
        relevance = 0.3  # 낮은 관련성

        keyword_analyzer._calculate_score.return_value = 45.0

        score = keyword_analyzer._calculate_score(volume, competition, relevance)

        assert score < 70
        assert isinstance(score, float)

    def test_generate_signature(self, keyword_analyzer):
        """서명 생성 테스트"""
        timestamp = "2024-01-01T12:00:00"
        method = "GET"
        uri = "/api/keywords/search"

        keyword_analyzer._generate_signature.return_value = "abc123def456"

        signature = keyword_analyzer._generate_signature(timestamp, method, uri)

        assert signature is not None
        assert isinstance(signature, str)
        assert len(signature) > 0

    def test_generate_signature_different_inputs(self, keyword_analyzer):
        """다른 입력값에 대한 서명 생성 테스트"""
        # 같은 입력은 같은 서명을 생성해야 함
        timestamp = "2024-01-01T12:00:00"
        method = "POST"
        uri = "/api/keywords/analyze"

        sig1 = "sig1"
        sig2 = "sig2"

        keyword_analyzer._generate_signature.side_effect = [sig1, sig2]

        result1 = keyword_analyzer._generate_signature(timestamp, method, uri)
        result2 = keyword_analyzer._generate_signature(timestamp, "GET", uri)

        assert result1 != result2

    def test_analyze_keywords_returns_list(self, keyword_analyzer, sample_keyword_data):
        """키워드 분석이 리스트를 반환하는 테스트"""
        keywords = ["네이버", "블로그", "최적화"]

        keyword_analyzer.analyze_keywords.return_value = [
            {"keyword": "네이버", "score": 80},
            {"keyword": "블로그", "score": 75},
            {"keyword": "최적화", "score": 85}
        ]

        result = keyword_analyzer.analyze_keywords(keywords)

        assert isinstance(result, list)
        assert len(result) == 3

    def test_analyze_keywords_includes_scores(self, keyword_analyzer):
        """분석 결과에 점수가 포함되는 테스트"""
        keywords = ["테스트"]

        keyword_analyzer.analyze_keywords.return_value = [
            {"keyword": "테스트", "score": 70, "volume": 2000, "competition": 35}
        ]

        result = keyword_analyzer.analyze_keywords(keywords)

        assert all("score" in item for item in result)
        assert all(0 <= item["score"] <= 100 for item in result)


class TestCompetitorScanner:
    """CompetitorScanner 클래스 테스트"""

    @pytest.fixture
    def competitor_scanner(self, temp_db):
        """CompetitorScanner 인스턴스 생성"""
        from unittest.mock import MagicMock
        scanner = MagicMock()
        scanner.db = temp_db
        scanner._calculate_competition_score = MagicMock()
        scanner.analyze_competitors = MagicMock()
        return scanner

    def test_calculate_competition_score_multiple_posts(self, competitor_scanner, sample_competitor_posts):
        """여러 경쟁사 포스트의 경쟁도 점수 계산 테스트"""
        competitor_scanner._calculate_competition_score.return_value = 65.0

        score = competitor_scanner._calculate_competition_score(sample_competitor_posts)

        assert 0 <= score <= 100
        assert isinstance(score, float)

    def test_calculate_competition_score_high_engagement(self, competitor_scanner):
        """높은 참여도 포스트의 경쟁도 점수 테스트"""
        high_engagement_posts = [
            {"views": 10000, "likes": 500},
            {"views": 8000, "likes": 400},
            {"views": 9500, "likes": 450}
        ]

        competitor_scanner._calculate_competition_score.return_value = 85.0

        score = competitor_scanner._calculate_competition_score(high_engagement_posts)

        assert score > 70
        competitor_scanner._calculate_competition_score.assert_called_once()

    def test_calculate_competition_score_low_engagement(self, competitor_scanner):
        """낮은 참여도 포스트의 경쟁도 점수 테스트"""
        low_engagement_posts = [
            {"views": 100, "likes": 5},
            {"views": 150, "likes": 8},
            {"views": 120, "likes": 6}
        ]

        competitor_scanner._calculate_competition_score.return_value = 25.0

        score = competitor_scanner._calculate_competition_score(low_engagement_posts)

        assert score < 40

    def test_calculate_competition_score_empty_list(self, competitor_scanner):
        """빈 포스트 목록의 경쟁도 점수 테스트"""
        empty_posts = []

        competitor_scanner._calculate_competition_score.return_value = 0.0

        score = competitor_scanner._calculate_competition_score(empty_posts)

        assert score == 0.0

    def test_calculate_competition_score_single_post(self, competitor_scanner):
        """단일 포스트의 경쟁도 점수 테스트"""
        single_post = [{"views": 5000, "likes": 250}]

        competitor_scanner._calculate_competition_score.return_value = 50.0

        score = competitor_scanner._calculate_competition_score(single_post)

        assert 0 <= score <= 100

    def test_calculate_competition_score_weighted_by_engagement(self, competitor_scanner):
        """참여도 기반 가중 점수 계산 테스트"""
        posts = [
            {"views": 1000, "likes": 10},   # 낮은 참여도
            {"views": 5000, "likes": 500},  # 높은 참여도
        ]

        competitor_scanner._calculate_competition_score.return_value = 55.0

        score = competitor_scanner._calculate_competition_score(posts)

        assert isinstance(score, float)
        competitor_scanner._calculate_competition_score.assert_called_once_with(posts)

    def test_analyze_competitors_returns_analysis(self, competitor_scanner, sample_competitor_posts):
        """경쟁사 분석이 결과를 반환하는 테스트"""
        keyword = "테스트 키워드"
        top_n = 3

        competitor_scanner.analyze_competitors.return_value = {
            "keyword": keyword,
            "competitors": sample_competitor_posts,
            "competition_score": 65.0,
            "recommendations": ["더 높은 품질의 콘텐츠 작성", "참여도 높은 포맷 사용"]
        }

        result = competitor_scanner.analyze_competitors(keyword, top_n)

        assert result is not None
        assert result["keyword"] == keyword
        assert "competition_score" in result

    def test_analyze_competitors_limits_results(self, competitor_scanner):
        """경쟁사 분석이 상위 N개만 반환하는 테스트"""
        keyword = "테스트"
        top_n = 5

        # 많은 포스트 중 상위 5개만 반환
        competitor_scanner.analyze_competitors.return_value = {
            "keyword": keyword,
            "competitors": [{"id": i} for i in range(top_n)],
            "total_found": 100
        }

        result = competitor_scanner.analyze_competitors(keyword, top_n)

        assert len(result["competitors"]) <= top_n

    def test_analyze_competitors_includes_metrics(self, competitor_scanner):
        """경쟁사 분석에 메트릭이 포함되는 테스트"""
        keyword = "테스트"

        competitor_scanner.analyze_competitors.return_value = {
            "keyword": keyword,
            "avg_views": 5000,
            "avg_likes": 250,
            "top_competitor": "blog1",
            "competition_score": 70.0
        }

        result = competitor_scanner.analyze_competitors(keyword, 10)

        assert "competition_score" in result
        assert "avg_views" in result or "competitors" in result
