#!/usr/bin/env python3
"""
NaverBlogAutoPilot - 메인 CLI 엔트리포인트

사용법:
    python main.py init-db                    # 데이터베이스 초기화
    python main.py crawl [--limit N]          # silmu.kr 크롤링
    python main.py research                   # 키워드 분석
    python main.py generate [--count N]       # 포스트 생성
    python main.py publish                    # 블로그 발행
    python main.py monitor                    # 순위 추적
    python main.py report --type weekly       # 리포트 생성
    python main.py schedule                   # 자동 스케줄러 시작
    python main.py status                     # 현재 상태 확인
"""

import asyncio
import sys
import argparse
import time
from datetime import datetime

try:
    import schedule
except ImportError:
    schedule = None

from config.settings import settings
from utils.database import Database
from utils.logger import setup_logger, get_logger


def get_db() -> Database:
    """데이터베이스 인스턴스 반환"""
    return Database(settings.DB_PATH)


# ============================================================
# CLI 명령어 핸들러
# ============================================================

def cmd_init_db(args):
    """데이터베이스 초기화"""
    logger = get_logger()
    db = get_db()
    db.init_db()
    logger.info("데이터베이스 초기화 완료!")
    print("✅ 데이터베이스 초기화 완료!")


def cmd_crawl(args):
    """Phase 1: silmu.kr 크롤링"""
    from modules.collector import SilmuCrawler

    logger = get_logger()
    limit = args.limit if hasattr(args, "limit") else None

    logger.info(f"크롤링 시작 (limit={limit})")
    print(f"🕷️  silmu.kr 크롤링 시작... (limit={limit or '전체'})")

    db = get_db()
    crawler = SilmuCrawler(db=db)
    count = asyncio.run(crawler.crawl(limit=limit))

    logger.info(f"크롤링 완료: {count}개 기사 수집")
    print(f"✅ 크롤링 완료! {count}개 기사를 수집했습니다.")


def cmd_research(args):
    """Phase 2: 키워드 분석"""
    import json
    from modules.researcher import KeywordAnalyzer, TrendTracker, CompetitorScanner

    logger = get_logger()
    logger.info("키워드 분석 시작")
    print("🔍 키워드 분석 시작...")

    # 키워드 클러스터 로드
    clusters_path = settings.BASE_DIR / "config" / "keyword_clusters.json"
    with open(clusters_path, "r", encoding="utf-8") as f:
        clusters_data = json.load(f)

    db = get_db()

    # 모든 시드 키워드 수집
    all_keywords = []
    for cluster_name, cluster_info in clusters_data["clusters"].items():
        all_keywords.extend(cluster_info["seed_keywords"])

    async def run_research():
        # 1. 키워드 확장 (자동완성, 연관검색어)
        tracker = TrendTracker(db)
        expanded = await tracker.expand_keywords(all_keywords[:10])
        print(f"  📊 키워드 확장 완료: {sum(len(v) for v in expanded.values())}개 추가 키워드")

        # 2. 검색량 분석
        analyzer = KeywordAnalyzer(db)
        results = await analyzer.analyze_keywords(all_keywords)
        print(f"  📈 검색량 분석 완료: {len(results)}개 키워드")

        # 3. 경쟁 분석 (상위 5개 키워드만)
        scanner = CompetitorScanner(db)
        top_keywords = sorted(results, key=lambda x: x.get("total_score", 0), reverse=True)[:5]
        for kw_data in top_keywords:
            keyword = kw_data.get("keyword", "")
            if keyword:
                comp = await scanner.analyze_competitors(keyword)
                print(f"  🏆 경쟁 분석: '{keyword}' - 경쟁도 {comp.get('competition_score', 0):.1f}")

    asyncio.run(run_research())

    logger.info("키워드 분석 완료")
    print("✅ 키워드 분석 완료!")


