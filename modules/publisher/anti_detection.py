"""
안티-디텍션 시스템: 네이버 봇 탐지 방지
Anti-Detection System: Prevents Naver from detecting bot behavior
"""

import random
from datetime import datetime, timedelta
from typing import Optional, Tuple
from utils.database import Database
from utils.logger import get_logger
from config.settings import settings

logger = get_logger()


class AntiDetection:
    """
    네이버 봇 탐지를 방지하는 안티-디텍션 시스템
    """

    def __init__(self, db: Optional[Database] = None):
        """초기화"""
        self.db = db or Database(settings.DB_PATH)
        self.min_interval_hours = getattr(settings, "MIN_INTERVAL_HOURS", 4)
        self.max_posts_per_day = getattr(settings, "MAX_POSTS_PER_DAY", 2)
        self.max_posts_per_week = getattr(settings, "MAX_POSTS_PER_WEEK", 5)
        self.preferred_hours = getattr(settings, "PREFERRED_HOURS", [9, 15, 20])

    def can_publish(self) -> Tuple[bool, str]:
        """현재 발행 가능 여부를 확인합니다"""
        if not self._check_interval():
            next_time = self.get_next_publish_time()
            return False, f"최소 간격 미충족. 다음 발행 시간: {next_time.strftime('%Y-%m-%d %H:%M:%S')}"

        if not self._check_daily_limit():
            return False, f"일일 제한 초과 (최대 {self.max_posts_per_day}개)"

        if not self._check_weekly_limit():
            return False, f"주간 제한 초과 (최대 {self.max_posts_per_week}개)"

        return True, "발행 가능"

    def _check_interval(self) -> bool:
        """마지막 발행으로부터 최소 4시간 경과 확인"""
        try:
            result = self.db.execute(
                """SELECT published_at FROM posting_history
                   WHERE publish_status = 'success'
                   ORDER BY published_at DESC
                   LIMIT 1"""
            )

            if not result:
                logger.info("첫 발행입니다")
                return True

            last_publish_time = result[0]["published_at"]
            if isinstance(last_publish_time, str):
                last_publish_time = datetime.fromisoformat(last_publish_time)

            time_since_last = datetime.now() - last_publish_time
            min_interval = timedelta(hours=self.min_interval_hours)

            if time_since_last >= min_interval:
                logger.info(f"시간 간격 조건 만족: {time_since_last}")
                return True
            else:
                logger.warning(f"시간 간격 부족: {time_since_last} < {min_interval}")
                return False

        except Exception as e:
            logger.error(f"시간 간격 확인 오류: {e}")
            return True  # 오류 시 발행 허용

    def _check_daily_limit(self) -> bool:
        """일일 발행 제한 (최대 2개) 확인"""
        try:
            result = self.db.execute(
                """SELECT COUNT(*) as count FROM posting_history
                   WHERE publish_status = 'success'
                   AND DATE(published_at) = DATE('now')"""
            )

            count = result[0]["count"] if result else 0

            if count < self.max_posts_per_day:
                logger.info(f"일일 제한 확인: {count}/{self.max_posts_per_day}")
                return True
            else:
                logger.warning(f"일일 제한 초과: {count}/{self.max_posts_per_day}")
                return False

        except Exception as e:
            logger.error(f"일일 제한 확인 오류: {e}")
            return True

    def _check_weekly_limit(self) -> bool:
        """주간 발행 제한 (최대 5개) 확인"""
        try:
            result = self.db.execute(
                """SELECT COUNT(*) as count FROM posting_history
                   WHERE publish_status = 'success'
                   AND published_at >= datetime('now', '-7 days')"""
            )

            count = result[0]["count"] if result else 0

            if count < self.max_posts_per_week:
                logger.info(f"주간 제한 확인: {count}/{self.max_posts_per_week}")
                return True
            else:
                logger.warning(f"주간 제한 초과: {count}/{self.max_posts_per_week}")
                return False

        except Exception as e:
            logger.error(f"주간 제한 확인 오류: {e}")
            return True

    def get_next_publish_time(self) -> datetime:
        """다음 발행 가능 시간을 계산합니다 (가우시안 지연 포함)"""
        try:
            result = self.db.execute(
                """SELECT published_at FROM posting_history
                   WHERE publish_status = 'success'
                   ORDER BY published_at DESC
                   LIMIT 1"""
            )

            if result:
                last_publish = result[0]["published_at"]
                if isinstance(last_publish, str):
                    last_publish = datetime.fromisoformat(last_publish)
                base_time = last_publish + timedelta(hours=self.min_interval_hours)
            else:
                base_time = datetime.now() + timedelta(hours=self.min_interval_hours)

            # 가우시안 지연 적용 (numpy 대신 random 사용)
            next_time = self._add_gaussian_delay(base_time)

            logger.info(f"다음 발행 시간: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return next_time

        except Exception as e:
            logger.error(f"다음 발행 시간 계산 오류: {e}")
            return datetime.now() + timedelta(hours=self.min_interval_hours)

    def _add_gaussian_delay(self, base_time: datetime) -> datetime:
        """기본 시간에 가우시안 분포의 지연을 추가합니다"""
        try:
            # random.gauss를 사용 (numpy 의존성 제거)
            delay_minutes = random.gauss(0, 30)
            delay = timedelta(minutes=delay_minutes)

            result_time = base_time + delay

            # 선호 시간대 확인
            hour = result_time.hour
            if hour not in self.preferred_hours:
                closest_hour = min(self.preferred_hours, key=lambda x: abs(x - hour))
                result_time = result_time.replace(hour=closest_hour, minute=0, second=0)

            logger.debug(f"가우시안 지연 적용: {delay_minutes:.1f}분")
            return result_time

        except Exception as e:
            logger.error(f"가우시안 지연 계산 오류: {e}")
            return base_time
