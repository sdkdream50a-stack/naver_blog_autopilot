"""
API 엔드포인트
"""

from flask import Blueprint, jsonify, request, session
from utils.database import Database
from config.settings import settings
import asyncio
import threading

bp = Blueprint('api', __name__)


def get_current_blog_id():
    """현재 선택된 블로그 ID 반환"""
    db = Database(settings.DB_PATH)

    # 세션에서 blog_id 가져오기
    blog_id = session.get('current_blog_id')

    if not blog_id:
        # 세션에 없으면 첫 번째 활성 블로그 사용
        blog = db.get_blog()
        if blog:
            blog_id = blog['id']
            session['current_blog_id'] = blog_id
        else:
            blog_id = 1  # 기본값

    return blog_id


@bp.route('/stats')
def get_stats():
    """전체 통계 조회 (현재 블로그)"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    # 총 포스트 수
    total_posts = db.count('posts', f"blog_id={blog_id}")

    # 발행된 포스트 수
    published_posts = db.count('posts', f"blog_id={blog_id} AND status='published'")

    # 초안 포스트 수
    draft_posts = db.count('posts', f"blog_id={blog_id} AND status='draft'")

    # 승인된 포스트 수
    approved_posts = db.count('posts', f"blog_id={blog_id} AND status='approved'")

    # 평균 SEO 점수
    avg_seo_result = db.execute(
        "SELECT AVG(seo_score) as avg_score FROM posts WHERE blog_id=? AND seo_score > 0",
        (blog_id,)
    )
    avg_seo_score = round(avg_seo_result[0]['avg_score'], 1) if avg_seo_result and avg_seo_result[0]['avg_score'] else 0

    # 총 비용 (이번 달)
    total_cost_result = db.execute(
        "SELECT SUM(generation_cost) as total FROM posts WHERE blog_id=? AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')",
        (blog_id,)
    )
    total_cost = round(total_cost_result[0]['total'], 0) if total_cost_result and total_cost_result[0]['total'] else 0

    # 예산 사용률
    monthly_budget = settings.MAX_POSTS_PER_WEEK * 4 * 60  # 주간 5개 * 4주 * 60원/포스트 = 1,200원
    budget_usage = round((total_cost / monthly_budget * 100), 1) if monthly_budget > 0 else 0

    stats = {
        'total_posts': total_posts,
        'published_posts': published_posts,
        'draft_posts': draft_posts,
        'approved_posts': approved_posts,
        'total_views': 0,  # TODO: 네이버 블로그 API 연동 후 구현
        'avg_seo_score': avg_seo_score,
        'total_cost': total_cost,
        'monthly_budget': monthly_budget,
        'budget_usage': budget_usage,
    }

    return jsonify(stats)


@bp.route('/chart/daily')
def get_daily_chart():
    """일별 차트 데이터 (최근 7일)"""
    db = Database(settings.DB_PATH)
    from datetime import datetime, timedelta

    # 최근 7일 날짜 및 카운트 초기화
    labels = []
    data_counts = []

    for i in range(7):
        date = datetime.now() - timedelta(days=6-i)
        date_str = date.strftime('%Y-%m-%d')
        label = date.strftime('%-m/%-d')
        labels.append(label)

        # 해당 날짜의 포스트 수 조회
        count = db.count('posts', f"DATE(created_at) = '{date_str}'")
        data_counts.append(count)

    data = {
        'labels': labels,
        'datasets': [
            {
                'label': '생성 수',
                'data': data_counts,
                'borderColor': 'rgb(75, 192, 192)',
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'tension': 0.1,
                'fill': True
            }
        ]
    }

    return jsonify(data)


@bp.route('/activity/recent')
def get_recent_activity():
    """최근 활동 (최근 10개)"""
    db = Database(settings.DB_PATH)

    # 최근 포스트 10개 조회
    recent_posts = db.execute("""
        SELECT
            id,
            title,
            status,
            created_at
        FROM posts
        ORDER BY created_at DESC
        LIMIT 10
    """)

    activities = []
    for post in recent_posts:
        activities.append({
            'id': post['id'],
            'type': 'post_created',
            'title': post['title'],
            'timestamp': post['created_at'],
            'status': post['status']
        })

    return jsonify(activities)


@bp.route('/posts')
def get_posts():
    """포스트 목록 (페이지네이션) - 현재 블로그"""
    from flask import request
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    # 쿼리 파라미터
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    status = request.args.get('status', '')  # draft, approved, published
    offset = (page - 1) * limit

    # WHERE 절 구성 (blog_id 필터 추가)
    where_clause = "WHERE p.blog_id = ?"
    params = [blog_id]

    if status:
        where_clause += " AND status = ?"
        params.append(status)

    # 총 개수 조회
    count_where = where_clause.replace('WHERE p.blog_id = ?', f'blog_id = {blog_id}')
    if status:
        count_where = count_where.replace(' AND status = ?', f" AND status = '{status}'")
    total = db.count('posts', count_where.replace('WHERE ', ''))

    # 포스트 목록 조회
    query = f"""
        SELECT
            p.id,
            p.title,
            k.keyword,
            p.seo_score,
            p.status,
            p.created_at
        FROM posts p
        LEFT JOIN keywords k ON p.keyword_id = k.id
        {where_clause}
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """
    posts_data = db.execute(query, tuple(params) + (limit, offset))

    posts = []
    for post in posts_data:
        posts.append({
            'id': post['id'],
            'title': post['title'],
            'keyword': post['keyword'] if post['keyword'] else '',
            'seo_score': round(post['seo_score'], 1) if post['seo_score'] else 0,
            'status': post['status'],
            'created_at': post['created_at']
        })

    return jsonify({
        'posts': posts,
        'total': total,
        'page': page,
        'limit': limit,
        'total_pages': (total + limit - 1) // limit
    })


@bp.route('/generate', methods=['POST'])
def generate_post():
    """포스트 생성 (백그라운드)"""
    from app.routes.sse import send_event

    # 요청 데이터
    data = request.get_json() or {}
    count = data.get('count', 1)
    category = data.get('category', '계약/조달')

    # 백그라운드 스레드로 실행
    def run_generation():
        import asyncio
        from modules.generator.content_engine import ContentEngine
        from utils.logger import get_logger

        logger = get_logger()
        blog_id = get_current_blog_id()

        try:
            # SSE 이벤트: 시작
            send_event('workflow.started', {
                'title': f'{category} 카테고리 포스트 {count}개 생성',
                'count': count,
                'category': category,
                'blog_id': blog_id
            })

            # Content Engine 초기화 (블로그별 설정 적용)
            db = Database(settings.DB_PATH)
            blog_data = db.get_blog(blog_id=blog_id)
            blog_config = None
            if blog_data:
                from models.blog_config import BlogConfig
                blog_config = BlogConfig.from_db_row(blog_data)
                logger.info(f"블로그 '{blog_config.display_name}'의 설정을 Content Engine에 적용")

            engine = ContentEngine(db, blog_config=blog_config)

            generated_posts = []

            for i in range(count):
                try:
                    # 1단계: 원본 기사 조회
                    send_event('workflow.progress', {
                        'step': 1,
                        'progress': 25,
                        'message': f'[{i+1}/{count}] 원본 콘텐츠 조회 중...'
                    })

                    # DB에서 처리되지 않은 기사 가져오기 (현재 블로그)
                    articles = db.execute("""
                        SELECT a.id, a.title, a.url, a.category, p.clean_text
                        FROM articles a
                        LEFT JOIN processed_articles p ON a.id = p.article_id
                        WHERE a.blog_id = ?
                        AND a.id NOT IN (SELECT article_id FROM posts WHERE article_id IS NOT NULL AND blog_id = ?)
                        AND p.clean_text IS NOT NULL
                        LIMIT 1
                    """, (blog_id, blog_id))

                    if not articles:
                        logger.warning(f"블로그 {blog_id}에 사용 가능한 기사가 없습니다")
                        send_event('workflow.failed', {
                            'error': '크롤링된 기사가 없습니다. 먼저 크롤러를 실행해주세요.'
                        })
                        return

                    article = dict(articles[0])

                    # 2단계: 키워드 선택 (현재 블로그)
                    keywords = db.execute("""
                        SELECT id, keyword, total_score
                        FROM keywords
                        WHERE blog_id = ?
                        ORDER BY total_score DESC
                        LIMIT 1
                    """, (blog_id,))

                    keyword = dict(keywords[0]) if keywords else None

                    # 3단계: AI 콘텐츠 생성
                    send_event('workflow.progress', {
                        'step': 2,
                        'progress': 50,
                        'message': f'[{i+1}/{count}] AI 콘텐츠 생성 중...'
                    })

                    # 비동기 함수 실행
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    post_data = loop.run_until_complete(
                        engine.generate_post(article, keyword)
                    )
                    loop.close()

                    # 4단계: 품질 검증
                    send_event('workflow.progress', {
                        'step': 3,
                        'progress': 75,
                        'message': f'[{i+1}/{count}] SEO 및 품질 검증 중...'
                    })

                    # 이미 검증 완료 (content_engine에서 수행)
                    generated_posts.append(post_data)

                    logger.info(f"포스트 생성 완료: {post_data['title']}")

                except Exception as post_error:
                    logger.error(f"포스트 생성 실패: {post_error}")
                    continue

            # 5단계: 완료
            send_event('workflow.completed', {
                'message': f'{len(generated_posts)}개 포스트 생성 완료',
                'count': len(generated_posts),
                'posts': [{'id': p['id'], 'title': p['title']} for p in generated_posts]
            })

        except Exception as e:
            logger.error(f"워크플로우 실패: {e}")
            send_event('workflow.failed', {
                'error': str(e)
            })

    # 백그라운드 실행
    thread = threading.Thread(target=run_generation)
    thread.daemon = True
    thread.start()

    return jsonify({
        'status': 'started',
        'message': f'{count}개 포스트 생성 시작'
    })


@bp.route('/posts/<int:post_id>')
def get_post_detail(post_id):
    """포스트 상세 조회 - 현재 블로그"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    post = db.execute("""
        SELECT
            p.*,
            k.keyword
        FROM posts p
        LEFT JOIN keywords k ON p.keyword_id = k.id
        WHERE p.id = ? AND p.blog_id = ?
    """, (post_id, blog_id))

    if not post:
        return jsonify({'error': '포스트를 찾을 수 없습니다'}), 404

    post_data = dict(post[0])
    return jsonify(post_data)


@bp.route('/posts/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    """포스트 수정 - 현재 블로그"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()
    data = request.get_json()

    # 필수 필드 확인
    if 'title' not in data or 'body' not in data:
        return jsonify({'error': '제목과 본문은 필수입니다'}), 400

    # 포스트 존재 확인 (blog_id도 확인)
    existing = db.execute("SELECT id FROM posts WHERE id = ? AND blog_id = ?", (post_id, blog_id))
    if not existing:
        return jsonify({'error': '포스트를 찾을 수 없습니다'}), 404

    # 업데이트
    db.execute("""
        UPDATE posts
        SET title = ?, body = ?, html_body = ?
        WHERE id = ? AND blog_id = ?
    """, (data['title'], data['body'], data['body'], post_id, blog_id))  # TODO: 마크다운 → HTML 변환

    return jsonify({
        'status': 'success',
        'message': '포스트가 수정되었습니다'
    })


