#!/bin/bash
# ============================================================
# Oracle Cloud Free VM 초기 설정 스크립트
# Ubuntu 22.04 LTS (ARM 또는 x86)
# 실행: bash setup_oracle.sh
# ============================================================

set -e

APP_DIR="/opt/naver_blog_autopilot"
APP_USER="autopilot"
GITHUB_REPO="https://github.com/sdkdream50a-stack/naver_blog_autopilot.git"

echo "======================================"
echo " 네이버 블로그 자동화 서버 설치 시작"
echo "======================================"

# 1. 시스템 업데이트 및 필수 패키지
echo "[1/8] 시스템 패키지 업데이트..."
sudo apt-get update -q
sudo apt-get install -y -q \
    python3.11 python3.11-venv python3-pip \
    git curl wget nginx \
    sqlite3 \
    # Playwright 의존성
    libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2

# 2. 앱 전용 유저 생성
echo "[2/8] 앱 유저 생성..."
if ! id "$APP_USER" &>/dev/null; then
    sudo useradd -r -m -s /bin/bash "$APP_USER"
fi

# 3. 코드 클론
echo "[3/8] 코드 클론..."
sudo mkdir -p "$APP_DIR"
sudo chown "$APP_USER:$APP_USER" "$APP_DIR"
sudo -u "$APP_USER" git clone "$GITHUB_REPO" "$APP_DIR" 2>/dev/null || \
    sudo -u "$APP_USER" bash -c "cd $APP_DIR && git pull origin main"

# 4. Python 가상환경 및 패키지 설치
echo "[4/8] Python 패키지 설치..."
sudo -u "$APP_USER" bash -c "
    cd $APP_DIR
    python3.11 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
"

# 5. Playwright Chromium 설치
echo "[5/8] Playwright Chromium 설치..."
sudo -u "$APP_USER" bash -c "
    cd $APP_DIR
    source venv/bin/activate
    playwright install chromium
    playwright install-deps chromium
"

# 6. 데이터 디렉토리 및 .env 설정
echo "[6/8] 디렉토리 설정..."
sudo -u "$APP_USER" mkdir -p "$APP_DIR/data/images" "$APP_DIR/data/reports" "$APP_DIR/logs"

# .env 파일이 없으면 예시에서 복사
if [ ! -f "$APP_DIR/.env" ]; then
    sudo -u "$APP_USER" cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo ""
    echo "⚠️  $APP_DIR/.env 파일에 API 키를 입력해주세요!"
    echo "    sudo nano $APP_DIR/.env"
fi

# 7. DB 초기화
echo "[7/8] 데이터베이스 초기화..."
sudo -u "$APP_USER" bash -c "
    cd $APP_DIR
    source venv/bin/activate
    python3 -c \"
from utils.database import Database
from config.settings import settings
db = Database(settings.DB_PATH)
db.init_db()
print('DB 초기화 완료')
\"
"

# 8. systemd 서비스 설치
echo "[8/8] systemd 서비스 설치..."
sudo cp "$APP_DIR/deploy/naver_blog_autopilot.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable naver_blog_autopilot
sudo systemctl start naver_blog_autopilot

# Nginx 설정
sudo cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/naver_blog_autopilot
sudo ln -sf /etc/nginx/sites-available/naver_blog_autopilot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo ""
echo "======================================"
echo " 설치 완료!"
echo "======================================"
echo " 앱 상태: sudo systemctl status naver_blog_autopilot"
echo " 로그:    sudo journalctl -u naver_blog_autopilot -f"
echo " .env 설정: sudo nano $APP_DIR/.env"
echo "======================================"
