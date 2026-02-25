"""
법령 검증 모듈 (#16-19)

포스트 본문에서 법령 인용을 추출하고 Claude API로 검증 후 DB에 저장.
"""

import re
import json
from typing import Optional
from utils.database import Database
from utils.logger import get_logger
from config.settings import settings

logger = get_logger()

# 통용 약칭 — 존재 검증 불필요
ACCEPTED_ABBREVIATIONS = {
    "지방계약법", "국가계약법", "지방재정법", "국가재정법",
    "학교회계법", "물품관리법", "공유재산법", "건설기술진흥법",
    "지방계약법 시행령", "국가계약법 시행령", "지방재정법 시행령",
    "지방계약법 시행규칙", "국가계약법 시행규칙",
}

# 법령명 추출 패턴
CITATION_PATTERNS = [
    r'「([^」]+)」\s*(제\d+조(?:의\d+)?(?:\s*제\d+항(?:\s*제\d+호)?)?)?',
    r'([가-힣]+법(?:\s*시행령|\s*시행규칙)?)\s*(제\d+조(?:의\d+)?(?:\s*제\d+항(?:\s*제\d+호)?)?)',
]


def extract_citations(text: str) -> list[dict]:
    """
    본문에서 법령 인용 추출.

    Returns:
        list of {law_name, article_number, citation_text}
    """
    results = []
    seen = set()

    for pattern in CITATION_PATTERNS:
        for m in re.finditer(pattern, text):
            law_name = m.group(1).strip()
            article = m.group(2).strip() if m.lastindex >= 2 and m.group(2) else ""
            citation_text = m.group(0).strip()

            key = (law_name, article)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "law_name": law_name,
                "law_name_normalized": _normalize_law_name(law_name),
                "article_number": article,
                "citation_text": citation_text,
            })

    return results


def _normalize_law_name(name: str) -> str:
    """법령명 정규화 (공백, 약칭 통일)"""
    name = name.strip()
    # '지방계약법' → '지방자치단체를 당사자로 하는 계약에 관한 법률' 같은 정규화는
    # 필요 시 확장. 현재는 공백 정리만.
    return re.sub(r'\s+', ' ', name)


