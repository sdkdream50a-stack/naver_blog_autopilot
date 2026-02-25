"""
AI 감지 회피를 위한 휴먼라이징 검토·수정 모듈

AI가 생성한 텍스트의 특징적 패턴을 감지하고,
사람이 작성한 것처럼 자연스럽게 수정합니다.

2단계 프로세스:
  1단계: 규칙 기반 패턴 감지 (API 없이 빠르게)
  2단계: Claude API로 자연스러운 리라이팅
"""

import re
from typing import Optional
from utils.database import Database
from utils.logger import get_logger
from config.settings import settings

logger = get_logger()


# ─────────────────────────────────────────────
# 1단계: 규칙 기반 AI 패턴 감지
# ─────────────────────────────────────────────

# AI가 자주 쓰는 상투적 표현 (한국어 블로그 기준)
AI_CLICHE_PATTERNS = [
    # 도입부 상투어
    (r"오늘은\s+.{5,30}에\s+대해\s+(?:알아보겠습니다|살펴보겠습니다)", "도입부 상투어"),
    (r"(?:많은\s+분들이|많은\s+실무자들이)\s+(?:궁금해하시는|헷갈려하시는|고민하시는)", "도입부 상투어"),
    (r"이번\s+(?:포스팅|글)에서는\s+.{5,30}(?:정리해|알아보|살펴보)", "도입부 상투어"),

    # 전환 상투어
    (r"(?:그렇다면|그럼|그러면)\s+(?:지금부터|이제)\s+(?:하나씩|자세히|본격적으로)\s+(?:알아보|살펴보|확인해)", "전환 상투어"),
    (r"(?:자,?\s*)?(?:그러면|그럼)\s+(?:구체적으로|실질적으로)\s+(?:어떤|어떻게)", "전환 상투어"),

    # 마무리 상투어
    (r"(?:지금까지|이상으로)\s+.{5,30}에\s+대해\s+(?:알아보았습니다|살펴보았습니다|정리해보았습니다)", "마무리 상투어"),
    (r"(?:도움이\s+되셨으면|도움이\s+되었으면)\s+(?:좋겠습니다|합니다)", "마무리 상투어"),
    (r"(?:궁금한\s+점이?\s+있으시면|질문이\s+있으시면)\s+(?:댓글|문의)", "마무리 상투어"),

    # AI 특유의 과잉 친절
    (r"(?:걱정하지\s+마세요|걱정\s+마세요)[!.]?\s+(?:지금부터|아래에서|이\s+글에서)", "과잉 친절"),
    (r"(?:쉽게|한눈에|완벽하게)\s+(?:정리해|알려)\s*(?:드리겠습니다|드릴게요)", "과잉 친절"),

    # 나열형 서두 반복
    (r"(?:첫째|첫\s*번째)[,.]?\s+.{10,50}\n.*?(?:둘째|두\s*번째)[,.]?\s+.{10,50}\n.*?(?:셋째|세\s*번째)", "나열형 반복"),
]

# AI가 과도하게 사용하는 접속사/연결어
AI_OVERUSED_CONNECTORS = [
    "또한", "특히", "따라서", "그러므로", "결론적으로",
    "무엇보다", "이처럼", "이렇게", "즉,", "다시 말해",
    "한편", "아울러", "뿐만 아니라", "나아가", "더불어",
]

# AI 특유의 구조적 패턴
AI_STRUCTURAL_PATTERNS = [
    # 모든 단락이 비슷한 길이 (±20% 이내)
    "uniform_paragraph_length",
    # H2 아래 항상 3-5개 포인트 나열
    "rigid_section_structure",
    # 단락 시작이 모두 비슷한 패턴
    "repetitive_paragraph_starts",
]


