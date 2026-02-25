-- Migration: 001_add_multi_blog_support
-- Description: 멀티 블로그 지원을 위한 스키마 변경
-- Date: 2026-02-24

-- =====================================================
-- 1. blogs 테이블 생성
-- =====================================================

CREATE TABLE IF NOT EXISTS blogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 기본 정보
    name TEXT NOT NULL UNIQUE,                 -- 블로그 식별자 (예: "silmu", "tech-blog")
    display_name TEXT NOT NULL,                -- 표시명 (예: "실무 블로그", "테크 블로그")
    domain TEXT,                               -- 도메인 (예: "silmu.kr")
    description TEXT,                          -- 블로그 설명
    theme TEXT DEFAULT 'default',              -- 테마 (예: "education", "tech", "finance")

    -- 콘텐츠 설정
    system_prompt TEXT NOT NULL,               -- 블로그별 시스템 프롬프트
    categories TEXT DEFAULT '[]',              -- JSON: ["카테고리1", "카테고리2", ...]

    -- 크롤러 설정
    crawler_configs TEXT DEFAULT '{}',         -- JSON: {"law": true, "mogef": true, ...}
    crawler_urls TEXT DEFAULT '[]',            -- JSON: ["https://...", ...]

    -- 검증 설정
    verification_modules TEXT DEFAULT '[]',    -- JSON: ["legal", "factcheck", "plagiarism"]

    -- 예산/스케줄
    monthly_budget INTEGER DEFAULT 5000,       -- 월 예산 (원)
    max_posts_per_day INTEGER DEFAULT 2,       -- 일일 최대 포스트
    max_posts_per_week INTEGER DEFAULT 5,      -- 주간 최대 포스트
    min_interval_hours INTEGER DEFAULT 4,      -- 최소 발행 간격 (시간)

    -- 스케줄 설정
    schedule_crawl_hour INTEGER DEFAULT 3,     -- 크롤링 시간 (시)
    schedule_publish_hours TEXT DEFAULT '[9, 15]',  -- JSON: 발행 시간대
    schedule_monitor_hour INTEGER DEFAULT 23,  -- 모니터링 시간 (시)

    -- 품질 기준
    min_seo_score INTEGER DEFAULT 70,          -- 최소 SEO 점수
    plagiarism_threshold FLOAT DEFAULT 0.3,    -- 표절 임계값
    max_regeneration INTEGER DEFAULT 3,        -- 최대 재생성 횟수

    -- API 키 (암호화 필요 시 별도 처리)
    api_keys TEXT DEFAULT '{}',                -- JSON: {"anthropic": "", "gemini": "", ...}

    -- 상태
    active BOOLEAN DEFAULT 1,                  -- 활성화 여부
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 2. 기존 테이블에 blog_id 추가
-- =====================================================

