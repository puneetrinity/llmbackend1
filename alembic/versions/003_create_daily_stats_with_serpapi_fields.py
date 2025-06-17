"""Create daily_stats table and add SerpAPI fields

Revision ID: 003_create_daily_stats
Revises: 002_serpapi_migration
Create Date: 2024-12-02 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '003_create_daily_stats'
down_revision = '002_serpapi_migration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create daily_stats table and add SerpAPI cost fields"""

    # ✅ Create daily_stats table
    op.create_table(
        'daily_stats',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('date', sa.Date, nullable=False),
        sa.Column('total_requests', sa.Integer, server_default="0"),
        sa.Column('successful_requests', sa.Integer, server_default="0"),
        sa.Column('failed_requests', sa.Integer, server_default="0"),
        sa.Column('cached_requests', sa.Integer, server_default="0"),
        sa.Column('avg_response_time', sa.Float, server_default="0"),
        sa.Column('p95_response_time', sa.Float, server_default="0"),
        sa.Column('avg_confidence_score', sa.Float, server_default="0"),
        sa.Column('total_cost', sa.Float, server_default="0"),
        sa.Column('brave_search_cost', sa.Float, server_default="0"),
        sa.Column('bing_search_cost', sa.Float, server_default="0"),
        sa.Column('zenrows_cost', sa.Float, server_default="0"),
        sa.Column('serpapi_search_cost', sa.Float, server_default="0"),  # ✅ Added
        sa.Column('total_api_calls', sa.Integer, server_default="0"),
        sa.Column('total_content_fetched', sa.Integer, server_default="0"),
        sa.Column('total_llm_tokens', sa.Integer, server_default="0"),
        sa.Column('cache_hit_rate', sa.Float, server_default="0"),
        sa.Column('total_cache_hits', sa.Integer, server_default="0"),
        sa.Column('total_cache_misses', sa.Integer, server_default="0"),
        sa.Column('unique_users', sa.Integer, server_default="0"),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_index('ix_daily_stats_date', 'daily_stats', ['date'])

    # ✅ Add new columns to cost_records
    op.add_column('cost_records', sa.Column('serpapi_search_cost', sa.Float(), nullable=True, server_default="0.0"))
    op.add_column('cost_records', sa.Column('serpapi_searches', sa.Integer(), nullable=True, server_default="0"))

    # ✅ Add check constraints
    op.create_check_constraint('check_serpapi_searches', 'cost_records', 'serpapi_searches >= 0')
    op.create_check_constraint('check_serpapi_cost', 'cost_records', 'serpapi_search_cost >= 0')
    op.create_check_constraint('check_daily_serpapi_cost', 'daily_stats', 'serpapi_search_cost >= 0')

    # ✅ Ensure default values in existing rows
    op.execute(text("UPDATE cost_records SET serpapi_search_cost = 0.0 WHERE serpapi_search_cost IS NULL"))
    op.execute(text("UPDATE cost_records SET serpapi_searches = 0 WHERE serpapi_searches IS NULL"))

    # ✅ Make columns non-nullable
    op.alter_column('cost_records', 'serpapi_search_cost', nullable=False)
    op.alter_column('cost_records', 'serpapi_searches', nullable=False)
    op.alter_column('daily_stats', 'serpapi_search_cost', nullable=False)

    # ✅ Remove server defaults (optional cleanup)
    op.alter_column('cost_records', 'serpapi_search_cost', server_default=None)
    op.alter_column('cost_records', 'serpapi_searches', server_default=None)
    op.alter_column('daily_stats', 'serpapi_search_cost', server_default=None)


def downgrade() -> None:
    """Revert daily_stats table and SerpAPI fields"""

    # Drop constraints
    op.drop_constraint('check_serpapi_searches', 'cost_records', type_='check')
    op.drop_constraint('check_serpapi_cost', 'cost_records', type_='check')
    op.drop_constraint('check_daily_serpapi_cost', 'daily_stats', type_='check')

    # Drop SerpAPI columns from cost_records
    op.drop_column('cost_records', 'serpapi_search_cost')
    op.drop_column('cost_records', 'serpapi_searches')

    # Drop daily_stats table
    op.drop_index('ix_daily_stats_date', table_name='daily_stats')
    op.drop_table('daily_stats')