class HumanReviewResult:
    """휴먼 리뷰 결과"""

    def __init__(self):
        self.issues: list[dict] = []
        self.score: int = 100  # 100 = 완전 사람같음, 0 = AI 감지 가능성 높음
        self.rewritten_body: Optional[str] = None

    def add_issue(self, category: str, detail: str, severity: int = 5):
        """
        이슈 추가
        severity: 1(경미) ~ 10(심각)
        """
        self.issues.append({
            "category": category,
            "detail": detail,
            "severity": severity,
        })
        self.score = max(0, self.score - severity)

    @property
    def needs_rewrite(self) -> bool:
        return self.score < 80

    def summary(self) -> str:
        lines = [f"🔍 휴먼 리뷰 점수: {self.score}/100"]
        if not self.issues:
            lines.append("  ✅ AI 패턴 감지 없음 — 자연스러운 글입니다")
        else:
            lines.append(f"  ⚠️  감지된 이슈 {len(self.issues)}개:")
            for iss in self.issues:
                lines.append(f"    - [{iss['category']}] {iss['detail']} (심각도: {iss['severity']})")
        return "\n".join(lines)


def detect_ai_patterns(body: str) -> HumanReviewResult:
    """
    규칙 기반으로 AI 생성 텍스트의 패턴을 감지합니다.
    API 호출 없이 빠르게 동작합니다.
    """
    from collections import Counter

    result = HumanReviewResult()

    # ── 1. 상투적 표현 검사 ──
    for pattern, category in AI_CLICHE_PATTERNS:
        matches = re.findall(pattern, body)
        if matches:
            result.add_issue(
                "상투적 표현",
                f"{category}: \"{matches[0][:40]}\"",
                severity=4,
            )

    # ── 1-1. 직접 검색: AI가 즐겨 쓰는 표현 ──
    ai_direct_phrases = [
        ("정리해드리겠습니다", "AI 상투어", 3),
        ("살펴보겠습니다", "AI 상투어", 3),
        ("알아보겠습니다", "AI 상투어", 3),
        ("결론부터 말씀드리면", "AI 상투어", 3),
        ("함께 알아보", "AI 상투어", 2),
        ("하나씩 살펴보", "AI 상투어", 2),
        ("꼼꼼히 정리해", "AI 상투어", 2),
        ("완벽 정리", "AI 상투어", 2),
        ("총정리", "AI 상투어", 2),
    ]
    ai_phrase_count = 0
    for phrase, cat, sev in ai_direct_phrases:
        cnt = body.count(phrase)
        if cnt >= 1:
            ai_phrase_count += cnt
            if ai_phrase_count <= 3:  # 상위 3개만 개별 보고
                result.add_issue("상투적 표현", f'"{phrase}" ({cnt}회)', severity=sev)
    if ai_phrase_count >= 3:
        result.add_issue("상투적 표현", f"AI 상투어 총 {ai_phrase_count}개 감지", severity=5)

    # ── 2. 접속사/연결어 과다 사용 ──
    connector_counts = {}
    for connector in AI_OVERUSED_CONNECTORS:
        count = body.count(connector)
        if count >= 2:  # 임계값 낮춤: 2회부터 체크
            connector_counts[connector] = count

    if len(connector_counts) >= 3:
        top3 = sorted(connector_counts.items(), key=lambda x: -x[1])[:3]
        detail = ", ".join(f'"{k}"({v}회)' for k, v in top3)
        result.add_issue("접속사 과다", f"과도한 접속사 사용: {detail}", severity=6)
    elif len(connector_counts) >= 2:
        detail = ", ".join(f'"{k}"({v}회)' for k, v in connector_counts.items())
        result.add_issue("접속사 과다", f"접속사 반복: {detail}", severity=3)

    # ── 3. 종결어미 다양성 검사 (핵심 감지 항목) ──
    # "~니다" (~합니다, ~입니다, ~됩니다) 비율이 너무 높으면 AI
    ending_nida = len(re.findall(r'니다[.!?\s]', body))
    ending_seyo = len(re.findall(r'세요[.!?\s]', body))
    ending_ndeyo = len(re.findall(r'는데요[.!?\s]', body))
    ending_geodeunyo = len(re.findall(r'거든요[.!?\s]', body))
    ending_jiyo = len(re.findall(r'(?:이죠|지요|이에요)[.!?\s]', body))
    ending_rago = len(re.findall(r'더라고요[.!?\s]', body))

    total_endings = ending_nida + ending_seyo + ending_ndeyo + ending_geodeunyo + ending_jiyo + ending_rago
    if total_endings > 0:
        nida_ratio = ending_nida / total_endings
        if nida_ratio > 0.85 and ending_nida >= 15:
            result.add_issue(
                "종결어미 단조",
                f'"~니다" 종결이 {ending_nida}/{total_endings}회 ({nida_ratio:.0%}). '
                f'"~거든요/~는데요/~이죠" 등을 섞어야 자연스럽습니다.',
                severity=7,
            )
        elif nida_ratio > 0.75 and ending_nida >= 10:
            result.add_issue(
                "종결어미 단조",
                f'"~니다" 종결 비율이 높음: {ending_nida}/{total_endings}회 ({nida_ratio:.0%})',
                severity=4,
            )

    # ── 4. 볼드(**) 과다 사용 ──
    bold_count = len(re.findall(r'\*\*[^*]+\*\*', body))
    body_length = len(body)
    if bold_count >= 15:
        result.add_issue(
            "강조 과다",
            f"볼드(**) {bold_count}회 사용 — AI는 과도하게 강조합니다. 핵심만 강조해야 합니다.",
            severity=5,
        )
    elif bold_count >= 10:
        result.add_issue(
            "강조 과다",
            f"볼드(**) {bold_count}회 — 좀 더 절제하면 자연스럽습니다.",
            severity=3,
        )

    # ── 5. "첫째/둘째/셋째" 기계적 나열 ──
    ordinal_pattern = re.findall(r'\*\*(?:첫째|둘째|셋째|넷째|다섯째|첫\s*번째|두\s*번째|세\s*번째)', body)
    if len(ordinal_pattern) >= 3:
        result.add_issue(
            "기계적 나열",
            f'"첫째/둘째/셋째" 순서 나열 {len(ordinal_pattern)}회 — 자연스러운 문장으로 풀어야 합니다.',
            severity=5,
        )

    # ── 6. FAQ 구조 (Q1/Q2/Q3 정확히 3개) ──
    faq_count = len(re.findall(r'\*\*Q\d+\.', body))
    if faq_count == 3:
        result.add_issue(
            "기계적 구조",
            "FAQ가 정확히 3개 — AI 생성의 전형적 패턴입니다. 2개 또는 4개로 바꾸세요.",
            severity=4,
        )

    # ── 7. 단락 길이 균일성 검사 ──
    paragraphs = [p.strip() for p in body.split("\n\n")
                  if p.strip() and not p.strip().startswith("#") and not p.strip().startswith("|")]
    if len(paragraphs) >= 4:
        lengths = [len(p) for p in paragraphs]
        avg_len = sum(lengths) / len(lengths)
        if avg_len > 0:
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            cv = (variance ** 0.5) / avg_len
            if cv < 0.20:
                result.add_issue(
                    "구조적 패턴",
                    f"단락 길이가 균일함 (변동계수: {cv:.2f}). 짧은 단락과 긴 단락을 섞어야 합니다.",
                    severity=4,
                )

    # ── 8. 단락 시작 패턴 반복 검사 ──
    if len(paragraphs) >= 5:
        starts = []
        for p in paragraphs:
            first_word = p.split()[0] if p.split() else ""
            if first_word:
                starts.append(first_word)

        start_counter = Counter(starts)
        repeated = [(w, c) for w, c in start_counter.items() if c >= 3]
        if repeated:
            detail = ", ".join(f'"{w}"로 시작 {c}회' for w, c in repeated)
            result.add_issue(
                "구조적 패턴",
                f"단락 시작 반복: {detail}",
                severity=4,
            )

    # ── 9. 감탄부호 과다 ──
    exclamation_count = body.count("!")
    if exclamation_count > 8:
        result.add_issue(
            "톤 부자연스러움",
            f"느낌표 {exclamation_count}개 — 과도한 감탄은 AI 특징입니다.",
            severity=3,
        )

    # ── 10. 모든 섹션이 동일 패턴 ──
    h2_sections = re.split(r'^## ', body, flags=re.MULTILINE)
    if len(h2_sections) >= 4:
        bullet_counts = []
        for section in h2_sections[1:]:
            bullets = len(re.findall(r'^[-*]\s', section, re.MULTILINE))
            bullet_counts.append(bullets)
        if bullet_counts and len(set(bullet_counts)) == 1 and bullet_counts[0] >= 3:
            result.add_issue(
                "구조적 패턴",
                f"모든 섹션이 동일하게 {bullet_counts[0]}개 포인트 — 기계적 구조입니다.",
                severity=5,
            )

    # ── 11. "~주의하세요" "~확인하세요" 과다 ──
    advice_endings = len(re.findall(r'(?:주의하세요|확인하세요|유의하세요|참고하세요|기억하세요)', body))
    if advice_endings >= 4:
        result.add_issue(
            "톤 부자연스러움",
            f'"~하세요" 류 조언형 문장이 {advice_endings}회 — 다양한 표현으로 바꿔야 합니다.',
            severity=3,
        )

    # ── 12. 개인 경험 부재 ──
    personal_markers = [
        "제가 담당", "제 경험", "직접 처리", "제가 실제",
        "저도 처음", "실무에서 겪", "현장에서", "실제로 해보",
        "담당했던", "경험상", "체감", "솔직히",
    ]
    personal_found = sum(1 for m in personal_markers if m in body)
    if personal_found == 0:
        result.add_issue(
            "개인성 부재",
            "개인 경험이나 실무 체감 표현이 전혀 없음 — 사람 블로거라면 경험담이 있어야 합니다.",
            severity=5,
        )

    logger.info(result.summary())
    return result