def _get_current_publish_category(db) -> str:
    """현재 발행해야 할 카테고리를 결정합니다.

    로직:
    1. 발행 순서(PUBLISH_CATEGORY_ORDER)를 따름
    2. 각 카테고리에 POSTS_PER_CATEGORY_ROTATE개를 발행한 후 다음 카테고리로
    3. 모든 카테고리를 한 바퀴 돌면 다시 처음부터
    """
    order = settings.PUBLISH_CATEGORY_ORDER
    rotate_count = settings.POSTS_PER_CATEGORY_ROTATE

    # 각 카테고리별 발행(published) + 승인(approved) 포스트 수 확인
    for publish_cat in order:
        # 이 카테고리에서 발행/승인된 포스트 수
        count = db.count("posts", "publish_category = ? AND status IN ('published', 'approved')", (publish_cat,))
        if count < rotate_count:
            return publish_cat

    # 모든 카테고리가 rotate_count를 채운 경우 → 2라운드 체크
    # 전체 발행 수를 기반으로 현재 라운드와 카테고리 결정
    total_published = db.count("posts", "status IN ('published', 'approved')")
    total_per_round = rotate_count * len(order)

    if total_per_round == 0:
        return order[0]

    position_in_round = total_published % total_per_round
    category_index = position_in_round // rotate_count
    return order[min(category_index, len(order) - 1)]


def cmd_generate(args):
    """Phase 3: 포스트 생성 (카테고리 순서 기반)"""
    from modules.generator import ContentEngine, SEOOptimizer, QualityChecker

    logger = get_logger()
    count = args.count if hasattr(args, "count") else 1
    category = args.category if hasattr(args, "category") and args.category else None

    db = get_db()

    # 카테고리 결정
    if not category:
        category = _get_current_publish_category(db)

    logger.info(f"포스트 생성 시작 (count={count}, category={category})")
    print(f"✍️  포스트 생성 시작... ({count}개, 카테고리: {category})")

    # 크롤링 카테고리 → 발행 카테고리 역매핑 (어떤 크롤링 카테고리가 이 발행 카테고리에 해당하는지)
    source_categories = [
        crawl_cat for crawl_cat, pub_cat in settings.CATEGORY_MAP.items()
        if pub_cat == category
    ]
    if not source_categories:
        # 매핑이 없으면 동일 이름으로 시도
        source_categories = [category]

    source_placeholders = ",".join(["?"] * len(source_categories))

    async def run_generate():
        engine = ContentEngine(db)
        seo = SEOOptimizer()
        quality = QualityChecker()

        # 해당 카테고리의 미사용 기사 선택
        articles = db.execute(
            f"""SELECT a.id, a.title, pa.clean_text, a.category, a.url
               FROM articles a
               JOIN processed_articles pa ON pa.article_id = a.id
               WHERE a.id NOT IN (SELECT COALESCE(article_id, 0) FROM posts)
               AND a.category IN ({source_placeholders})
               ORDER BY a.crawled_at DESC
               LIMIT ?""",
            (*source_categories, count),
        )

        if not articles:
            # 해당 카테고리에 기사가 없으면 전체에서 선택
            logger.warning(f"'{category}' 카테고리에 미사용 기사가 없어 전체에서 선택합니다")
            print(f"  ⚠️  '{category}' 카테고리 기사 부족 → 전체에서 선택")
            articles = db.execute(
                """SELECT a.id, a.title, pa.clean_text, a.category
                   FROM articles a
                   JOIN processed_articles pa ON pa.article_id = a.id
                   WHERE a.id NOT IN (SELECT COALESCE(article_id, 0) FROM posts)
                   ORDER BY a.crawled_at DESC
                   LIMIT ?""",
                (count,),
            )

        # 해당 카테고리 키워드 우선 선택
        keywords = db.execute(
            f"""SELECT id, keyword, cluster, total_score
               FROM keywords
               WHERE id NOT IN (SELECT COALESCE(keyword_id, 0) FROM posts)
               AND cluster IN ({source_placeholders})
               ORDER BY total_score DESC
               LIMIT ?""",
            (*source_categories, count),
        )

        if not keywords:
            # 키워드가 없으면 전체에서 선택
            keywords = db.execute(
                """SELECT id, keyword, cluster, total_score
                   FROM keywords
                   WHERE id NOT IN (SELECT COALESCE(keyword_id, 0) FROM posts)
                   ORDER BY total_score DESC
                   LIMIT ?""",
                (count,),
            )

        generated = 0
        for i in range(min(count, len(articles), max(len(keywords), 1))):
            article = dict(articles[i]) if i < len(articles) else None
            keyword = dict(keywords[i]) if i < len(keywords) else None

            if not article:
                logger.warning("사용 가능한 기사가 없습니다")
                break

            try:
                post = await engine.generate_post(article, keyword or {})

                # 발행 카테고리 태깅 (DB에도 반영)
                post["publish_category"] = category
                if post.get("id"):
                    db.execute(
                        "UPDATE posts SET publish_category = ? WHERE id = ?",
                        (category, post["id"]),
                    )

                # SEO 점수 계산
                seo_result = seo.calculate_score(
                    post["title"], post["body"], keyword.get("keyword", "") if keyword else ""
                )
                post["seo_score"] = seo_result["total_score"]

                # 품질 검사 (원본 표절)
                quality_result = quality.check_plagiarism(
                    post["body"], article.get("clean_text", "")
                )

                # 기존 발행 글 중복 검사
                dup_result = quality.check_duplicate(post["title"], post["body"], db, exclude_post_id=post.get("id"))

                if dup_result["is_duplicate"]:
                    post["status"] = "draft"
                    print(f"  🔄 [{i+1}/{count}] [{category}] '{post['title']}' - 중복 감지: {dup_result['reason']}")
                    print(f"     유사 글: '{dup_result['most_similar_title'][:40]}...'")
                elif seo_result["total_score"] >= settings.MIN_SEO_SCORE and quality_result <= settings.PLAGIARISM_THRESHOLD:
                    post["status"] = "approved"
                    print(f"  ✅ [{i+1}/{count}] [{category}] '{post['title']}' - SEO: {seo_result['total_score']:.0f}점")
                else:
                    post["status"] = "draft"
                    print(f"  ⚠️  [{i+1}/{count}] [{category}] '{post['title']}' - SEO: {seo_result['total_score']:.0f}점 (재검토 필요)")

                # DB에 status와 seo_score 반영
                if post.get("id"):
                    db.execute(
                        "UPDATE posts SET status = ?, seo_score = ? WHERE id = ?",
                        (post["status"], seo_result["total_score"], post["id"]),
                    )

                generated += 1

            except Exception as e:
                logger.error(f"포스트 생성 실패: {e}")
                print(f"  ❌ [{i+1}/{count}] 생성 실패: {e}")

        return generated

    generated = asyncio.run(run_generate())

    logger.info(f"포스트 생성 완료: {generated}개 (카테고리: {category})")
    print(f"✅ 포스트 생성 완료! {generated}개 생성됨 (카테고리: {category})")


