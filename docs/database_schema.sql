-- Feature Voting System - Complete Database Schema
-- PostgreSQL 16 with pgvector extension
-- Run this after: CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(20) NOT NULL DEFAULT 'voter' CHECK (role IN ('admin', 'voter', 'viewer')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

-- ============================================================================
-- COMPETITORS TABLE
-- ============================================================================
CREATE TABLE competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    website_url TEXT,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'pending')),
    added_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_scraped_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_competitors_status ON competitors(status);
CREATE INDEX idx_competitors_added_by ON competitors(added_by);
CREATE INDEX idx_competitors_name ON competitors(name);

-- ============================================================================
-- PRODUCTS TABLE
-- ============================================================================
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competitor_id UUID REFERENCES competitors(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    url TEXT,
    description TEXT,
    is_confirmed BOOLEAN DEFAULT false,
    discovery_method VARCHAR(50) CHECK (discovery_method IN ('automated', 'manual')),
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    confirmed_at TIMESTAMP WITH TIME ZONE,
    confirmed_by UUID REFERENCES users(id),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_products_competitor ON products(competitor_id);
CREATE INDEX idx_products_confirmed ON products(is_confirmed);
CREATE INDEX idx_products_name ON products(name);

-- ============================================================================
-- FEATURES TABLE
-- ============================================================================
CREATE TABLE features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    raw_feature_text TEXT NOT NULL,
    feature_category VARCHAR(100),
    feature_url TEXT,
    extraction_method VARCHAR(50) CHECK (extraction_method IN ('llm', 'scraping', 'manual')),
    extracted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_features_product ON features(product_id);
CREATE INDEX idx_features_category ON features(feature_category);
CREATE INDEX idx_features_extracted_at ON features(extracted_at DESC);

-- ============================================================================
-- IDEAS TABLE (CORE)
-- ============================================================================
-- Enable pgvector extension first
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE ideas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    
    -- Structured content
    what_description TEXT NOT NULL,
    why_description TEXT NOT NULL,
    use_case_description TEXT NOT NULL,
    
    -- Source tracking
    source_type VARCHAR(30) NOT NULL CHECK (source_type IN ('competitor_automated', 'manual_submission')),
    feature_id UUID REFERENCES features(id) ON DELETE SET NULL,
    submitter_id UUID REFERENCES users(id),
    
    -- Categorization
    category VARCHAR(100),
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Status
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'archived', 'merged', 'implemented')),
    
    -- Vector embedding for similarity search (1536 dimensions for OpenAI ada-002)
    embedding vector(1536),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Constraints
    CONSTRAINT check_source_tracking CHECK (
        (source_type = 'competitor_automated' AND feature_id IS NOT NULL) OR
        (source_type = 'manual_submission' AND submitter_id IS NOT NULL)
    )
);

CREATE INDEX idx_ideas_source_type ON ideas(source_type);
CREATE INDEX idx_ideas_submitter ON ideas(submitter_id);
CREATE INDEX idx_ideas_category ON ideas(category);
CREATE INDEX idx_ideas_status ON ideas(status);
CREATE INDEX idx_ideas_created_at ON ideas(created_at DESC);
CREATE INDEX idx_ideas_title ON ideas USING gin(to_tsvector('english', title));

-- Vector similarity index using HNSW (Hierarchical Navigable Small World)
CREATE INDEX idx_ideas_embedding ON ideas USING hnsw (embedding vector_cosine_ops);

-- ============================================================================
-- SUBMISSIONS TABLE
-- ============================================================================
CREATE TABLE submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idea_id UUID REFERENCES ideas(id) ON DELETE CASCADE,
    submitter_id UUID NOT NULL REFERENCES users(id),
    
    -- Original input
    original_freeform_text TEXT NOT NULL,
    
    -- AI processing
    ai_structured_version JSONB, -- {what, why, use_case}
    user_edits JSONB, -- Track what user changed from AI suggestions
    structuring_time_seconds INTEGER,
    
    -- Similarity check results
    similarity_check_results JSONB, -- Array of similar ideas shown to user
    dismissed_similar_ideas UUID[], -- IDs of ideas user saw but chose not to vote on
    similarity_check_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_submissions_idea ON submissions(idea_id);
