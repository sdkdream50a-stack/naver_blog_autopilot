"""
포스트 품질 검사 모듈
표절 검사 및 콘텐츠 품질 평가
"""

import re
import difflib
from typing import Dict, List
from utils.logger import get_logger
from config.settings import settings


logger = get_logger()
PLAGIARISM_THRESHOLD = getattr(settings, 'PLAGIARISM_THRESHOLD', 0.30)


class QualityChecker:
    """
    생성된 블로그 포스트의 품질 검사

    기능:
    - 표절 검사 (원본과의 유사도 비교)
    - 기존 발행 글과의 중복 검사
    - 가독성 검사
    - 전체 품질 평가
    """

    DUPLICATE_TITLE_THRESHOLD = 0.6   # 제목 유사도 60% 이상이면 중복
    DUPLICATE_BODY_THRESHOLD = 0.4    # 본문 유사도 40% 이상이면 중복

    def __init__(self):
        """품질 검사기 초기화"""
        self.logger = logger
        self.plagiarism_threshold = PLAGIARISM_THRESHOLD

    def check_duplicate(self, title: str, body: str, db, exclude_post_id: int = None) -> dict:
        """
        기존 발행/승인 포스트와의 중복 검사

        Args:
            title: 새로 생성된 포스트 제목
            body: 새로 생성된 포스트 본문
            db: Database 인스턴스
            exclude_post_id: 제외할 포스트 ID (현재 생성 중인 포스트)

        Returns:
            {
                'is_duplicate': bool,
                'reason': str,
                'most_similar_title': str,
                'title_similarity': float,
                'body_similarity': float,
            }
        """
        self.logger.info("기존 발행 글 중복 검사 시작")

        # 기존 발행/승인 포스트 가져오기 (현재 포스트 제외)
        if exclude_post_id:
            existing_posts = db.execute(
                """SELECT title, body FROM posts
                   WHERE status IN ('published', 'approved', 'draft')
                   AND id != ?
                   ORDER BY created_at DESC
                   LIMIT 50""",
                (exclude_post_id,)
            )
        else:
            existing_posts = db.execute(
                """SELECT title, body FROM posts
                   WHERE status IN ('published', 'approved', 'draft')
                   ORDER BY created_at DESC
                   LIMIT 50"""
            )

        if not existing_posts:
            self.logger.info("비교할 기존 포스트 없음, 중복 아님")
            return {
                'is_duplicate': False,
                'reason': '기존 포스트 없음',
                'most_similar_title': '',
                'title_similarity': 0.0,
                'body_similarity': 0.0,
            }

        new_title_norm = self._normalize_text(title)
        new_body_norm = self._normalize_text(body[:1000])  # 본문은 앞 1000자만 비교 (성능)

        max_title_sim = 0.0
        max_body_sim = 0.0
        most_similar_title = ''

        for post in existing_posts:
            existing_title = post['title'] if post['title'] else ''
            existing_body = post['body'] if post['body'] else ''

            # 제목 유사도
            title_sim = self._calculate_similarity(
                new_title_norm,
                self._normalize_text(existing_title)
            )

            # 본문 유사도 (앞 1000자)
            body_sim = self._calculate_similarity(
                new_body_norm,
                self._normalize_text(existing_body[:1000])
            )

            if title_sim > max_title_sim:
                max_title_sim = title_sim
                most_similar_title = existing_title

            if body_sim > max_body_sim:
                max_body_sim = body_sim

        # 중복 판정
        is_duplicate = False
        reason = '통과'

        if max_title_sim >= self.DUPLICATE_TITLE_THRESHOLD:
            is_duplicate = True
            reason = f'제목 유사도 {max_title_sim*100:.0f}% (기준: {self.DUPLICATE_TITLE_THRESHOLD*100:.0f}%)'
        elif max_body_sim >= self.DUPLICATE_BODY_THRESHOLD:
            is_duplicate = True
            reason = f'본문 유사도 {max_body_sim*100:.0f}% (기준: {self.DUPLICATE_BODY_THRESHOLD*100:.0f}%)'

        status = "중복 감지" if is_duplicate else "통과"
        self.logger.info(
            f"중복 검사 완료: {status}, 제목 유사도={max_title_sim:.2f}, "
            f"본문 유사도={max_body_sim:.2f}, 가장 유사: '{most_similar_title[:30]}...'"
        )

        return {
            'is_duplicate': is_duplicate,
            'reason': reason,
            'most_similar_title': most_similar_title,
            'title_similarity': round(max_title_sim, 4),
            'body_similarity': round(max_body_sim, 4),
        }

    def check_plagiarism(self, generated: str, original: str) -> float:
        """
        생성된 포스트와 원본의 표절 비율 검사

        Args:
            generated: 생성된 포스트 본문
            original: 원본 기사 본문

        Returns:
            유사도 비율 (0.0-1.0)
            0.0 = 완전히 다름
            1.0 = 완전히 같음
            threshold (기본 0.30) 이상이면 표절로 판정
        """
        self.logger.info("표절 검사 시작")

        if not generated or not original:
            self.logger.warning("빈 문자열 입력: 표절 검사 불가")
            return 0.0

        # 텍스트 정규화
        gen_normalized = self._normalize_text(generated)
        orig_normalized = self._normalize_text(original)

        # 유사도 계산
        similarity = self._calculate_similarity(gen_normalized, orig_normalized)

        # 표절 판정
        is_plagiarism = similarity >= self.plagiarism_threshold
        status = "표절 의심" if is_plagiarism else "통과"

        self.logger.info(
            f"표절 검사 완료: 유사도={similarity:.4f}, 상태={status}, 임계값={self.plagiarism_threshold}"
        )

        return round(similarity, 4)

    def check_quality(self, post: dict) -> dict:
        """
        생성된 포스트의 전체 품질 평가

        Args:
            post: 포스트 정보
            {
                'title': str,
                'body': str,
                'original_content': str (선택사항),
                'seo_score': float (선택사항),
                'keyword_density': float (선택사항)
            }

        Returns:
            품질 평가 결과
            {
                'overall_quality': 'excellent/good/fair/poor',
                'quality_score': 0-100,
                'readability_score': 0-100,
                'plagiarism_score': 0.0-1.0,
                'plagiarism_status': 'pass/fail',
                'grammar_score': 0-100,
                'issues': [],
                'recommendations': []
            }
        """
        self.logger.info("품질 검사 시작")

        title = post.get('title', '')
        body = post.get('body', '')
        original_content = post.get('original_content', '')
        seo_score = post.get('seo_score', 0)

        quality_scores = {}

        # 1. 가독성 검사
        readability_score = self._check_readability(body)
        quality_scores['readability'] = readability_score

        # 2. 문법 검사 (기본적인 규칙)
        grammar_score = self._check_grammar(title, body)
        quality_scores['grammar'] = grammar_score

        # 3. 표절 검사
        plagiarism_score = 0.0
        plagiarism_status = 'pass'
        if original_content:
            plagiarism_score = self.check_plagiarism(body, original_content)
            plagiarism_status = 'fail' if plagiarism_score >= self.plagiarism_threshold else 'pass'
        quality_scores['plagiarism'] = plagiarism_score

        # 4. 길이 적절성 검사
        length_score = self._check_content_length(body)
        quality_scores['length'] = length_score

        # 5. 구조 적절성 검사
        structure_score = self._check_content_structure(body)
        quality_scores['structure'] = structure_score

        # 전체 품질 점수 계산 (가중치 적용)
        overall_score = (
            readability_score * 0.25 +
            grammar_score * 0.25 +
            structure_score * 0.20 +
            length_score * 0.15 +
            (100 - (plagiarism_score * 100)) * 0.15
        )

        # 품질 등급 판정
        if overall_score >= 85:
            quality_level = 'excellent'
        elif overall_score >= 70:
            quality_level = 'good'
        elif overall_score >= 50:
            quality_level = 'fair'
        else:
            quality_level = 'poor'

        # 문제점 및 개선사항 도출
        issues = self._identify_issues(
            title, body, plagiarism_score, readability_score,
            grammar_score, length_score, structure_score
        )

        recommendations = self._generate_quality_recommendations(
            quality_level, plagiarism_status, readability_score, grammar_score
        )

        result = {
            'overall_quality': quality_level,
            'quality_score': round(overall_score, 2),
            'readability_score': readability_score,
            'grammar_score': grammar_score,
            'plagiarism_score': plagiarism_score,
            'plagiarism_status': plagiarism_status,
            'length_score': length_score,
            'structure_score': structure_score,
            'seo_score': seo_score,
            'issues': issues,
            'recommendations': recommendations
        }

        self.logger.info(
            f"품질 검사 완료: 등급={quality_level}, 점수={overall_score:.2f}, "
            f"표절={plagiarism_status}"
        )

        return result

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        두 텍스트의 유사도 계산 (difflib.SequenceMatcher 사용)

        Args:
            text1: 첫 번째 텍스트
            text2: 두 번째 텍스트

        Returns:
            유사도 비율 (0.0-1.0)
        """
        if not text1 or not text2:
            return 0.0

        matcher = difflib.SequenceMatcher(None, text1, text2)
        similarity = matcher.ratio()

        self.logger.debug(f"텍스트 유사도: {similarity:.4f}")
        return similarity

    def _check_readability(self, text: str) -> float:
        """
        콘텐츠 가독성 검사

        평가 기준:
        - 평균 문장 길이 (권장: 20-40 단어)
        - 문단 길이 (권장: 3-5 문장)
        - 어휘 다양성
        - 수동태 사용 비율

        Args:
            text: 분석할 텍스트

        Returns:
            가독성 점수 (0-100)
        """
        if not text:
            return 0

        score = 100
        issues = []

        # 문장 분리
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0

        # 1. 평균 문장 길이 확인
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_sentence_length > 50:
            score -= 10
            issues.append(f"평균 문장 길이 {avg_sentence_length:.1f} (권장: 20-40단어)")
        elif avg_sentence_length < 10:
            score -= 5
            issues.append(f"평균 문장 길이 {avg_sentence_length:.1f} (너무 짧음)")

        # 2. 수동태 사용 빈도
        passive_patterns = [r'되었다', r'되고 있다', r'되어야 한다', r'는 것이다']
        passive_count = sum(len(re.findall(pattern, text)) for pattern in passive_patterns)
        passive_ratio = (passive_count / len(sentences)) * 100
        if passive_ratio > 30:
            score -= 10
            issues.append(f"수동태 사용 비율 {passive_ratio:.1f}% (권장: 30% 이하)")

        # 3. 어려운 단어 사용 확인
        difficult_words = ['방안', '현황', '대응', '마련', '추진']
        difficult_count = sum(text.count(word) for word in difficult_words)
        if difficult_count > len(sentences) * 2:
            score -= 5
            issues.append(f"어려운 용어 과다 사용 ({difficult_count}회)")

        # 4. 중복 단어 확인
        words = text.split()
        if words:
            word_freq = {}
            for word in words:
                if len(word) > 2:
                    word_freq[word] = word_freq.get(word, 0) + 1
            duplicates = [w for w, freq in word_freq.items() if freq > len(words) * 0.05]
            if len(duplicates) > 5:
                score -= 5
                issues.append(f"중복 단어 과다 ({len(duplicates)}개)")

        score = max(0, score)
        self.logger.debug(f"가독성 점수: {score} (평균 문장 길이: {avg_sentence_length:.1f})")
        return score

    def _check_grammar(self, title: str, body: str) -> float:
        """
        기본적인 문법 검사

        Args:
            title: 포스트 제목
            body: 포스트 본문

        Returns:
            문법 점수 (0-100)
        """
        score = 100
        full_text = title + ' ' + body

        # 1. 종결 표현 확인
        if not re.search(r'다[.!?]$', full_text):
            score -= 5

        # 2. 기본적인 오류 패턴
        error_patterns = [
            (r'  +', '이중 공백'),  # 이중 공백
            (r'[ㄱ-ㅎ]', '자모 분리'),  # 자모 분리
            (r'[^\w\s\.\!\?\,;가-힣]', '특수문자 과다'),  # 특수문자 과다
        ]

        error_count = 0
        for pattern, error_type in error_patterns:
            matches = len(re.findall(pattern, full_text))
            if matches > 10:
                score -= 5
                error_count += 1

        # 3. 따옴표 균형 확인
        single_quotes = full_text.count("'")
        double_quotes = full_text.count('"')
        if single_quotes % 2 != 0 or double_quotes % 2 != 0:
            score -= 3

        score = max(0, score)
        self.logger.debug(f"문법 점수: {score}")
        return score

    def _check_content_length(self, body: str) -> float:
        """
        콘텐츠 길이 적절성 검사

        권장 범위: 2000-3000 자

        Args:
            body: 포스트 본문

        Returns:
            길이 점수 (0-100)
        """
        length = len(body)
        optimal_min = 2000
        optimal_max = 3000
        min_acceptable = 1500
        max_acceptable = 4000

        if optimal_min <= length <= optimal_max:
            score = 100
        elif min_acceptable <= length < optimal_min:
            score = 80
        elif optimal_max < length <= max_acceptable:
            score = 80
        elif length < min_acceptable:
            score = 50
        else:
            score = 60

        self.logger.debug(f"길이 점수: {score} (본문 길이: {length}자)")
        return score

    def _check_content_structure(self, body: str) -> float:
        """
        콘텐츠 구조 적절성 검사

        Args:
            body: 포스트 본문

        Returns:
            구조 점수 (0-100)
        """
        score = 50

        # H2 제목 확인
        h2_count = len(re.findall(r'##\s+|<h2[^>]*>', body, re.IGNORECASE))
        if h2_count >= 3:
            score += 20
        elif h2_count >= 2:
            score += 10
        elif h2_count >= 1:
            score += 5

        # 목록 구조 확인
        list_count = len(re.findall(r'[-•*]\s+|\d+\.\s+', body))
        if list_count >= 5:
            score += 15
        elif list_count >= 3:
            score += 10

        # 문단 구조 확인
        paragraphs = body.split('\n\n')
        avg_para_length = len(body) / len(paragraphs) if paragraphs else 0
        if 100 < avg_para_length < 500:
            score += 15

        score = min(100, score)
        self.logger.debug(f"구조 점수: {score} (H2: {h2_count}, 목록: {list_count})")
        return score

    def _identify_issues(
        self,
        title: str,
        body: str,
        plagiarism_score: float,
        readability: float,
        grammar: float,
        length: float,
        structure: float
    ) -> List[str]:
        """
        식별된 문제점 도출

        Args:
            title: 제목
            body: 본문
            plagiarism_score: 표절 점수
            readability: 가독성 점수
            grammar: 문법 점수
            length: 길이 점수
            structure: 구조 점수

        Returns:
            문제점 목록
        """
        issues = []

        if plagiarism_score >= self.plagiarism_threshold:
            issues.append(f"표절 의심: 원본과의 유사도 {plagiarism_score*100:.1f}%")

        if readability < 70:
            issues.append(f"가독성 낮음: {readability:.1f}점")

        if grammar < 80:
            issues.append(f"문법 오류 감지: {grammar:.1f}점")

        if length < 70:
            issues.append(f"콘텐츠 길이 부족: {length:.1f}점")

        if structure < 70:
            issues.append(f"콘텐츠 구조 미흡: {structure:.1f}점")

        if len(title) < 10:
            issues.append("제목이 너무 짧습니다")

        if len(title) > 100:
            issues.append("제목이 너무 깁니다")

        return issues

    def _generate_quality_recommendations(
        self,
        quality_level: str,
        plagiarism_status: str,
        readability: float,
        grammar: float
    ) -> List[str]:
        """
        품질 개선 추천사항 생성

        Args:
            quality_level: 품질 등급
            plagiarism_status: 표절 상태
            readability: 가독성 점수
            grammar: 문법 점수

        Returns:
            추천사항 목록
        """
        recommendations = []

        if plagiarism_status == 'fail':
            recommendations.append("원본과의 유사도를 낮추기 위해 콘텐츠를 재작성하세요")

        if readability < 70:
            recommendations.append("문장을 더 짧고 간단하게 만들어 가독성을 높이세요")

        if grammar < 80:
            recommendations.append("문법 오류를 수정하고 표현을 자연스럽게 다듬으세요")

        if quality_level == 'poor':
            recommendations.append("전반적인 품질 개선이 필요합니다. 처음부터 재작성을 고려하세요")
        elif quality_level == 'fair':
            recommendations.append("품질을 높이기 위해 구조와 내용을 보강하세요")

        if not recommendations:
            recommendations.append("현재 품질이 우수합니다. 계속 유지하세요")

        return recommendations

    def _normalize_text(self, text: str) -> str:
        """
        표절 검사를 위한 텍스트 정규화

        Args:
            text: 정규화할 텍스트

        Returns:
            정규화된 텍스트
        """
        # 공백 정규화
        text = re.sub(r'\s+', ' ', text)

        # 특수 문자 제거
        text = re.sub(r'[^\w\s가-힣]', '', text)

        # 소문자로 통일
        text = text.lower()

        return text.strip()
