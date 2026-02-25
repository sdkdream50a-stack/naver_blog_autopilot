# Phase 3: 법령 검증 자동화 아키텍처

**작성일:** 2026-02-24
**버전:** 1.0

---

## 📋 개요

5개 정부 사이트를 크롤링하여 생성된 블로그 포스트의 법령 인용을 자동 검증하는 시스템입니다.

**핵심 목표:**
- 법령 인용의 정확성 100% 보장
- 법령 개정 시 자동 감지 및 알림
- 신뢰도 향상 (법적 오류 0건)

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│              Content Generation (Phase 1)                │
│                  포스트 생성 완료                         │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│           Legal Reference Extractor                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 1. 정규표현식으로 법령 인용 추출                  │   │
│  │    - 「법령명」 패턴                              │   │
│  │    - 제N조, 시행령, 시행규칙 패턴                │   │
│  │ 2. 법령명 정규화 (통용약칭 → 정식명칭)           │   │
│  │ 3. 조문 번호 파싱                                │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│              Legal Verification Engine                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Level 1: 법령 존재 확인                          │   │
│  │   - 국가법령정보센터 API 조회                    │   │
│  │   - 결과: EXISTS / NOT_FOUND                     │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ Level 2: 조문 번호 유효성 확인                   │   │
│  │   - 해당 법령의 조문 목록 조회                   │   │
│  │   - 결과: VALID / INVALID                        │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ Level 3: 조문 내용 일치 확인 (선택)              │   │
│  │   - 조문 전문 비교 (유사도)                      │   │
│  │   - 결과: MATCH / PARTIAL / MISMATCH             │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│                 Verification Results                     │
│  ┌──────────────────────────────────────────────────┐   │
│  │ ✅ PASS: 모든 검증 통과                          │   │
│  │ ⚠️  WARNING: 일부 경고 (예: 개정 예정)          │   │
│  │ ❌ FAIL: 검증 실패 (법령 없음, 조문 오류 등)     │   │
│  └──────────────────────────────────────────────────┘   │
│  → DB 저장 (legal_references, legal_checks)              │
│  → 알림 생성 (검증 실패 시)                              │
└─────────────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│           Legal Change Detection (Scheduler)             │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 1. 일일 1회 실행 (새벽 3시)                      │   │
│  │ 2. 모든 인용된 법령의 개정일 확인                │   │
│  │ 3. 개정 발견 시:                                 │   │
│  │    - legal_changes 테이블에 기록                │   │
│  │    - 영향받는 포스트 목록 생성                   │   │
│  │    - 알림 생성                                   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 데이터 모델

### legal_references (법령 인용)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER | Primary Key |
| post_id | INTEGER | 포스트 ID (FK) |
| law_name | TEXT | 법령명 (원본) |
| law_name_normalized | TEXT | 정규화된 법령명 |
| article_number | TEXT | 조문 번호 (예: 제9조) |
| citation_text | TEXT | 인용 원문 |
| verification_status | TEXT | pending/verified/failed/warning |
| error_message | TEXT | 오류 메시지 |
| last_verified_at | TIMESTAMP | 마지막 검증 시각 |
| created_at | TIMESTAMP | 생성 시각 |

### legal_checks (검증 기록)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER | Primary Key |
| reference_id | INTEGER | 법령 인용 ID (FK) |
| check_type | TEXT | exists/article_valid/content_match |
| result | TEXT | pass/fail/warning |
| details | TEXT | JSON 상세 정보 |
| checked_at | TIMESTAMP | 검증 시각 |

### legal_changes (법령 변경)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER | Primary Key |
| law_name | TEXT | 법령명 |
| change_type | TEXT | amended/repealed/new |
| change_date | DATE | 변경일 |
| description | TEXT | 변경 내용 |
| affected_posts_count | INTEGER | 영향받는 포스트 수 |
| notified | BOOLEAN | 알림 발송 여부 |
| detected_at | TIMESTAMP | 감지 시각 |

---

## 🔌 크롤러 아키텍처

### BaseLegalCrawler (추상 클래스)

```python
class BaseLegalCrawler:
    """법령 정보 크롤러 베이스 클래스"""

    def search_law(self, law_name: str) -> Optional[dict]:
        """법령 검색"""
        raise NotImplementedError

    def get_article(self, law_name: str, article_number: str) -> Optional[dict]:
        """조문 조회"""
        raise NotImplementedError

    def get_amendments(self, law_name: str, since: date) -> List[dict]:
        """개정 이력 조회"""
        raise NotImplementedError
```

### 구현체 (5개 사이트)

1. **LawCrawler** - 국가법령정보센터 (Open API)
   - 우선순위: 최고
   - 방식: REST API
   - 인증: API Key
   - 제한: 일일 1,000회

2. **MogefCrawler** - 행정안전부 (웹 크롤링)
   - 우선순위: 중
   - 방식: BeautifulSoup4
   - 인증: 불필요
   - 제한: 없음

3. **PPSCrawler** - 조달청 (웹 크롤링)
   - 우선순위: 중
   - 방식: Selenium (동적 페이지)
   - 인증: 불필요
   - 제한: Rate limiting 주의

4. **LocalGovCrawler** - 지자체 (웹 크롤링)
   - 우선순위: 낮
   - 방식: 사이트별 커스텀
   - 인증: 불필요

