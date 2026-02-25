"""
블로그 포스트 콘텐츠 생성 엔진
Claude AI API를 활용한 블로그 포스트 자동 생성
"""

import json
import re
from typing import Optional
from jinja2 import Environment, FileSystemLoader
from utils.database import Database
from utils.logger import get_logger
from config.settings import settings
from models.blog_config import BlogConfig


logger = get_logger()
MAX_REGENERATION = 3


class ContentEngine:
    """
    Claude AI API를 활용한 블로그 포스트 콘텐츠 생성 엔진

    삼중 API 호출 프로세스:
    1. 5개의 제목 생성 후 최고 점수 선택
    2. SEO 최적화된 본문 생성 (2000-3000 자)
    3. SEO 검토 및 점수 확인 (70점 미만시 최대 3회 재생성)
    """

    def __init__(self, db: Optional[Database] = None, blog_config: Optional[BlogConfig] = None):
        """
        콘텐츠 엔진 초기화

        Args:
            db: 데이터베이스 인스턴스
            blog_config: 블로그 설정 (제공 시 블로그별 시스템 프롬프트 사용)
        """
        import anthropic
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.CLAUDE_MODEL
        self.max_tokens = settings.CLAUDE_MAX_TOKENS
        self.db = db or Database(settings.DB_PATH)
        self.blog_config = blog_config
        self._setup_templates()

    def _setup_templates(self):
        """Jinja2 템플릿 환경 설정"""
        template_dir = settings.BASE_DIR / "templates" / "prompts"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

        # 블로그별 시스템 프롬프트 사용 (blog_config 제공 시)
        if self.blog_config and self.blog_config.system_prompt:
            self.system_prompt = self.blog_config.system_prompt
            logger.info(f"블로그 '{self.blog_config.display_name}'의 시스템 프롬프트 사용")
            return

        # 기본 시스템 프롬프트 (하위 호환성)
        from datetime import datetime
        current_year = datetime.now().year

        self.system_prompt = f"""당신은 교육행정·지방자치단체 실무 전문 블로그 작성자입니다.

## 핵심 원칙
1. **SEO 최적화 우선**: 네이버 검색 알고리즘(C-RANK, DIA+, AUTH.GR, AI.BRIEFING) 최적화
2. **실무자 관점**: 공무원, 학교 행정직이 실무에 바로 적용할 수 있는 정보 제공
3. **법적 정확성**: 법령, 시행령, 시행규칙 인용 시 정확성 필수
4. **가독성 최우선**: 전문 용어를 알기 쉽게 풀어 설명
5. **최신 정보 제공**: 현재 연도는 {current_year}년입니다. 모든 제목과 내용에서 과거 연도(2024, 2025 등)를 {current_year}년으로 변경하세요.

## 작성 규칙

### 구조 (D.I.A+ 알고리즘 최적화)
- H2 소제목(##)을 최소 3개 이상 사용
- 각 섹션은 300~500자 분량
- **마크다운 표(table)를 1개 이상 반드시 포함** (| 구분자 사용)
- FAQ 섹션을 마지막에 추가 (Q&A 3개)

### SEO 최적화
- 타겟 키워드 밀도 1.5~2.5%
- 키워드를 제목과 첫 문단에 반드시 포함
- 관련 키워드도 자연스럽게 배치
- 본문 길이 2000~3000자

### 법령 인용
- 법령명은 「」로 감싸기 (예: 「지방계약법」)
- 조항은 정확히 명시 (예: 제25조 제1항)
- 출처를 명확히 표기

### 문체
- 반말 사용 ("~합니다" → "~해요", "~됩니다" → "~돼요")
- 친근하지만 전문적인 톤
- 불필요한 수식어 제거
- 능동태 우선, 수동태 최소화

### 금지사항
- AI 냄새 나는 표현 금지: "또한", "따라서", "즉", "물론" 등 과도한 접속사
- 원본 기사 표절 금지 (30% 미만 유사도)
- 추상적 표현 금지 (구체적 숫자, 사례 활용)
- 불필요한 인사말 금지 ("안녕하세요" 등)
- **과거 연도 사용 금지**: 제목과 본문에 2024, 2025 등 과거 연도를 사용하지 말고, 항상 {current_year}년을 사용하세요.

위 규칙을 모두 준수하여 작성하세요."""

    async def generate_post(self, article: dict, keyword: dict) -> dict:
        """
        전체 블로그 포스트 생성

        Args:
            article: 원본 기사 정보 {id, title, clean_text, category, url}
            keyword: 키워드 정보 {id, keyword, total_score}

        Returns:
            생성된 포스트 정보
        """
        kw_text = keyword.get("keyword", "") if keyword else ""
        article_id = article.get("id", 0)
        keyword_id = keyword.get("id", 0) if keyword else None
        content = article.get("clean_text", article.get("content", ""))
        self._article_url = article.get("url", "")

        logger.info(f"포스트 생성 시작: article_id={article_id}, keyword={kw_text}")

        try:
            # 1단계: 제목 생성 및 선택
            titles = self._generate_titles(content, kw_text)
            best_title = self._select_best_title(titles, kw_text)
            logger.info(f"선택된 제목: {best_title}")

            # 2단계: 본문 생성
            body = self._generate_body(best_title, content, kw_text)
            logger.info(f"본문 생성 완료: {len(body)} 자")

            # 3단계: SEO 검토 및 재생성 루프
            seo_result = self._review_seo(best_title, body, kw_text)
            regeneration_count = 0

            while seo_result.get("score", 0) < 70 and regeneration_count < MAX_REGENERATION:
                regeneration_count += 1
                logger.warning(f"SEO 점수 {seo_result.get('score', 0)} 미만, 재생성 {regeneration_count}/{MAX_REGENERATION}")
                body = self._generate_body(best_title, content, kw_text)
                seo_result = self._review_seo(best_title, body, kw_text)

            # 3.5단계: 법령·규정 검증 (hallucination 방지)
            body = self._verify_legal_references(body, content)

            # 4단계: 휴먼라이징 검토 (AI 감지 회피)
            try:
                from modules.generator.humanizer import Humanizer
                humanizer = Humanizer(self.db)
                body, human_review = humanizer.review_and_fix(body, best_title, kw_text)
                logger.info(f"휴먼 리뷰 점수: {human_review.score}/100 (이슈 {len(human_review.issues)}개)")
            except Exception as e:
                logger.warning(f"휴먼라이징 단계 스킵: {e}")

            # 4.5단계: 이미지 생성 (썸네일 + 본문 이미지)
            thumbnail_path = None
            body_image_path = None
            try:
                from modules.generator.image_generator import ImageGenerator
                image_gen = ImageGenerator()

                # 썸네일 생성
                thumbnail_path = await image_gen.generate_thumbnail(kw_text, best_title)

                # 본문 이미지 생성
                body_image_path = await image_gen.generate_body_image(kw_text, body[:500])

                logger.info(f"이미지 생성 완료: thumbnail={thumbnail_path}, body={body_image_path}")
            except Exception as e:
                logger.warning(f"이미지 생성 스킵: {e}")

            # HTML 변환
            html_body = self._convert_to_html(body)

            # 이미지 삽입 (본문 시작 부분)
            if body_image_path:
                html_body = self._insert_body_image(html_body, str(body_image_path))

            # 인포그래픽 카드 삽입 (첫 번째 H2 앞 + 마지막 H2 앞)
            html_body = self._insert_info_cards(html_body, best_title, kw_text)

            # 비용 계산
            generation_cost = self._estimate_cost(
                input_tokens=seo_result.get("input_tokens", 0),
                output_tokens=seo_result.get("output_tokens", 0),
            )

            # 블로그 ID (BlogConfig에서 가져오거나 기본값 1)
            blog_id = self.blog_config.id if self.blog_config else 1

            # 데이터베이스 저장
            post_id = self.db.insert(
                """INSERT INTO posts
                   (article_id, keyword_id, title, body, html_body,
                    seo_score, keyword_density, word_count, generation_cost, status, publish_category, blog_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    article_id,
                    keyword_id,
                    best_title,
                    body,
                    html_body,
                    seo_result.get("score", 0),
                    seo_result.get("keyword_density", 0),
                    len(body),
                    generation_cost,
                    "draft",
                    "",  # publish_category는 main.py에서 설정
                    blog_id,
                ),
            )

            # 법령 인용 추출 및 DB 저장 (실무 블로그만)
            legal_citations_count = 0
            if self.blog_config is None or self.blog_config.theme == "education_admin":
                try:
                    from modules.legal.verifier import LegalVerifier
                    verifier = LegalVerifier(self.db)
                    legal_result = verifier.process_post(post_id, body)
                    legal_citations_count = legal_result["saved"]
                    if legal_citations_count:
                        logger.info(f"법령 인용 {legal_citations_count}개 저장됨 (포스트 {post_id})")
                except Exception as e:
                    logger.warning(f"법령 인용 저장 실패: {e}")

            post_data = {
                "id": post_id,
                "article_id": article_id,
                "keyword_id": keyword_id,
                "title": best_title,
                "body": body,
                "html_body": html_body,
                "seo_score": seo_result.get("score", 0),
                "keyword_density": seo_result.get("keyword_density", 0),
                "word_count": len(body),
                "generation_cost": generation_cost,
                "status": "draft",
                "legal_citations_count": legal_citations_count,
            }

            logger.info(f"포스트 생성 완료: id={post_id}, SEO 점수={seo_result.get('score', 0)}")
            return post_data

        except Exception as e:
            logger.error(f"포스트 생성 실패: {str(e)}")
            raise

    def _generate_titles(self, content: str, keyword: str) -> list[str]:
        """5개의 블로그 포스트 제목 생성"""
        logger.info("제목 생성 시작")

        try:
            template = self.env.get_template("blog_post_v1.txt")
            prompt = template.render(
                task="title_generation",
                article_content=content[:500],
                keyword=keyword,
                search_volume=0,
            )
        except Exception:
            prompt = f"""다음 내용을 바탕으로 네이버 블로그 포스트 제목 5개를 작성하세요.
키워드: {keyword}
내용 요약: {content[:500]}

요구사항:
- 키워드를 반드시 제목에 포함
- 클릭율이 높을 만한 제목
- 번호를 붙여서 작성 (1. 2. 3. 4. 5.)
"""

        # 프롬프트 캐싱 적용
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )

        titles = self._parse_titles(response.content[0].text)
        logger.info(f"생성된 제목 {len(titles)}개: {titles}")
        return titles

    def _select_best_title(self, titles: list[str], keyword: str) -> str:
        """5개 제목 중 최고 점수의 제목 선택"""
        if not titles:
            return f"{keyword} 완벽 가이드"

        if len(titles) == 1:
            return titles[0]

        logger.info("최적 제목 선택 중")

        titles_text = "\n".join([f"{i+1}. {title}" for i, title in enumerate(titles)])

        prompt = f"""다음 블로그 포스트 제목들 중에서 SEO 최적화와 클릭율이 가장 높을 것 같은 제목을 선택하세요.
키워드: {keyword}

제목 목록:
{titles_text}

선택된 제목의 번호만 답하세요 (예: 3)"""

        # 프롬프트 캐싱 적용
        response = self.client.messages.create(
            model=self.model,
            max_tokens=100,
            system=[
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )

        selected_index = self._parse_selection(response.content[0].text)
        selected_title = titles[selected_index - 1] if 1 <= selected_index <= len(titles) else titles[0]
        logger.info(f"선택된 제목: {selected_title}")
        return selected_title

    def _generate_body(self, title: str, content: str, keyword: str) -> str:
        """SEO 최적화된 본문 생성 (2000-3000 자)"""
        logger.info("본문 생성 시작")

        article_url = getattr(self, "_article_url", "")

        try:
            template = self.env.get_template("blog_post_v1.txt")
            prompt = template.render(
                task="body_generation",
                title=title,
                article_content=content,
                keyword=keyword,
                keyword_density_target=2.0,
                min_length=2000,
                max_length=3000,
                article_url=article_url,
            )
        except Exception:
            link_text = f"\n- 글 하단에 참고자료 링크 포함: [실무.kr]({article_url})" if article_url else ""
            prompt = f"""다음 정보를 바탕으로 네이버 블로그 포스트 본문을 작성하세요.

제목: {title}
키워드: {keyword}
참고 내용: {content[:2000]}

요구사항:
- 2000~3000자 분량
- 키워드 밀도 1.5~2.5%
- H2 소제목 3개 이상 포함
- 전문적이면서 읽기 쉬운 문체
- 실무 관점의 실용적 정보 포함{link_text}
"""

        # 프롬프트 캐싱 적용 (90% 비용 절감)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"}  # 캐싱 활성화
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )

        body = response.content[0].text
        logger.info(f"본문 생성 완료: {len(body)} 자")
        return body

    def _review_seo(self, title: str, body: str, keyword: str) -> dict:
        """생성된 포스트의 SEO 점수 검토"""
        logger.info("SEO 검토 시작")

        # 키워드 밀도 직접 계산 (API 호출 없이)
        body_length = len(body)
        keyword_count = body.count(keyword) if keyword else 0
        keyword_density = (keyword_count * len(keyword) / body_length * 100) if body_length > 0 and keyword else 0.0

        # 점수 계산 (규칙 기반)
        score = 50  # 기본 점수

        # 1. 제목에 키워드 포함 (+15)
        if keyword and keyword in title:
            score += 15

        # 2. 첫 100자에 키워드 포함 (+10)
        if keyword and keyword in body[:100]:
            score += 10

        # 3. 키워드 밀도 1.0~3.0% (+15)
        if 1.0 <= keyword_density <= 3.0:
            score += 15
        elif 0.5 <= keyword_density < 1.0 or 3.0 < keyword_density <= 4.0:
            score += 8

        # 4. H2 소제목 3개 이상 (+10)
        h2_count = len(re.findall(r"^##\s+", body, re.MULTILINE))
        if h2_count >= 3:
            score += 10
        elif h2_count >= 1:
            score += 5

        # 5. 본문 길이 2000자 이상 (+10)
        if body_length >= 2000:
            score += 10
        elif body_length >= 1500:
            score += 5

        # 6. silmu.kr 링크 포함 (+5)
        if "silmu.kr" in body:
            score += 5

        logger.info(f"SEO 검토 완료: 점수={score}, 키워드밀도={keyword_density:.2f}%, H2={h2_count}개")

        result = {
            "score": min(score, 100),
            "keyword_density": round(keyword_density, 2),
            "input_tokens": 0,
            "output_tokens": 0,
        }

        logger.info(f"SEO 검토 완료: 점수={result.get('score', 0)}")
        return result

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Claude API 사용 비용 추정"""
        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0
        return round(input_cost + output_cost, 6)

    def _parse_titles(self, content: str) -> list[str]:
        """응답에서 제목 목록 추출"""
        titles = []
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line and any(line.startswith(f"{i}.") for i in range(1, 6)):
                title = line.split(". ", 1)[1] if ". " in line else line
                if title:
                    titles.append(title)
        return titles[:5]

    def _parse_selection(self, content: str) -> int:
        """응답에서 선택 번호 추출"""
        match = re.search(r"\d+", content)
        return int(match.group()) if match else 1

    def _convert_to_html(self, body: str) -> str:
        """
        마크다운 형식의 본문을 네이버 블로그 최적화 HTML로 변환.

        네이버 블로그 SmartEditor ONE 특성:
        - 인라인 style만 지원 (CSS class 미지원)
        - 큰 글씨, 색상 강조로 가독성 확보
        - 모바일 최적화 (반응형 테이블, 큰 폰트)
        """
        import re as re_module

        html = body

        # 마크다운 테이블 → HTML 테이블 변환 (다른 변환보다 먼저 처리)
        html = self._convert_tables_to_html(html)

        # H2 변환 (네이버 블로그 스타일: 큰 글씨 + 좌측 색상 바)
        html = re_module.sub(
            r"^## (.+)$",
            r'<div style="border-left: 4px solid #2DB400; padding: 8px 0 8px 16px; margin: 32px 0 16px 0;">'
            r'<span style="font-size: 22px; font-weight: bold; color: #1a1a1a; line-height: 1.4;">\1</span></div>',
            html, flags=re_module.MULTILINE
        )
        # H3 변환 (중간 소제목)
        html = re_module.sub(
            r"^### (.+)$",
            r'<p style="font-size: 18px; font-weight: bold; color: #333; margin: 24px 0 8px 0; '
            r'padding-bottom: 6px; border-bottom: 2px solid #e8e8e8;">\1</p>',
            html, flags=re_module.MULTILINE
        )
        # 마크다운 링크 변환
        html = re_module.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            r'<a href="\2" target="_blank" style="color: #2DB400; text-decoration: underline; font-weight: bold;">\1</a>',
            html,
        )
        # Bold 변환 (강조색 적용)
        html = re_module.sub(
            r"\*\*(.+?)\*\*",
            r'<strong style="color: #d63031; font-weight: bold;">\1</strong>',
            html,
        )
        # Italic 변환
        html = re_module.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

        # 단락 처리 (큰 폰트 + 줄간격)
        paragraphs = html.split("\n\n")
        processed = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            if p.startswith("<"):
                # 이미 HTML 태그로 시작하는 것은 그대로
                processed.append(p)
            else:
                processed.append(
                    f'<p style="font-size: 16px; line-height: 1.8; color: #333; margin: 12px 0;">{p}</p>'
                )

        return "\n".join(processed)

    def _convert_tables_to_html(self, text: str) -> str:
        """마크다운 테이블을 네이버 블로그용 HTML 테이블로 변환"""
        import re as re_module

        lines = text.split("\n")
        result = []
        table_lines = []
        in_table = False

        for line in lines:
            stripped = line.strip()
            # 테이블 행 감지: | 로 시작하고 | 로 끝나는 줄
            if stripped.startswith("|") and stripped.endswith("|"):
                # 구분선 (|---|---|) 은 건너뛰기
                inner = stripped[1:-1]  # 양쪽 | 제거
                if all(c in "-|: " for c in inner) and "-" in inner:
                    if not in_table:
                        in_table = True
                    continue
                in_table = True
                # 셀 분리
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                table_lines.append(cells)
            else:
                # 테이블 끝 → HTML로 변환
                if in_table and table_lines:
                    result.append(self._build_html_table(table_lines))
                    table_lines = []
                    in_table = False
                result.append(line)

        # 마지막에 테이블이 남아 있으면 변환
        if table_lines:
            result.append(self._build_html_table(table_lines))

        return "\n".join(result)

    def _build_html_table(self, rows: list) -> str:
        """테이블 행 데이터를 네이버 블로그 프리미엄 스타일 HTML 테이블로 변환"""
        if not rows:
            return ""

        table_style = (
            'style="border-collapse: collapse; width: 100%; margin: 24px 0; '
            'font-size: 15px; border: 2px solid #2DB400; border-radius: 8px; '
            'overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08);"'
        )
        th_style = (
            'style="background-color: #2DB400; color: white; padding: 14px 16px; '
            'border: 1px solid #28a745; text-align: center; font-weight: bold; '
            'font-size: 15px; letter-spacing: 0.5px;"'
        )

        html = f"<table {table_style}>\n"

        # 첫 번째 행 = 헤더
        html += "<thead><tr>\n"
        for cell in rows[0]:
            html += f"  <th {th_style}>{cell}</th>\n"
        html += "</tr></thead>\n"

        # 나머지 행 = 본문 (교차 색상)
        if len(rows) > 1:
            html += "<tbody>\n"
            for i, row in enumerate(rows[1:]):
                bg_color = "#f7faf7" if i % 2 == 0 else "#ffffff"
                tr_style = f'style="background-color: {bg_color};"'
                html += f"<tr {tr_style}>\n"
                for j, cell in enumerate(row):
                    # 첫 번째 열은 볼드+색상
                    if j == 0:
                        td_s = (
                            'style="padding: 12px 16px; border: 1px solid #e0e0e0; '
                            'text-align: left; font-weight: bold; color: #2DB400; font-size: 15px;"'
                        )
                    else:
                        td_s = (
                            'style="padding: 12px 16px; border: 1px solid #e0e0e0; '
                            'text-align: left; color: #333; font-size: 15px; line-height: 1.5;"'
                        )
                    html += f"  <td {td_s}>{cell}</td>\n"
                html += "</tr>\n"
            html += "</tbody>\n"

        html += "</table>"
        return html

    def _insert_info_cards(self, html_body: str, title: str, keyword: str) -> str:
        """본문에 시각적 인포그래픽 카드를 삽입 (이미지 대체)"""
        import re as re_module

        # 핵심 요약 카드 (본문 맨 앞에 삽입)
        summary_card = self._create_summary_card(title, keyword)

        # 체크리스트 카드 (마지막 섹션 앞에 삽입)
        checklist_card = self._create_checklist_card(keyword)

        # 중요 포인트 강조 박스 (중간에 삽입)
        highlight_box = self._create_highlight_box(keyword)

        # H2 스타일 div 위치 찾기 (border-left: 4px solid #2DB400)
        h2_pattern = r'<div style="border-left: 4px solid #2DB400'
        h2_positions = [m.start() for m in re_module.finditer(h2_pattern, html_body)]

        if len(h2_positions) >= 3:
            # 마지막 섹션 앞에 체크리스트
            html_body = html_body[:h2_positions[-1]] + checklist_card + "\n" + html_body[h2_positions[-1]:]
            # 중간 섹션 앞에 강조 박스
            mid = len(h2_positions) // 2
            html_body = html_body[:h2_positions[mid]] + highlight_box + "\n" + html_body[h2_positions[mid]:]
        elif len(h2_positions) >= 2:
            html_body = html_body[:h2_positions[-1]] + checklist_card + "\n" + html_body[h2_positions[-1]:]

        # 맨 앞에 요약 카드 삽입
        html_body = summary_card + "\n" + html_body

        # 맨 뒤에 CTA 카드 추가
        cta_card = self._create_cta_card(keyword)
        html_body = html_body + "\n" + cta_card

        return html_body

    def _create_summary_card(self, title: str, keyword: str) -> str:
        """핵심 요약 카드 (상단 배너 스타일)"""
        return f'''<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; padding: 28px 32px; margin: 10px 0 28px 0; color: white;">
<p style="font-size: 13px; letter-spacing: 3px; margin: 0 0 10px 0; opacity: 0.85; text-transform: uppercase;">📌 핵심 요약</p>
<p style="font-size: 20px; font-weight: bold; margin: 0 0 14px 0; line-height: 1.5;">{title}</p>
<p style="font-size: 14px; margin: 0; padding-top: 14px; border-top: 1px solid rgba(255,255,255,0.3); opacity: 0.9;">🔑 키워드: <strong>{keyword}</strong> · 실무자를 위한 핵심 정리</p>
</div>'''

    def _create_highlight_box(self, keyword: str) -> str:
        """중요 포인트 강조 박스 (파란색 테마)"""
        return f'''<div style="background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%); border: 2px solid #42a5f5; border-radius: 12px; padding: 24px 28px; margin: 28px 0;">
<p style="font-size: 17px; font-weight: bold; color: #1565c0; margin: 0 0 14px 0;">💡 꼭 알아두세요!</p>
<p style="font-size: 15px; color: #333; margin: 0; line-height: 1.9;">
{keyword} 관련 업무를 처리할 때는 <strong style="color: #d63031;">관련 법령의 최신 개정 여부</strong>를 반드시 확인해야 합니다.
특히 금액 기준이나 절차가 변경되었을 수 있으므로, 실무 적용 전에 원문을 꼭 확인하세요.
</p>
</div>'''

    def _create_checklist_card(self, keyword: str) -> str:
        """실무 체크리스트 카드 (노란색 테마)"""
        return f'''<div style="background-color: #FFF8E1; border-left: 5px solid #FFC107; border-radius: 0 12px 12px 0; padding: 24px 28px; margin: 28px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
<p style="font-size: 17px; font-weight: bold; color: #F57F17; margin: 0 0 14px 0;">⚡ 실무 체크리스트</p>
<p style="font-size: 15px; color: #333; margin: 0; line-height: 2.0;">
✅ {keyword} 관련 법령·규정을 반드시 확인하세요<br>
✅ 담당부서 협의 및 결재 절차를 사전에 파악하세요<br>
✅ 관련 서식과 양식을 미리 준비해 두세요<br>
✅ <strong style="color: #d63031;">최신 개정사항</strong>을 실무.kr에서 확인하세요
</p>
</div>'''

    def _create_cta_card(self, keyword: str) -> str:
        """하단 CTA (Call-to-Action) 카드"""
        return f'''<div style="background: linear-gradient(135deg, #2DB400 0%, #1a8a00 100%); border-radius: 16px; padding: 28px 32px; margin: 32px 0 10px 0; color: white; text-align: center;">
<p style="font-size: 18px; font-weight: bold; margin: 0 0 12px 0;">📚 더 많은 실무 정보가 필요하신가요?</p>
<p style="font-size: 15px; margin: 0 0 16px 0; opacity: 0.9;">학교회계·계약·예산 관련 최신 실무 자료를 확인하세요</p>
<p style="margin: 0;"><a href="https://silmu.kr" target="_blank" style="display: inline-block; background: white; color: #2DB400; font-weight: bold; font-size: 16px; padding: 12px 32px; border-radius: 30px; text-decoration: none;">실무.kr 바로가기 →</a></p>
</div>'''

    def _verify_legal_references(self, body: str, original_content: str) -> str:
        """
        생성된 본문의 법령·규정 인용을 검증하고 수정

        전략:
        1. 본문에서 법령 인용 패턴 추출
        2. 원본 기사에 있는 법령과 대조
        3. 원본에 없는 법령은 Claude에게 검증 요청
        4. 확인 불가한 법령은 안전한 표현으로 대체
        """
        import re as re_module

        logger.info("법령·규정 검증 시작")

        # 통용 약칭 목록 (검증 불필요)
        ACCEPTED_ABBREVIATIONS = {
            "지방계약법", "국가계약법", "지방재정법", "국가재정법",
            "학교회계법", "물품관리법", "공유재산법", "건설기술진흥법",
            "지방계약법 시행령", "국가계약법 시행령", "지방재정법 시행령",
            "지방계약법 시행규칙", "국가계약법 시행규칙",
        }

        # 1. 본문에서 법령 인용 추출
        law_patterns = [
            r'「[^」]+」',                          # 「법률명」
            r'제\d+조(?:의\d+)?(?:\s*제\d+항)?',    # 제OO조, 제OO조의2, 제OO조 제O항
        ]

        found_laws = []
        for pattern in law_patterns:
            found_laws.extend(re_module.findall(pattern, body))

        if not found_laws:
            logger.info("법령 인용 없음, 검증 스킵")
            return body

        # 2. 원본 기사에 있는 법령 추출
        original_laws = []
        for pattern in law_patterns:
            original_laws.extend(re_module.findall(pattern, original_content))
        original_laws_set = set(original_laws)

        # 3. 원본에 없는 법령 식별 (통용 약칭은 제외)
        unverified_laws = []
        for law in found_laws:
            if law in original_laws_set:
                continue
            # 「」 안의 내용 추출하여 약칭 확인
            inner = law.strip("「」")
            if inner in ACCEPTED_ABBREVIATIONS:
                continue
            unverified_laws.append(law)

        if not unverified_laws:
            logger.info(f"모든 법령 인용이 확인됨: {len(found_laws)}개 (원본+통용약칭)")
            return body

        logger.warning(f"원본에 없는 법령 {len(unverified_laws)}개 발견: {unverified_laws}")

        # 4. Claude API로 검증 (구체적 조문번호만 검증)
        # 법률명만 있는 것(제OO조 없는 것)은 스킵
        laws_to_verify = [law for law in set(unverified_laws)
                          if re_module.search(r'제\d+조', law)]

        if not laws_to_verify:
            logger.info("구체적 조문번호 없음, 검증 스킵")
            return body

        try:
            verification_prompt = f"""다음 법령 조문이 실제로 존재하고 정확한지 검증해주세요.

검증 대상:
{chr(10).join(f'- {law}' for law in laws_to_verify)}

맥락: 공무원 계약·조달·예산·복무 관련 블로그 글에서 인용된 조문입니다.

반드시 아래 형식으로만 응답하세요 (한 줄에 하나, 부가 설명 없이):
법령내용 | 정확
법령내용 | 부정확 | 올바른조문(짧게)
법령내용 | 확인불가"""

            response = self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": verification_prompt}],
            )

            verification_text = response.content[0].text
            logger.info(f"법령 검증 응답:\n{verification_text}")

            # 5. 부정확한 법령 수정 또는 제거
            for line in verification_text.strip().split("\n"):
                if "|" not in line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 2:
                    continue

                law_text = parts[0]
                judgment = parts[1]

                if "부정확" in judgment and len(parts) >= 3:
                    correction = parts[2].strip()
                    # 수정값이 50자 이하이고 법령 형식일 때만 교체
                    if correction and len(correction) <= 50 and law_text in body:
                        body = body.replace(law_text, correction, 1)
                        logger.info(f"법령 수정: '{law_text}' → '{correction}'")
                    elif law_text in body:
                        # 수정값이 너무 길면 조문번호만 제거
                        safe_ref = re_module.sub(r'\s*제\d+조(?:의\d+)?(?:\s*제\d+항)?', '', law_text)
                        if safe_ref:
                            body = body.replace(law_text, f"{safe_ref} 관련 규정", 1)
                            logger.info(f"법령 안전 처리: '{law_text}' → '{safe_ref} 관련 규정'")

                elif "확인불가" in judgment:
                    safe_ref = re_module.sub(r'\s*제\d+조(?:의\d+)?(?:\s*제\d+항)?', '', law_text)
                    if safe_ref and law_text in body:
                        body = body.replace(law_text, f"{safe_ref} 관련 규정", 1)
                        logger.info(f"법령 안전 처리: '{law_text}' → '{safe_ref} 관련 규정'")

            logger.info("법령 검증 완료")

        except Exception as e:
            logger.warning(f"법령 검증 API 실패: {e}, 안전 모드 적용")
            for law in set(laws_to_verify):
                # 구체적 조문번호가 원본에 없으면 조문번호만 제거
                safe_ref = re_module.sub(r'\s*제\d+조(?:의\d+)?(?:\s*제\d+항)?', '', law)
                if safe_ref and law in body:
                    body = body.replace(law, f"{safe_ref} 관련 규정", 1)
                    logger.info(f"안전 모드: '{law}' → '{safe_ref} 관련 규정'")

        return body

    def _insert_body_image(self, html_body: str, image_path: str) -> str:
        """
        본문 이미지 삽입 (첫 번째 단락 또는 H2 앞에 삽입)

        Args:
            html_body: HTML 본문
            image_path: 이미지 파일 경로

        Returns:
            이미지가 삽입된 HTML
        """
        import re as re_module

        # 이미지 태그 생성 (네이버 블로그 최적화)
        img_tag = f'''<div style="text-align: center; margin: 32px 0;">
    <img src="{image_path}" alt="본문 이미지" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
</div>'''

        # 첫 번째 H2 앞에 삽입 (가장 자연스러운 위치)
        h2_pattern = r'<div style="border-left: 4px solid #2DB400'
        match = re_module.search(h2_pattern, html_body)

        if match:
            # 첫 번째 H2 앞에 삽입
            insert_pos = match.start()
            html_body = html_body[:insert_pos] + img_tag + "\n" + html_body[insert_pos:]
            logger.info("본문 이미지 삽입 완료 (첫 번째 H2 앞)")
        else:
            # H2가 없으면 첫 번째 <p> 태그 뒤에 삽입
            p_pattern = r'</p>'
            match = re_module.search(p_pattern, html_body)
            if match:
                insert_pos = match.end()
                html_body = html_body[:insert_pos] + "\n" + img_tag + html_body[insert_pos:]
                logger.info("본문 이미지 삽입 완료 (첫 번째 단락 뒤)")

        return html_body