def cmd_publish(args):
    """Phase 4: 블로그 발행 (카테고리 순서 기반)"""
    from modules.publisher import AntiDetection, NaverBlogPoster

    logger = get_logger()
    logger.info("발행 프로세스 시작")
    print("📤 발행 프로세스 시작...")

    db = get_db()
    anti = AntiDetection(db)

    # 어뷰징 방지 체크 (--force 옵션으로 무시 가능)
    force = getattr(args, "force", False)
    if force:
        print("⚠️  --force 모드: 안티디텍션 간격 체크 무시")
        logger.warning("--force 모드: 안티디텍션 간격 체크 무시")
    else:
        can_publish, reason = anti.can_publish()
        if not can_publish:
            next_time = anti.get_next_publish_time()
            print(f"⏳ 발행 불가: {reason}")
            print(f"   다음 발행 가능 시간: {next_time.strftime('%Y-%m-%d %H:%M')}")
            return

    # 현재 발행할 카테고리 확인
    current_category = _get_current_publish_category(db)
    print(f"  📂 현재 발행 카테고리: {current_category}")

    # 해당 카테고리의 승인된 포스트 우선 선택
    posts = db.execute(
        """SELECT id, title, body, html_body, publish_category
           FROM posts
           WHERE status = 'approved' AND publish_category = ?
           ORDER BY seo_score DESC
           LIMIT 1""",
        (current_category,),
    )

    if not posts:
        # 해당 카테고리에 없으면 전체에서 선택
        posts = db.execute(
            """SELECT id, title, body, html_body, publish_category
               FROM posts
               WHERE status = 'approved'
               ORDER BY seo_score DESC
               LIMIT 1"""
        )

    if not posts:
        print("📭 발행할 포스트가 없습니다. 먼저 generate를 실행하세요.")
        return

    post = dict(posts[0])
    pub_cat = post.get("publish_category", "미분류")
    print(f"  📝 발행 대상: [{pub_cat}] {post['title']}")

    # ── 발행 전 휴먼 리뷰 (--skip-review로 건너뛸 수 있음) ──
    skip_review = getattr(args, "skip_review", False)
    if not skip_review and post.get("body"):
        try:
            from modules.generator.humanizer import detect_ai_patterns
            print(f"\n  🔍 발행 전 휴먼 리뷰 실행 중...")
            review = detect_ai_patterns(post["body"])

            score = review.score
            if score >= 80:
                indicator = "🟢"
            elif score >= 60:
                indicator = "🟡"
            else:
                indicator = "🔴"
            print(f"  {indicator} 휴먼 리뷰 점수: {score}/100")

            if review.issues:
                for iss in review.issues[:3]:  # 상위 3개만 표시
                    print(f"     ⚠️  [{iss['category']}] {iss['detail']}")
                if len(review.issues) > 3:
                    print(f"     ... 외 {len(review.issues) - 3}개 이슈")

            if score < 50:
                print(f"\n  🚫 휴먼 리뷰 점수가 매우 낮습니다 ({score}/100).")
                print(f"     먼저 'python main.py review --fix --id {post['id']}' 로 수정하세요.")
                print(f"     강행하려면: python main.py publish --skip-review")
                return
            elif score < 70:
                print(f"\n  ⚠️  AI 감지 위험이 있습니다. 수정을 권장합니다.")
                print(f"     수정: python main.py review --fix --id {post['id']}")
                print(f"     (3초 후 발행을 계속합니다...)")
                import time as time_module
                time_module.sleep(3)

            print()
        except Exception as e:
            logger.warning(f"휴먼 리뷰 스킵: {e}")

    async def run_publish():
        poster = NaverBlogPoster(db)
        result = await poster.publish(post)  # publish 내부에서 _close() 처리
        if result.get("success"):
            # 상태 업데이트
            db.execute(
                "UPDATE posts SET status = 'published' WHERE id = ?",
                (post["id"],),
            )
            print(f"✅ 발행 성공!")
            print(f"   카테고리: {pub_cat}")
            print(f"   제목: {post['title']}")
            print(f"   URL: {result.get('blog_url', 'N/A')}")
        else:
            print(f"❌ 발행 실패: {result.get('error', 'Unknown error')}")
            # 디버깅 스크린샷 확인 안내
            print(f"   💡 디버깅 스크린샷: data/debug_screenshots/ 폴더를 확인하세요")

    asyncio.run(run_publish())


