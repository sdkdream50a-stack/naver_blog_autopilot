#!/bin/bash
# ============================================================
# Cloudflare Tunnel 설치 및 설정 스크립트
# Oracle Cloud VM에서 실행
# 공식 문서: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
# ============================================================

set -e

echo "======================================"
echo " Cloudflare Tunnel 설치"
echo "======================================"

# 1. cloudflared 설치 (ARM64 또는 x86_64 자동 감지)
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
    DOWNLOAD_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb"
else
    DOWNLOAD_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb"
fi

echo "[1/4] cloudflared 다운로드 및 설치 ($ARCH)..."
wget -q "$DOWNLOAD_URL" -O /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb
rm /tmp/cloudflared.deb

# 2. Cloudflare 로그인
echo ""
echo "[2/4] Cloudflare 로그인"
echo "  브라우저가 열리면 Cloudflare 계정으로 로그인하세요"
echo "  (SSH 환경에서는 출력된 URL을 복사해 로컬 브라우저에서 열기)"
echo ""
cloudflared tunnel login

# 3. 터널 생성
TUNNEL_NAME="naver-blog-autopilot"
echo "[3/4] 터널 생성: $TUNNEL_NAME"
cloudflared tunnel create "$TUNNEL_NAME"

# 터널 ID 가져오기
TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
echo "  터널 ID: $TUNNEL_ID"

# 4. 설정 파일 생성
echo "[4/4] 설정 파일 생성..."
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << CFEOF
tunnel: $TUNNEL_ID
credentials-file: /root/.cloudflared/${TUNNEL_ID}.json

ingress:
  - service: http://localhost:80

CFEOF

# systemd 서비스 설치
sudo cloudflared service install

echo ""
echo "======================================"
echo " Cloudflare Tunnel 설치 완료!"
echo "======================================"
echo ""
echo "⚠️  마지막 단계: DNS 레코드 연결"
echo ""
echo "  방법 A) 보유 도메인 연결:"
echo "  cloudflared tunnel route dns $TUNNEL_NAME your-domain.com"
echo ""
echo "  방법 B) Cloudflare에서 무료 .trycloudflare.com 서브도메인 사용:"
echo "  cloudflared tunnel --url http://localhost:80"
echo ""
echo " 터널 상태 확인: sudo systemctl status cloudflared"