@bp.route('/posts/<int:post_id>/regenerate', methods=['POST'])
def regenerate_post(post_id):
    """포스트 재생성"""
    from app.routes.sse import send_event

    # 포스트 존재 확인
    db = Database(settings.DB_PATH)
    post = db.execute("SELECT id, title FROM posts WHERE id = ?", (post_id,))
    if not post:
        return jsonify({'error': '포스트를 찾을 수 없습니다'}), 404

    # 백그라운드 재생성
    def run_regeneration():
        try:
            send_event('workflow.started', {
                'title': f'포스트 재생성: {post[0]["title"]}',
                'post_id': post_id
            })

            # TODO: 실제 재생성 로직 (content_engine 호출)
            import time
            time.sleep(2)

            send_event('workflow.completed', {
                'message': '포스트 재생성 완료',
                'post_id': post_id
            })

        except Exception as e:
            send_event('workflow.failed', {
                'error': str(e)
            })

    thread = threading.Thread(target=run_regeneration)
    thread.daemon = True
    thread.start()

    return jsonify({
        'status': 'started',
        'message': '포스트 재생성이 시작되었습니다'
    })


@bp.route('/posts/<int:post_id>/approve', methods=['POST'])
def approve_post(post_id):
    """포스트 승인 (draft → approved)"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    post = db.execute("SELECT id, status FROM posts WHERE id = ? AND blog_id = ?", (post_id, blog_id))
    if not post:
        return jsonify({'error': '포스트를 찾을 수 없습니다'}), 404
    if post[0]['status'] == 'published':
        return jsonify({'error': '이미 발행된 포스트입니다'}), 400

    db.execute("UPDATE posts SET status = 'approved' WHERE id = ? AND blog_id = ?", (post_id, blog_id))
    return jsonify({'status': 'success', 'message': '포스트가 승인되었습니다'})


@bp.route('/posts/<int:post_id>/reject', methods=['POST'])
def reject_post(post_id):
    """포스트 반려 (approved → draft)"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    post = db.execute("SELECT id, status FROM posts WHERE id = ? AND blog_id = ?", (post_id, blog_id))
    if not post:
        return jsonify({'error': '포스트를 찾을 수 없습니다'}), 404

    db.execute("UPDATE posts SET status = 'draft' WHERE id = ? AND blog_id = ?", (post_id, blog_id))
    return jsonify({'status': 'success', 'message': '포스트가 반려되었습니다'})


