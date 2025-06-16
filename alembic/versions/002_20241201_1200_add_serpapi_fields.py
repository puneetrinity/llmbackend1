# alembic/versions/002_20241201_1200_add_serpapi_fields.py
"""Add SerpApi cost tracking fields

Revision ID: 002_serpapi_migration
Revises: 001_initial_tables
Create Date: 2024-12-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_serpapi_migration'
down_revision = '001_initial_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add SerpApi-specific cost tracking fields"""
    
    # Add SerpApi cost fields to cost_records table
    op.add_column('cost_records', sa.Column('serpapi_search_cost', sa.Float(), nullable=True, default=0.0))
    op.add_column('cost_records', sa.Column('serpapi_searches', sa.Integer(), nullable=True, default=0))
    
    # Add SerpApi cost fields to daily_stats table
    op.add_column('daily_stats', sa.Column('serpapi_search_cost', sa.Float(), nullable=True, default=0.0))
    
    # Add check constraints for new fields
    op.create_check_constraint('check_serpapi_searches', 'cost_records', 'serpapi_searches >= 0')
    op.create_check_constraint('check_serpapi_cost', 'cost_records', 'serpapi_search_cost >= 0')
    op.create_check_constraint('check_daily_serpapi_cost', 'daily_stats', 'serpapi_search_cost >= 0')
    
    # Update existing records to set default values
    op.execute("UPDATE cost_records SET serpapi_search_cost = 0.0 WHERE serpapi_search_cost IS NULL")
    op.execute("UPDATE cost_records SET serpapi_searches = 0 WHERE serpapi_searches IS NULL")
    op.execute("UPDATE daily_stats SET serpapi_search_cost = 0.0 WHERE serpapi_search_cost IS NULL")
    
    # Make columns non-nullable after setting defaults
    op.alter_column('cost_records', 'serpapi_search_cost', nullable=False)
    op.alter_column('cost_records', 'serpapi_searches', nullable=False)
    op.alter_column('daily_stats', 'serpapi_search_cost', nullable=False)


def downgrade() -> None:
    """Remove SerpApi-specific cost tracking fields"""
    
    # Drop check constraints
    op.drop_constraint('check_serpapi_searches', 'cost_records', type_='check')
    op.drop_constraint('check_serpapi_cost', 'cost_records', type_='check')
    op.drop_constraint('check_daily_serpapi_cost', 'daily_stats', type_='check')
    
    # Remove SerpApi columns
    op.drop_column('cost_records', 'serpapi_search_cost')
    op.drop_column('cost_records', 'serpapi_searches')
    op.drop_column('daily_stats', 'serpapi_search_cost')
