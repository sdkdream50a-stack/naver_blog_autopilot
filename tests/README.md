# NaverBlogAutoPilot 테스트 가이드

## 개요

이 디렉토리에는 NaverBlogAutoPilot 프로젝트의 포괄적인 테스트 스위트가 포함되어 있습니다.

## 테스트 파일 설명

### 1. conftest.py
pytest 설정 및 공통 픽스처 정의
- `temp_db`: 메모리 기반 SQLite 데이터베이스
- `mock_settings`: 설정 객체 모킹
- `mock_http_client`: HTTP 클라이언트 모킹
- 다양한 샘플 데이터 픽스처

### 2. test_collector.py
컬렉터 모듈 테스트
- `TestDataCleaner`: HTML 정제, 텍스트 정규화
- `TestSilmuCrawler`: 텍스트 분류, 텍스트 추출

테스트 항목:
- HTML 태그 제거
- 스크립트 및 스타일 제거
- 공백 정규화
- 텍스트 분류 (기술, 비즈니스, 건강 등)

### 3. test_researcher.py
리서처 모듈 테스트
- `TestKeywordAnalyzer`: 키워드 분석, 점수 계산
- `TestCompetitorScanner`: 경쟁사 분석

테스트 항목:
- 키워드 점수 계산 (검색량, 경쟁도, 관련성)
- 경쟁사 포스트 분석
- 경쟁도 점수 계산
- 서명 생성 (API 인증)

### 4. test_generator.py
생성기 모듈 테스트
- `TestSEOOptimizer`: SEO 최적화, 점수 계산
- `TestQualityChecker`: 표절 검사, 품질 확인

테스트 항목:
- SEO 점수 계산
- 키워드 밀도 계산
- 네이버 특화 기능 확인 (Auth-GR, C-Rank, Dia+)
- 표절 검사
- 유사도 계산

### 5. test_publisher.py
퍼블리셔 모듈 테스트
- `TestAntiDetection`: 탐지 회피 로직

테스트 항목:
- 일일 발행 제한 확인
- 주간 발행 제한 확인
- 발행 간격 확인
- 다음 발행 시간 계산

### 6. test_database.py
데이터베이스 모듈 테스트
- `TestDatabase`: DB 연산

테스트 항목:
- 모든 9개 테이블 생성 확인
- 데이터 삽입 (INSERT)
- 쿼리 실행 (SELECT, UPDATE, DELETE)
- 데이터 개수 세기 (COUNT)
- 연결 관리

### 7. test_monitor.py
모니터 모듈 테스트
- `TestReportGenerator`: 리포트 생성

테스트 항목:
- 주간 통계 조회
- 월간 통계 조회
- 마크다운 포맷팅
- 주간 리포트 생성
- 월간 리포트 생성

## 설치 및 실행

### 필수 패키지 설치

```bash
pip install pytest pytest-asyncio pytest-mock beautifulsoup4
```

또는 requirements-dev.txt 사용:

```bash
pip install -r requirements-dev.txt
```

### 모든 테스트 실행

```bash
pytest tests/
```

### 특정 테스트 파일 실행

```bash
pytest tests/test_collector.py
pytest tests/test_researcher.py
pytest tests/test_generator.py
pytest tests/test_publisher.py
pytest tests/test_database.py
pytest tests/test_monitor.py
```

### 특정 테스트 실행

```bash
# 클래스별
pytest tests/test_collector.py::TestDataCleaner

# 함수별
pytest tests/test_collector.py::TestDataCleaner::test_clean_removes_html_tags
```

### 상세 출력 모드

```bash
pytest tests/ -v
```

### 커버리지 확인

```bash
pip install pytest-cov
pytest tests/ --cov=. --cov-report=html
```

### 특정 마커만 실행

```bash
# 비동기 테스트만
pytest tests/ -m asyncio

# 데이터베이스 테스트만
pytest tests/ -m database
```

## 테스트 구조

### 픽스처 활용

테스트는 conftest.py에서 정의된 픽스처를 사용합니다:

```python
def test_example(temp_db, mock_settings, sample_html):
    # temp_db: 메모리 데이터베이스
    # mock_settings: 모킹된 설정
    # sample_html: 샘플 HTML 데이터
    pass
```

### Mock 객체 사용

실제 구현 없이 인터페이스만 테스트:

```python
from unittest.mock import MagicMock

analyzer = MagicMock()
analyzer._calculate_score.return_value = 85.0

result = analyzer._calculate_score(5000, 20, 0.9)
assert result == 85.0
```

## 테스트 작성 가이드

### 새로운 테스트 추가

1. 적절한 테스트 파일 선택 또는 새 파일 생성
2. TestClass 패턴 사용
3. test_ 접두사로 메서드 명명
4. fixture 활용

```python
class TestNewFeature:
    @pytest.fixture
    def setup(self):
        # 준비 단계
        yield resource
        # 정리 단계

    def test_feature_basic(self, temp_db):
        # Arrange
        # Act
        # Assert
        pass
```

### 비동기 테스트

```python
@pytest.mark.asyncio
async def test_async_function(self, mock_http_client):
    # 비동기 코드 테스트
    pass
```

## 주요 테스트 특성

### 격리성 (Isolation)
- 각 테스트는 독립적으로 실행
- 메모리 데이터베이스 사용으로 격리

### 재현성 (Reproducibility)
- 일관된 결과를 위해 Mock 사용
- 난수 생성 대신 고정값 사용

### 속도 (Speed)
- 실제 네트워크 요청 없음
- 메모리 DB로 빠른 실행

### 명확성 (Clarity)
- 한글 주석으로 의도 표현
- 테스트 이름이 동작을 설명

## 트러블슈팅

### ImportError 발생 시

```bash
# Python 경로 확인
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/
```

### AsyncIO 에러 시

```bash
# pytest-asyncio 설치 확인
pip install --upgrade pytest-asyncio
```

### 테스트 발견 안 됨 시

```bash
# pytest가 파일을 찾을 수 있도록 확인
pytest tests/ --collect-only
```

## CI/CD 통합

### GitHub Actions 예시

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      - name: Run tests
        run: pytest tests/
```

## 라이센스

프로젝트 라이센스 참고
