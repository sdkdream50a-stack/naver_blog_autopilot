# NaverBlogAutoPilot 테스트 전략 문서

## 테스트 목표

이 프로젝트의 테스트 전략은 다음 목표를 달성합니다:

1. **기능 검증**: 각 모듈이 명시된 기능을 올바르게 수행
2. **회귀 방지**: 코드 변경이 기존 기능에 영향을 주지 않음
3. **품질 보증**: 높은 코드 품질 유지
4. **신뢰성**: 프로덕션 배포 전 확신

## 테스트 범위

### 1. 컬렉터 모듈 (Collector Module)
**파일**: `tests/test_collector.py`

#### DataCleaner 테스트
- ✓ HTML 태그 제거
- ✓ 스크립트/스타일 제거
- ✓ 공백 정규화
- ✓ 한글 보존
- ✓ 빈 HTML 처리

#### SilmuCrawler 테스트
- ✓ 텍스트 분류 (기술, 비즈니스, 건강, 기타)
- ✓ HTML에서 텍스트 추출
- ✓ 단락 구분 유지
- ✓ 빈 HTML 처리
- ✓ 다중 키워드 분류

### 2. 리서처 모듈 (Researcher Module)
**파일**: `tests/test_researcher.py`

#### KeywordAnalyzer 테스트
- ✓ 점수 계산 (높은 검색량, 낮은 경쟁도)
- ✓ 점수 계산 (낮은 검색량, 낮은 경쟁도)
- ✓ 점수 계산 (높은 검색량, 높은 경쟁도)
- ✓ 0 검색량 처리
- ✓ 관련성 기반 점수 조정
- ✓ 서명 생성 (API 인증)
- ✓ 키워드 분석 결과 반환

#### CompetitorScanner 테스트
- ✓ 다중 포스트 경쟁도 점수
- ✓ 높은 참여도 포스트
- ✓ 낮은 참여도 포스트
- ✓ 빈 포스트 목록 처리
- ✓ 단일 포스트 처리
- ✓ 가중 점수 계산
- ✓ 경쟁사 분석 결과 제한

### 3. 생성기 모듈 (Generator Module)
**파일**: `tests/test_generator.py`

#### SEOOptimizer 테스트
- ✓ 점수 계산 (좋은 품질)
- ✓ 점수 계산 (저품질)
- ✓ 제목에 키워드 포함 확인
- ✓ 빈 콘텐츠 처리
- ✓ 긴 콘텐츠 점수
- ✓ 키워드 밀도 계산
- ✓ Auth-GR 확인
- ✓ C-Rank 확인
- ✓ Dia+ 확인
- ✓ AI 요약 확인

#### QualityChecker 테스트
- ✓ 표절 없음 확인
- ✓ 높은 유사도 표절 감지
- ✓ 부분 일치 표절
- ✓ 빈 텍스트 처리
- ✓ 동일 텍스트 유사도 (1.0)
- ✓ 완전히 다른 텍스트 (0.0)
- ✓ 부분 일치 유사도
- ✓ 단어 순서 영향도
- ✓ 우수한 포스트 품질
- ✓ 저품질 포스트
- ✓ 문제점 식별

### 4. 퍼블리셔 모듈 (Publisher Module)
**파일**: `tests/test_publisher.py`

#### AntiDetection 테스트
- ✓ 일일 제한 미만
- ✓ 일일 제한 도달
- ✓ 일일 제한 초과
- ✓ 0 제한 처리
- ✓ 높은 제한 처리
- ✓ 주간 제한 미만
- ✓ 주간 제한 도달
- ✓ 주간 제한 초과
- ✓ 주간 제한 리셋
- ✓ 발행 간격 충분
- ✓ 발행 간격 부족
- ✓ 첫 발행 처리
- ✓ 모든 조건 만족 시 발행 가능
- ✓ 다음 발행 시간 계산

### 5. 데이터베이스 모듈 (Database Module)
**파일**: `tests/test_database.py`

#### Database 테스트
- ✓ 9개 모든 테이블 생성
  - articles
  - processed_articles
  - crawl_log
  - keywords
  - keyword_history
  - competitor_posts
  - posts
  - posting_history
  - ranking_history
- ✓ 데이터 삽입 (INSERT)
- ✓ 쿼리 실행 (SELECT)
- ✓ 업데이트 (UPDATE)
- ✓ 삭제 (DELETE)
- ✓ 데이터 개수 (COUNT)
- ✓ NULL 값 처리
- ✓ UNIQUE 제약 조건
- ✓ 매개변수화 쿼리
- ✓ 트랜잭션 커밋
- ✓ 트랜잭션 롤백

### 6. 모니터 모듈 (Monitor Module)
**파일**: `tests/test_monitor.py`

