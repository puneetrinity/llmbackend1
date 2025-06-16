-- scripts/create_indexes.sql  
-- Additional indexes for performance optimization
-- These complement the indexes defined in the SQLAlchemy models

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_search_requests_user_status_created 
ON search_requests(user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_requests_status_created 
ON search_requests(status, created_at DESC) 
WHERE status IN ('completed', 'failed');

CREATE INDEX IF NOT EXISTS idx_cost_records_user_date 
ON cost_records(user_id, created_at::date);

CREATE INDEX IF NOT EXISTS idx_api_usage_provider_success_created 
ON api_usage(provider, success, created_at DESC);

-- Partial indexes for better performance on filtered queries
CREATE INDEX IF NOT EXISTS idx_search_requests_successful 
ON search_requests(created_at DESC) 
WHERE status = 'completed';

CREATE INDEX IF NOT EXISTS idx_search_requests_failed 
ON search_requests(created_at DESC, error_message) 
WHERE status = 'failed';

CREATE INDEX IF NOT EXISTS idx_cache_entries_active 
ON cache_entries(cache_type, last_accessed DESC) 
WHERE expires_at > NOW();

-- Text search indexes for query analysis
CREATE INDEX IF NOT EXISTS idx_search_requests_query_text 
ON search_requests USING gin(to_tsvector('english', original_query));

-- Log that index creation completed
-- Note: In production, use proper logging instead of this hack
DO $$
BEGIN
    RAISE NOTICE 'Additional indexes created successfully';
END $$;
