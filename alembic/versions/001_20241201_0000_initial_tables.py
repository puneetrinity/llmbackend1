"""Create initial database tables

Revision ID: 001_initial_tables
Revises: 
Create Date: 2024-12-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all initial tables"""
    
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_identifier', sa.String(length=255), nullable=False),
        sa.Column('user_type', sa.String(length=50), nullable=True),
        sa.Column('api_key', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('daily_request_limit', sa.Integer(), nullable=True),
        sa.Column('monthly_cost_limit', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_request_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_api_key'), 'users', ['api_key'], unique=True)
    op.create_index(op.f('ix_users_created_at'), 'users', ['created_at'], unique=False)
    op.create_index(op.f('ix_users_last_request'), 'users', ['last_request_at'], unique=False)
    op.create_index(op.f('ix_users_user_identifier'), 'users', ['user_identifier'], unique=True)

    # Create search_requests table
    op.create_table('search_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('original_query', sa.Text(), nullable=False),
        sa.Column('enhanced_queries', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('max_results', sa.Integer(), nullable=True),
        sa.Column('include_sources', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('response_answer', sa.Text(), nullable=True),
        sa.Column('response_sources', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('processing_time', sa.Float(), nullable=True),
        sa.Column('cache_hit', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('client_ip', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='check_confidence_score'),
        sa.CheckConstraint('processing_time >= 0', name='check_processing_time'),
        sa.CheckConstraint('total_cost >= 0', name='check_total_cost'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_search_requests_cache_hit'), 'search_requests', ['cache_hit'], unique=False)
    op.create_index(op.f('ix_search_requests_created_at'), 'search_requests', ['created_at'], unique=False)
    op.create_index(op.f('ix_search_requests_request_id'), 'search_requests', ['request_id'], unique=True)
    op.create_index(op.f('ix_search_requests_status'), 'search_requests', ['status'], unique=False)
    op.create_index('ix_search_requests_user_created', 'search_requests', ['user_id', 'created_at'], unique=False)

    # Create content_sources table
    op.create_table('content_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('search_request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('source_type', sa.String(length=20), nullable=True),
        sa.Column('extraction_method', sa.String(length=50), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('fetch_time', sa.Float(), nullable=True),
        sa.Column('fetch_successful', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='check_content_confidence_score'),
        sa.CheckConstraint('fetch_time >= 0', name='check_fetch_time'),
        sa.CheckConstraint('word_count >= 0', name='check_word_count'),
        sa.ForeignKeyConstraint(['search_request_id'], ['search_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_content_sources_created_at'), 'content_sources', ['created_at'], unique=False)
    op.create_index(op.f('ix_content_sources_search_request'), 'content_sources', ['search_request_id'], unique=False)
    op.create_index('ix_content_sources_url_hash', 'content_sources', [sa.text('md5(url)')], unique=False)

    # Create cost_records table
    op.create_table('cost_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('search_request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('brave_search_cost', sa.Float(), nullable=True),
        sa.Column('bing_search_cost', sa.Float(), nullable=True),
        sa.Column('bing_autosuggest_cost', sa.Float(), nullable=True),
        sa.Column('zenrows_cost', sa.Float(), nullable=True),
        sa.Column('llm_cost', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('brave_searches', sa.Integer(), nullable=True),
        sa.Column('bing_searches', sa.Integer(), nullable=True),
        sa.Column('bing_autosuggest_calls', sa.Integer(), nullable=True),
        sa.Column('zenrows_requests', sa.Integer(), nullable=True),
        sa.Column('llm_tokens', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('bing_searches >= 0', name='check_bing_searches'),
        sa.CheckConstraint('brave_searches >= 0', name='check_brave_searches'),
        sa.CheckConstraint('total_cost >= 0', name='check_cost_records_total_cost'),
        sa.CheckConstraint('zenrows_requests >= 0', name='check_zenrows_requests'),
        sa.ForeignKeyConstraint(['search_request_id'], ['search_requests.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cost_records_created_at'), 'cost_records', ['created_at'], unique=False)
    op.create_index(op.f('ix_cost_records_search_request'), 'cost_records', ['search_request_id'], unique=False)
    op.create_index('ix_cost_records_user_created', 'cost_records', ['user_id', 'created_at'], unique=False)

    # Create api_usage table
    op.create_table('api_usage',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('search_request_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('endpoint', sa.String(length=255), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=True),
        sa.Column('request_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_time', sa.Float(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('cost >= 0', name='check_api_cost'),
        sa.CheckConstraint('response_time >= 0', name='check_response_time'),
        sa.ForeignKeyConstraint(['search_request_id'], ['search_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_usage_created_at'), 'api_usage', ['created_at'], unique=False)
    op.create_index('ix_api_usage_provider_created', 'api_usage', ['provider', 'created_at'], unique=False)
    op.create_index(op.f('ix_api_usage_search_request'), 'api_usage', ['search_request_id'], unique=False)
    op.create_index(op.f('ix_api_usage_success'), 'api_usage', ['success'], unique=False)

    # Create cache_entries table
    op.create_table('cache_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cache_key', sa.String(length=255), nullable=False),
        sa.Column('cache_type', sa.String(length=50), nullable=False),
        sa.Column('data_size', sa.Integer(), nullable=True),
        sa.Column('ttl', sa.Integer(), nullable=True),
        sa.Column('hit_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_accessed', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('data_size >= 0', name='check_data_size'),
        sa.CheckConstraint('hit_count >= 0', name='check_hit_count'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cache_key', 'cache_type', name='uq_cache_key_type')
    )
    op.create_index(op.f('ix_cache_entries_cache_key'), 'cache_entries', ['cache_key'], unique=False)
    op.create_index(op.f('ix_cache_entries_expires_at'), 'cache_entries', ['expires_at'], unique=False)
    op.create_index(op.f('ix_cache_entries_last_accessed'), 'cache_entries', ['last_accessed'], unique=False)
    op.create_index('ix_cache_entries_type_created', 'cache_entries', ['cache_type', 'created_at'], unique=False)

    # Create system_metrics table
    op.create_table('system_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_type', sa.String(length=50), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('labels', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_metrics_created_at'), 'system_metrics', ['created_at'], unique=False)
    op.create_index('ix_system_metrics_name_created', 'system_metrics', ['metric_name', 'created_at'], unique=False)
    op.create_index(op.f('ix_system_metrics_type'), 'system_metrics', ['metric_type'], unique=False)

    # Create daily_stats table
    op.create_table('daily_stats',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_requests', sa.Integer(), nullable=True),
        sa.Column('successful_requests', sa.Integer(), nullable=True),
        sa.Column('failed_requests', sa.Integer(), nullable=True),
        sa.Column('cached_requests', sa.Integer(), nullable=True),
        sa.Column('avg_response_time', sa.Float(), nullable=True),
        sa.Column('p95_response_time', sa.Float(), nullable=True),
        sa.Column('avg_confidence_score', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('brave_search_cost', sa.Float(), nullable=True),
        sa.Column('bing_search_cost', sa.Float(), nullable=True),
        sa.Column('zenrows_cost', sa.Float(), nullable=True),
        sa.Column('total_api_calls', sa.Integer(), nullable=True),
        sa.Column('total_content_fetched', sa.Integer(), nullable=True),
        sa.Column('total_llm_tokens', sa.Integer(), nullable=True),
        sa.Column('cache_hit_rate', sa.Float(), nullable=True),
        sa.Column('total_cache_hits', sa.Integer(), nullable=True),
        sa.Column('total_cache_misses', sa.Integer(), nullable=True),
        sa.Column('unique_users', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('cache_hit_rate >= 0 AND cache_hit_rate <= 1', name='check_cache_hit_rate'),
        sa.CheckConstraint('total_cost >= 0', name='check_daily_total_cost'),
        sa.CheckConstraint('total_requests >= 0', name='check_total_requests'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date', name='uq_daily_stats_date')
    )
    op.create_index(op.f('ix_daily_stats_date'), 'daily_stats', ['date'], unique=False)

    # Create error_logs table
    op.create_table('error_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('error_type', sa.String(length=100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(length=255), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('endpoint', sa.String(length=255), nullable=True),
        sa.Column('context_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_error_logs_created_at'), 'error_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_error_logs_request_id'), 'error_logs', ['request_id'], unique=False)
    op.create_index('ix_error_logs_type_created', 'error_logs', ['error_type', 'created_at'], unique=False)

    # Create rate_limit_records table
    op.create_table('rate_limit_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('identifier', sa.String(length=255), nullable=False),
        sa.Column('limit_type', sa.String(length=50), nullable=False),
        sa.Column('requests_count', sa.Integer(), nullable=True),
        sa.Column('limit_exceeded', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('requests_count >= 0', name='check_requests_count'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rate_limit_records_created_at'), 'rate_limit_records', ['created_at'], unique=False)
    op.create_index(op.f('ix_rate_limit_records_exceeded'), 'rate_limit_records', ['limit_exceeded'], unique=False)
    op.create_index(op.f('ix_rate_limit_records_identifier'), 'rate_limit_records', ['identifier'], unique=False)
    op.create_index('ix_rate_limit_identifier_window', 'rate_limit_records', ['identifier', 'window_start', 'window_end'], unique=False)


def downgrade() -> None:
    """Drop all tables"""
    op.drop_table('rate_limit_records')
    op.drop_table('error_logs')
    op.drop_table('daily_stats')
    op.drop_table('system_metrics')
    op.drop_table('cache_entries')
    op.drop_table('api_usage')
    op.drop_table('cost_records')
    op.drop_table('content_sources')
    op.drop_table('search_requests')
    op.drop_table('users')
