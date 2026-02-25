"""
주간/월간 리포트 생성 모듈
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from utils.database import Database
from utils.logger import get_logger
from config.settings import settings


logger = get_logger()


class ReportGenerator:
    """주간/월간 리포트 생성 클래스"""

    def __init__(self, db: Optional[Database] = None):
        """초기화"""
        self.db = db or Database(settings.DB_PATH)
        self.reports_dir = Path(getattr(settings, "DATA_DIR", settings.BASE_DIR / "data")) / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_weekly_report(self) -> str:
        """지난 7일간의 주간 리포트를 생성합니다."""
        try:
            logger.info("주간 리포트 생성 시작")
            stats = self._get_period_stats(days=7)
            content = self._format_markdown(stats, period="주간")
            report_path = self._save_report(content, report_type="weekly")
            logger.info(f"주간 리포트 생성 완료: {report_path}")
            return str(report_path)

        except Exception as e:
            logger.error(f"주간 리포트 생성 실패: {e}")
            raise

    def generate_monthly_report(self) -> str:
        """지난 30일간의 월간 리포트를 생성합니다."""
        try:
            logger.info("월간 리포트 생성 시작")
            stats = self._get_period_stats(days=30)
            content = self._format_markdown(stats, period="월간")
            report_path = self._save_report(content, report_type="monthly")
            logger.info(f"월간 리포트 생성 완료: {report_path}")
            return str(report_path)

        except Exception as e:
            logger.error(f"월간 리포트 생성 실패: {e}")
            raise

    def _get_period_stats(self, days: int) -> dict:
        """지정된 기간의 통계를 조회합니다."""
        try:
            now = datetime.now()
            period_start = now - timedelta(days=days)

            # 발행된 포스트 수
            pub_rows = self.db.execute(
                """SELECT COUNT(*) as cnt FROM posting_history
                   WHERE publish_status = 'success'
                   AND published_at >= ?""",
                (period_start.isoformat(),),
            )
            published_count = pub_rows[0]["cnt"] if pub_rows else 0

            # 평균 순위, 최고 순위
            rank_rows = self.db.execute(
                """SELECT AVG(naver_rank) as avg_rank, MIN(naver_rank) as best_rank
                   FROM ranking_history
                   WHERE naver_rank IS NOT NULL
                   AND checked_at >= ?""",
                (period_start.isoformat(),),
            )
            avg_rank = rank_rows[0]["avg_rank"] if rank_rows and rank_rows[0]["avg_rank"] else 0
            best_rank = rank_rows[0]["best_rank"] if rank_rows and rank_rows[0]["best_rank"] else None

            # 평균 SEO 점수
            seo_rows = self.db.execute(
                """SELECT AVG(seo_score) as avg_seo FROM posts
                   WHERE created_at >= ?""",
                (period_start.isoformat(),),
            )
            avg_seo_score = seo_rows[0]["avg_seo"] if seo_rows and seo_rows[0]["avg_seo"] else 0

            # 생성 비용 합계
            cost_rows = self.db.execute(
                """SELECT SUM(generation_cost) as total_cost FROM posts
                   WHERE created_at >= ?""",
                (period_start.isoformat(),),
            )
            total_cost = cost_rows[0]["total_cost"] if cost_rows and cost_rows[0]["total_cost"] else 0

            return {
                "period_start": period_start.strftime("%Y-%m-%d"),
                "period_end": now.strftime("%Y-%m-%d"),
                "published_count": published_count,
                "avg_rank": round(avg_rank, 2) if avg_rank else 0,
                "best_rank": best_rank,
                "avg_seo_score": round(avg_seo_score, 2) if avg_seo_score else 0,
                "total_generation_cost": round(total_cost, 2),
            }

        except Exception as e:
            logger.error(f"기간 통계 조회 실패: {e}")
            return {
                "period_start": (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
                "period_end": datetime.now().strftime("%Y-%m-%d"),
                "published_count": 0,
                "avg_rank": 0,
                "best_rank": None,
                "avg_seo_score": 0,
                "total_generation_cost": 0,
            }

    def _format_markdown(self, stats: dict, period: str) -> str:
        """통계를 Markdown 형식으로 변환합니다."""
        best_rank_str = f"{stats.get('best_rank')}위" if stats.get("best_rank") else "N/A"

        markdown = f"""# {period} 리포트

**기간**: {stats.get('period_start', 'N/A')} ~ {stats.get('period_end', 'N/A')}

---

## 주요 지표

- **발행된 포스트**: {stats.get('published_count', 0)}개
- **평균 순위**: {stats.get('avg_rank', 0)}위
- **최고 순위**: {best_rank_str}
- **평균 SEO 점수**: {stats.get('avg_seo_score', 0)}점
- **생성 비용 합계**: ${stats.get('total_generation_cost', 0):.2f}

---

*리포트 생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        return markdown

    def _save_report(self, content: str, report_type: str) -> Path:
        """리포트를 파일로 저장합니다."""
        try:
            now = datetime.now()
            if report_type == "weekly":
                filename = f"weekly_{now.strftime('%Y-%m-%d')}.md"
            elif report_type == "monthly":
                filename = f"monthly_{now.strftime('%Y-%m')}.md"
            else:
                filename = f"report_{now.strftime('%Y-%m-%d_%H%M%S')}.md"

            report_path = self.reports_dir / filename

            with open(report_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"리포트 저장 완료: {report_path}")
            return report_path

        except Exception as e:
            logger.error(f"리포트 저장 실패: {e}")
            raise
