"""
네이버 블로그 포스트 발행 자동화 (Playwright 기반)
- SmartEditor ONE 대응
- 디버깅 스크린샷 지원
"""

import asyncio
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from utils.database import Database
from utils.logger import get_logger
from config.settings import settings

logger = get_logger()

# 디버깅용 스크린샷 저장 디렉토리
DEBUG_DIR = Path(settings.DATA_DIR) / "debug_screenshots"


class NaverBlogPoster:
    """네이버 블로그에 포스트를 발행하는 자동화 클래스"""

    def __init__(self, db: Optional[Database] = None):
        """초기화"""
        self.db = db or Database(settings.DB_PATH)
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.blog_id = settings.NAVER_BLOG_ID
        self.blog_url = f"https://blog.naver.com/{self.blog_id}"
        self.write_url = f"https://blog.naver.com/{self.blog_id}/postwrite"
        self.cookies_path = getattr(
            settings, "NAVER_COOKIES_PATH",
            str(settings.DATA_DIR / "naver_cookies.json")
        )
        self.playwright = None

    # ──────────────────────────────────────────
    #  공개 메서드
    # ──────────────────────────────────────────
    async def publish(self, post: Dict) -> Dict:
        """포스트를 발행합니다"""
        try:
            title = post.get("title") or post["title"]
            logger.info(f"포스트 발행 시작: {title}")

            await self._init_browser()

            is_logged_in = await self._load_cookies()
            if not is_logged_in:
                logger.info("쿠키 로드 실패, 수동 로그인 필요")
                await self._login()

            blog_post_url = await self._write_post(
                title=title,
                body=post.get("html_body") or post.get("body", ""),
                category=post.get("publish_category", ""),
            )

            # 데이터베이스에 기록
            self.db.insert(
                """INSERT INTO posting_history (post_id, blog_url, publish_status, published_at)
                   VALUES (?, ?, ?, ?)""",
                (post.get("id"), blog_post_url, "success", datetime.now().isoformat()),
            )

            logger.info(f"포스트 발행 성공: {blog_post_url}")
            return {"success": True, "blog_url": blog_post_url, "error": None}

        except Exception as e:
            logger.error(f"포스트 발행 실패: {str(e)}")
            try:
                self.db.insert(
                    """INSERT INTO posting_history (post_id, publish_status, error_message, published_at)
                       VALUES (?, ?, ?, ?)""",
                    (post.get("id"), "failed", str(e), datetime.now().isoformat()),
                )
            except Exception as db_error:
                logger.error(f"데이터베이스 기록 실패: {db_error}")

            return {"success": False, "blog_url": None, "error": str(e)}

        finally:
            await self._close()

    # ──────────────────────────────────────────
    #  브라우저 관리
    # ──────────────────────────────────────────
    async def _init_browser(self):
        """브라우저 초기화 및 시작"""
        if self.browser is not None:
            return

        logger.info("브라우저 초기화 중")

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            permissions=["clipboard-read", "clipboard-write"],
        )
        self.page = await self.context.new_page()
        logger.info("브라우저 초기화 완료")

    async def _close(self):
        """브라우저 및 리소스 정리"""
        try:
            if self.page:
                await self.page.close()
                self.page = None
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            logger.info("브라우저 종료 완료")
        except Exception as e:
            logger.error(f"브라우저 종료 오류: {e}")

    # ──────────────────────────────────────────
    #  디버깅
    # ──────────────────────────────────────────
    async def _debug_screenshot(self, name: str):
        """디버깅용 스크린샷 저장"""
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%H%M%S")
            path = DEBUG_DIR / f"{ts}_{name}.png"
            await self.page.screenshot(path=str(path), full_page=False)
            logger.info(f"📸 디버깅 스크린샷: {path}")
        except Exception as e:
            logger.warning(f"스크린샷 저장 실패: {e}")

    async def _debug_dump_selectors(self):
        """현재 페이지의 주요 요소를 로그에 덤프"""
        try:
            info = await self.page.evaluate("""() => {
                const result = {};
                result.url = window.location.href;
                result.title_tag = document.title;

                // iframe 목록
                const iframes = document.querySelectorAll('iframe');
                result.iframes = Array.from(iframes).map(f => ({
                    id: f.id, name: f.name, src: f.src?.substring(0, 100),
                    className: f.className
                }));

                // contenteditable 요소들
                const editables = document.querySelectorAll('[contenteditable="true"]');
                result.editables = Array.from(editables).map(e => ({
                    tag: e.tagName, id: e.id, className: e.className?.substring(0, 80),
                    text: e.textContent?.substring(0, 50)
                }));

                // 주요 버튼들
                const buttons = document.querySelectorAll('button, a.btn, input[type="submit"]');
                result.buttons = Array.from(buttons).slice(0, 20).map(b => ({
                    tag: b.tagName, text: b.textContent?.trim()?.substring(0, 30),
                    className: b.className?.substring(0, 60)
                }));

                return result;
            }""")
            logger.info(f"📋 페이지 분석: URL={info.get('url')}")
            logger.info(f"   iframes: {json.dumps(info.get('iframes', []), ensure_ascii=False)}")
            logger.info(f"   editables: {json.dumps(info.get('editables', []), ensure_ascii=False)}")
            logger.info(f"   buttons (first 10): {json.dumps(info.get('buttons', [])[:10], ensure_ascii=False)}")
        except Exception as e:
            logger.warning(f"페이지 분석 실패: {e}")

    # ──────────────────────────────────────────
    #  로그인 / 쿠키
    # ──────────────────────────────────────────
    async def _login(self):
        """네이버 로그인 처리 (수동 로그인)"""
        try:
            logger.info("로그인 페이지로 이동")
            await self.page.goto("https://nid.naver.com/nidlogin.login")

            print("\n🔐 브라우저에서 네이버 로그인을 완료하세요!")
            print("   로그인 후 자동으로 진행됩니다 (5분 타임아웃)\n")
            logger.info("사용자 수동 로그인 대기 중 (5분 타임아웃)")

            # 로그인 성공 = 로그인 페이지에서 벗어남
            await self.page.wait_for_url(
                lambda url: "nidlogin.login" not in url and "nid.naver.com" not in url,
                timeout=5 * 60 * 1000,
            )

            await asyncio.sleep(2)
            logger.info("로그인 감지, 블로그 페이지로 이동 중...")

            await self.page.goto(self.blog_url)
            await self.page.wait_for_load_state("networkidle", timeout=15000)

            logger.info("✅ 로그인 성공")
            await self._save_cookies()

        except Exception as e:
            logger.error(f"로그인 오류: {e}")
            raise

    async def _save_cookies(self):
        """브라우저 쿠키를 파일로 저장"""
        try:
            cookies = await self.context.cookies()
            Path(self.cookies_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.cookies_path, "w") as f:
                json.dump(cookies, f, indent=2)
            logger.info(f"쿠키 저장 완료: {self.cookies_path} ({len(cookies)}개)")
        except Exception as e:
            logger.error(f"쿠키 저장 오류: {e}")

    async def _load_cookies(self) -> bool:
        """파일에서 쿠키를 로드하여 적용"""
        try:
            if not os.path.exists(self.cookies_path):
                logger.warning(f"쿠키 파일 없음: {self.cookies_path}")
                return False

            with open(self.cookies_path, "r") as f:
                cookies = json.load(f)

            if not self.context:
                return False

            await self.context.add_cookies(cookies)
            logger.info(f"쿠키 로드 완료: {len(cookies)}개")

            # 블로그 페이지로 이동하여 로그인 상태 확인
            await self.page.goto(self.blog_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # 로그인 확인: 글쓰기 버튼이나 프로필 영역 존재 여부
            is_logged_in = await self.page.evaluate("""() => {
                // 네이버 블로그 로그인 상태 확인
                const profileArea = document.querySelector(
                    '[class*="profile"], [class*="Profile"], ' +
                    '.area_my, .btn_write, [class*="write"]'
                );
                // 로그인 안 된 경우 로그인 버튼이 있음
                const loginBtn = document.querySelector(
                    'a[href*="nidlogin"], .btn_login, [class*="login"]'
                );
                return profileArea !== null || loginBtn === null;
            }""")

            if is_logged_in:
                logger.info("✅ 쿠키를 통한 로그인 확인")
            else:
                logger.warning("쿠키 로드했지만 로그인 상태가 아님")

            return is_logged_in

        except Exception as e:
            logger.error(f"쿠키 로드 오류: {e}")
            return False

    # ──────────────────────────────────────────
    #  오버레이/팝업 닫기
    # ──────────────────────────────────────────
    async def _close_overlays(self):
        """
        도움말 팝업만 정밀하게 닫습니다.
        에러 로그에서 확인된 차단 요소:
          <h1 class="se-help-title">도움말</h1> from <div class="container__HW_tc">

        주의: [class*="container__"] 같은 넓은 셀렉터를 쓰면
        에디터 본체 컨테이너까지 삭제되므로, 반드시 "도움말" 관련만 타겟합니다.
        """
        closed = await self.page.evaluate("""() => {
            let closed = 0;

            // 1) "도움말" 텍스트를 가진 h1 요소의 상위 오버레이만 제거
            const helpTitles = document.querySelectorAll(
                '.se-help-title, h1'
            );
            for (const h1 of helpTitles) {
                if (h1.textContent?.trim() === '도움말') {
                    // 가장 가까운 오버레이 컨테이너를 찾아서 숨기기
                    let overlay = h1.closest(
                        '[class*="container__"], [class*="help"], ' +
                        '[class*="layer"], [class*="Layer"]'
                    );
                    if (overlay) {
                        overlay.style.display = 'none';
                        closed++;
                    }
                }
            }

            // 2) se-help 클래스를 가진 요소 숨기기
            const seHelps = document.querySelectorAll(
                '.se-help-panel, .se-help-layer, [class*="se-help"]'
            );
            for (const el of seHelps) {
                if (el.offsetParent !== null) {
                    el.style.display = 'none';
                    closed++;
                }
            }

            // 3) 도움말 관련 툴팁만 숨기기 (에디터 본체 아닌 것만)
            const tooltips = document.querySelectorAll('[class*="tooltip"]');
            for (const el of tooltips) {
                const text = el.textContent?.trim() || '';
                // 도움말, 가이드 관련 툴팁만
                if (text.includes('도움말') || text.includes('가이드') || text.includes('안내')) {
                    el.style.display = 'none';
                    closed++;
                }
            }

            return closed;
        }""")

        if closed > 0:
            logger.info(f"🔲 도움말 오버레이 {closed}개 닫기 완료")
            await asyncio.sleep(0.5)
        else:
            logger.debug("닫을 오버레이 없음")

    # ──────────────────────────────────────────
    #  포스트 작성 (SmartEditor ONE 대응)
    # ──────────────────────────────────────────
    async def _dismiss_draft_popup(self):
        """
        '작성 중인 글이 있습니다' 팝업이 뜨면 '취소'를 클릭하여 새 글 작성.
        스크린샷에서 확인됨: 취소/확인 두 버튼이 있는 중앙 다이얼로그.
        """
        try:
            await asyncio.sleep(1)
            # "취소" 버튼 클릭 (새 글 작성)
            dismissed = await self.page.evaluate("""() => {
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    const text = btn.textContent?.trim() || '';
                    if (text === '취소') {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }""")
            if dismissed:
                logger.info("📝 이전 작성 중 글 팝업 → '취소' 클릭 (새 글 작성)")
                await asyncio.sleep(2)
            else:
                logger.debug("작성 중인 글 팝업 없음")
        except Exception as e:
            logger.debug(f"draft 팝업 처리: {e}")

    async def _close_help_panel(self):
        """우측 도움말 패널의 X 닫기 버튼을 클릭합니다."""
        try:
            closed = await self.page.evaluate("""() => {
                // 도움말 패널의 X(닫기) 버튼 찾기
                const closeButtons = document.querySelectorAll(
                    'button[class*="close"], [class*="close"]'
                );
                for (const btn of closeButtons) {
                    // 부모가 도움말 관련 컨테이너인 경우만
                    const parent = btn.closest('[class*="help"], [class*="container__"]');
                    if (parent && parent.textContent?.includes('도움말')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }""")
            if closed:
                logger.info("🔲 도움말 패널 닫기 완료")
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.debug(f"도움말 패널 닫기: {e}")

    async def _write_post(self, title: str, body: str, category: str = "") -> str:
        """
        SmartEditor ONE 기반 네이버 블로그 포스트를 작성·발행합니다.

        실제 UI 흐름 (스크린샷 기반):
        1. postwrite 페이지 로드
        2. "작성 중인 글이 있습니다" 팝업 → "취소" 클릭
        3. 도움말 패널 닫기
        4. 제목 입력 (제목 영역 클릭 후 타이핑)
        5. "소스코드" 툴바 버튼 클릭 → HTML 편집기에서 본문 HTML 붙여넣기
        6. "발행" 버튼 클릭 → 발행 설정 패널
        7. 카테고리 선택 + "발행" 확인
        """
        try:
            logger.info("포스트 작성 페이지로 이동")
            await self.page.goto(self.write_url, wait_until="networkidle")
            await asyncio.sleep(4)  # SPA 로딩 대기

            await self._debug_screenshot("01_write_page_loaded")
            await self._debug_dump_selectors()

            # ── 0. 팝업/오버레이 처리 ──
            await self._dismiss_draft_popup()
            await self._close_help_panel()
            await self._close_overlays()

            await self._debug_screenshot("02_popups_cleared")

            # ── 1. 제목 입력 ──
            await self._input_title(title)
            await asyncio.sleep(1)

            # 제목 입력 후 본문 영역으로 명시적 이동 (Tab 또는 클릭)
            # SE ONE은 제목+본문이 하나의 contenteditable이므로 커서 위치가 중요
            await self.page.keyboard.press("Escape")  # 제목 편집 모드 해제
            await asyncio.sleep(0.3)

            # ── 2. 본문 입력 ──
            await self._input_body(body, title=title)
            await asyncio.sleep(2)

            await self._debug_screenshot("04_content_filled")

            # ── 3. 발행 (카테고리 선택은 발행 패널에서) ──
            blog_post_url = await self._publish_post(category)

            return blog_post_url

        except Exception as e:
            await self._debug_screenshot("error_write_post")
            logger.error(f"포스트 작성 오류: {e}")
            raise

    async def _input_title(self, title: str):
        """제목을 입력합니다 (여러 전략 시도)"""
        logger.info(f"제목 입력: {title}")

        strategies = [
            # 전략 1: SmartEditor ONE 제목 영역 (이전 실행에서 성공한 방법)
            self._input_title_se_one,
            # 전략 2: placeholder로 찾기
            self._input_title_placeholder,
            # 전략 3: 첫 번째 contenteditable 영역 클릭 후 타이핑
            self._input_title_first_editable,
            # 전략 4: 페이지 상단 클릭 후 Tab으로 제목 영역 이동
            self._input_title_tab_navigate,
            # 전략 5: JavaScript로 직접 입력
            self._input_title_js,
        ]

        for i, strategy in enumerate(strategies):
            try:
                result = await strategy(title)
                if result:
                    logger.info(f"✅ 제목 입력 성공 (전략 {i+1})")
                    await self._debug_screenshot("02_title_entered")
                    return
            except Exception as e:
                logger.debug(f"제목 전략 {i+1} 실패: {e}")

        raise Exception("제목 입력 실패: 모든 전략 실패")

    async def _input_title_se_one(self, title: str) -> bool:
        """SmartEditor ONE 제목 영역 (넓은 셀렉터)"""
        selectors = [
            ".se-title-text",
            ".se-component.se-title .se-text-paragraph",
            "span.se-fs36",
            ".se-title .se-text-paragraph span",
            # 추가: 에디터 제목 관련 클래스
            ".se-component.se-documentTitle .se-text-paragraph",
            ".se-documentTitle",
            '[class*="title"] [contenteditable]',
            '[class*="Title"] [contenteditable]',
        ]
        for sel in selectors:
            el = await self.page.query_selector(sel)
            if el:
                await el.click()
                await asyncio.sleep(0.3)
                await self.page.keyboard.press("Control+a")
                await self.page.keyboard.type(title, delay=30)
                return True
        return False

    async def _input_title_tab_navigate(self, title: str) -> bool:
        """에디터 영역 클릭 후 Tab/Shift-Tab으로 제목 위치로 이동"""
        # contenteditable이 1개만 있는 경우, 그 안에서 제목 영역이 맨 위
        editables = await self.page.query_selector_all('[contenteditable="true"]')
        if editables:
            el = editables[0]
            await el.click()
            await asyncio.sleep(0.3)
            # Ctrl+Home으로 맨 위로 이동
            await self.page.keyboard.press("Control+Home")
            await asyncio.sleep(0.2)
            # 전체 선택 후 입력
            await self.page.keyboard.press("Control+a")
            await self.page.keyboard.type(title, delay=30)
            return True
        return False

    async def _input_title_placeholder(self, title: str) -> bool:
        """placeholder 속성으로 제목 입력란 찾기"""
        selectors = [
            'input[placeholder*="제목"]',
            '[placeholder*="제목"]',
            'input[name*="title"]',
            'input[id*="title"]',
        ]
        for sel in selectors:
            el = await self.page.query_selector(sel)
            if el:
                await el.fill(title)
                return True
        return False

    async def _input_title_first_editable(self, title: str) -> bool:
        """첫 번째 contenteditable 영역에 제목 입력"""
        editables = await self.page.query_selector_all('[contenteditable="true"]')
        if editables:
            # 첫 번째 editable은 보통 제목
            await editables[0].click()
            await asyncio.sleep(0.3)
            await self.page.keyboard.press("Control+a")
            await self.page.keyboard.type(title, delay=30)
            return True
        return False

    async def _input_title_js(self, title: str) -> bool:
        """JavaScript로 제목 직접 설정"""
        result = await self.page.evaluate(f"""() => {{
            // SmartEditor ONE 제목 영역 찾기
            const titleEl = document.querySelector(
                '.se-title-text, .se-component.se-title span, ' +
                '[class*="title"] [contenteditable], ' +
                'input[placeholder*="제목"]'
            );
            if (titleEl) {{
                if (titleEl.tagName === 'INPUT') {{
                    titleEl.value = {json.dumps(title)};
                    titleEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }} else {{
                    titleEl.textContent = {json.dumps(title)};
                    titleEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
                return true;
            }}
            return false;
        }}""")
        return result

    async def _input_body(self, body: str, title: str = ""):
        """본문 HTML을 입력합니다 (여러 전략 시도)"""
        logger.info("본문 입력 중...")

        # 본문에서 제목 중복 제거 (핵심 요약 카드 내 제목, h1/h2, 마크다운 헤딩 등)
        body = self._strip_title_from_body(body, title)

        # SE ONE 에디터 구조 디버깅 (전략 실행 전)
        await self._debug_se_one_structure()

        # HTML 서식 유지 전략들 (SE 내부 모델 동기화 필요)
        html_strategies = [
            # 전략 1: SmartEditor 내부 API — 에디터 상태와 완벽 동기화
            ("SmartEditor API", self._input_body_se_api),
            # 전략 2: paste 이벤트 디스패치 (SE ONE paste handler)
            ("paste 이벤트 디스패치", self._input_body_dispatch_paste_event),
            # 전략 3: 실제 시스템 클립보드 + Ctrl+V
            ("시스템 클립보드 Ctrl+V", self._input_body_real_clipboard_paste),
        ]

        for i, (name, strategy) in enumerate(html_strategies):
            try:
                result = await strategy(body)
                if result:
                    has_content = await self._verify_body_content(require_se_model=True)
                    if has_content:
                        logger.info(f"✅ 본문 입력 + SE모델 검증 성공 (전략 {i+1}: {name})")
                        await self._debug_screenshot("03_body_entered")
                        return
                    else:
                        logger.warning(f"전략 {i+1} ({name}): SE 내부 모델에 반영 안 됨, 다음 전략 시도")
            except Exception as e:
                logger.warning(f"본문 전략 {i+1} ({name}) 실패: {e}")

        # HTML 전략 모두 실패 → 페이지 새로고침 후 텍스트 타이핑 (최후수단)
        # 이전 전략들이 에디터 DOM을 오염시켰을 수 있으므로 새 페이지에서 시작
        logger.warning("HTML 전략 모두 실패, 페이지 새로고침 후 텍스트 타이핑 시도...")
        try:
            await self.page.goto(self.write_url, wait_until="networkidle")
            await asyncio.sleep(4)
            await self._dismiss_draft_popup()
            await self._close_help_panel()
            await self._close_overlays()
            await asyncio.sleep(1)
            # 제목 다시 입력
            await self._input_title(title)
            await asyncio.sleep(1)
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.warning(f"페이지 새로고침 실패: {e}")

        # 텍스트 타이핑 (키보드 입력은 SE ONE 파이프라인을 통하므로 DOM-only 검증으로 충분)
        try:
            result = await self._input_body_text_fallback(body)
            if result:
                has_content = await self._verify_body_content(require_se_model=False)
                if has_content:
                    logger.info("✅ 본문 입력 + DOM 검증 성공 (텍스트 타이핑 — 서식 없음)")
                    await self._debug_screenshot("03_body_entered")
                    return
                else:
                    logger.warning("텍스트 타이핑: DOM에도 내용 없음")
        except Exception as e:
            logger.warning(f"텍스트 타이핑 실패: {e}")

        raise Exception("본문 입력 실패: 모든 전략 실패 (검증 포함)")

    def _strip_title_from_body(self, body: str, title: str) -> str:
        """
        본문 HTML에서 제목 중복을 제거합니다.

        SE ONE에서 제목은 별도 필드에 입력되므로, 본문에 포함된 제목 텍스트를
        제거해야 합니다. 제거 대상:

        1. 핵심 요약 카드 내 제목 줄:
           <p style="font-size: 20px; font-weight: bold; ...">제목</p>
        2. <h1>제목</h1> 또는 <h2>제목</h2>
        3. <p># 제목</p> (마크다운 헤딩이 p 태그로 감싸진 경우)
        """
        original = body

        # 1) 핵심 요약 카드 내 제목 줄 제거 (font-size: 18~22px + bold)
        body = re.sub(
            r'<p\s+style="[^"]*font-size:\s*(?:18|19|20|22)px[^"]*font-weight:\s*bold[^"]*"[^>]*>'
            r'[^<]*'
            r'</p>\s*',
            '',
            body,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # font-weight가 font-size 앞에 올 수도 있음
        if body == original:
            body = re.sub(
                r'<p\s+style="[^"]*font-weight:\s*bold[^"]*font-size:\s*(?:18|19|20|22)px[^"]*"[^>]*>'
                r'[^<]*'
                r'</p>\s*',
                '',
                body,
                count=1,
                flags=re.DOTALL | re.IGNORECASE,
            )

        # 2) <h1>...</h1> 또는 <h2>...</h2> 제거
        body = re.sub(r'^\s*<h[12][^>]*>.*?</h[12]>\s*', '', body, count=1, flags=re.DOTALL)

        # 3) <p># 제목</p> 패턴 (마크다운 헤딩)
        body = re.sub(r'^\s*<p>\s*#{1,3}\s+.*?</p>\s*', '', body, count=1, flags=re.DOTALL)

        # 4) 제목 텍스트가 그대로 본문 첫 줄에 있는 경우
        if title and title.strip():
            escaped_title = re.escape(title.strip())
            body = re.sub(
                rf'^\s*<p[^>]*>\s*{escaped_title}\s*</p>\s*',
                '',
                body,
                count=1,
                flags=re.DOTALL,
            )

        if body != original:
            logger.debug("본문에서 제목 중복 제거 완료")
        return body.strip()

    async def _verify_body_content(self, require_se_model: bool = True) -> bool:
        """
        본문 영역에 실제로 내용이 들어갔는지 검증합니다.

        require_se_model=True: SE 내부 모델에 내용이 있어야 통과 (HTML 전략용)
        require_se_model=False: DOM에 내용이 있으면 통과 (키보드 타이핑 전략용)

        키보드 타이핑은 SE ONE 입력 파이프라인을 통하므로
        내부 모델이 자동 업데이트되지만, getContentText()가 즉시 반영하지 않을 수 있음.
        이전 실행에서 텍스트 타이핑 후 발행에 성공한 경험이 있으므로 DOM-only 검증 허용.
        """
        try:
            result = await self.page.evaluate("""() => {
                const output = { domContent: false, seModelContent: false };

                // ── 1) SE ONE 내부 모델 확인 (가장 중요!) ──
                try {
                    let editor = null;
                    if (window.SmartEditor && typeof window.SmartEditor.getEditor === 'function') {
                        editor = window.SmartEditor.getEditor();
                    }
                    if (!editor && window.SmartEditor && window.SmartEditor._editors) {
                        const keys = Object.keys(window.SmartEditor._editors);
                        if (keys.length > 0) editor = window.SmartEditor._editors[keys[0]];
                    }
                    if (editor && typeof editor.getContentText === 'function') {
                        const modelText = editor.getContentText() || '';
                        output.seModelTextLen = modelText.length;
                        output.seModelPreview = modelText.substring(0, 80);
                        if (modelText.length > 30
                            && !modelText.includes('글감과 함께')
                            && !modelText.includes('일상을 기록')) {
                            output.seModelContent = true;
                        }
                    }
                } catch(e) {
                    output.seModelError = e.message;
                }

                // ── 2) DOM 확인 (기존 방식) ──
                const checkArea = (el) => {
                    if (!el) return null;
                    const text = el.textContent?.trim() || '';
                    const html = el.innerHTML || '';
                    if (text.length > 30
                        && !text.includes('글감과 함께')
                        && !text.includes('일상을 기록')) {
                        const hasRawTags = text.includes('<div') || text.includes('<table')
                                        || text.includes('<span') || text.includes('style=');
                        const hasRenderedHTML = html.includes('<div') || html.includes('<table')
                                             || html.includes('<span') || html.includes('style=');
                        return {
                            hasContent: true,
                            length: text.length,
                            preview: text.substring(0, 80),
                            hasRawTags: hasRawTags,
                            hasRenderedHTML: hasRenderedHTML,
                        };
                    }
                    return null;
                };

                const editables = document.querySelectorAll('[contenteditable="true"]');
                for (const el of editables) {
                    const r = checkArea(el);
                    if (r) { Object.assign(output, r); output.domContent = true; break; }
                }
                if (!output.domContent) {
                    for (const sel of ['.se-main-container', '.se-content']) {
                        const r = checkArea(document.querySelector(sel));
                        if (r) { Object.assign(output, r); output.domContent = true; break; }
                    }
                }

                output.hasContent = output.domContent || output.seModelContent;
                return output;
            }""")

            se_model = result.get('seModelContent', False)
            dom_content = result.get('domContent', False)
            se_model_len = result.get('seModelTextLen', 0)

            logger.info(f"📋 본문 검증: DOM={dom_content}, SE모델={se_model} (모델텍스트={se_model_len}자)")

            if result.get("hasRawTags"):
                logger.warning(f"📋 HTML 태그가 텍스트로 노출됨! 실패 처리")
                return False

            if se_model:
                # SE 내부 모델에 내용이 있으면 → 발행 가능 (최선)
                html_status = "서식 있음" if result.get("hasRenderedHTML") else "텍스트만"
                preview = result.get('seModelPreview', result.get('preview', ''))
                logger.info(f"📋 본문 검증 OK (SE모델 확인): {se_model_len}자 ({html_status}), [{preview}...]")
                return True

            if dom_content and not se_model:
                if not require_se_model:
                    # 텍스트 타이핑 전략: DOM에 내용이 있으면 OK
                    # (키보드 입력은 SE ONE 파이프라인을 통하므로 발행 시 동작함)
                    preview = result.get('preview', '')
                    length = result.get('length', 0)
                    logger.info(f"📋 본문 검증 OK (DOM-only): {length}자, [{preview}...]")
                    return True
                else:
                    # HTML 전략: SE 모델에 없으면 "본문 내용을 입력해주세요" 에러 발생
                    preview = result.get('preview', '')
                    length = result.get('length', 0)
                    logger.warning(f"📋 DOM에 {length}자 있지만 SE 내부 모델이 비어있음 → 발행 불가, [{preview}...]")
                    return False

            logger.warning("📋 본문 검증 실패: 본문 영역이 비어있거나 placeholder만 있음")
            return False

        except Exception as e:
            logger.warning(f"본문 검증 오류: {e}")
            return False

    async def _debug_se_one_structure(self):
        """SE ONE 에디터의 내부 구조를 상세히 분석합니다 (에디터 API 메서드 포함)"""
        try:
            info = await self.page.evaluate("""() => {
                const result = {
                    editableCount: 0,
                    editables: [],
                    seComponents: [],
                    globalEditorAPIs: [],
                    editorInstance: null,
                };

                // 1) contenteditable 영역 분석
                const editables = document.querySelectorAll('[contenteditable="true"]');
                result.editableCount = editables.length;
                for (const el of editables) {
                    const rect = el.getBoundingClientRect();
                    result.editables.push({
                        tag: el.tagName,
                        class: el.className?.substring(0, 80),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                        childCount: el.children.length,
                        textLen: el.textContent?.length || 0,
                        firstChildClass: el.firstElementChild?.className?.substring(0, 60) || 'none',
                    });
                }

                // 2) SE 컴포넌트 구조 분석
                const seComps = document.querySelectorAll('.se-component');
                for (const comp of Array.from(seComps).slice(0, 10)) {
                    result.seComponents.push({
                        class: comp.className?.substring(0, 80),
                        tag: comp.tagName,
                        textPreview: comp.textContent?.substring(0, 40),
                    });
                }

                // 3) 글로벌 에디터 API 탐색
                const apiCandidates = [
                    'SE', '__se__', 'se', 'SmartEditor', 'editor',
                    'SMARTEDITOR', 'seEditor', 'postEditor',
                ];
                for (const name of apiCandidates) {
                    if (window[name]) {
                        result.globalEditorAPIs.push({
                            name: name,
                            type: typeof window[name],
                            keys: Object.keys(window[name]).slice(0, 15),
                        });
                    }
                }

                // 4) SmartEditor.getEditor() 인스턴스 메서드 탐색
                try {
                    let editorInst = null;
                    if (window.SmartEditor && typeof window.SmartEditor.getEditor === 'function') {
                        editorInst = window.SmartEditor.getEditor();
                    }
                    if (!editorInst && window.SmartEditor && window.SmartEditor._editors) {
                        const editors = window.SmartEditor._editors;
                        if (typeof editors === 'object') {
                            const keys = Object.keys(editors);
                            if (keys.length > 0) {
                                editorInst = editors[keys[0]];
                            }
                        }
                    }
                    if (editorInst) {
                        // 에디터 인스턴스의 프로토타입 메서드 + 자체 프로퍼티 탐색
                        const allKeys = new Set();
                        // own properties
                        Object.keys(editorInst).forEach(k => allKeys.add(k));
                        // prototype methods
                        let proto = Object.getPrototypeOf(editorInst);
                        let depth = 0;
                        while (proto && proto !== Object.prototype && depth < 3) {
                            Object.getOwnPropertyNames(proto).forEach(k => allKeys.add(k));
                            proto = Object.getPrototypeOf(proto);
                            depth++;
                        }
                        const methods = [];
                        const properties = [];
                        for (const k of allKeys) {
                            try {
                                if (typeof editorInst[k] === 'function') {
                                    methods.push(k);
                                } else {
                                    properties.push(k);
                                }
                            } catch(e) {}
                        }
                        result.editorInstance = {
                            type: typeof editorInst,
                            constructor: editorInst.constructor?.name || 'unknown',
                            methods: methods.sort().slice(0, 50),
                            properties: properties.sort().slice(0, 30),
                        };
                    }
                } catch(e) {
                    result.editorInstance = { error: e.message };
                }

                // 5) SE.launcher 탐색
                try {
                    if (window.SE && window.SE.launcher) {
                        const launcher = window.SE.launcher;
                        const launcherKeys = Object.keys(launcher).slice(0, 20);
                        result.seLauncher = {
                            keys: launcherKeys,
                            type: typeof launcher,
                        };
                    }
                } catch(e) {}

                // 6) __reactInternalInstance 확인 (React 기반 여부)
                const mainContainer = document.querySelector('.se-main-container');
                if (mainContainer) {
                    const reactKey = Object.keys(mainContainer).find(k => k.startsWith('__react'));
                    result.reactKey = reactKey || 'none';
                }

                return result;
            }""")

            logger.info(f"📋 SE ONE 구조 분석:")
            logger.info(f"   contenteditable 수: {info.get('editableCount')}")
            for i, ed in enumerate(info.get('editables', [])):
                logger.info(f"   editable[{i}]: {ed}")
            logger.info(f"   SE 컴포넌트: {len(info.get('seComponents', []))}개")
            for comp in info.get('seComponents', [])[:5]:
                logger.info(f"     {comp}")
            if info.get('globalEditorAPIs'):
                logger.info(f"   에디터 API 발견: {info.get('globalEditorAPIs')}")
            if info.get('editorInstance'):
                ei = info['editorInstance']
                logger.info(f"   에디터 인스턴스: constructor={ei.get('constructor')}")
                logger.info(f"   메서드 ({len(ei.get('methods', []))}개): {ei.get('methods', [])}")
                logger.info(f"   프로퍼티 ({len(ei.get('properties', []))}개): {ei.get('properties', [])}")
            if info.get('seLauncher'):
                logger.info(f"   SE.launcher: {info.get('seLauncher')}")
            logger.info(f"   React: {info.get('reactKey', 'N/A')}")

        except Exception as e:
            logger.warning(f"SE ONE 구조 분석 실패: {e}")

    async def _input_body_se_api(self, body: str) -> bool:
        """
        SmartEditor ONE의 내부 API를 사용하여 HTML 컨텐츠를 삽입합니다.

        이전 실행에서 발견된 정보:
        - editor.execCommand('SET_CONTENTS', html) → 호출은 성공하나 내부 모델에 반영 안 됨
        - editor.crawlFrom() 메서드 존재 → DOM→내부모델 동기화 가능성
        - editor._documentService, editor._editingService 프로퍼티 존재
        - SmartEditor.COMMAND, SmartEditor.PLUGIN 상수 존재

        전략:
        1단계: COMMAND 상수를 먼저 전체 탐색 (정확한 커맨드명 파악)
        2단계: execCommand에 다양한 인자 형태로 시도
        3단계: innerHTML DOM 주입 후 crawlFrom()으로 내부 모델 동기화
        4단계: _documentService 등 내부 서비스 메서드 직접 호출
        """
        logger.info("SmartEditor API 전략 시도...")

        result = await self.page.evaluate("""(htmlContent) => {
            const log = [];

            try {
                // ── 에디터 인스턴스 가져오기 ──
                let editor = null;
                if (window.SmartEditor && typeof window.SmartEditor.getEditor === 'function') {
                    editor = window.SmartEditor.getEditor();
                }
                if (!editor && window.SmartEditor && window.SmartEditor._editors) {
                    const keys = Object.keys(window.SmartEditor._editors);
                    if (keys.length > 0) editor = window.SmartEditor._editors[keys[0]];
                }
                if (!editor) {
                    return { success: false, error: 'editor instance not found', log };
                }
                log.push('에디터 인스턴스 획득 성공');

                // ── 1단계: COMMAND 상수 전체 탐색 (중첩 객체 포함) ──
                let allCommands = {};
                const flatCommands = {}; // 평탄화된 커맨드 모음
                if (window.SmartEditor && window.SmartEditor.COMMAND) {
                    allCommands = window.SmartEditor.COMMAND;
                    const cmdKeys = Object.keys(allCommands);
                    log.push(`COMMAND 최상위 (${cmdKeys.length}개): ${cmdKeys.join(', ')}`);

                    // 중첩 객체 탐색 (COMMON, IMAGE 등이 [object Object])
                    for (const topKey of cmdKeys) {
                        const val = allCommands[topKey];
                        if (val && typeof val === 'object') {
                            const subKeys = Object.keys(val);
                            log.push(`COMMAND.${topKey} 하위 (${subKeys.length}개): ${subKeys.slice(0, 40).join(', ')}`);
                            // 하위 값들도 확인
                            const subValues = {};
                            for (const sk of subKeys.slice(0, 50)) {
                                const sv = val[sk];
                                if (typeof sv === 'string') {
                                    flatCommands[`${topKey}.${sk}`] = sv;
                                    subValues[sk] = sv;
                                } else if (typeof sv === 'object' && sv !== null) {
                                    const innerKeys = Object.keys(sv);
                                    subValues[sk] = `{${innerKeys.slice(0,5).join(',')}}`;
                                    for (const ik of innerKeys) {
                                        if (typeof sv[ik] === 'string') {
                                            flatCommands[`${topKey}.${sk}.${ik}`] = sv[ik];
                                        }
                                    }
                                } else {
                                    subValues[sk] = String(sv).substring(0, 30);
                                    flatCommands[`${topKey}.${sk}`] = sv;
                                }
                            }
                            log.push(`COMMAND.${topKey} 값: ${JSON.stringify(subValues).substring(0, 300)}`);
                        } else {
                            flatCommands[topKey] = val;
                        }
                    }
                    log.push(`평탄화된 커맨드 총 ${Object.keys(flatCommands).length}개`);
                }

                // PLUGIN 상수도 탐색
                if (window.SmartEditor && window.SmartEditor.PLUGIN) {
                    const pluginKeys = Object.keys(window.SmartEditor.PLUGIN);
                    log.push(`PLUGIN 전체 (${pluginKeys.length}개): ${pluginKeys.join(', ')}`);
                }

                // ── 2단계: execCommand — 평탄화된 커맨드 중 관련 것 시도 ──
                if (typeof editor.execCommand === 'function') {
                    const relevantFlat = Object.entries(flatCommands).filter(([k, v]) => {
                        const lower = k.toLowerCase();
                        return lower.includes('content') || lower.includes('html')
                            || lower.includes('paste') || lower.includes('set')
                            || lower.includes('insert') || lower.includes('import')
                            || lower.includes('load') || lower.includes('body')
                            || lower.includes('crawl') || lower.includes('document');
                    });
                    log.push(`관련 커맨드: ${relevantFlat.map(([k]) => k).join(', ') || 'none'}`);

                    for (const [cmdPath, cmdValue] of relevantFlat) {
                        try {
                            editor.execCommand(cmdValue, htmlContent);
                            log.push(`execCommand(${cmdPath}=${cmdValue}, html) 호출 성공`);

                            if (typeof editor.getContentText === 'function') {
                                const text = editor.getContentText();
                                const textLen = text ? text.length : 0;
                                log.push(`getContentText 길이: ${textLen}`);
                                if (textLen > 50) {
                                    return { success: true, method: `execCommand(${cmdPath})`, log };
                                }
                                log.push(`내용이 반영되지 않음, 다음 커맨드 시도`);
                            } else {
                                return { success: true, method: `execCommand(${cmdPath})`, log };
                            }
                        } catch(e) {
                            log.push(`execCommand(${cmdPath}=${cmdValue}) 실패: ${e.message}`);
                        }
                    }

                    // 직접 문자열 커맨드명도 시도 (상수 등록 안 된 경우)
                    const directCmds = [
                        'SET_CONTENTS', 'LOAD_CONTENTS', 'IMPORT_DOCUMENT',
                        'PASTE_CONTENT', 'INSERT_CONTENT', 'REPLACE_CONTENT',
                        'SET_DOCUMENT_DATA', 'LOAD_DOCUMENT',
                    ];
                    for (const cmd of directCmds) {
                        try {
                            // 다양한 인자 형태: (cmd, html), (cmd, {html}), (cmd, {content: html})
                            const argFormats = [
                                htmlContent,
                                { html: htmlContent },
                                { content: htmlContent },
                                { body: htmlContent },
                                { data: htmlContent },
                                { value: htmlContent },
                            ];
                            for (const arg of argFormats) {
                                try {
                                    editor.execCommand(cmd, arg);
                                    if (typeof editor.getContentText === 'function') {
                                        const text = editor.getContentText();
                                        if (text && text.length > 50) {
                                            log.push(`execCommand('${cmd}', ${typeof arg === 'string' ? 'html' : JSON.stringify(Object.keys(arg))}) 성공!`);
                                            return { success: true, method: `execCommand(${cmd})`, log };
                                        }
                                    }
                                } catch(e) {}
                            }
                        } catch(e) {}
                    }
                }

                // ── 3단계: innerHTML 주입 후 crawlFrom()으로 동기화 ──
                if (typeof editor.crawlFrom === 'function') {
                    log.push('crawlFrom() 메서드 발견, DOM 주입 후 동기화 시도...');

                    // SE ONE의 본문 영역에 HTML 주입
                    const mainContainer = document.querySelector('.se-main-container');
                    if (mainContainer) {
                        // 기존 텍스트 컴포넌트 (placeholder) 찾기
                        const textComps = mainContainer.querySelectorAll('.se-component.se-text');
                        for (const comp of textComps) {
                            // placeholder만 제거
                            if (comp.textContent?.includes('글감과 함께') || comp.textContent?.includes('일상을 기록')) {
                                comp.remove();
                            }
                        }

                        // HTML을 SE ONE 형식의 텍스트 컴포넌트로 감싸서 삽입
                        const wrapper = document.createElement('div');
                        wrapper.className = 'se-component se-text se-l-default';
                        const contentDiv = document.createElement('div');
                        contentDiv.className = 'se-component-content';
                        const sectionDiv = document.createElement('div');
                        sectionDiv.className = 'se-section-text se-l-default';
                        // 각 블록을 p.se-text-paragraph 로 감싸기
                        const tempDiv = document.createElement('div');
                        tempDiv.innerHTML = htmlContent;
                        for (const child of Array.from(tempDiv.children)) {
                            const p = document.createElement('p');
                            p.className = 'se-text-paragraph se-text-paragraph-align-';
                            const span = document.createElement('span');
                            span.className = 'se-fs- se-ff-';
                            span.innerHTML = child.outerHTML || child.textContent;
                            p.appendChild(span);
                            sectionDiv.appendChild(p);
                        }
                        // 자식이 없으면 전체 HTML을 하나의 p로
                        if (sectionDiv.children.length === 0) {
                            const p = document.createElement('p');
                            p.className = 'se-text-paragraph se-text-paragraph-align-';
                            p.innerHTML = htmlContent;
                            sectionDiv.appendChild(p);
                        }
                        contentDiv.appendChild(sectionDiv);
                        wrapper.appendChild(contentDiv);
                        mainContainer.appendChild(wrapper);
                        log.push(`DOM에 HTML 주입 완료 (${sectionDiv.children.length} paragraphs)`);
                    }

                    // crawlFrom 호출 시도 (다양한 인자 형태)
                    try {
                        // 인자 없이 시도
                        const crawlResult = editor.crawlFrom();
                        log.push(`crawlFrom() 호출 결과: ${JSON.stringify(crawlResult)?.substring(0, 100)}`);
                    } catch(e) {
                        log.push(`crawlFrom() 실패: ${e.message}`);
                    }

                    // DOM 소스에서 crawl
                    try {
                        const mainEl = document.querySelector('.se-main-container');
                        if (mainEl) {
                            editor.crawlFrom(mainEl);
                            log.push('crawlFrom(mainContainer) 호출 성공');
                        }
                    } catch(e) {
                        log.push(`crawlFrom(element) 실패: ${e.message}`);
                    }

                    // HTML 문자열에서 crawl
                    try {
                        editor.crawlFrom(htmlContent);
                        log.push('crawlFrom(htmlString) 호출 성공');
                    } catch(e) {
                        log.push(`crawlFrom(string) 실패: ${e.message}`);
                    }

                    // 결과 확인
                    if (typeof editor.getContentText === 'function') {
                        const text = editor.getContentText();
                        log.push(`crawlFrom 후 getContentText 길이: ${text?.length || 0}`);
                        if (text && text.length > 50) {
                            return { success: true, method: 'crawlFrom', log };
                        }
                    }
                }

                // ── 4단계: _documentService 내부 서비스 탐색 ──
                const serviceNames = [
                    '_documentService', '_editingService', '_document', '_papyrus'
                ];
                for (const sName of serviceNames) {
                    const svc = editor[sName];
                    if (!svc) continue;
                    const svcMethods = [];
                    try {
                        let proto = svc;
                        let depth = 0;
                        while (proto && depth < 3) {
                            Object.getOwnPropertyNames(proto).forEach(k => {
                                if (typeof svc[k] === 'function') svcMethods.push(k);
                            });
                            proto = Object.getPrototypeOf(proto);
                            depth++;
                        }
                    } catch(e) {}
                    log.push(`${sName} 메서드: ${svcMethods.sort().slice(0, 25).join(', ')}`);

                    // setContent/setHTML 등 시도
                    const setMethods = svcMethods.filter(m => {
                        const l = m.toLowerCase();
                        return l.includes('set') || l.includes('insert')
                            || l.includes('import') || l.includes('load')
                            || l.includes('html') || l.includes('content');
                    });
                    for (const m of setMethods) {
                        try {
                            svc[m](htmlContent);
                            log.push(`${sName}.${m}(html) 호출 성공`);
                            if (typeof editor.getContentText === 'function') {
                                const text = editor.getContentText();
                                if (text && text.length > 50) {
                                    return { success: true, method: `${sName}.${m}`, log };
                                }
                            }
                        } catch(e) {
                            log.push(`${sName}.${m}() 실패: ${e.message}`);
                        }
                    }
                }

                // ── 5단계: getDocumentData로 현재 데이터 구조 파악 ──
                if (typeof editor.getDocumentData === 'function') {
                    try {
                        const docData = editor.getDocumentData();
                        const docDataStr = JSON.stringify(docData);
                        log.push(`getDocumentData 구조: ${docDataStr.substring(0, 300)}`);

                        // 데이터 구조에서 body/content 필드 찾기
                        if (docData && typeof docData === 'object') {
                            const dataKeys = Object.keys(docData);
                            log.push(`documentData keys: ${dataKeys.join(', ')}`);
                        }
                    } catch(e) {
                        log.push(`getDocumentData 실패: ${e.message}`);
                    }
                }

                return { success: false, error: 'all SE API methods failed', log };

            } catch(e) {
                log.push(`치명적 오류: ${e.message}`);
                return { success: false, error: e.message, log };
            }
        }""", body)

        if result:
            for msg in result.get('log', []):
                logger.info(f"   SE API: {msg}")

            if result.get('success'):
                logger.info(f"✅ SmartEditor API 삽입 성공: {result.get('method')}")
                await asyncio.sleep(1)
                return True

        logger.warning(f"SmartEditor API 삽입 실패: {result.get('error', 'unknown')}")
        return False

    async def _input_body_dispatch_paste_event(self, body: str) -> bool:
        """
        본문 영역에 직접 paste 이벤트를 디스패치합니다.

        이전 실행 결과: defaultPrevented=true → SE ONE paste handler가 이벤트를
        가로챘지만 데이터가 비어있었음. Chrome은 synthetic ClipboardEvent의
        clipboardData.getData()가 빈 문자열을 반환하는 보안 제한이 있음.

        해결: clipboardData.getData를 monkey-patch하여 데이터 반환하도록 함.
        """
        logger.info("paste 이벤트 디스패치 전략 시도 (monkey-patch getData)...")

        # 본문 영역 클릭하여 에디터 활성화 + 포커스
        if not await self._click_body_area():
            return False
        await asyncio.sleep(0.5)

        result = await self.page.evaluate("""(htmlContent) => {
            const log = [];

            try {
                // 1) 포커스된 요소 찾기
                let target = document.activeElement;
                if (!target || !target.isContentEditable) {
                    const editables = document.querySelectorAll('[contenteditable="true"]');
                    if (editables.length > 0) {
                        target = editables[0];
                        target.focus();
                    }
                }
                if (!target) {
                    return { success: false, error: 'paste target not found', log };
                }
                log.push(`타겟: ${target.tagName}.${target.className?.substring(0, 30)}`);

                const textContent = htmlContent.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim();

                // 2) DataTransfer를 monkey-patch하여 getData()가 실제 데이터 반환하도록 함
                // Chrome은 synthetic ClipboardEvent의 getData()가 빈 문자열 반환하는 보안 제한이 있음
                const dt = new DataTransfer();
                dt.setData('text/html', htmlContent);
                dt.setData('text/plain', textContent);

                // getData를 오버라이드
                const originalGetData = dt.getData.bind(dt);
                const dataMap = {
                    'text/html': htmlContent,
                    'text/plain': textContent,
                    'text': textContent,
                };
                dt.getData = function(type) {
                    return dataMap[type] || originalGetData(type) || '';
                };

                // types 프로퍼티도 오버라이드 (SE ONE이 types를 체크할 수 있음)
                Object.defineProperty(dt, 'types', {
                    get: () => ['text/html', 'text/plain'],
                    configurable: true,
                });

                // items도 설정
                try {
                    Object.defineProperty(dt, 'items', {
                        get: () => ({
                            length: 2,
                            0: { kind: 'string', type: 'text/html', getAsString: (cb) => cb(htmlContent) },
                            1: { kind: 'string', type: 'text/plain', getAsString: (cb) => cb(textContent) },
                        }),
                        configurable: true,
                    });
                } catch(e) {
                    log.push(`items 오버라이드 실패: ${e.message}`);
                }

                // 3) ClipboardEvent 생성 (clipboardData를 직접 설정)
                const pasteEvent = new ClipboardEvent('paste', {
                    bubbles: true,
                    cancelable: true,
                    clipboardData: dt,
                });

                // clipboardData getter도 오버라이드 (일부 브라우저에서 constructor에서 설정한 것이 무시됨)
                try {
                    Object.defineProperty(pasteEvent, 'clipboardData', {
                        get: () => dt,
                        configurable: true,
                    });
                } catch(e) {
                    log.push(`clipboardData 오버라이드 실패: ${e.message}`);
                }

                // 검증: 이벤트에서 데이터 읽기 테스트
                const testData = pasteEvent.clipboardData?.getData('text/html');
                log.push(`이벤트 데이터 검증: ${testData ? testData.length + '자' : 'empty'}`);

                // 4) 디스패치
                const dispatched = target.dispatchEvent(pasteEvent);
                log.push(`디스패치 결과: dispatched=${dispatched}, prevented=${pasteEvent.defaultPrevented}`);

                return { success: true, log };

            } catch(e) {
                log.push(`오류: ${e.message}`);
                return { success: false, error: e.message, log };
            }
        }""", body)

        if result:
            for msg in result.get('log', []):
                logger.info(f"   paste event: {msg}")

        if result and result.get('success'):
            await asyncio.sleep(2)
            logger.info("paste 이벤트 디스패치 완료")
            return True

        logger.warning(f"paste 이벤트 디스패치 실패: {result.get('error', 'unknown')}")
        return False

    async def _click_body_area(self) -> bool:
        """본문 편집 영역을 클릭하여 커서를 위치시킵니다"""
        # 방법 1: placeholder 텍스트로 찾아서 클릭
        clicked = await self.page.evaluate("""() => {
            // placeholder 영역 찾기
            const allEls = document.querySelectorAll('p, span, div');
            for (const el of allEls) {
                const text = el.textContent?.trim() || '';
                if (text.includes('글감과 함께') || text.includes('일상을 기록')) {
                    el.click();
                    return 'placeholder';
                }
            }

            // contenteditable 영역 중 본문 영역 클릭 (제목이 아닌 것)
            const editables = document.querySelectorAll('[contenteditable="true"]');
            for (const el of editables) {
                const cls = el.className || '';
                // 제목 영역이 아닌 것
                if (!cls.includes('title') && !cls.includes('Title')) {
                    // 본문 컨테이너인지 확인
                    const rect = el.getBoundingClientRect();
                    if (rect.height > 100) {
                        el.click();
                        return 'editable_large';
                    }
                }
            }

            // 마지막 수단: 두 번째 contenteditable (첫 번째가 보통 제목)
            if (editables.length > 1) {
                editables[1].click();
                return 'editable_second';
            }

            return null;
        }""")
        if clicked:
            logger.info(f"본문 영역 클릭: {clicked}")
            await asyncio.sleep(0.5)
            return True

        # 방법 2: 좌표 기반 클릭 (제목 영역 아래, 에디터 중앙)
        try:
            viewport = self.page.viewport_size
            if viewport:
                # 페이지 중앙 x, 상단에서 400px 아래 (제목 밑 본문 영역)
                x = viewport["width"] // 2
                y = 400
                await self.page.mouse.click(x, y)
                logger.info(f"본문 영역 좌표 클릭: ({x}, {y})")
                await asyncio.sleep(0.5)
                return True
        except Exception as e:
            logger.debug(f"좌표 클릭 실패: {e}")

        return False

    async def _input_body_real_clipboard_paste(self, body: str) -> bool:
        """
        실제 시스템 클립보드에 HTML을 쓰고 Ctrl+V로 붙여넣습니다.

        중요: SE ONE은 제목+본문이 하나의 contenteditable이므로
        Control+a를 절대 사용하면 안 됩니다 (제목까지 선택됨).
        본문 placeholder를 클릭하면 커서가 본문 위치에 놓이므로
        그 상태에서 바로 paste합니다.
        """
        logger.info("시스템 클립보드 Ctrl+V 전략 시도...")

        # 본문 영역 클릭 (placeholder 클릭 → 커서가 본문 위치에 놓임)
        if not await self._click_body_area():
            return False
        await asyncio.sleep(0.5)

        # ⚠️ Control+a 사용 금지! (제목+본문 전체 선택됨)
        # 새 글이므로 본문은 비어있음 → 별도 삭제 불필요

        # 시스템 클립보드에 HTML 쓰기 (navigator.clipboard API)
        clipboard_written = await self.page.evaluate("""async (htmlContent) => {
            try {
                const htmlBlob = new Blob([htmlContent], { type: 'text/html' });
                const textContent = htmlContent.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim();
                const textBlob = new Blob([textContent], { type: 'text/plain' });

                const item = new ClipboardItem({
                    'text/html': htmlBlob,
                    'text/plain': textBlob,
                });
                await navigator.clipboard.write([item]);
                return { success: true };
            } catch (e) {
                return { success: false, error: e.message };
            }
        }""", body)

        if not clipboard_written or not clipboard_written.get("success"):
            logger.warning(f"클립보드 쓰기 실패: {clipboard_written}")
            return False

        logger.info("클립보드에 HTML 쓰기 완료, Ctrl+V 실행...")

        # macOS에서 Playwright+Chromium: Meta+v가 시스템 붙여넣기
        await self.page.keyboard.press("Meta+v")
        await asyncio.sleep(3)

        has_content = await self._verify_body_content()
        if has_content:
            logger.info("✅ 시스템 클립보드 Meta+V 성공")
            return True

        # Meta+V 실패 → Control+V 시도
        logger.info("Meta+V 실패, Control+V 시도...")
        await self._click_body_area()
        await asyncio.sleep(0.3)
        await self.page.keyboard.press("Control+v")
        await asyncio.sleep(3)

        has_content = await self._verify_body_content()
        if has_content:
            logger.info("✅ 시스템 클립보드 Control+V 성공")
            return True

        logger.warning("시스템 클립보드 붙여넣기 실패")
        return False

    async def _input_body_innerHTML(self, body: str) -> bool:
        """
        SmartEditor ONE의 본문 contenteditable 영역에 innerHTML을 직접 주입합니다.

        SE ONE 구조:
          .se-main-container > .se-component.se-text > .se-text-paragraph
        본문 영역은 제목 영역(.se-documentTitle)과 분리되어 있으며,
        본문 텍스트 컴포넌트들이 .se-main-container 안에 들어갑니다.

        innerHTML 주입 후 에디터의 내부 상태와 동기화하기 위해
        input/change 이벤트를 발생시킵니다.
        """
        logger.info("innerHTML 직접 주입 전략 시도...")

        # 먼저 본문 영역 클릭하여 에디터 활성화
        await self._click_body_area()
        await asyncio.sleep(1)

        result = await self.page.evaluate("""(htmlContent) => {
            // SmartEditor ONE 본문 영역 찾기 (여러 셀렉터 시도)
            const selectors = [
                // SE ONE 메인 컨테이너 (제목 제외 본문 영역)
                '.se-main-container',
                // 본문 편집 영역
                '.se-component-content',
                // contenteditable 중 본문 영역 (제목 아닌 것)
                '.se-content',
            ];

            let bodyContainer = null;

            // 방법 1: SE 컨테이너에서 본문 컴포넌트 영역 찾기
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el) {
                    bodyContainer = el;
                    break;
                }
            }

            // 방법 2: contenteditable 중 본문 영역 (제목 다음 것)
            if (!bodyContainer) {
                const editables = document.querySelectorAll('[contenteditable="true"]');
                for (const el of editables) {
                    const cls = (el.className || '').toLowerCase();
                    // 제목이 아닌 contenteditable
                    if (!cls.includes('title') && !cls.includes('documenttitle')) {
                        const rect = el.getBoundingClientRect();
                        if (rect.height > 50) {
                            bodyContainer = el;
                            break;
                        }
                    }
                }
                // 제목 하나, 본문 하나인 경우 두 번째
                if (!bodyContainer && editables.length >= 2) {
                    bodyContainer = editables[1];
                }
                // 하나뿐인 경우 그것을 사용 (제목+본문 통합 에디터)
                if (!bodyContainer && editables.length === 1) {
                    bodyContainer = editables[0];
                }
            }

            if (!bodyContainer) {
                return { success: false, error: 'body container not found' };
            }

            // SE ONE 에디터의 기존 본문 컴포넌트들 제거 (제목 컴포넌트 보존)
            // 제목 컴포넌트(.se-documentTitle)는 남기고 나머지 본문 컴포넌트만 제거
            const titleComp = bodyContainer.querySelector('.se-documentTitle, .se-component.se-title');
            const existingComps = bodyContainer.querySelectorAll('.se-component');
            for (const comp of existingComps) {
                if (comp !== titleComp && !comp.contains(titleComp) && !titleComp?.contains(comp)) {
                    comp.remove();
                }
            }

            // HTML을 SE ONE 텍스트 컴포넌트 형태로 감싸서 삽입
            // SE ONE은 .se-component > .se-component-content > .se-section-text 구조
            const wrapper = document.createElement('div');
            wrapper.className = 'se-component se-text se-l-default';
            wrapper.setAttribute('data-custom-html', 'true');

            const contentDiv = document.createElement('div');
            contentDiv.className = 'se-component-content';

            const sectionDiv = document.createElement('div');
            sectionDiv.className = 'se-section-text se-l-default';

            // HTML 본문을 p 태그로 감싸지 않고 직접 삽입
            sectionDiv.innerHTML = htmlContent;
            contentDiv.appendChild(sectionDiv);
            wrapper.appendChild(contentDiv);

            bodyContainer.appendChild(wrapper);

            // 이벤트 발생으로 에디터 상태 동기화
            bodyContainer.dispatchEvent(new Event('input', { bubbles: true }));
            bodyContainer.dispatchEvent(new Event('change', { bubbles: true }));

            // MutationObserver가 있을 경우를 위해 추가 이벤트
            const inputEvent = new InputEvent('input', {
                bubbles: true,
                cancelable: true,
                inputType: 'insertFromPaste',
                data: null,
            });
            bodyContainer.dispatchEvent(inputEvent);

            return {
                success: true,
                container: bodyContainer.className?.substring(0, 60),
                htmlLength: htmlContent.length,
            };
        }""", body)

        if result and result.get("success"):
            logger.info(f"innerHTML 주입 완료: container={result.get('container')}, {result.get('htmlLength')}자")
            await asyncio.sleep(1)
            return True

        logger.warning(f"innerHTML 주입 실패: {result}")
        return False

    async def _input_body_exec_command(self, body: str) -> bool:
        """
        본문 영역을 클릭 후 execCommand('insertHTML')로 HTML 삽입.
        ⚠️ Control+a 사용 금지 (제목 오염 방지)
        """
        if not await self._click_body_area():
            return False

        await asyncio.sleep(0.5)

        # execCommand로 HTML 삽입 (현재 커서 위치에)
        result = await self.page.evaluate("""(htmlContent) => {
            try {
                const success = document.execCommand('insertHTML', false, htmlContent);
                if (success) {
                    return { success: true, method: 'execCommand' };
                }
            } catch(e) {}

            try {
                const sel = window.getSelection();
                if (sel && sel.rangeCount > 0) {
                    const range = sel.getRangeAt(0);
                    const frag = range.createContextualFragment(htmlContent);
                    range.insertNode(frag);
                    return { success: true, method: 'selection_range' };
                }
            } catch(e2) {}

            return { success: false };
        }""", body)

        if result.get("success"):
            logger.info(f"execCommand HTML 삽입 완료: {result.get('method')}")
            await asyncio.sleep(1)
            return True

        return False

    async def _input_body_text_fallback(self, body: str) -> bool:
        """본문 영역 클릭 후 텍스트를 직접 타이핑 (HTML 포기, 평문)"""
        # HTML 태그 제거
        plain_text = re.sub(r"<[^>]+>", "\n", body)
        plain_text = plain_text.replace("&nbsp;", " ").replace("&amp;", "&")
        plain_text = plain_text.replace("&lt;", "<").replace("&gt;", ">")
        # 마크다운 문법 제거 (# 헤딩, ** 볼드, * 이탤릭 등)
        plain_text = re.sub(r"^#{1,6}\s+", "", plain_text, flags=re.MULTILINE)
        plain_text = re.sub(r"\*\*(.+?)\*\*", r"\1", plain_text)
        plain_text = re.sub(r"\*(.+?)\*", r"\1", plain_text)
        # 연속 줄바꿈 정리
        plain_text = re.sub(r"\n{3,}", "\n\n", plain_text).strip()

        if not await self._click_body_area():
            return False

        await asyncio.sleep(0.5)

        # 텍스트를 줄 단위로 입력 (Enter로 줄바꿈)
        lines = plain_text.split("\n")
        typed_count = 0
        for line in lines[:100]:  # 최대 100줄
            if line.strip():
                await self.page.keyboard.type(line.strip(), delay=5)
                typed_count += 1
            await self.page.keyboard.press("Enter")

        logger.info(f"텍스트 타이핑 완료: {typed_count}줄")
        await asyncio.sleep(1)
        return typed_count > 0

    async def _select_category_in_panel(self, blog_category: str):
        """
        발행 설정 패널 내의 카테고리 selectbox에서 카테고리를 변경합니다.
        패널 내 selectbox_button을 클릭 → 드롭다운에서 카테고리 선택.
        """
        try:
            variants = [blog_category, blog_category.replace("·", "/"), blog_category.replace("·", " ")]
            logger.info(f"패널 내 카테고리 변경: {blog_category}")

            # 패널 내 selectbox 버튼 클릭
            clicked = await self.page.evaluate("""() => {
                const panel = document.querySelector('[class*="layer_publish"]');
                if (!panel) return false;
                const selectBtn = panel.querySelector('[class*="selectbox_button"]');
                if (selectBtn) {
                    selectBtn.click();
                    return true;
                }
                return false;
            }""")

            if not clicked:
                logger.warning("패널 내 카테고리 selectbox 버튼을 찾을 수 없음")
                return

            await asyncio.sleep(1)

            # 드롭다운에서 카테고리 항목 선택
            selected = await self.page.evaluate("""(variants) => {
                // 패널 내 또는 드롭다운 리스트에서 카테고리 찾기
                const listItems = document.querySelectorAll(
                    '[class*="layer_publish"] li, ' +
                    '[class*="selectbox"] li, ' +
                    '[class*="dropdown"] li, ' +
                    '[class*="list"] li'
                );

                for (const li of listItems) {
                    const text = li.textContent?.trim() || '';
                    for (const v of variants) {
                        if (text === v || (text.includes(v) && text.length < v.length + 10)) {
                            const rect = li.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                li.click();
                                return { success: true, text: text };
                            }
                        }
                    }
                }
                return { success: false };
            }""", variants)

            if selected and selected.get("success"):
                logger.info(f"✅ 패널 내 카테고리 선택 완료: {selected.get('text')}")
            else:
                logger.warning("패널 내 카테고리 드롭다운에서 항목을 찾을 수 없음")
                # 드롭다운 닫기
                await self.page.keyboard.press("Escape")

            await asyncio.sleep(0.5)

        except Exception as e:
            logger.warning(f"패널 내 카테고리 선택 실패: {e}")

    async def _js_click(self, selector_text: str, description: str = "",
                        exact: bool = False) -> bool:
        """
        JavaScript로 버튼을 클릭합니다 (오버레이에 의한 클릭 차단 우회).
        selector_text: 버튼의 텍스트 내용 (예: "발행")
        exact: True면 정확히 일치하는 텍스트만 매칭
        """
        result = await self.page.evaluate("""([btnText, exactMatch]) => {
            const buttons = document.querySelectorAll('button');
            // 정확히 일치하는 것을 우선 찾기
            for (const btn of buttons) {
                const text = btn.textContent?.trim() || '';
                if (text === btnText) {
                    btn.click();
                    return { success: true, text: text, class: btn.className?.substring(0, 60) };
                }
            }
            // exact가 아니면 포함 매칭도 시도
            if (!exactMatch) {
                for (const btn of buttons) {
                    const text = btn.textContent?.trim() || '';
                    if (text.includes(btnText) && text.length < btnText.length + 5) {
                        btn.click();
                        return { success: true, text: text, class: btn.className?.substring(0, 60) };
                    }
                }
            }
            return { success: false };
        }""", [selector_text, exact])

        if result.get("success"):
            logger.info(f"✅ JS 클릭 성공 ({description}): {result.get('text')} [{result.get('class')}]")
            return True
        return False

    async def _publish_post(self, category: str = "") -> str:
        """
        발행 버튼 클릭 → 발행 설정 패널에서 카테고리 확인 → 최종 발행.

        네이버 블로그 발행 플로우 (로그에서 확인된 실제 클래스명 기반):
        1) 상단 "발행" 버튼 (publish_btn__m9KHH) 클릭 → 설정 패널 슬라이드
        2) 패널에서 카테고리가 이미 올바른지 확인 (selectbox_button__jb1Dt)
        3) 패널 하단 "발행" 확인 버튼 (confirm_btn__WEaBq) 클릭 → 실제 발행
        """
        logger.info("포스트 발행 시도")

        # 오버레이 닫기
        await self._close_overlays()

        # ── 1단계: 상단 "발행" 버튼 클릭 → 설정 패널 열기 ──
        # 정확한 클래스명으로 상단 발행 버튼만 타겟
        clicked = await self.page.evaluate("""() => {
            // 1) 정확한 클래스로 찾기
            const publishBtn = document.querySelector('button[class*="publish_btn"]');
            if (publishBtn) {
                publishBtn.click();
                return { success: true, method: 'class', class: publishBtn.className?.substring(0, 60) };
            }
            // 2) 텍스트로 찾되, confirm_btn은 제외
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.textContent?.trim() || '';
                const cls = btn.className || '';
                if (text === '발행' && !cls.includes('confirm')) {
                    btn.click();
                    return { success: true, method: 'text', class: cls?.substring(0, 60) };
                }
            }
            return { success: false };
        }""")

        if not clicked or not clicked.get("success"):
            raise Exception("상단 발행 버튼을 찾거나 클릭할 수 없음")

        logger.info(f"✅ 상단 '발행' 버튼 클릭: [{clicked.get('class')}]")
        await asyncio.sleep(3)
        await self._debug_screenshot("05_publish_panel")

        # ── 2단계: 발행 설정 패널 확인 ──
        # 패널이 열렸는지 확인 (layer_publish 클래스)
        panel_check = await self.page.evaluate("""() => {
            const panel = document.querySelector('[class*="layer_publish"], [class*="layer_content_set_publish"]');
            if (!panel || panel.offsetParent === null) {
                return { open: false };
            }
            // 현재 카테고리 확인
            const catBtn = panel.querySelector('[class*="selectbox_button"]');
            const catText = catBtn ? catBtn.textContent?.trim() : null;

            // confirm 버튼 확인
            const confirmBtn = panel.querySelector('[class*="confirm_btn"]');
            const hasConfirm = confirmBtn !== null && confirmBtn.offsetParent !== null;

            return {
                open: true,
                currentCategory: catText,
                hasConfirmBtn: hasConfirm,
                confirmClass: confirmBtn?.className?.substring(0, 60)
            };
        }""")

        logger.info(f"📋 발행 패널 상태: {json.dumps(panel_check, ensure_ascii=False)}")

        if not panel_check.get("open"):
            logger.warning("발행 패널이 열리지 않음, 다시 시도...")
            # 한번 더 클릭 시도
            await self.page.evaluate("""() => {
                const btn = document.querySelector('button[class*="publish_btn"]');
                if (btn) btn.click();
            }""")
            await asyncio.sleep(3)

        # ── 2-1. 카테고리 확인 (이미 올바르면 스킵) ──
        if category:
            blog_category = category.replace("/", "·")
            current_cat = panel_check.get("currentCategory", "")
            if current_cat and blog_category in current_cat:
                logger.info(f"✅ 카테고리 이미 올바름: {current_cat}")
            else:
                logger.info(f"카테고리 변경 필요: 현재={current_cat}, 목표={blog_category}")
                # 패널 내 카테고리 selectbox 클릭 → 드롭다운에서 선택
                await self._select_category_in_panel(blog_category)

        await asyncio.sleep(1)

        # ── 3단계: 패널 내 "발행" 확인 버튼 클릭 (confirm_btn) ──
        logger.info("패널 내 최종 '발행' 확인 버튼 클릭 시도...")

        final_clicked = await self.page.evaluate("""() => {
            // 1) 정확한 클래스명으로 confirm 버튼 찾기
            const confirmBtn = document.querySelector('button[class*="confirm_btn"]');
            if (confirmBtn && confirmBtn.offsetParent !== null) {
                confirmBtn.click();
                return { success: true, method: 'confirm_class', class: confirmBtn.className?.substring(0, 60) };
            }

            // 2) 발행 패널 내부에서 "발행" 버튼 찾기 (publish_btn 제외)
            const panel = document.querySelector('[class*="layer_publish"]');
            if (panel) {
                const btns = panel.querySelectorAll('button');
                for (const btn of btns) {
                    const text = btn.textContent?.trim() || '';
                    const cls = btn.className || '';
                    if (text === '발행' && !cls.includes('publish_btn') && !cls.includes('fold')) {
                        btn.click();
                        return { success: true, method: 'panel_text', class: cls?.substring(0, 60) };
                    }
                }
            }

            // 3) 모든 버튼 중 confirm 관련 찾기
            const allBtns = document.querySelectorAll('button');
            for (const btn of allBtns) {
                const cls = btn.className || '';
                const text = btn.textContent?.trim() || '';
                if (cls.includes('confirm') && text.includes('발행')) {
                    btn.click();
                    return { success: true, method: 'confirm_any', class: cls?.substring(0, 60) };
                }
            }

            return { success: false };
        }""")

        if final_clicked and final_clicked.get("success"):
            logger.info(f"✅ 최종 발행 확인 버튼 클릭: {final_clicked.get('method')} [{final_clicked.get('class')}]")
        else:
            logger.error("❌ 패널 내 확인 버튼을 찾을 수 없음!")
            await self._debug_screenshot("05b_no_confirm_btn")
            raise Exception("발행 확인 버튼(confirm_btn)을 찾을 수 없음")

        # ── 4단계: 발행 완료 대기 ──
        logger.info("발행 완료 대기 중...")

        # 에러 팝업이 뜨는지 먼저 잠시 대기
        await asyncio.sleep(2)

        # 에러 팝업 감지 (본문 비어있음, 네트워크 오류 등)
        error_popup = await self.page.evaluate("""() => {
            // alert/confirm 다이얼로그, 에러 메시지 팝업 찾기
            const allEls = document.querySelectorAll(
                '[class*="alert"], [class*="error"], [class*="warn"], ' +
                '[class*="toast"], [class*="snackbar"], [class*="dialog"], ' +
                '[class*="modal"], [class*="popup"]'
            );
            for (const el of allEls) {
                const text = el.textContent?.trim() || '';
                if (text.length > 5 && text.length < 200 && el.offsetParent !== null) {
                    // 발행 패널 자체는 제외
                    if (!text.includes('발행') || text.includes('실패') || text.includes('오류')
                        || text.includes('입력') || text.includes('내용')) {
                        return { found: true, text: text.substring(0, 150), class: el.className?.substring(0, 60) };
                    }
                }
            }
            return { found: false };
        }""")

        if error_popup.get("found"):
            logger.error(f"❌ 발행 에러 팝업 감지: {error_popup.get('text')}")
            await self._debug_screenshot("05c_error_popup")

        # URL 변경 감지 (postwrite → PostView로 변경될 때까지)
        try:
            await self.page.wait_for_url(
                lambda url: "postwrite" not in url,
                timeout=20000,
            )
            logger.info(f"✅ URL 변경 감지: {self.page.url}")
        except Exception:
            logger.warning("URL 변경 없음 (20초 타임아웃)")

        await asyncio.sleep(3)
        await self._debug_screenshot("06_published")

        current_url = self.page.url
        logger.info(f"발행 후 URL: {current_url}")

        # 발행 후 보통 포스트 보기 페이지로 이동됨
        if "postwrite" not in current_url:
            return current_url

        # 아직 에디터에 있다면 — 에디터 본문 상태 디버깅
        editor_state = await self.page.evaluate("""() => {
            const editables = document.querySelectorAll('[contenteditable="true"]');
            const result = [];
            for (const el of editables) {
                result.push({
                    class: el.className?.substring(0, 60),
                    textLength: el.textContent?.trim()?.length || 0,
                    htmlLength: el.innerHTML?.length || 0,
                    hasChildren: el.children.length,
                });
            }
            return result;
        }""")
        logger.error(f"📋 에디터 상태 덤프: {json.dumps(editor_state, ensure_ascii=False)}")

        await self._debug_screenshot("07_still_on_editor")
        raise Exception(
            f"발행 실패: 발행 후에도 여전히 에디터 페이지 (URL: {current_url}). "
            f"에러 팝업: {error_popup.get('text', '없음')}. "
            "data/debug_screenshots/ 폴더의 스크린샷을 확인하세요."
        )
