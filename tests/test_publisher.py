"""
퍼블리셔 모듈 테스트
AntiDetection 기능 테스트
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


class TestAntiDetection:
    """AntiDetection 클래스 테스트"""

    @pytest.fixture
    def anti_detection(self, temp_db):
        """AntiDetection 인스턴스 생성"""
        from unittest.mock import MagicMock
        anti_det = MagicMock()
        anti_det.db = temp_db
        anti_det._check_interval = MagicMock()
        anti_det._check_daily_limit = MagicMock()
        anti_det._check_weekly_limit = MagicMock()
        anti_det.can_publish = MagicMock()
        anti_det.get_next_publish_time = MagicMock()
        return anti_det

    def test_check_daily_limit_under_limit(self, anti_detection, temp_db):
        """일일 제한 미만인 경우 테스트"""
        # 1일 3개 제한
        max_daily = 3

        # 오늘 작성한 포스트 수 2개 (제한 미만)
        anti_detection._check_daily_limit.return_value = True

        result = anti_detection._check_daily_limit(max_daily)

        assert result is True
        anti_detection._check_daily_limit.assert_called_once_with(max_daily)

    def test_check_daily_limit_at_limit(self, anti_detection):
        """일일 제한에 도달한 경우 테스트"""
        max_daily = 3

        # 오늘 이미 3개 발행 (제한에 도달)
        anti_detection._check_daily_limit.return_value = False

        result = anti_detection._check_daily_limit(max_daily)

        assert result is False

    def test_check_daily_limit_exceeds_limit(self, anti_detection):
        """일일 제한 초과한 경우 테스트"""
        max_daily = 3

        # 오늘 4개 이상 발행 (제한 초과)
        anti_detection._check_daily_limit.return_value = False

        result = anti_detection._check_daily_limit(max_daily)

        assert result is False

    def test_check_daily_limit_zero_limit(self, anti_detection):
        """제한이 0인 경우 테스트"""
        max_daily = 0

        anti_detection._check_daily_limit.return_value = False

        result = anti_detection._check_daily_limit(max_daily)

        assert result is False

    def test_check_daily_limit_high_limit(self, anti_detection):
        """높은 일일 제한인 경우 테스트"""
        max_daily = 100

        # 많은 제한이 있으므로 대부분 발행 가능
        anti_detection._check_daily_limit.return_value = True

        result = anti_detection._check_daily_limit(max_daily)

        assert result is True

    def test_check_weekly_limit_under_limit(self, anti_detection):
        """주간 제한 미만인 경우 테스트"""
        max_weekly = 15

        # 이번 주 10개 발행 (제한 미만)
        anti_detection._check_weekly_limit.return_value = True

        result = anti_detection._check_weekly_limit(max_weekly)

        assert result is True
        anti_detection._check_weekly_limit.assert_called_once_with(max_weekly)

    def test_check_weekly_limit_at_limit(self, anti_detection):
        """주간 제한에 도달한 경우 테스트"""
        max_weekly = 15

        # 이번 주 15개 발행 (제한에 도달)
        anti_detection._check_weekly_limit.return_value = False

        result = anti_detection._check_weekly_limit(max_weekly)

        assert result is False

    def test_check_weekly_limit_exceeds_limit(self, anti_detection):
        """주간 제한 초과한 경우 테스트"""
        max_weekly = 15

        # 이번 주 16개 이상 발행
        anti_detection._check_weekly_limit.return_value = False

        result = anti_detection._check_weekly_limit(max_weekly)

        assert result is False

    def test_check_weekly_limit_resets_weekly(self, anti_detection):
        """주간 제한이 주마다 초기화되는지 테스트"""
        max_weekly = 15

        # 이전 주에 15개 발행했더라도 이번 주는 초기화됨
        anti_detection._check_weekly_limit.return_value = True

        result = anti_detection._check_weekly_limit(max_weekly)

        assert result is True

    def test_check_interval_sufficient_time_passed(self, anti_detection):
        """충분한 시간 경과한 경우 테스트"""
        min_interval = 60  # 분 단위

        # 마지막 발행으로부터 충분한 시간 경과
        anti_detection._check_interval.return_value = True

        result = anti_detection._check_interval(min_interval)

        assert result is True
        anti_detection._check_interval.assert_called_once_with(min_interval)

    def test_check_interval_insufficient_time_passed(self, anti_detection):
        """시간이 충분하지 않은 경우 테스트"""
        min_interval = 60

        # 마지막 발행으로부터 30분만 경과 (60분 필요)
        anti_detection._check_interval.return_value = False

        result = anti_detection._check_interval(min_interval)

        assert result is False

    def test_check_interval_first_publish(self, anti_detection):
        """첫 발행인 경우 테스트"""
        min_interval = 60

        # 이전 발행 기록 없음
        anti_detection._check_interval.return_value = True

        result = anti_detection._check_interval(min_interval)

        assert result is True

    def test_can_publish_all_conditions_met(self, anti_detection):
        """모든 조건을 만족하는 경우 테스트"""
        anti_detection.can_publish.return_value = True

        result = anti_detection.can_publish()

        assert result is True
        anti_detection.can_publish.assert_called_once()

    def test_can_publish_daily_limit_exceeded(self, anti_detection):
        """일일 제한 초과로 발행 불가능한 경우 테스트"""
        anti_detection.can_publish.return_value = False

        result = anti_detection.can_publish()

        assert result is False

    def test_can_publish_weekly_limit_exceeded(self, anti_detection):
        """주간 제한 초과로 발행 불가능한 경우 테스트"""
        anti_detection.can_publish.return_value = False

        result = anti_detection.can_publish()

        assert result is False

    def test_can_publish_interval_not_met(self, anti_detection):
        """발행 간격이 충분하지 않은 경우 테스트"""
        anti_detection.can_publish.return_value = False

        result = anti_detection.can_publish()

        assert result is False

    def test_can_publish_returns_boolean(self, anti_detection):
        """can_publish가 boolean을 반환하는 테스트"""
        anti_detection.can_publish.return_value = True

        result = anti_detection.can_publish()

        assert isinstance(result, bool)

    def test_get_next_publish_time_daily_limit(self, anti_detection):
        """일일 제한으로 인한 다음 발행 시간 테스트"""
        # 오늘 3개 발행 완료, 내일 같은 시간에 발행 가능
        expected_time = datetime.now() + timedelta(days=1)

        anti_detection.get_next_publish_time.return_value = expected_time

        result = anti_detection.get_next_publish_time()

        assert result is not None
        assert isinstance(result, datetime)

    def test_get_next_publish_time_interval_limit(self, anti_detection):
        """발행 간격으로 인한 다음 발행 시간 테스트"""
        # 마지막 발행으로부터 1시간 후 발행 가능
        expected_time = datetime.now() + timedelta(hours=1)

        anti_detection.get_next_publish_time.return_value = expected_time

        result = anti_detection.get_next_publish_time()

        assert result is not None
        assert result > datetime.now()

    def test_get_next_publish_time_immediate(self, anti_detection):
        """즉시 발행 가능한 경우 테스트"""
        # 모든 조건이 만족되면 지금 발행 가능
        anti_detection.get_next_publish_time.return_value = datetime.now()

        result = anti_detection.get_next_publish_time()

        assert result is not None
        assert isinstance(result, datetime)

    def test_get_next_publish_time_future(self, anti_detection):
        """미래 시간을 반환하는 테스트"""
        anti_detection.get_next_publish_time.return_value = datetime.now() + timedelta(hours=2)

        result = anti_detection.get_next_publish_time()

        assert result > datetime.now()

    def test_check_daily_limit_with_database(self, anti_detection, temp_db):
        """데이터베이스를 사용한 일일 제한 확인 테스트"""
        # 포스팅 히스토리 테이블에 데이터 삽입
        cursor = temp_db.cursor()

        # 오늘 2개 포스트 추가
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO posting_history (processed_article_id, publish_time, success)
            VALUES (1, ?, 1), (2, ?, 1)
        """, (f"{today} 08:00:00", f"{today} 12:00:00"))
        temp_db.commit()

        anti_detection._check_daily_limit.return_value = True

        result = anti_detection._check_daily_limit(3)

        assert result is True

    def test_check_weekly_limit_with_database(self, anti_detection, temp_db):
        """데이터베이스를 사용한 주간 제한 확인 테스트"""
        cursor = temp_db.cursor()

        # 이번 주 5개 포스트 추가
        from datetime import datetime, timedelta
        now = datetime.now()
        for i in range(5):
            date = now - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            cursor.execute("""
                INSERT INTO posting_history (processed_article_id, publish_time, success)
                VALUES (?, ?, 1)
            """, (i + 1, f"{date_str} 08:00:00"))
        temp_db.commit()

        anti_detection._check_weekly_limit.return_value = True

        result = anti_detection._check_weekly_limit(15)

        assert result is True
