"""
NaverBlogAutoPilot 테스트 패키지

이 패키지는 NaverBlogAutoPilot 프로젝트의 포괄적인 테스트 스위트를 포함합니다.

테스트 모듈:
- test_collector: 컬렉터 모듈 테스트
- test_researcher: 리서처 모듈 테스트
- test_generator: 생성기 모듈 테스트
- test_publisher: 퍼블리셔 모듈 테스트
- test_database: 데이터베이스 모듈 테스트
- test_monitor: 모니터 모듈 테스트

공통 픽스처:
- conftest.py: 공유 픽스처 및 설정

실행 방법:
    pytest tests/                          # 모든 테스트 실행
    pytest tests/test_collector.py         # 특정 모듈만
    pytest tests/ -v                       # 상세 출력
    pytest tests/ --cov                    # 커버리지 리포트
"""

__version__ = "1.0.0"
__author__ = "NaverBlogAutoPilot"