#### ReportGenerator 테스트
- ✓ 주간 통계 조회
- ✓ 월간 통계 조회
- ✓ 필수 메트릭 포함
- ✓ 포스트 없는 기간 처리
- ✓ 오류 정보 포함
- ✓ 마크다운 포맷팅
- ✓ 제목 포함
- ✓ 통계 포함
- ✓ 테이블 형식
- ✓ 주간 리포트 생성
- ✓ 기간 포함
- ✓ 통계 포함
- ✓ 월간 리포트 생성
- ✓ 성장률 포함
- ✓ 상위 키워드 포함

## 테스트 통계

### 총 테스트 수: 107개

| 모듈 | 테스트 수 | 커버리지 목표 |
|------|---------|------------|
| Collector | 16개 | 85% |
| Researcher | 20개 | 85% |
| Generator | 22개 | 85% |
| Publisher | 20개 | 90% |
| Database | 17개 | 95% |
| Monitor | 15개 | 80% |

## 테스트 실행 시간

- 전체 테스트: ~5-10초
- 단위 테스트: ~2-3초
- 통합 테스트: ~3-5초

## Mock 전략

### 사용 사유

- **네트워크 독립성**: HTTP 요청 모킹으로 외부 의존성 제거
- **빠른 실행**: 실제 API 호출 없이 빠른 테스트
- **격리**: 테스트 간 상호 영향 없음
- **재현성**: 일관된 결과 보장

### Mock 객체

```python
# 데이터베이스
mock_db = temp_db  # 메모리 기반 SQLite

# 설정
mock_settings = MagicMock()

# HTTP 클라이언트
mock_http_client = MagicMock()
```

## 픽스처 설계

### temp_db
- 메모리 기반 SQLite 데이터베이스
- 자동으로 스키마 생성
- 테스트마다 격리된 인스턴스

### mock_settings
- 설정 객체 모킹
- 파일 시스템 접근 없음
- 기본값 설정

### Sample Data Fixtures
- sample_html: 테스트용 HTML
- sample_article: 테스트용 기사
- sample_keyword_data: 키워드 데이터
- sample_generated_post: 생성된 포스트
- 등 7개 추가 샘플 데이터

## 테스트 실행 방법

### 모든 테스트
```bash
pytest tests/
```

### 특정 모듈
```bash
pytest tests/test_collector.py
pytest tests/test_researcher.py
pytest tests/test_generator.py
pytest tests/test_publisher.py
pytest tests/test_database.py
pytest tests/test_monitor.py
```

### 특정 클래스
```bash
pytest tests/test_collector.py::TestDataCleaner
pytest tests/test_generator.py::TestSEOOptimizer
```

### 특정 테스트
```bash
pytest tests/test_collector.py::TestDataCleaner::test_clean_removes_html_tags
```

### 상세 보고
```bash
pytest tests/ -v
pytest tests/ -vv  # 더 상세
```

### 커버리지 리포트
```bash
pytest tests/ --cov=. --cov-report=html
# htmlcov/index.html 확인
```

### 속도 측정
```bash
pytest tests/ --durations=10
```

## 테스트 명명 규칙

### 클래스
- `Test` + 클래스이름
- 예: `TestDataCleaner`, `TestSEOOptimizer`

### 메서드
- `test_` + 기능설명
- 예: `test_clean_removes_html_tags`
- 각 메서드는 하나의 동작만 테스트

## 주석 규칙

모든 테스트 메서드는 한글 docstring 포함:

```python
def test_clean_removes_html_tags(self):
    """HTML 태그 제거 테스트"""
    # 설정
    # 실행
    # 검증
```

## CI/CD 통합

테스트는 자동으로:
1. Pull Request 제출 시 실행
2. Main 브랜치 머지 전 실행
3. 배포 전 실행

## 추가 테스트 가이드

### 새로운 기능 추가 시
1. 해당 테스트 파일 확인
2. 새 테스트 메서드 추가
3. Mock 객체 필요 시 conftest.py 수정
4. 테스트 실행 및 확인

### 버그 수정 시
1. 버그를 재현하는 테스트 추가
2. 버그 수정
3. 해당 테스트 패스 확인
4. 전체 테스트 실행

### 리팩토링 시
1. 먼저 전체 테스트 실행 (기준선)
2. 리팩토링 수행
3. 테스트 재실행
4. 100% 패스 확인

## 트러블슈팅

### 테스트 찾기 실패
```bash
pytest tests/ --collect-only
# 테스트가 발견되는지 확인
```

### AsyncIO 에러
```bash
pip install --upgrade pytest-asyncio
```

### Import 에러
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/
```

### 특정 테스트만 실행 안 됨
```bash
pytest -k "test_specific_name" -v
```

## 성능 최적화

- 메모리 DB 사용으로 I/O 최소화
- Mock 객체로 네트워크 요청 제거
- 병렬 실행 가능 (pytest-xdist)

```bash
pip install pytest-xdist
pytest tests/ -n auto
```

## 문서화

- 모든 테스트에 한글 설명
- 복잡한 테스트는 주석 추가
- 샘플 데이터 구조 명확화