@bp.route('/posts/<int:post_id>/publish', methods=['POST'])
def publish_post(post_id):
    """포스트 발행 (approved → published, 네이버 블로그 자동 발행)"""
    from app.routes.sse import send_event

    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    post = db.execute(
        "SELECT * FROM posts p LEFT JOIN keywords k ON p.keyword_id = k.id WHERE p.id = ? AND p.blog_id = ?",
        (post_id, blog_id)
    )
    if not post:
        return jsonify({'error': '포스트를 찾을 수 없습니다'}), 404
    if post[0]['status'] != 'approved':
        return jsonify({'error': '승인된 포스트만 발행할 수 있습니다 (현재 상태: ' + post[0]['status'] + ')'}), 400

    data = request.get_json() or {}
    publish_category = data.get('category', '')

    post_data = dict(post[0])
    post_data['publish_category'] = publish_category

    def run_publish():
        try:
            send_event('publish.started', {'post_id': post_id, 'title': post_data['title']})

            import asyncio
            from modules.publisher.selenium_poster import NaverBlogPoster
            poster = NaverBlogPoster(db)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(poster.publish(post_data))
            loop.close()

            if result['success']:
                db.execute(
                    "UPDATE posts SET status = 'published' WHERE id = ?", (post_id,)
                )
                send_event('publish.completed', {
                    'post_id': post_id,
                    'blog_url': result['blog_url'],
                    'message': '발행 완료'
                })
            else:
                send_event('publish.failed', {
                    'post_id': post_id,
                    'error': result['error']
                })
        except Exception as e:
            send_event('publish.failed', {'post_id': post_id, 'error': str(e)})

    import threading
    thread = threading.Thread(target=run_publish)
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'started', 'message': '발행이 시작되었습니다'})