CREATE INDEX idx_submissions_submitter ON submissions(submitter_id);
CREATE INDEX idx_submissions_submitted_at ON submissions(submitted_at DESC);

-- ============================================================================
-- DRAFTS TABLE
-- ============================================================================
CREATE TABLE drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    freeform_text TEXT NOT NULL,
    
    -- Cached similarity results
    cached_similarity_results JSONB,
    similarity_cache_updated_at TIMESTAMP WITH TIME ZONE,
    
    -- Draft metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    auto_save_count INTEGER DEFAULT 0
);

CREATE INDEX idx_drafts_user ON drafts(user_id);
CREATE INDEX idx_drafts_updated ON drafts(last_updated DESC);

-- ============================================================================
-- VOTES TABLE
-- ============================================================================
CREATE TABLE votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vote_value INTEGER NOT NULL CHECK (vote_value IN (-1, 1)), -- -1 downvote, 1 upvote
    voted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(idea_id, user_id) -- One vote per user per idea
);

CREATE INDEX idx_votes_idea ON votes(idea_id);
CREATE INDEX idx_votes_user ON votes(user_id);
CREATE INDEX idx_votes_voted_at ON votes(voted_at DESC);

-- ============================================================================
-- MATERIALIZED VIEW FOR VOTE COUNTS
-- ============================================================================
CREATE MATERIALIZED VIEW idea_vote_summary AS
SELECT 
    i.id AS idea_id,
    COALESCE(SUM(CASE WHEN v.vote_value = 1 THEN 1 ELSE 0 END), 0) AS upvotes,
    COALESCE(SUM(CASE WHEN v.vote_value = -1 THEN 1 ELSE 0 END), 0) AS downvotes,
    COALESCE(SUM(v.vote_value), 0) AS score,
    COUNT(v.id) AS total_votes
FROM ideas i
LEFT JOIN votes v ON i.id = v.idea_id
GROUP BY i.id;

CREATE UNIQUE INDEX idx_vote_summary_idea ON idea_vote_summary(idea_id);
CREATE INDEX idx_vote_summary_score ON idea_vote_summary(score DESC);

-- Refresh function for materialized view
CREATE OR REPLACE FUNCTION refresh_vote_summary()
RETURNS trigger AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY idea_vote_summary;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger to refresh vote summary after vote changes
CREATE TRIGGER trigger_refresh_vote_summary
AFTER INSERT OR UPDATE OR DELETE ON votes
FOR EACH STATEMENT
EXECUTE FUNCTION refresh_vote_summary();