def humanize_body(body: str, title: str, keyword: str, review: HumanReviewResult) -> str:
    """
    감지된 AI 패턴을 기반으로 Claude API를 사용하여 자연스럽게 리라이팅합니다.
    """
    import anthropic

    if not review.issues:
        logger.info("AI 패턴 미감지 — 리라이팅 스킵")
        return body

    logger.info(f"🔄 휴먼라이징 리라이팅 시작 (점수: {review.score}/100, 이슈: {len(review.issues)}개)")

    # 감지된 이슈를 프롬프트에 반영
    issues_text = "\n".join(
        f"- [{iss['category']}] {iss['detail']}"
        for iss in review.issues
    )

    prompt = f"""당신은 교육행정·지방자치단체 실무 경력 15년차 공무원 블로거입니다.
아래 글은 AI가 생성한 것으로 의심될 수 있는 패턴이 감지되었습니다.
사람이 직접 작성한 것처럼 자연스럽게 수정해 주세요.

## 감지된 문제점
{issues_text}

## 수정 지침

### 1. 문체 자연스럽게
- "오늘은 ~에 대해 알아보겠습니다" 같은 AI 상투어를 제거하세요
- 실무자가 실제로 쓰는 표현으로 바꾸세요 (예: "이번 건이 좀 헷갈리시죠?", "저도 처음에 많이 헤맸는데요")
- 때때로 짧은 문장 + 긴 문장을 섞으세요
- 한두 군데에 구어체를 살짝 넣으세요 (예: "솔직히 이 부분은 좀 까다롭습니다")

### 2. 종결어미 다양화
- "~입니다", "~합니다"만 반복하지 마세요
- "~거든요", "~는데요", "~잖아요", "~셈이죠", "~더라고요" 등을 섞으세요
- 가끔 질문형으로 ("혹시 이런 경우 겪어보셨나요?")

### 3. 접속사 줄이기
- "또한", "특히", "따라서" 등 기계적 연결어를 줄이세요
- 대신 문맥으로 자연스럽게 연결하거나, 줄바꿈으로 처리하세요

### 4. 단락 길이 불규칙하게
- 한 줄짜리 짧은 단락도 있고, 5-6줄 긴 단락도 있게 하세요
- 사람은 완벽하게 균일한 단락을 쓰지 않습니다

### 5. 개인 경험 요소 추가
- "제가 실제로 담당했던 건에서는~" 류의 경험담을 1-2개 넣으세요
- "현장에서 자주 실수하는 부분인데~" 같은 실전 팁을 추가하세요
- 구체적인 수치나 사례가 있으면 더 자연스럽습니다

### 6. 불완전함 유지
- 모든 것을 완벽하게 정리하지 마세요
- "이 부분은 각 기관마다 약간 다를 수 있어서 확인이 필요합니다" 같은 불확실성 표현도 좋습니다
- 사람은 모든 걸 다 아는 것처럼 쓰지 않습니다

## 중요 규칙
- **원문의 핵심 정보와 법령 인용은 절대 변경하지 마세요**
- **마크다운 형식(##, **, |표|)을 유지하세요**
- **키워드 "{keyword}"의 밀도를 유지하세요**
- **silmu.kr 링크를 유지하세요**
- **전체 분량을 유지하세요 (±10% 이내)**
- **표(table)의 데이터는 변경하지 마세요**
- **수정된 본문만 출력하세요 (설명이나 코멘트 없이)**

## 원문
{body}"""

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        rewritten = response.content[0].text.strip()

        # 기본 검증: 리라이팅 결과가 원본 대비 너무 짧거나 길면 거부
        original_len = len(body)
        rewritten_len = len(rewritten)

        if rewritten_len < original_len * 0.7:
            logger.warning(f"리라이팅 결과가 너무 짧음 ({rewritten_len} < {original_len * 0.7:.0f}자), 원본 유지")
            return body

        if rewritten_len > original_len * 1.4:
            logger.warning(f"리라이팅 결과가 너무 김 ({rewritten_len} > {original_len * 1.4:.0f}자), 원본 유지")
            return body

        # 키워드 밀도 검증
        original_kw_count = body.count(keyword) if keyword else 0
        rewritten_kw_count = rewritten.count(keyword) if keyword else 0

        if keyword and original_kw_count > 0:
            # 키워드가 긴 복합어일 경우 변형 표현도 카운트 (예: "추가경정예산" → "추경예산", "추경")
            kw_variants_count = rewritten_kw_count
            if len(keyword) >= 4:
                # 키워드의 앞 2글자로 시작하는 변형도 체크
                kw_prefix = keyword[:2]
                kw_variants_count += len(re.findall(rf'{re.escape(kw_prefix)}[가-힣]{{1,6}}', rewritten)) - rewritten_kw_count

            if rewritten_kw_count < original_kw_count * 0.3 and kw_variants_count < original_kw_count * 0.5:
                logger.warning(f"키워드 밀도 급감 ({original_kw_count}→{rewritten_kw_count}회, 변형 포함 {kw_variants_count}회), 원본 유지")
                return body

        # 링크 보존 검증
        if "silmu.kr" in body and "silmu.kr" not in rewritten:
            logger.warning("silmu.kr 링크 유실, 원본 유지")
            return body

        # 표 보존 검증
        original_tables = len(re.findall(r'^\|.+\|$', body, re.MULTILINE))
        rewritten_tables = len(re.findall(r'^\|.+\|$', rewritten, re.MULTILINE))
        if original_tables > 0 and rewritten_tables < original_tables * 0.5:
            logger.warning(f"표가 유실됨 ({original_tables}→{rewritten_tables}개), 원본 유지")
            return body

        logger.info(f"✅ 휴먼라이징 완료: {original_len}자 → {rewritten_len}자")
        return rewritten

    except Exception as e:
        logger.error(f"휴먼라이징 API 호출 실패: {e}, 원본 유지")
        return body


