#!/bin/bash
# ============================================================
# 코드 업데이트 스크립트 (git pull → 재시작)
# 서버에서 실행: bash /opt/naver_blog_autopilot/deploy/update.sh
# ============================================================

APP_DIR="/opt/naver_blog_autopilot"
APP_USER="autopilot"

echo "[1/3] 코드 업데이트..."
sudo -u "$APP_USER" bash -c "cd $APP_DIR && git pull origin main"

echo "[2/3] 패키지 업데이트..."
sudo -u "$APP_USER" bash -c "
    cd $APP_DIR
    source venv/bin/activate
    pip install -r requirements.txt -q
"

echo "[3/3] 서비스 재시작..."
sudo systemctl restart naver_blog_autopilot

echo "✅ 업데이트 완료!"
sudo systemctl status naver_blog_autopilot --no-pager -l