-- ============================================================================
-- AUDIT LOG TABLE
-- ============================================================================
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_created_at ON audit_log(created_at DESC);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to find similar ideas using vector similarity
CREATE OR REPLACE FUNCTION find_similar_ideas(
    query_embedding vector(1536),
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 5
)
RETURNS TABLE (
    idea_id UUID,
    title VARCHAR,
    similarity_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        i.id,
        i.title,
        1 - (i.embedding <=> query_embedding) AS similarity
    FROM ideas i
    WHERE i.status = 'active'
        AND 1 - (i.embedding <=> query_embedding) >= similarity_threshold
    ORDER BY i.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Function to get user's submission history
CREATE OR REPLACE FUNCTION get_user_submissions(
    p_user_id UUID,
    p_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    idea_id UUID,
    title VARCHAR,
    score INTEGER,
    submitted_at TIMESTAMP WITH TIME ZONE,
    original_text TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        i.id,
        i.title,
        COALESCE(vs.score, 0)::INTEGER,
        s.submitted_at,
        s.original_freeform_text
    FROM ideas i
    JOIN submissions s ON i.id = s.idea_id
    LEFT JOIN idea_vote_summary vs ON i.id = vs.idea_id
    WHERE s.submitter_id = p_user_id
    ORDER BY s.submitted_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to get idea with full context (admin view)
CREATE OR REPLACE FUNCTION get_idea_with_source(
    p_idea_id UUID
)
RETURNS TABLE (
    idea_id UUID,
    title VARCHAR,
    what_description TEXT,
    why_description TEXT,
    use_case_description TEXT,
    source_type VARCHAR,
    competitor_name VARCHAR,
    product_name VARCHAR,
    submitter_username VARCHAR,
    score INTEGER,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        i.id,
        i.title,
        i.what_description,
        i.why_description,
        i.use_case_description,
        i.source_type,
        c.name AS competitor_name,
        p.name AS product_name,
        u.username AS submitter_username,
        COALESCE(vs.score, 0)::INTEGER,
        i.created_at
    FROM ideas i
    LEFT JOIN features f ON i.feature_id = f.id
    LEFT JOIN products p ON f.product_id = p.id
    LEFT JOIN competitors c ON p.competitor_id = c.id
    LEFT JOIN users u ON i.submitter_id = u.id
    LEFT JOIN idea_vote_summary vs ON i.id = vs.idea_id
    WHERE i.id = p_idea_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================================

-- Generic function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at column
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_competitors_updated_at BEFORE UPDATE ON competitors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ideas_updated_at BEFORE UPDATE ON ideas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_votes_updated_at BEFORE UPDATE ON votes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_drafts_updated_at BEFORE UPDATE ON drafts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SAMPLE DATA (OPTIONAL - FOR DEVELOPMENT)
-- ============================================================================

-- Insert admin user (password: 'admin123' - CHANGE IN PRODUCTION!)
-- Password hash generated with: bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
INSERT INTO users (email, username, password_hash, full_name, role) VALUES
('admin@example.com', 'admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5nyvhKhN.I5ae', 'System Admin', 'admin');

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Public view of ideas (no source attribution)
CREATE VIEW public_ideas AS
SELECT 
    i.id,
    i.title,
    i.what_description,
    i.why_description,
    i.use_case_description,
    i.category,
    i.tags,
    i.status,
    i.created_at,
    COALESCE(vs.score, 0) AS score,
    COALESCE(vs.upvotes, 0) AS upvotes,
    COALESCE(vs.downvotes, 0) AS downvotes,
    COALESCE(vs.total_votes, 0) AS total_votes
FROM ideas i
LEFT JOIN idea_vote_summary vs ON i.id = vs.idea_id
WHERE i.status = 'active';

-- Admin view of ideas with source attribution
CREATE VIEW admin_ideas AS
SELECT 
    i.*,
    COALESCE(vs.score, 0) AS score,
    c.name AS competitor_name,
    p.name AS product_name,
    u.username AS submitter_username,
    u.email AS submitter_email
FROM ideas i
LEFT JOIN idea_vote_summary vs ON i.id = vs.idea_id
LEFT JOIN features f ON i.feature_id = f.id
LEFT JOIN products p ON f.product_id = p.id
LEFT JOIN competitors c ON p.competitor_id = c.id
LEFT JOIN users u ON i.submitter_id = u.id;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE ideas IS 'Core table storing all feature ideas (both competitor-sourced and user-submitted)';
COMMENT ON COLUMN ideas.embedding IS 'Vector embedding for semantic similarity search (1536 dimensions)';
COMMENT ON TABLE submissions IS 'Tracks manual idea submissions with original text and AI processing details';
COMMENT ON TABLE votes IS 'User votes on ideas (upvote/downvote system)';
COMMENT ON MATERIALIZED VIEW idea_vote_summary IS 'Pre-computed vote statistics for fast querying';
COMMENT ON FUNCTION find_similar_ideas IS 'Find semantically similar ideas using vector cosine similarity';