def quick_fix_patterns(body: str) -> str:
    """
    API 호출 없이 간단한 패턴만 빠르게 수정합니다.
    (리라이팅이 필요 없는 경미한 이슈용)
    """
    fixed = body

    # 1. 과도한 느낌표 줄이기 (3개 이상 연속 → 1개)
    fixed = re.sub(r'!{2,}', '!', fixed)

    # 2. 반복되는 "또한" 일부를 다른 표현으로 교체
    replacements = {
        0: "",          # 그냥 삭제 (문맥 연결)
        1: "그리고 ",
        2: "더불어 ",
        3: "이 밖에도 ",
    }
    idx = [0]

    def replace_connector(match):
        i = idx[0] % 4
        idx[0] += 1
        if i == 0 and idx[0] > 1:  # 첫 번째는 유지
            return replacements[i]
        return match.group(0)

    # "또한"이 5개 이상일 때만 교체
    if body.count("또한") >= 5:
        fixed = re.sub(r'또한[,]?\s', replace_connector, fixed)

    # 3. "~것입니다."를 다양하게 (5개 이상일 때)
    ending_replacements = ["거든요.", "셈이죠.", "는 겁니다.", "점, 기억하세요."]
    end_idx = [0]

    def diversify_endings(match):
        i = end_idx[0]
        end_idx[0] += 1
        if i % 3 == 0 and i > 0:
            return ending_replacements[i % len(ending_replacements)]
        return match.group(0)

    if len(re.findall(r'것입니다\.', fixed)) >= 5:
        fixed = re.sub(r'것입니다\.', diversify_endings, fixed)

    return fixed


