"""
Flask 앱 팩토리
"""

import os
from flask import Flask
from pathlib import Path


def create_app():
    """Flask 앱 생성 및 초기화"""
    app = Flask(__name__)

    # 설정 (환경변수 우선, 없으면 개발용 기본값)
    app.config['SECRET_KEY'] = os.environ.get(
        'FLASK_SECRET_KEY',
        'naver-blog-autopilot-dev-key-change-in-production'
    )
    app.config['JSON_AS_ASCII'] = False  # 한글 JSON 응답

    # 라우트 등록
    from app.routes import main, api, sse
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp, url_prefix='/api')
    app.register_blueprint(sse.bp, url_prefix='/api')

    return app