def cmd_monitor(args):
    """Phase 5: 순위 추적"""
    from modules.monitor import RankingTracker

    logger = get_logger()
    logger.info("순위 추적 시작")
    print("📊 순위 추적 시작...")

    db = get_db()

    async def run_monitor():
        tracker = RankingTracker(db)
        rankings = await tracker.check_rankings()
        return rankings

    rankings = asyncio.run(run_monitor())

    if rankings:
        print(f"\n📈 순위 결과 ({len(rankings)}개 키워드):")
        for r in rankings:
            rank = r.get("rank", "순위 외")
            print(f"  • '{r.get('keyword', '')}' → {rank}위")
    else:
        print("📭 추적할 발행 포스트가 없습니다.")

    print("✅ 순위 추적 완료!")


def cmd_report(args):
    """Phase 5: 리포트 생성"""
    from modules.monitor import ReportGenerator

    logger = get_logger()
    report_type = args.type if hasattr(args, "type") else "weekly"

    logger.info(f"리포트 생성 시작 ({report_type})")
    print(f"📋 {report_type} 리포트 생성 중...")

    db = get_db()
    generator = ReportGenerator(db)

    if report_type == "weekly":
        report_path = generator.generate_weekly_report()
    elif report_type == "monthly":
        report_path = generator.generate_monthly_report()
    else:
        print(f"❌ 지원하지 않는 리포트 타입: {report_type}")
        return

    print(f"✅ 리포트 생성 완료!")
    print(f"   파일: {report_path}")