class Humanizer:
    """
    발행 전 휴먼 리뷰 & 리라이팅 통합 클래스

    사용법:
        humanizer = Humanizer()
        body = humanizer.review_and_fix(body, title, keyword)
    """

    def __init__(self, db: Optional[Database] = None):
        self.db = db

    def review_and_fix(self, body: str, title: str, keyword: str,
                       force_rewrite: bool = False) -> tuple[str, HumanReviewResult]:
        """
        본문을 검토하고 필요시 수정합니다.

        Args:
            body: 마크다운 본문
            title: 포스트 제목
            keyword: 타겟 키워드
            force_rewrite: True이면 점수와 관계없이 항상 리라이팅

        Returns:
            (수정된 본문, 리뷰 결과)
        """
        # 1단계: 규칙 기반 패턴 감지
        review = detect_ai_patterns(body)
        logger.info(f"패턴 감지 결과: 점수 {review.score}/100, 이슈 {len(review.issues)}개")

        # 2단계: 간단한 패턴 퀵 픽스 (항상 적용)
        fixed_body = quick_fix_patterns(body)

        # 3단계: 심각한 경우 또는 강제 모드일 때 Claude API 리라이팅
        if review.needs_rewrite or force_rewrite:
            logger.info(f"{'강제 모드' if force_rewrite else '점수 미달'} → Claude API 리라이팅 실행")
            fixed_body = humanize_body(fixed_body, title, keyword, review)

            # 리라이팅 후 재검사
            post_review = detect_ai_patterns(fixed_body)
            logger.info(f"리라이팅 후 재검사: {review.score} → {post_review.score}")

            if post_review.score > review.score:
                review = post_review
                review.rewritten_body = fixed_body
            else:
                logger.info("리라이팅 결과가 개선되지 않아 원본 유지")
                fixed_body = body
        else:
            # 퀵 픽스만 적용
            if fixed_body != body:
                logger.info("퀵 픽스만 적용 (API 리라이팅 불필요)")

        return fixed_body, review
