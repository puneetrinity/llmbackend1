#!/usr/bin/env python3
"""
Database Migration Management Script
Provides a unified interface for Alembic operations
"""

import argparse
import asyncio
import os
import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config.settings import settings
from app.database.connection import db_manager

def run_alembic_command(command: list) -> int:
    """Run an alembic command and return exit code"""
    try:
        # Ensure we're in the project root directory
        os.chdir(project_root)
        
        # Set environment variables for the command
        env = os.environ.copy()
        env['DATABASE_URL'] = settings.DATABASE_URL
        
        print(f"🔧 Running: alembic {' '.join(command)}")
        result = subprocess.run(['alembic'] + command, env=env)
        return result.returncode
        
    except Exception as e:
        print(f"❌ Error running alembic command: {e}")
        return 1

async def check_database_connection():
    """Verify database connection before running migrations"""
    try:
        print("🔍 Checking database connection...")
        await db_manager.initialize()
        
        async with db_manager.get_session() as session:
            await session.execute("SELECT 1")
        
        print("✅ Database connection successful")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    finally:
        await db_manager.close()

def create_migration(message: str, autogenerate: bool = True) -> int:
    """Create a new migration"""
    if not message:
        print("❌ Migration message is required")
        return 1
    
    command = ['revision']
    if autogenerate:
        command.append('--autogenerate')
    command.extend(['-m', message])
    
    return run_alembic_command(command)

def upgrade_database(revision: str = 'head') -> int:
    """Upgrade database to specified revision"""
    return run_alembic_command(['upgrade', revision])

def downgrade_database(revision: str) -> int:
    """Downgrade database to specified revision"""
    if not revision:
        print("❌ Revision is required for downgrade")
        return 1
    
    return run_alembic_command(['downgrade', revision])

def show_current_revision() -> int:
    """Show current database revision"""
    return run_alembic_command(['current'])

def show_migration_history() -> int:
    """Show migration history"""
    return run_alembic_command(['history', '--verbose'])

def show_pending_migrations() -> int:
    """Show pending migrations"""
    return run_alembic_command(['show', 'head'])

def validate_migrations() -> int:
    """Validate migration scripts"""
    return run_alembic_command(['check'])

def stamp_database(revision: str) -> int:
    """Stamp database with specific revision (without running migrations)"""
    if not revision:
        print("❌ Revision is required for stamp")
        return 1
    
    return run_alembic_command(['stamp', revision])

async def init_database_with_migrations():
    """Initialize database and run all migrations"""
    print("🚀 Initializing database with migrations...")
    
    # Check connection first
    if not await check_database_connection():
        return 1
    
    # Create tables using Alembic
    exit_code = upgrade_database()
    
    if exit_code == 0:
        print("✅ Database initialized and migrations applied successfully")
    else:
        print("❌ Database initialization failed")
    
    return exit_code

def main():
    parser = argparse.ArgumentParser(description="Database Migration Management")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create migration
    create_parser = subparsers.add_parser('create', help='Create a new migration')
    create_parser.add_argument('message', help='Migration message')
    create_parser.add_argument('--no-autogenerate', action='store_true', 
                             help='Create empty migration (no autogenerate)')
    
    # Upgrade
    upgrade_parser = subparsers.add_parser('upgrade', help='Upgrade database')
    upgrade_parser.add_argument('revision', nargs='?', default='head', 
                               help='Target revision (default: head)')
    
    # Downgrade
    downgrade_parser = subparsers.add_parser('downgrade', help='Downgrade database')
    downgrade_parser.add_argument('revision', help='Target revision')
    
    # Status commands
    subparsers.add_parser('current', help='Show current revision')
    subparsers.add_parser('history', help='Show migration history')
    subparsers.add_parser('pending', help='Show pending migrations')
    subparsers.add_parser('validate', help='Validate migration scripts')
    
    # Stamp
    stamp_parser = subparsers.add_parser('stamp', help='Stamp database with revision')
    stamp_parser.add_argument('revision', help='Revision to stamp')
    
    # Initialize
    subparsers.add_parser('init', help='Initialize database with all migrations')
    
    # Raw alembic command
    raw_parser = subparsers.add_parser('raw', help='Run raw alembic command')
    raw_parser.add_argument('args', nargs=argparse.REMAINDER, help='Alembic arguments')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Handle async commands
    if args.command == 'init':
        return asyncio.run(init_database_with_migrations())
    
    # Handle sync commands
    if args.command == 'create':
        autogenerate = not args.no_autogenerate
        return create_migration(args.message, autogenerate)
    elif args.command == 'upgrade':
        return upgrade_database(args.revision)
    elif args.command == 'downgrade':
        return downgrade_database(args.revision)
    elif args.command == 'current':
        return show_current_revision()
    elif args.command == 'history':
        return show_migration_history()
    elif args.command == 'pending':
        return show_pending_migrations()
    elif args.command == 'validate':
        return validate_migrations()
    elif args.command == 'stamp':
        return stamp_database(args.revision)
    elif args.command == 'raw':
        return run_alembic_command(args.args)
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
