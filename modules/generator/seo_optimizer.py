"""
Naver SEO 최적화 모듈
네이버 블로그의 4가지 SEO 알고리즘 기반 점수 계산
"""

import re
from typing import Dict, List
from utils.logger import get_logger


logger = get_logger()


class SEOOptimizer:
    """
    Naver SEO 알고리즘 기반 최적화

    4가지 평가 알고리즘:
    1. AUTH.GR: 법령 인용, 출처 링크 (최대 25점)
    2. C-RANK: 키워드 밀도 1.5-2.5% (최대 25점)
    3. DIA+: H2 3개 이상, 표, FAQ (최대 25점)
    4. AI.BRIEFING: 첫 문장 키워드 포함 (최대 25점)
    """

    def __init__(self):
        """SEO 옵티마이저 초기화"""
        self.logger = logger

    def calculate_score(self, title: str, body: str, keyword: str) -> dict:
        """
        전체 SEO 점수 계산

        Args:
            title: 블로그 포스트 제목
            body: 블로그 포스트 본문
            keyword: 검색 키워드

        Returns:
            SEO 점수 및 상세 정보
            {
                'total_score': 0-100,
                'auth_gr_score': 0-25,
                'c_rank_score': 0-25,
                'dia_plus_score': 0-25,
                'ai_briefing_score': 0-25,
                'keyword_density': 0.0-100.0,
                'keyword_density_level': 'low/optimal/high',
                'recommendations': [...]
            }
        """
        self.logger.info(f"SEO 점수 계산 시작: keyword={keyword}")

        # 각 알고리즘별 점수 계산
        auth_gr_score = self._check_auth_gr(body)
        c_rank_score, keyword_density = self._check_c_rank(body, keyword)
        dia_plus_score = self._check_dia_plus(body)
        ai_briefing_score = self._check_ai_briefing(title, body, keyword)

        # 전체 점수
        total_score = auth_gr_score + c_rank_score + dia_plus_score + ai_briefing_score

        # 키워드 밀도 레벨 판정
        if keyword_density < 1.5:
            density_level = 'low'
        elif 1.5 <= keyword_density <= 2.5:
            density_level = 'optimal'
        else:
            density_level = 'high'

        # 개선사항 추천
        recommendations = self._generate_recommendations(
            auth_gr_score, c_rank_score, dia_plus_score, ai_briefing_score, density_level
        )

        result = {
            'total_score': min(100, total_score),
            'auth_gr_score': auth_gr_score,
            'c_rank_score': c_rank_score,
            'dia_plus_score': dia_plus_score,
            'ai_briefing_score': ai_briefing_score,
            'keyword_density': round(keyword_density, 2),
            'keyword_density_level': density_level,
            'recommendations': recommendations
        }

        self.logger.info(f"SEO 점수 계산 완료: total={result['total_score']}, density={result['keyword_density']}%")
        return result

    def _check_auth_gr(self, body: str) -> float:
        """
        AUTH.GR 알고리즘 평가 (최대 25점)
        법령 인용, 출처 링크 확인

        Args:
            body: 블로그 포스트 본문

        Returns:
            0-25점 사이의 점수
        """
        score = 0

        # 법령 인용 확인 (정규식)
        citation_patterns = [
            r'법령|규칙|규정|기준',
            r'대통령령|부령|고시|예규',
            r'출처:|참고:',
            r'https?://[^\s]+',  # URL 링크
        ]

        matches = 0
        for pattern in citation_patterns:
            matches += len(re.findall(pattern, body, re.IGNORECASE))

        # 링크 개수에 따른 점수 부여
        if matches >= 5:
            score = 25
        elif matches >= 3:
            score = 20
        elif matches >= 1:
            score = 10
        else:
            score = 0

        self.logger.debug(f"AUTH.GR 점수: {score} (인용/링크 {matches}개)")
        return float(score)

    def _check_c_rank(self, body: str, keyword: str) -> tuple:
        """
        C-RANK 알고리즘 평가 (최대 25점)
        키워드 밀도 1.5-2.5% 확인

        Args:
            body: 블로그 포스트 본문
            keyword: 검색 키워드

        Returns:
            (점수, 키워드 밀도) 튜플
        """
        keyword_density = self.get_keyword_density(body, keyword)

        # 최적 범위: 1.5-2.5%
        if 1.5 <= keyword_density <= 2.5:
            score = 25
        elif 1.0 <= keyword_density < 1.5:
            score = 20
        elif 2.5 < keyword_density <= 3.0:
            score = 20
        elif 0.5 <= keyword_density < 1.0:
            score = 15
        elif 3.0 < keyword_density <= 3.5:
            score = 15
        else:
            score = 5

        self.logger.debug(f"C-RANK 점수: {score} (키워드 밀도 {keyword_density}%)")
        return float(score), keyword_density

    def _check_dia_plus(self, body: str) -> float:
        """
        DIA+ 알고리즘 평가 (최대 25점)
        구조화된 콘텐츠: H2 3개 이상, 표, FAQ

        Args:
            body: 블로그 포스트 본문

        Returns:
            0-25점 사이의 점수
        """
        score = 0
        bonus_points = 0

        # H2 태그 개수 확인
        h2_count = len(re.findall(r'##\s+|<h2[^>]*>|## ', body, re.IGNORECASE))
        if h2_count >= 3:
            bonus_points += 15
        elif h2_count >= 2:
            bonus_points += 10
        elif h2_count >= 1:
            bonus_points += 5

        # 표(테이블) 확인
        table_count = len(re.findall(r'\|.*\|.*\||\<table[^>]*\>', body, re.IGNORECASE))
        if table_count > 0:
            bonus_points += 5

        # FAQ 형식 확인
        faq_patterns = [r'Q\.|Q\.|Q&A|FAQ|자주 묻는|질문과 답변']
        faq_count = sum(len(re.findall(pattern, body, re.IGNORECASE)) for pattern in faq_patterns)
        if faq_count >= 3:
            bonus_points += 5

        score = min(25, bonus_points)
        self.logger.debug(f"DIA+ 점수: {score} (H2:{h2_count}, Table:{table_count}, FAQ:{faq_count})")
        return float(score)

    def _check_ai_briefing(self, title: str, body: str, keyword: str) -> float:
        """
        AI.BRIEFING 알고리즘 평가 (최대 25점)
        첫 문장에 키워드 포함 여부

        Args:
            title: 블로그 포스트 제목
            body: 블로그 포스트 본문
            keyword: 검색 키워드

        Returns:
            0-25점 사이의 점수
        """
        score = 0

        # 제목에 키워드 포함
        if keyword.lower() in title.lower():
            score += 10

        # 첫 100자 내 키워드 포함
        first_100 = body[:100].lower()
        if keyword.lower() in first_100:
            score += 15

        # 추가 보너스: 첫 문장 완성도 확인
        first_sentence = re.match(r'[^.!?]+[.!?]', body)
        if first_sentence and len(first_sentence.group()) > 30:
            score += 5 if keyword.lower() in first_sentence.group().lower() else 0

        score = min(25, score)
        self.logger.debug(f"AI.BRIEFING 점수: {score} (제목 키워드:{keyword in title}, 첫 100자:{keyword in first_100})")
        return float(score)

    def get_keyword_density(self, text: str, keyword: str) -> float:
        """
        키워드 밀도 계산

        Args:
            text: 분석할 텍스트
            keyword: 검색 키워드

        Returns:
            키워드 밀도 (%)
        """
        # 텍스트 정규화
        clean_text = re.sub(r'[^ㄱ-ㅎㅏ-ㅣ가-힣a-zA-Z0-9\s]', '', text)
        words = clean_text.split()

        if not words:
            return 0.0

        # 키워드 개수
        keyword_lower = keyword.lower()
        keyword_count = sum(1 for word in words if keyword_lower in word.lower())

        # 밀도 계산
        density = (keyword_count / len(words)) * 100

        self.logger.debug(f"키워드 밀도: {density:.2f}% (키워드:{keyword_count}개, 총 단어:{len(words)}개)")
        return round(density, 2)

    def _generate_recommendations(
        self,
        auth_gr: float,
        c_rank: float,
        dia_plus: float,
        ai_briefing: float,
        density_level: str
    ) -> List[str]:
        """
        SEO 점수 기반 개선사항 추천

        Args:
            auth_gr: AUTH.GR 점수
            c_rank: C-RANK 점수
            dia_plus: DIA+ 점수
            ai_briefing: AI.BRIEFING 점수
            density_level: 키워드 밀도 레벨

        Returns:
            개선사항 추천 목록
        """
        recommendations = []

        if auth_gr < 20:
            recommendations.append('법령 인용이나 출처 링크를 추가하여 신뢰성을 높이세요.')

        if c_rank < 20:
            if density_level == 'low':
                recommendations.append('키워드 밀도를 1.5-2.5% 범위로 높이세요.')
            elif density_level == 'high':
                recommendations.append('과도한 키워드 반복을 줄여 자연스러운 문장으로 수정하세요.')

        if dia_plus < 20:
            recommendations.append('H2 제목 3개 이상, 표, FAQ 형식 등으로 콘텐츠를 구조화하세요.')

        if ai_briefing < 20:
            recommendations.append('제목과 첫 문장에 주요 키워드를 포함시키세요.')

        if not recommendations:
            recommendations.append('SEO 최적화가 잘 진행되고 있습니다. 계속 좋은 품질을 유지하세요.')

        return recommendations
