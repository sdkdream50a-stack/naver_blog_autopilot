"""
메인 페이지 라우트
"""

from flask import Blueprint, render_template

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """대시보드 메인 페이지"""
    return render_template('index.html')


@bp.route('/workflow')
def workflow():
    """워크플로우 관리 페이지"""
    return render_template('workflow.html')


@bp.route('/schedule')
def schedule():
    """스케줄 설정 페이지"""
    return render_template('schedule.html')


@bp.route('/content')
def content():
    """콘텐츠 관리 페이지"""
    return render_template('content.html')


@bp.route('/monitor')
def monitor():
    """모니터링 페이지"""
    return render_template('monitor.html')


@bp.route('/settings')
def settings():
    """설정 페이지"""
    return render_template('settings.html')