@bp.route('/posts/<int:post_id>/publish-history')
def get_publish_history(post_id):
    """포스트 발행 이력 조회"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    post = db.execute("SELECT id FROM posts WHERE id = ? AND blog_id = ?", (post_id, blog_id))
    if not post:
        return jsonify({'error': '포스트를 찾을 수 없습니다'}), 404

    history = db.execute(
        "SELECT * FROM posting_history WHERE post_id = ? ORDER BY published_at DESC",
        (post_id,)
    )
    return jsonify([dict(h) for h in history])


@bp.route('/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    """포스트 삭제 - 현재 블로그"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    # 포스트 존재 확인 (blog_id도 확인)
    existing = db.execute("SELECT id FROM posts WHERE id = ? AND blog_id = ?", (post_id, blog_id))
    if not existing:
        return jsonify({'error': '포스트를 찾을 수 없습니다'}), 404

    # 삭제
    db.execute("DELETE FROM posts WHERE id = ? AND blog_id = ?", (post_id, blog_id))

    return jsonify({
        'status': 'success',
        'message': '포스트가 삭제되었습니다'
    })


@bp.route('/schedule')
def get_schedule():
    """스케줄 설정 조회"""
    # TODO: DB 또는 파일에서 로드
    schedule = {
        'crawl': {
            'enabled': True,
            'time': settings.SCHEDULE_CRAWL_HOUR
        },
        'publish': {
            'enabled': True,
            'times': settings.SCHEDULE_PUBLISH_HOURS,
            'days': ['월', '화', '수', '목', '금'],
            'max_per_day': settings.MAX_POSTS_PER_DAY
        },
        'monitor': {
            'enabled': True,
            'time': settings.SCHEDULE_MONITOR_HOUR
        }
    }

    return jsonify(schedule)


