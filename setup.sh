#!/bin/bash
# ============================================================
# NaverBlogAutoPilot 원클릭 셋업 스크립트
# Mac 터미널에서 실행: bash setup.sh
# ============================================================

set -e

echo "🚀 NaverBlogAutoPilot 셋업 시작..."
echo ""

# 1. 현재 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
echo "📂 프로젝트 경로: $SCRIPT_DIR"

# 2. Python 확인
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3가 설치되어 있지 않습니다."
    echo "   brew install python3 으로 설치하세요."
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo "🐍 $PYTHON_VERSION"

# 3. 기존 venv 정리 및 새로 생성
if [ -d "venv" ]; then
    echo "🔄 기존 venv 삭제 중..."
    rm -rf venv
fi
echo "📦 가상환경 생성 중..."
python3 -m venv venv
source venv/bin/activate

# 4. 패키지 설치
echo "📥 패키지 설치 중... (1~2분 소요)"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ 패키지 설치 완료!"

# 5. Playwright 설치
echo "🌐 Playwright Chromium 설치 중..."
playwright install chromium
echo "✅ Playwright 설치 완료!"

# 6. .env 파일 확인
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  .env 파일이 없습니다. 템플릿에서 복사합니다."
    cp .env.example .env
    echo "📝 .env 파일이 생성되었습니다."
    echo "   아래 API 키를 직접 입력해야 합니다:"
    echo ""
    echo "   1. ANTHROPIC_API_KEY → https://console.anthropic.com/"
    echo "   2. NAVER_CLIENT_ID / SECRET → https://developers.naver.com/"
    echo "   3. NAVER_BLOG_ID → 네이버 블로그 아이디"
    echo ""
    echo "   편집: nano .env 또는 open .env"
    echo ""
fi

# 7. 데이터베이스 초기화
echo "🗄️  데이터베이스 초기화 중..."
python main.py init-db

# 8. 디렉토리 생성
mkdir -p data/reports logs

# 9. 완료
echo ""
echo "============================================"
echo "✅ NaverBlogAutoPilot 셋업 완료!"
echo "============================================"
echo ""
echo "📋 다음 단계:"
echo "  1. .env 파일에 API 키 입력"
echo "     nano .env"
echo ""
echo "  2. 가상환경 활성화"
echo "     source venv/bin/activate"
echo ""
echo "  3. 테스트 크롤링"
echo "     python main.py crawl --limit 5"
echo ""
echo "  4. 키워드 분석"
echo "     python main.py research"
echo ""
echo "  5. 포스트 생성"
echo "     python main.py generate --count 1"
echo ""
echo "  6. 발행"
echo "     python main.py publish"
echo ""
echo "  7. 자동 스케줄러 (매일 자동 발행)"
echo "     python main.py schedule"
echo ""
echo "  8. 상태 확인"
echo "     python main.py status"
echo ""