class LegalVerifier:
    """법령 인용 추출 → 검증 → DB 저장"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database(settings.DB_PATH)
        self._client = None  # 필요 시 초기화 (API 호출 있을 때만)

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    # ──────────────────────────────────────────
    # 퍼블릭 API
    # ──────────────────────────────────────────

    def process_post(self, post_id: int, body: str) -> dict:
        """
        포스트 생성/저장 후 법령 인용을 추출하여 DB에 저장.
        검증은 비동기로 별도 실행 (verify_post).

        Returns: {'saved': int, 'citations': list}
        """
        citations = extract_citations(body)
        if not citations:
            logger.info(f"포스트 {post_id}: 법령 인용 없음")
            return {"saved": 0, "citations": []}

        # 기존 인용 삭제 후 재저장 (재생성 대응)
        self.db.execute("DELETE FROM legal_references WHERE post_id = ?", (post_id,))

        ref_ids = []
        for c in citations:
            ref_id = self.db.insert(
                """INSERT INTO legal_references
                   (post_id, law_name, law_name_normalized, article_number,
                    citation_text, verification_status)
                   VALUES (?, ?, ?, ?, ?, 'pending')""",
                (post_id, c["law_name"], c["law_name_normalized"],
                 c["article_number"], c["citation_text"]),
            )
            c["id"] = ref_id
            ref_ids.append(ref_id)

        logger.info(f"포스트 {post_id}: 법령 인용 {len(citations)}개 저장")
        return {"saved": len(citations), "citations": citations}

    def verify_post(self, post_id: int) -> dict:
        """
        저장된 법령 인용을 Claude API로 검증하고 결과를 DB에 저장.

        Returns: {'verified': int, 'pass': int, 'fail': int, 'warning': int}
        """
        refs = self.db.execute(
            "SELECT * FROM legal_references WHERE post_id = ?", (post_id,)
        )
        if not refs:
            return {"verified": 0, "pass": 0, "fail": 0, "warning": 0}

        # 통용 약칭은 자동 통과
        auto_pass = []
        to_verify = []
        for r in refs:
            if r["law_name_normalized"] in ACCEPTED_ABBREVIATIONS and not r["article_number"]:
                auto_pass.append(r)
            else:
                to_verify.append(r)

        # 자동 통과 처리
        for r in auto_pass:
            self._save_check(r["id"], "exists", "pass", "통용 약칭 자동 승인")
            self.db.execute(
                "UPDATE legal_references SET verification_status='verified' WHERE id=?",
                (r["id"],),
            )

        # Claude API 검증
        results = {"verified": len(refs), "pass": len(auto_pass), "fail": 0, "warning": 0}

        if to_verify:
            api_results = self._verify_with_claude(to_verify)
            for ref_id, verdict, detail in api_results:
                check_result = "pass" if verdict == "정확" else ("fail" if verdict == "부정확" else "warning")
                self._save_check(ref_id, "article_valid", check_result, detail)

                status = "verified" if check_result == "pass" else (
                    "failed" if check_result == "fail" else "warning"
                )
                self.db.execute(
                    "UPDATE legal_references SET verification_status=?, last_verified_at=CURRENT_TIMESTAMP WHERE id=?",
                    (status, ref_id),
                )
                results[check_result] = results.get(check_result, 0) + 1

        logger.info(f"포스트 {post_id} 법령 검증 완료: {results}")
        return results

    def get_post_citations(self, post_id: int) -> list[dict]:
        """포스트의 법령 인용 목록 조회"""
        refs = self.db.execute(
            """SELECT r.*,
                      (SELECT result FROM legal_checks WHERE reference_id = r.id ORDER BY checked_at DESC LIMIT 1) as last_check_result,
                      (SELECT details FROM legal_checks WHERE reference_id = r.id ORDER BY checked_at DESC LIMIT 1) as last_check_details
               FROM legal_references r
               WHERE r.post_id = ?
               ORDER BY r.id""",
            (post_id,),
        )
        return [dict(r) for r in refs]

    # ──────────────────────────────────────────
    # 내부 메서드
    # ──────────────────────────────────────────

    def _verify_with_claude(self, refs: list) -> list[tuple]:
        """Claude API로 법령 조문 검증. Returns list of (ref_id, verdict, detail)"""
        items = []
        for r in refs:
            label = r["citation_text"] if r["citation_text"] else r["law_name"]
            if r["article_number"]:
                label = f"{r['law_name']} {r['article_number']}"
            items.append((r["id"], label))

        prompt = f"""다음 법령 조문이 실제로 존재하고 정확한지 검증해주세요.
검증 대상:
{chr(10).join(f'- {label}' for _, label in items)}

맥락: 공무원 계약·조달·예산·복무 관련 블로그에서 인용된 조문입니다.

반드시 아래 형식으로만 응답하세요 (한 줄에 하나, 부가 설명 없이):
인용문 | 정확
인용문 | 부정확 | 올바른조문
인용문 | 확인불가"""

        try:
            response = self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            logger.info(f"법령 검증 API 응답:\n{text}")

            # 파싱
            results = []
            lines = text.split("\n")
            for i, (ref_id, label) in enumerate(items):
                verdict = "확인불가"
                detail = ""
                if i < len(lines):
                    parts = [p.strip() for p in lines[i].split("|")]
                    if len(parts) >= 2:
                        verdict = parts[1]
                        detail = parts[2] if len(parts) >= 3 else ""
                results.append((ref_id, verdict, detail))
            return results

        except Exception as e:
            logger.warning(f"Claude 법령 검증 실패: {e}")
            return [(r["id"], "확인불가", f"API 오류: {str(e)[:50]}") for r in refs]

    def _save_check(self, reference_id: int, check_type: str, result: str, details: str):
        self.db.insert(
            """INSERT INTO legal_checks (reference_id, check_type, result, details)
               VALUES (?, ?, ?, ?)""",
            (reference_id, check_type, result, details),
        )