@bp.route('/schedule', methods=['PUT'])
def update_schedule():
    """스케줄 설정 업데이트"""
    data = request.get_json()

    # TODO: DB 또는 파일에 저장
    # 실제로는 APScheduler에 반영하거나 설정 파일 업데이트 필요

    return jsonify({
        'status': 'success',
        'message': '스케줄이 저장되었습니다'
    })


@bp.route('/settings')
def get_settings():
    """설정 조회"""
    # TODO: DB 또는 파일에서 로드
    settings_data = {
        'api_keys': {
            'claude': settings.ANTHROPIC_API_KEY[:20] + '...' if settings.ANTHROPIC_API_KEY else '',
            'gemini': settings.GEMINI_API_KEY[:20] + '...' if settings.GEMINI_API_KEY else '',
            'naver_client_id': settings.NAVER_CLIENT_ID,
            'naver_client_secret': settings.NAVER_CLIENT_SECRET[:5] + '...' if settings.NAVER_CLIENT_SECRET else ''
        },
        'limits': {
            'max_posts_per_day': settings.MAX_POSTS_PER_DAY,
            'max_posts_per_week': settings.MAX_POSTS_PER_WEEK,
            'min_interval_hours': settings.MIN_INTERVAL_HOURS
        },
        'quality': {
            'min_seo_score': settings.MIN_SEO_SCORE,
            'min_human_score': 90,  # TODO: settings에 추가
            'plagiarism_threshold': int(settings.PLAGIARISM_THRESHOLD * 100),
            'max_regeneration': settings.MAX_REGENERATION
        },
        'notifications': {
            'on_error': True,
            'on_publish': True,
            'on_rank_change': True,
            'on_budget_warning': True
        }
    }

    return jsonify(settings_data)


@bp.route('/settings', methods=['PUT'])
def update_settings():
    """설정 업데이트"""
    data = request.get_json()

    # TODO: DB 또는 .env 파일에 저장

    return jsonify({
        'status': 'success',
        'message': '설정이 저장되었습니다'
    })


@bp.route('/notifications')
def get_notifications():
    """알림 목록 조회"""
    # TODO: DB에서 실제 알림 조회
    notifications = [
        {
            'id': 1,
            'type': 'info',
            'title': '포스트 발행 완료',
            'message': '2024 수의계약 한도액과 입찰 방법 총정리',
            'timestamp': '2026-02-24 20:59:09',
            'read': False
        }
    ]

    return jsonify(notifications)


@bp.route('/notifications/<int:notification_id>/read', methods=['PUT'])
def mark_notification_read(notification_id):
    """알림 읽음 처리"""
    # TODO: DB 업데이트

    return jsonify({
        'status': 'success',
        'message': '알림이 읽음 처리되었습니다'
    })