def cmd_schedule(args):
    """자동 스케줄러"""
    logger = get_logger()
    logger.info("스케줄러 시작")
    print("⏰ 자동 스케줄러 시작!")
    print(f"   크롤링: 매일 {settings.SCHEDULE_CRAWL_HOUR}")
    print(f"   발행: 매일 {', '.join(settings.SCHEDULE_PUBLISH_HOURS)}")
    print(f"   모니터링: 매일 {settings.SCHEDULE_MONITOR_HOUR}")
    print("   종료: Ctrl+C\n")

    # 크롤링 스케줄
    schedule.every().day.at(settings.SCHEDULE_CRAWL_HOUR).do(
        lambda: cmd_crawl(argparse.Namespace(limit=20))
    )

    # 발행 스케줄
    for pub_hour in settings.SCHEDULE_PUBLISH_HOURS:
        schedule.every().day.at(pub_hour).do(
            lambda: (
                cmd_generate(argparse.Namespace(count=1)),
                cmd_publish(argparse.Namespace()),
            )
        )

    # 모니터링 스케줄
    schedule.every().day.at(settings.SCHEDULE_MONITOR_HOUR).do(
        lambda: cmd_monitor(argparse.Namespace())
    )

    # 주간 리포트 (월요일)
    schedule.every().monday.at("09:00").do(
        lambda: cmd_report(argparse.Namespace(type="weekly"))
    )

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n⏹️  스케줄러 종료")


def cmd_status(args):
    """현재 상태 확인"""
    db = get_db()
    print("\n📊 NaverBlogAutoPilot 상태")
    print("=" * 50)

    try:
        articles = db.count("articles")
        keywords = db.count("keywords")
        posts_draft = db.count("posts", "status='draft'")
        posts_approved = db.count("posts", "status='approved'")
        posts_published = db.count("posts", "status='published'")
        published_today = db.count(
            "posting_history",
            "publish_status='success' AND date(published_at)=date('now')",
        )
        published_week = db.count(
            "posting_history",
            "publish_status='success' AND published_at >= datetime('now', '-7 days')",
        )

        print(f"  📰 수집된 기사:     {articles}개")
        print(f"  🔑 분석된 키워드:   {keywords}개")
        print(f"  ✍️  초안 포스트:     {posts_draft}개")
        print(f"  ✅ 승인된 포스트:   {posts_approved}개")
        print(f"  📤 발행된 포스트:   {posts_published}개")
        print(f"  📅 오늘 발행:       {published_today}개 / {settings.MAX_POSTS_PER_DAY}개")
        print(f"  📅 이번 주 발행:    {published_week}개 / {settings.MAX_POSTS_PER_WEEK}개")

        # 카테고리별 현황
        current_cat = _get_current_publish_category(db)
        print(f"\n  📂 카테고리별 현황 (발행 순서):")
        for cat in settings.PUBLISH_CATEGORY_ORDER:
            cat_count = db.count("posts", "publish_category = ? AND status IN ('published', 'approved')", (cat,))
            marker = " ◀ 현재" if cat == current_cat else ""
            bar = "█" * cat_count + "░" * (settings.POSTS_PER_CATEGORY_ROTATE - cat_count)
            print(f"     {cat}: [{bar}] {cat_count}/{settings.POSTS_PER_CATEGORY_ROTATE}{marker}")

        # 최근 발행
        recent = db.execute(
            """SELECT p.title, ph.blog_url, ph.published_at
               FROM posting_history ph
               JOIN posts p ON p.id = ph.post_id
               WHERE ph.publish_status = 'success'
               ORDER BY ph.published_at DESC
               LIMIT 3"""
        )
        if recent:
            print(f"\n  📌 최근 발행:")
            for r in recent:
                print(f"     • {r['title'][:40]}... ({r['published_at'][:10]})")

    except Exception as e:
        print(f"  ⚠️  상태 조회 실패 (DB 초기화 필요?): {e}")
        print(f"     python main.py init-db 를 먼저 실행하세요.")

    print()