-- posts 테이블
ALTER TABLE posts ADD COLUMN blog_id INTEGER DEFAULT 1 REFERENCES blogs(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_posts_blog_id ON posts(blog_id);

-- keywords 테이블
ALTER TABLE keywords ADD COLUMN blog_id INTEGER DEFAULT 1 REFERENCES blogs(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_keywords_blog_id ON keywords(blog_id);

-- articles 테이블
ALTER TABLE articles ADD COLUMN blog_id INTEGER DEFAULT 1 REFERENCES blogs(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_articles_blog_id ON articles(blog_id);

-- processed_articles 테이블
ALTER TABLE processed_articles ADD COLUMN blog_id INTEGER DEFAULT 1 REFERENCES blogs(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_processed_articles_blog_id ON processed_articles(blog_id);

-- crawl_log 테이블
ALTER TABLE crawl_log ADD COLUMN blog_id INTEGER DEFAULT 1 REFERENCES blogs(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_crawl_log_blog_id ON crawl_log(blog_id);

-- competitor_posts 테이블
ALTER TABLE competitor_posts ADD COLUMN blog_id INTEGER DEFAULT 1 REFERENCES blogs(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_competitor_posts_blog_id ON competitor_posts(blog_id);

-- posting_history 테이블
ALTER TABLE posting_history ADD COLUMN blog_id INTEGER DEFAULT 1 REFERENCES blogs(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_posting_history_blog_id ON posting_history(blog_id);

-- ranking_history 테이블
ALTER TABLE ranking_history ADD COLUMN blog_id INTEGER DEFAULT 1 REFERENCES blogs(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_ranking_history_blog_id ON ranking_history(blog_id);

-- =====================================================
-- 3. 기본 블로그 데이터 삽입 (silmu.kr)
-- =====================================================

INSERT INTO blogs (
    id,
    name,
    display_name,
    domain,
    description,
    theme,
    system_prompt,
    categories,
    crawler_configs,
    verification_modules,
    monthly_budget,
    max_posts_per_day,
    schedule_crawl_hour,
    schedule_publish_hours
) VALUES (
    1,
    'silmu',
    '실무 블로그',
    'silmu.kr',
    '교육행정 및 지방자치단체 실무자를 위한 전문 블로그',
    'education_admin',
    '당신은 교육행정·지방자치단체 실무 전문 블로그 작성자입니다.

## 핵심 원칙
1. **SEO 최적화 우선**: 네이버 검색 알고리즘(C-RANK, DIA+, AUTH.GR, AI.BRIEFING) 최적화
2. **실무자 관점**: 공무원, 학교 행정직이 실무에 바로 적용할 수 있는 정보 제공
3. **법적 정확성**: 법령, 시행령, 시행규칙 인용 시 정확성 필수
4. **가독성 최우선**: 전문 용어를 알기 쉽게 풀어 설명
5. **최신 정보 제공**: 현재 연도는 2026년입니다. 모든 제목과 내용에서 과거 연도(2024, 2025 등)를 2026년으로 변경하세요.

## 작성 규칙

### 구조 (D.I.A+ 알고리즘 최적화)
- H2 소제목(##)을 최소 3개 이상 사용
- 각 섹션은 300~500자 분량
- **마크다운 표(table)를 1개 이상 반드시 포함** (| 구분자 사용)
- FAQ 섹션을 마지막에 추가 (Q&A 3개)

### SEO 최적화
- 타겟 키워드 밀도 1.5~2.5%
- 키워드를 제목과 첫 문단에 반드시 포함
- 관련 키워드도 자연스럽게 배치
- 본문 길이 2000~3000자

### 법령 인용
- 법령명은 「」로 감싸기 (예: 「지방계약법」)
- 조항은 정확히 명시 (예: 제25조 제1항)
- 출처를 명확히 표기

### 문체
- 반말 사용 ("~합니다" → "~해요", "~됩니다" → "~돼요")
- 친근하지만 전문적인 톤
- 불필요한 수식어 제거
- 능동태 우선, 수동태 최소화

### 금지사항
- AI 냄새 나는 표현 금지: "또한", "따라서", "즉", "물론" 등 과도한 접속사
- 원본 기사 표절 금지 (30% 미만 유사도)
- 추상적 표현 금지 (구체적 숫자, 사례 활용)
- 불필요한 인사말 금지 ("안녕하세요" 등)
- **과거 연도 사용 금지**: 제목과 본문에 2024, 2025 등 과거 연도를 사용하지 말고, 항상 2026년을 사용하세요.

위 규칙을 모두 준수하여 작성하세요.',
    '["계약/조달", "학교회계", "교육청", "예산편성", "세입세출"]',
    '{"law": true, "mogef": true, "pps": true, "local_gov": true, "edu": true}',
    '["legal", "plagiarism"]',
    5000,
    2,
    3,
    '[9, 15]'
);

-- =====================================================
-- 4. 마이그레이션 완료 확인
-- =====================================================

-- 블로그 수 확인
SELECT COUNT(*) as blog_count FROM blogs;

-- 기존 데이터의 blog_id 확인
SELECT
    (SELECT COUNT(*) FROM posts WHERE blog_id = 1) as posts_count,
    (SELECT COUNT(*) FROM keywords WHERE blog_id = 1) as keywords_count,
    (SELECT COUNT(*) FROM articles WHERE blog_id = 1) as articles_count;