# ===== 멀티 블로그 API =====

@bp.route('/blogs')
def get_blogs():
    """모든 활성 블로그 목록 조회"""
    db = Database(settings.DB_PATH)
    blogs = db.list_blogs(active_only=True)
    return jsonify(blogs)


@bp.route('/blogs/current')
def get_current_blog():
    """현재 선택된 블로그 조회"""
    from flask import session

    db = Database(settings.DB_PATH)

    # 세션에서 현재 블로그 ID 가져오기
    blog_id = session.get('current_blog_id')

    if not blog_id:
        # 세션에 없으면 첫 번째 활성 블로그 사용
        blog = db.get_blog()
        if blog:
            session['current_blog_id'] = blog['id']
            return jsonify(blog)
        else:
            return jsonify({'error': '활성 블로그가 없습니다'}), 404

    # 세션에 있으면 해당 블로그 반환
    blog = db.get_blog(blog_id=blog_id)
    if blog:
        return jsonify(blog)
    else:
        # 블로그가 삭제되었거나 비활성화된 경우
        session.pop('current_blog_id', None)
        return jsonify({'error': '블로그를 찾을 수 없습니다'}), 404


@bp.route('/blogs/current', methods=['PUT'])
def set_current_blog():
    """현재 블로그 전환"""
    from flask import session

    data = request.get_json()
    blog_id = data.get('blog_id')

    if not blog_id:
        return jsonify({'error': 'blog_id가 필요합니다'}), 400

    # 블로그 존재 확인
    db = Database(settings.DB_PATH)
    blog = db.get_blog(blog_id=blog_id)

    if not blog:
        return jsonify({'error': '블로그를 찾을 수 없습니다'}), 404

    if not blog.get('active'):
        return jsonify({'error': '비활성화된 블로그입니다'}), 400

    # 세션에 저장
    session['current_blog_id'] = blog_id

    return jsonify({
        'status': 'success',
        'message': f'블로그가 {blog["display_name"]}(으)로 전환되었습니다',
        'blog': blog
    })


# ===== 법령 검증 API (#20) =====

@bp.route('/posts/<int:post_id>/legal')
def get_legal_citations(post_id):
    """포스트의 법령 인용 목록 조회"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    # 포스트 존재 및 권한 확인
    post = db.execute("SELECT id, title FROM posts WHERE id = ? AND blog_id = ?", (post_id, blog_id))
    if not post:
        return jsonify({'error': '포스트를 찾을 수 없습니다'}), 404

    from modules.legal.verifier import LegalVerifier
    verifier = LegalVerifier(db)
    citations = verifier.get_post_citations(post_id)

    # 요약 통계
    status_counts = {'pending': 0, 'verified': 0, 'failed': 0, 'warning': 0}
    for c in citations:
        s = c.get('verification_status', 'pending')
        status_counts[s] = status_counts.get(s, 0) + 1

    return jsonify({
        'post_id': post_id,
        'post_title': post[0]['title'],
        'citations': citations,
        'summary': status_counts,
        'total': len(citations),
    })


@bp.route('/posts/<int:post_id>/legal/extract', methods=['POST'])
def extract_legal_citations(post_id):
    """포스트 본문에서 법령 인용 추출 후 DB 저장"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    post = db.execute("SELECT id, body FROM posts WHERE id = ? AND blog_id = ?", (post_id, blog_id))
    if not post:
        return jsonify({'error': '포스트를 찾을 수 없습니다'}), 404

    from modules.legal.verifier import LegalVerifier
    verifier = LegalVerifier(db)
    result = verifier.process_post(post_id, post[0]['body'])

    return jsonify({
        'status': 'success',
        'saved': result['saved'],
        'citations': result['citations'],
    })


