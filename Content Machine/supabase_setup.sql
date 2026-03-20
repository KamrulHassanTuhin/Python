-- Run this in Supabase SQL Editor (one time setup)
-- Go to: supabase.com → your project → SQL Editor → New Query

CREATE TABLE IF NOT EXISTS articles (
    id BIGSERIAL PRIMARY KEY,
    article_id TEXT UNIQUE,
    user_id TEXT,
    keyword TEXT,
    output_path TEXT,
    quality_score INTEGER DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'published',
    published_at TIMESTAMPTZ DEFAULT NOW()
);

-- Allow public read/write (simple setup — tighten later with RLS)
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all" ON articles
    FOR ALL USING (true) WITH CHECK (true);