def cmd_review(args):
    """Phase 3.5: 포스트 휴먼 리뷰 (AI 감지 회피 검토)"""
    from modules.generator.humanizer import Humanizer, detect_ai_patterns

    logger = get_logger()
    db = get_db()

    post_id = getattr(args, "id", None)
    fix = getattr(args, "fix", False)
    all_posts = getattr(args, "all", False)

    # 대상 포스트 선택
    if post_id:
        posts = db.execute(
            "SELECT id, title, body, html_body, status, publish_category FROM posts WHERE id = ?",
            (post_id,),
        )
    elif all_posts:
        posts = db.execute(
            "SELECT id, title, body, html_body, status, publish_category FROM posts WHERE status IN ('approved', 'draft') ORDER BY id"
        )
    else:
        # approved만 기본 대상
        posts = db.execute(
            "SELECT id, title, body, html_body, status, publish_category FROM posts WHERE status = 'approved' ORDER BY id"
        )

    if not posts:
        print("📭 리뷰할 포스트가 없습니다.")
        return

    print(f"🔍 휴먼 리뷰 시작 ({len(posts)}개 포스트)")
    print("=" * 60)

    humanizer = Humanizer(db) if fix else None
    total_issues = 0

    for p in posts:
        p = dict(p)
        body = p.get("body", "")
        if not body:
            continue

        print(f"\n📝 #{p['id']} [{p['status']}] {p['title'][:45]}...")

        # 패턴 감지
        review = detect_ai_patterns(body)
        total_issues += len(review.issues)

        # 점수 표시 (색상 바)
        score = review.score
        if score >= 80:
            bar_color = "🟢"
        elif score >= 60:
            bar_color = "🟡"
        else:
            bar_color = "🔴"
        filled = score // 5
        empty = 20 - filled
        bar = "█" * filled + "░" * empty
        print(f"   {bar_color} 점수: [{bar}] {score}/100")

        if review.issues:
            for iss in review.issues:
                sev_bar = "●" * min(iss["severity"], 10)
                print(f"   ⚠️  [{iss['category']}] {iss['detail']}")
                print(f"      심각도: {sev_bar} ({iss['severity']}/10)")

        # --fix 옵션: 실제 수정 적용
        if fix and humanizer and review.needs_rewrite:
            print(f"   🔄 리라이팅 실행 중...")
            # DB에서 실제 키워드 조회 (keyword_id → keywords 테이블)
            keyword = ""
            kw_row = db.execute(
                "SELECT k.keyword FROM keywords k JOIN posts p ON p.keyword_id = k.id WHERE p.id = ?",
                (p["id"],),
            )
            if kw_row:
                keyword = kw_row[0]["keyword"] if isinstance(kw_row[0], dict) else kw_row[0][0]
            else:
                # fallback: 제목에서 추출
                kw_parts = p["title"].split()
                keyword = kw_parts[0] if kw_parts else ""
            print(f"   📌 타겟 키워드: \"{keyword}\"")

            fixed_body, post_review = humanizer.review_and_fix(
                body, p["title"], keyword, force_rewrite=True
            )

            if fixed_body != body:
                # HTML 재변환
                from modules.generator.content_engine import ContentEngine
                # ContentEngine은 anthropic 필요 — HTML 변환만 사용
                import types
                from modules.generator import content_engine as ce_mod
                import re as re_module

                class DummyEngine:
                    pass

                engine = DummyEngine()
                for method_name in ['_convert_to_html', '_convert_tables_to_html', '_build_html_table',
                                    '_insert_info_cards', '_create_summary_card', '_create_highlight_box',
                                    '_create_checklist_card', '_create_cta_card']:
                    method = getattr(ce_mod.ContentEngine, method_name)
                    setattr(engine, method_name, types.MethodType(method, engine))

                html_body = engine._convert_to_html(fixed_body)
                html_body = engine._insert_info_cards(html_body, p["title"], keyword)

                # 제목 중복 제거
                html_body = re_module.sub(
                    r'<p style="font-size: 16px;[^"]*">\s*#\s+[^<]+</p>\s*',
                    '', html_body, count=1
                )

                # DB 업데이트
                db.execute(
                    "UPDATE posts SET body = ?, html_body = ? WHERE id = ?",
                    (fixed_body, html_body, p["id"]),
                )
                print(f"   ✅ 수정 완료! (점수: {review.score} → {post_review.score})")
            else:
                print(f"   ℹ️  리라이팅 결과가 원본과 동일 (변경 없음)")
        elif fix and review.needs_rewrite is False:
            print(f"   ✅ 점수 양호 — 수정 불필요")

    print(f"\n{'=' * 60}")
    print(f"📊 전체 결과: {len(posts)}개 포스트, {total_issues}개 이슈 감지")
    if not fix and total_issues > 0:
        print(f"   💡 수정하려면: python main.py review --fix")


