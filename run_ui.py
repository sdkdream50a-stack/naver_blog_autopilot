#!/usr/bin/env python3
"""
Flask UI 서버 실행 스크립트
"""

from app import create_app

# gunicorn에서 참조할 수 있도록 모듈 레벨에 app 노출
app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 네이버 블로그 자동화 UI 서버 시작")
    print("=" * 60)
    print(f"📡 URL: http://localhost:5002")
    print(f"🔧 환경: 개발 모드")
    print("=" * 60)

    app.run(
        host='0.0.0.0',
        port=5002,
        debug=True
    )