@bp.route('/posts/<int:post_id>/legal/verify', methods=['POST'])
def verify_legal_citations(post_id):
    """저장된 법령 인용을 Claude API로 검증 (백그라운드)"""
    from app.routes.sse import send_event

    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    post = db.execute("SELECT id, title FROM posts WHERE id = ? AND blog_id = ?", (post_id, blog_id))
    if not post:
        return jsonify({'error': '포스트를 찾을 수 없습니다'}), 404

    # 인용이 없으면 먼저 추출
    count = db.count('legal_references', f'post_id = {post_id}')
    if count == 0:
        post_body = db.execute("SELECT body FROM posts WHERE id = ?", (post_id,))
        if post_body:
            from modules.legal.verifier import LegalVerifier
            verifier = LegalVerifier(db)
            verifier.process_post(post_id, post_body[0]['body'])

    def run_verification():
        try:
            send_event('legal.started', {'post_id': post_id, 'title': post[0]['title']})

            from modules.legal.verifier import LegalVerifier
            verifier = LegalVerifier(db)
            result = verifier.verify_post(post_id)

            send_event('legal.completed', {
                'post_id': post_id,
                'result': result,
            })
        except Exception as e:
            send_event('legal.failed', {'post_id': post_id, 'error': str(e)})

    import threading
    thread = threading.Thread(target=run_verification)
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'started', 'message': '법령 검증이 시작되었습니다'})


# ===== 모니터링 API (Phase 2) =====

@bp.route('/monitor/stats')
def get_monitor_stats():
    """모니터링 종합 통계 조회"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    # 발행 이력
    published = db.execute(
        """SELECT COUNT(*) as cnt FROM posting_history ph
           JOIN posts p ON ph.post_id = p.id
           WHERE ph.publish_status = 'success' AND p.blog_id = ?""",
        (blog_id,)
    )
    published_count = published[0]['cnt'] if published else 0

    # 최근 발행 목록 (최대 10개)
    recent = db.execute(
        """SELECT p.id, p.title, p.seo_score, k.keyword,
                  ph.blog_url, ph.published_at, ph.publish_status
           FROM posting_history ph
           JOIN posts p ON ph.post_id = p.id
           LEFT JOIN keywords k ON p.keyword_id = k.id
           WHERE p.blog_id = ?
           ORDER BY ph.published_at DESC LIMIT 10""",
        (blog_id,)
    )

    # 순위 통계
    rank_stats = db.execute(
        """SELECT AVG(rh.naver_rank) as avg_rank,
                  MIN(rh.naver_rank) as best_rank,
                  COUNT(*) as check_count
           FROM ranking_history rh
           JOIN posts p ON rh.post_id = p.id
           WHERE rh.naver_rank IS NOT NULL AND p.blog_id = ?""",
        (blog_id,)
    )

    avg_rank = None
    best_rank = None
    if rank_stats and rank_stats[0]['check_count'] > 0:
        avg_rank = round(rank_stats[0]['avg_rank'], 1) if rank_stats[0]['avg_rank'] else None
        best_rank = rank_stats[0]['best_rank']

    # 이번 달 생성 비용
    cost = db.execute(
        """SELECT SUM(generation_cost) as total FROM posts
           WHERE blog_id = ? AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')""",
        (blog_id,)
    )
    monthly_cost = round(cost[0]['total'] or 0, 0) if cost else 0

    return jsonify({
        'published_count': published_count,
        'recent_posts': [dict(r) for r in recent],
        'avg_rank': avg_rank,
        'best_rank': best_rank,
        'monthly_cost': monthly_cost,
    })


