/**
 * 네이버 블로그 자동화 UI - 공통 JavaScript
 */

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 네이버 블로그 자동화 UI 로드 완료');

    // 페이드인 애니메이션
    document.querySelectorAll('.card').forEach(card => {
        card.classList.add('fade-in');
    });
});

/**
 * API 호출 헬퍼 함수
 */
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API 호출 실패:', error);
        showToast('오류', error.message, 'danger');
        throw error;
    }
}

/**
 * Toast 알림 표시
 */
function showToast(title, message, type = 'info') {
    // TODO: Bootstrap Toast 구현
    console.log(`[${type.toUpperCase()}] ${title}: ${message}`);
}

/**
 * 날짜 포맷팅
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;

    // 1분 이내
    if (diff < 60000) {
        return '방금 전';
    }

    // 1시간 이내
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes}분 전`;
    }

    // 24시간 이내
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours}시간 전`;
    }

    // 그 외
    return date.toLocaleDateString('ko-KR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

/**
 * 숫자 포맷팅 (천 단위 콤마)
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * 진행률 바 업데이트
 */
function updateProgress(elementId, percent) {
    const progressBar = document.getElementById(elementId);
    if (progressBar) {
        progressBar.style.width = `${percent}%`;
        progressBar.setAttribute('aria-valuenow', percent);
        progressBar.textContent = `${percent}%`;
    }
}