5. **EDUCrawler** - 교육청 (웹 크롤링)
   - 우선순위: 낮
   - 방식: 사이트별 커스텀
   - 인증: 불필요

---

## 🔍 법령 인용 추출 로직

### 정규표현식 패턴

```python
PATTERNS = {
    # 「법령명」 형식
    'law_bracket': r'「([^」]+)」',

    # 제N조, 제N조의N 형식
    'article': r'제(\d+)조(?:의(\d+))?',

    # 시행령, 시행규칙
    'enforcement': r'(시행령|시행규칙)',

    # 통합 패턴
    'full_citation': r'「([^」]+)」\s*(?:(시행령|시행규칙))?\s*제(\d+)조(?:의(\d+))?'
}
```

### 법령명 정규화 사전

```python
LAW_NORMALIZATION = {
    # 통용약칭 → 정식명칭
    '지방계약법': '지방자치단체를 당사자로 하는 계약에 관한 법률',
    '학교회계법': '학교회계 예산편성 기본지침',
    '교육공무원법': '교육공무원법',
    '지방공무원법': '지방공무원법',
    # ... 100개 이상
}
```

---

## ✅ 검증 프로세스

### 1단계: 법령 존재 확인

```python
def verify_law_exists(law_name: str) -> bool:
    """국가법령정보센터 API로 법령 존재 확인"""
    crawler = LawCrawler()
    result = crawler.search_law(law_name)
    return result is not None
```

### 2단계: 조문 유효성 확인

```python
def verify_article_valid(law_name: str, article_number: str) -> bool:
    """해당 법령에 조문이 존재하는지 확인"""
    crawler = LawCrawler()
    article = crawler.get_article(law_name, article_number)
    return article is not None
```

### 3단계: 조문 내용 일치 확인 (선택)

```python
def verify_article_content(citation_text: str, actual_content: str) -> float:
    """인용문과 실제 조문의 유사도 계산 (0~1)"""
    from difflib import SequenceMatcher
    similarity = SequenceMatcher(None, citation_text, actual_content).ratio()
    return similarity
```

---

## 🔔 알림 시나리오

### 검증 실패 시

**트리거:** 법령 검증 실패 (Level 1 또는 Level 2)

**알림 내용:**
- 제목: "법령 검증 실패: {포스트 제목}"
- 내용:
  - 실패한 법령명
  - 오류 원인 (법령 없음 / 조문 번호 오류)
  - 권장 조치: 포스트 수정 또는 삭제

**액션:**
- 포스트 상태 → `rejected`
- 알림 타입: `error`

### 법령 개정 감지 시

**트리거:** 일일 스케줄러에서 법령 개정 발견

**알림 내용:**
- 제목: "법령 개정 감지: {법령명}"
- 내용:
  - 개정일
  - 영향받는 포스트 수
  - 권장 조치: 포스트 재검증 또는 업데이트

**액션:**
- legal_changes 테이블에 기록
- 알림 타입: `warning`

---

## 🚀 구현 우선순위

### Phase 3.1 (필수, 1주)
1. ✅ DB 스키마 추가
2. ✅ 법령 인용 추출 로직
3. ✅ 국가법령정보센터 API 연동 (Level 1 검증)
4. ✅ 검증 엔진 기본 구현
5. ✅ UI 통합 (검증 결과 표시)

### Phase 3.2 (선택, 1주)
6. ⏸️ 행정안전부 크롤러
7. ⏸️ 조달청 크롤러
8. ⏸️ Level 2/3 검증 추가
9. ⏸️ 변경 감지 스케줄러

---

## 📊 성공 지표

| 지표 | 목표 | 측정 방법 |
|------|------|-----------|
| 법령 인용 추출 정확도 | 95% 이상 | 샘플 100개 수동 검증 |
| 검증 통과율 | 100% | 모든 포스트 검증 통과 |
| 법령 오류 건수 | 0건/월 | 사용자 신고 + 자체 감사 |
| 개정 감지 지연 시간 | 24시간 이내 | 개정일 - 감지일 |
| API 응답 시간 | 2초 이내 | 평균 응답 시간 |

---

## 🔒 리스크 및 완화 전략

### 1. API 호출 제한 초과 (High)
**위험:** 국가법령정보센터 일일 1,000회 제한

**완화:**
- 캐싱 (법령 정보 7일간 저장)
- 배치 처리 (한 번에 여러 법령 조회)
- 우선순위 큐 (중요한 법령부터)

### 2. 법령명 매칭 실패 (Medium)
**위험:** 통용약칭과 정식명칭 불일치

**완화:**
- 법령명 정규화 사전 (100개 이상)
- Fuzzy matching (유사도 90% 이상)
- 수동 매핑 UI 제공

### 3. 크롤링 차단 (Low)
**위험:** 사이트에서 크롤러 차단

**완화:**
- User-Agent 로테이션
- Rate limiting (1초 대기)
- API 우선 사용 (웹 크롤링 최소화)

---

## 📝 다음 단계

1. **Task #16:** 국가법령정보센터 API 연동
2. **Task #17:** 법령 인용 추출 로직 구현
3. **Task #18:** 검증 엔진 구현
4. **Task #19:** 변경 감지 시스템 (선택)
5. **Task #20:** UI 통합

---

**문서 버전:** 1.0
**마지막 업데이트:** 2026-02-24
