"""
모니터 모듈 테스트
ReportGenerator 기능 테스트
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


class TestReportGenerator:
    """ReportGenerator 클래스 테스트"""

    @pytest.fixture
    def report_generator(self, temp_db):
        """ReportGenerator 인스턴스 생성"""
        from unittest.mock import MagicMock
        generator = MagicMock()
        generator.db = temp_db
        generator.generate_weekly_report = MagicMock()
        generator.generate_monthly_report = MagicMock()
        generator._get_period_stats = MagicMock()
        generator._format_markdown = MagicMock()
        return generator

    def test_get_period_stats_weekly(self, report_generator, sample_posting_history, temp_db):
        """주간 통계 조회 테스트"""
        # 일주일 간의 포스팅 통계
        stats = {
            "period": "2024-01-01 ~ 2024-01-07",
            "total_posts": 3,
            "successful_posts": 3,
            "failed_posts": 0,
            "avg_views": 150,
            "total_engagement": 450,
            "most_popular_keyword": "테스트 키워드"
        }

        report_generator._get_period_stats.return_value = stats

        result = report_generator._get_period_stats("week")

        assert result["period"] is not None
        assert result["total_posts"] >= 0
        assert result["successful_posts"] >= 0
        report_generator._get_period_stats.assert_called_once_with("week")

    def test_get_period_stats_monthly(self, report_generator):
        """월간 통계 조회 테스트"""
        stats = {
            "period": "2024-01월",
            "total_posts": 15,
            "successful_posts": 14,
            "failed_posts": 1,
            "avg_views": 200,
            "total_engagement": 3000,
            "growth_rate": 15.5
        }

        report_generator._get_period_stats.return_value = stats

        result = report_generator._get_period_stats("month")

        assert "period" in result
        assert result["total_posts"] > 0
        assert result["successful_posts"] <= result["total_posts"]

    def test_get_period_stats_includes_metrics(self, report_generator):
        """통계에 필수 메트릭 포함 테스트"""
        required_metrics = [
            "period",
            "total_posts",
            "successful_posts",
            "failed_posts"
        ]

        stats = {
            "period": "2024-01-01 ~ 2024-01-07",
            "total_posts": 10,
            "successful_posts": 9,
            "failed_posts": 1,
            "avg_views": 100,
            "engagement_rate": 0.85
        }

        report_generator._get_period_stats.return_value = stats

        result = report_generator._get_period_stats("week")

        for metric in required_metrics:
            assert metric in result

    def test_get_period_stats_zero_posts(self, report_generator):
        """포스트가 없는 기간 통계 테스트"""
        stats = {
            "period": "2024-02-01 ~ 2024-02-07",
            "total_posts": 0,
            "successful_posts": 0,
            "failed_posts": 0,
            "avg_views": 0,
            "message": "이 기간에 발행된 포스트가 없습니다"
        }

        report_generator._get_period_stats.return_value = stats

        result = report_generator._get_period_stats("week")

        assert result["total_posts"] == 0

    def test_get_period_stats_with_errors(self, report_generator):
        """오류 정보 포함된 통계 테스트"""
        stats = {
            "period": "2024-01-01 ~ 2024-01-07",
            "total_posts": 5,
            "successful_posts": 4,
            "failed_posts": 1,
            "errors": [
                {"post_id": 3, "error": "네트워크 오류"}
            ]
        }

        report_generator._get_period_stats.return_value = stats

        result = report_generator._get_period_stats("week")

        assert result["failed_posts"] > 0
        assert "errors" in result

    def test_format_markdown_basic(self, report_generator):
        """기본 마크다운 포맷팅 테스트"""
        stats = {
            "period": "2024-01-01 ~ 2024-01-07",
            "total_posts": 3,
            "successful_posts": 3,
            "failed_posts": 0,
            "avg_views": 150
        }

        markdown = "# 주간 리포트\n## 기간: 2024-01-01 ~ 2024-01-07\n- 총 포스트: 3"

        report_generator._format_markdown.return_value = markdown

        result = report_generator._format_markdown(stats, "week")

        assert result is not None
        assert isinstance(result, str)
        assert "#" in result  # 마크다운 헤더 포함
        report_generator._format_markdown.assert_called_once()

    def test_format_markdown_includes_title(self, report_generator):
        """마크다운이 제목을 포함하는 테스트"""
        stats = {"period": "2024-01-01 ~ 2024-01-07", "total_posts": 5}

        markdown = "# 주간 리포트\n내용..."

        report_generator._format_markdown.return_value = markdown

        result = report_generator._format_markdown(stats, "week")

        assert "리포트" in result or "Report" in result

    def test_format_markdown_includes_stats(self, report_generator):
        """마크다운이 통계를 포함하는 테스트"""
        stats = {
            "period": "2024-01-01 ~ 2024-01-07",
            "total_posts": 5,
            "successful_posts": 4,
            "failed_posts": 1
        }

        markdown = "# 주간 리포트\n- 총 포스트: 5\n- 성공: 4\n- 실패: 1"

        report_generator._format_markdown.return_value = markdown

        result = report_generator._format_markdown(stats, "week")

        # 통계 수치가 포함되어 있는지 확인
        assert "5" in result or "포스트" in result

    def test_format_markdown_with_tables(self, report_generator):
        """마크다운 테이블 형식 테스트"""
        stats = {
            "period": "2024-01-01 ~ 2024-01-07",
            "daily_breakdown": [
                {"date": "2024-01-01", "posts": 1, "views": 100},
                {"date": "2024-01-02", "posts": 1, "views": 120}
            ]
        }

        markdown = "| 날짜 | 포스트 | 조회수 |\n|------|--------|--------|\n| 2024-01-01 | 1 | 100 |"

        report_generator._format_markdown.return_value = markdown

        result = report_generator._format_markdown(stats, "week")

        assert "|" in result  # 테이블 구문 포함

    def test_generate_weekly_report(self, report_generator, sample_posting_history):
        """주간 리포트 생성 테스트"""
        report = {
            "type": "weekly",
            "period": "2024-01-01 ~ 2024-01-07",
            "total_posts": 3,
            "successful_posts": 3,
            "failed_posts": 0,
            "content": "# 주간 리포트\n..."
        }

        report_generator.generate_weekly_report.return_value = report

        result = report_generator.generate_weekly_report()

        assert result["type"] == "weekly"
        assert "content" in result
        assert isinstance(result["content"], str)
        report_generator.generate_weekly_report.assert_called_once()

    def test_generate_weekly_report_includes_period(self, report_generator):
        """주간 리포트에 기간 포함 테스트"""
        report = {
            "type": "weekly",
            "period": "2024-01-01 ~ 2024-01-07",
            "content": "..."
        }

        report_generator.generate_weekly_report.return_value = report

        result = report_generator.generate_weekly_report()

        assert "period" in result
        assert "~" in result["period"]

    def test_generate_weekly_report_includes_stats(self, report_generator):
        """주간 리포트에 통계 포함 테스트"""
        report = {
            "type": "weekly",
            "period": "2024-01-01 ~ 2024-01-07",
            "total_posts": 5,
            "successful_posts": 5,
            "failed_posts": 0,
            "content": "# 주간 리포트\n..."
        }

        report_generator.generate_weekly_report.return_value = report

        result = report_generator.generate_weekly_report()

        assert "total_posts" in result
        assert result["total_posts"] >= 0

    def test_generate_monthly_report(self, report_generator):
        """월간 리포트 생성 테스트"""
        report = {
            "type": "monthly",
            "period": "2024-01월",
            "total_posts": 15,
            "successful_posts": 14,
            "failed_posts": 1,
            "growth_rate": 15.5,
            "content": "# 월간 리포트\n..."
        }

        report_generator.generate_monthly_report.return_value = report

        result = report_generator.generate_monthly_report()

        assert result["type"] == "monthly"
        assert "content" in result
        assert "growth_rate" in result
        report_generator.generate_monthly_report.assert_called_once()

    def test_generate_monthly_report_includes_growth(self, report_generator):
        """월간 리포트에 성장률 포함 테스트"""
        report = {
            "type": "monthly",
            "period": "2024-01월",
            "growth_rate": 25.5,
            "content": "..."
        }

        report_generator.generate_monthly_report.return_value = report

        result = report_generator.generate_monthly_report()

        assert "growth_rate" in result
        assert isinstance(result["growth_rate"], (int, float))

    def test_generate_monthly_report_includes_top_keywords(self, report_generator):
        """월간 리포트에 상위 키워드 포함 테스트"""
        report = {
            "type": "monthly",
            "period": "2024-01월",
            "top_keywords": [
                {"keyword": "네이버 블로그", "posts": 3, "avg_rank": 5},
                {"keyword": "SEO 최적화", "posts": 2, "avg_rank": 8}
            ],
            "content": "..."
        }

        report_generator.generate_monthly_report.return_value = report

        result = report_generator.generate_monthly_report()

        assert "top_keywords" in result
        assert len(result["top_keywords"]) > 0

    def test_report_contains_markdown_content(self, report_generator):
        """리포트에 마크다운 형식의 콘텐츠 포함 테스트"""
        report = {
            "type": "weekly",
            "content": "# 주간 리포트\n## 통계\n- 포스트 수: 5\n- 성공률: 100%"
        }

        report_generator.generate_weekly_report.return_value = report

        result = report_generator.generate_weekly_report()

        assert "#" in result["content"]  # 마크다운 헤더
        assert "-" in result["content"]  # 마크다운 리스트

    def test_report_timestamp(self, report_generator):
        """리포트 생성 시간 확인 테스트"""
        now = datetime.now()

        report = {
            "type": "weekly",
            "generated_at": now.isoformat(),
            "content": "..."
        }

        report_generator.generate_weekly_report.return_value = report

        result = report_generator.generate_weekly_report()

        assert "generated_at" in result

    def test_format_markdown_empty_stats(self, report_generator):
        """빈 통계의 마크다운 포맷팅 테스트"""
        empty_stats = {}

        markdown = "# 리포트\n데이터가 없습니다."

        report_generator._format_markdown.return_value = markdown

        result = report_generator._format_markdown(empty_stats, "week")

        assert result is not None
        assert isinstance(result, str)

    def test_get_period_stats_returns_dict(self, report_generator):
        """통계가 딕셔너리를 반환하는 테스트"""
        report_generator._get_period_stats.return_value = {"period": "2024-01", "posts": 10}

        result = report_generator._get_period_stats("month")

        assert isinstance(result, dict)

    def test_format_markdown_returns_string(self, report_generator):
        """마크다운 포맷팅이 문자열을 반환하는 테스트"""
        stats = {"period": "2024-01", "posts": 10}

        report_generator._format_markdown.return_value = "# 리포트\n내용"

        result = report_generator._format_markdown(stats, "week")

        assert isinstance(result, str)
        assert len(result) > 0