@bp.route('/monitor/rankings')
def get_rankings():
    """순위 이력 조회"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    rows = db.execute(
        """SELECT rh.*, p.title, k.keyword as kw
           FROM ranking_history rh
           JOIN posts p ON rh.post_id = p.id
           LEFT JOIN keywords k ON p.keyword_id = k.id
           WHERE p.blog_id = ?
           ORDER BY rh.checked_at DESC LIMIT 50""",
        (blog_id,)
    )
    return jsonify([dict(r) for r in rows])


@bp.route('/monitor/check-rankings', methods=['POST'])
def check_rankings():
    """현재 블로그의 발행 포스트 순위 체크 (백그라운드)"""
    from app.routes.sse import send_event

    blog_id = get_current_blog_id()

    def run_check():
        try:
            import asyncio
            from modules.monitor.ranking_tracker import RankingTracker
            db = Database(settings.DB_PATH)
            tracker = RankingTracker(db)

            send_event('monitor.started', {'message': '순위 체크 시작'})
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(tracker.check_rankings())
            loop.close()

            send_event('monitor.completed', {
                'message': f'{len(results)}개 포스트 순위 체크 완료',
                'results': results
            })
        except Exception as e:
            send_event('monitor.failed', {'error': str(e)})

    import threading
    thread = threading.Thread(target=run_check)
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'started', 'message': '순위 체크 시작'})


@bp.route('/monitor/report')
def get_report():
    """주간/월간 리포트 생성"""
    period = request.args.get('period', 'weekly')
    from modules.monitor.report_generator import ReportGenerator
    db = Database(settings.DB_PATH)
    gen = ReportGenerator(db)

    if period == 'monthly':
        path = gen.generate_monthly_report()
    else:
        path = gen.generate_weekly_report()

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    return jsonify({'period': period, 'path': path, 'content': content})


# ===== 크롤러 API (Phase 3) =====

@bp.route('/crawl/status')
def get_crawl_status():
    """크롤링 현황 조회"""
    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    articles = db.count('articles', f'blog_id = {blog_id}')
    processed = db.execute(
        """SELECT COUNT(*) as cnt FROM processed_articles pa
           JOIN articles a ON pa.article_id = a.id
           WHERE a.blog_id = ?""", (blog_id,)
    )
    processed_count = processed[0]['cnt'] if processed else 0

    # 최근 크롤링 로그 (현재 블로그만)
    logs = db.execute(
        "SELECT * FROM crawl_log WHERE blog_id = ? ORDER BY crawled_at DESC LIMIT 10",
        (blog_id,)
    )

    # 미사용 기사 (아직 포스트로 변환 안 된 것)
    unused = db.execute(
        """SELECT COUNT(*) as cnt FROM articles a
           JOIN processed_articles pa ON a.id = pa.article_id
           WHERE a.blog_id = ?
           AND a.id NOT IN (SELECT article_id FROM posts WHERE article_id IS NOT NULL AND blog_id = ?)""",
        (blog_id, blog_id)
    )
    unused_count = unused[0]['cnt'] if unused else 0

    return jsonify({
        'total_articles': articles,
        'processed': processed_count,
        'unused': unused_count,
        'recent_logs': [dict(l) for l in logs],
    })


@bp.route('/crawl/run', methods=['POST'])
def run_crawl():
    """크롤러 실행 (백그라운드)"""
    from app.routes.sse import send_event

    db = Database(settings.DB_PATH)
    blog_id = get_current_blog_id()

    data = request.get_json() or {}
    crawl_type = data.get('type', 'all')  # all, law, news

    blog = db.get_blog(blog_id=blog_id)
    if not blog:
        return jsonify({'error': '블로그 설정을 찾을 수 없습니다'}), 404

    def run_crawler():
        try:
            import asyncio
            from modules.collector.silmu_crawler import SilmuCrawler
            from modules.collector.data_cleaner import DataCleaner

            send_event('crawl.started', {
                'blog_id': blog_id,
                'type': crawl_type,
                'message': f'크롤링 시작 ({crawl_type})'
            })

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            crawler = SilmuCrawler(db, blog_id=blog_id)
            articles = loop.run_until_complete(crawler.run())

            send_event('crawl.progress', {
                'message': f'기사 {len(articles)}개 수집, 정제 중...',
                'collected': len(articles)
            })

            cleaner = DataCleaner(db)
            processed = cleaner.process_all(blog_id=blog_id)

            loop.close()

            send_event('crawl.completed', {
                'collected': len(articles),
                'processed': processed,
                'message': f'{len(articles)}개 수집, {processed}개 정제 완료'
            })
        except Exception as e:
            send_event('crawl.failed', {'error': str(e)})

    import threading
    thread = threading.Thread(target=run_crawler)
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'started', 'message': '크롤링이 시작되었습니다'})
