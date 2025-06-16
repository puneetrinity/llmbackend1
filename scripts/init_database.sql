# scripts/init_database.sql
-- Initial database setup script
-- This runs when the PostgreSQL container first starts

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create basic indexes will be handled by Alembic migrations
-- This file just ensures the database is properly initialized

-- Log that initialization completed
INSERT INTO pg_stat_statements_info (version) VALUES ('database_initialized') ON CONFLICT DO NOTHING;