# ============================================================
# 메인
# ============================================================

def main():
    """CLI 엔트리포인트"""
    # 환경 설정
    settings.ensure_dirs()
    setup_logger(settings.LOG_LEVEL, settings.LOG_DIR)

    parser = argparse.ArgumentParser(
        description="NaverBlogAutoPilot - 네이버 블로그 자동 발행 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python main.py init-db                  # DB 초기화
  python main.py crawl --limit 5          # 기사 5개 크롤링
  python main.py research                 # 키워드 분석
  python main.py generate --count 1       # 포스트 1개 생성
  python main.py review                   # AI 감지 회피 검토
  python main.py review --fix             # 검토 + 자동 수정
  python main.py publish                  # 발행
  python main.py monitor                  # 순위 추적
  python main.py report --type weekly     # 주간 리포트
  python main.py schedule                 # 자동 스케줄러
  python main.py status                   # 상태 확인
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="실행할 명령")

    # init-db
    subparsers.add_parser("init-db", help="데이터베이스 초기화")

    # crawl
    crawl_parser = subparsers.add_parser("crawl", help="silmu.kr 크롤링")
    crawl_parser.add_argument("--limit", type=int, default=None, help="크롤링할 기사 수 제한")

    # research
    subparsers.add_parser("research", help="키워드 분석")

    # generate
    gen_parser = subparsers.add_parser("generate", help="포스트 생성")
    gen_parser.add_argument("--count", type=int, default=1, help="생성할 포스트 수")
    gen_parser.add_argument("--category", type=str, default=None, help="카테고리 지정 (예: 계약/조달)")

    # review (NEW: 휴먼 리뷰)
    review_parser = subparsers.add_parser("review", help="AI 감지 회피 검토 (휴먼 리뷰)")
    review_parser.add_argument("--id", type=int, default=None, help="특정 포스트 ID만 검토")
    review_parser.add_argument("--fix", action="store_true", help="감지된 문제를 자동 수정 (Claude API 사용)")
    review_parser.add_argument("--all", action="store_true", help="draft 포함 전체 검토")

    # publish
    publish_parser = subparsers.add_parser("publish", help="블로그 발행")
    publish_parser.add_argument("--force", action="store_true", help="안티디텍션 간격 체크 무시 (테스트용)")
    publish_parser.add_argument("--skip-review", action="store_true", help="발행 전 휴먼 리뷰 스킵")

    # monitor
    subparsers.add_parser("monitor", help="순위 추적")

    # report
    report_parser = subparsers.add_parser("report", help="리포트 생성")
    report_parser.add_argument("--type", choices=["weekly", "monthly"], default="weekly", help="리포트 타입")

    # schedule
    subparsers.add_parser("schedule", help="자동 스케줄러 시작")

    # status
    subparsers.add_parser("status", help="현재 상태 확인")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # 환경변수 검증 (init-db, status 제외)
    if args.command not in ("init-db", "status"):
        missing = settings.validate()
        if missing and args.command not in ("crawl",):
            print(f"⚠️  필수 환경변수 누락: {', '.join(missing)}")
            print(f"   .env 파일을 확인하세요.")
            if args.command in ("publish", "generate"):
                sys.exit(1)

    # 명령 실행
    commands = {
        "init-db": cmd_init_db,
        "crawl": cmd_crawl,
        "research": cmd_research,
        "generate": cmd_generate,
        "review": cmd_review,
        "publish": cmd_publish,
        "monitor": cmd_monitor,
        "report": cmd_report,
        "schedule": cmd_schedule,
        "status": cmd_status,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
