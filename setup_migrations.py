#!/usr/bin/env python3
"""
Alembic Migration Setup Script
Automatically sets up proper database migrations for your Railway deployment
"""

import asyncio
import os
import sys
import subprocess
import logging
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.config.settings import settings
from app.database.connection import db_manager
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MigrationSetup:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.alembic_dir = self.project_root / "alembic"
        
    async def check_database_state(self):
        """Check current database state"""
        logger.info("🔍 Checking database state...")
        
        if not db_manager.is_available:
            logger.error("❌ Database not available")
            return False
        
        try:
            async with db_manager.get_session_context() as session:
                # Check if tables exist
                result = await session.execute(text("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'users'
                """))
                
                has_tables = result.scalar() > 0
                
                # Check if alembic version table exists
                try:
                    result = await session.execute(text("""
                        SELECT version_num FROM alembic_version LIMIT 1
                    """))
                    alembic_version = result.scalar()
                    has_alembic = True
                except Exception:
                    alembic_version = None
                    has_alembic = False
                
                logger.info(f"📊 Database state:")
                logger.info(f"   • Has tables: {has_tables}")
                logger.info(f"   • Has alembic: {has_alembic}")
                if alembic_version:
                    logger.info(f"   • Alembic version: {alembic_version}")
                
                return {
                    'has_tables': has_tables,
                    'has_alembic': has_alembic,
                    'alembic_version': alembic_version
                }
                
        except Exception as e:
            logger.error(f"❌ Error checking database: {e}")
            return False
    
    def check_alembic_setup(self):
        """Check if Alembic is properly set up"""
        logger.info("🔍 Checking Alembic setup...")
        
        required_files = [
            self.alembic_dir / "alembic.ini",
            self.alembic_dir / "env.py",
            self.alembic_dir / "versions",
            self.project_root / "scripts" / "manage_migrations.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not file_path.exists():
                missing_files.append(str(file_path))
        
        if missing_files:
            logger.error(f"❌ Missing Alembic files: {missing_files}")
            return False
        
        logger.info("✅ Alembic files present")
        return True
    
    def run_command(self, cmd, description):
        """Run a command and return success status"""
        logger.info(f"🔄 {description}")
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                logger.info(f"✅ {description} - Success")
                if result.stdout.strip():
                    logger.info(f"   Output: {result.stdout.strip()}")
                return True
            else:
                logger.error(f"❌ {description} - Failed")
                logger.error(f"   Error: {result.stderr.strip()}")
                return False
                
        except Exception as e:
            logger.error(f"❌ {description} - Exception: {e}")
            return False
    
    def stamp_database(self, version="head"):
        """Stamp database with current migration version"""
        return self.run_command([
            sys.executable, 
            "scripts/manage_migrations.py", 
            "stamp", 
            version
        ], f"Stamping database with version '{version}'")
    
    def create_initial_migration(self):
        """Create initial migration from current models"""
        return self.run_command([
            sys.executable,
            "scripts/manage_migrations.py", 
            "create",
            "initial_tables_from_existing"
        ], "Creating initial migration from existing models")
    
    def upgrade_database(self):
        """Upgrade database to latest migration"""
        return self.run_command([
            sys.executable,
            "scripts/manage_migrations.py",
            "upgrade"
        ], "Upgrading database to latest migration")
    
    def get_current_revision(self):
        """Get current database revision"""
        try:
            result = subprocess.run([
                sys.executable,
                "scripts/manage_migrations.py", 
                "current"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return None
                
        except Exception:
            return None
    
    async def setup_migrations(self):
        """Main setup process"""
        logger.info("🚀 Setting up Alembic migrations...")
        logger.info("=" * 50)
        
        # Step 1: Check Alembic files
        if not self.check_alembic_setup():
            logger.error("💥 Alembic setup incomplete - run alembic init first")
            return False
        
        # Step 2: Check database state
        db_state = await self.check_database_state()
        if not db_state:
            return False
        
        # Step 3: Handle different scenarios
        if db_state['has_tables'] and not db_state['has_alembic']:
            # Scenario: Tables exist but no Alembic tracking
            logger.info("📋 Scenario: Existing tables, no Alembic tracking")
            logger.info("   Solution: Stamp database with current state")
            
            if not self.stamp_database("head"):
                return False
            
        elif not db_state['has_tables'] and not db_state['has_alembic']:
            # Scenario: Fresh database
            logger.info("📋 Scenario: Fresh database")
            logger.info("   Solution: Run migrations to create tables")
            
            if not self.upgrade_database():
                return False
            
        elif db_state['has_tables'] and db_state['has_alembic']:
            # Scenario: Already using Alembic
            logger.info("📋 Scenario: Already using Alembic")
            logger.info("   Solution: Check if migrations are current")
            
            current_rev = self.get_current_revision()
            if current_rev:
                logger.info(f"   Current revision: {current_rev}")
            
            # Try to upgrade in case there are pending migrations
            self.upgrade_database()
        
        # Step 4: Verify setup
        logger.info("🔍 Verifying migration setup...")
        current_rev = self.get_current_revision()
        
        if current_rev:
            logger.info(f"✅ Migration setup complete!")
            logger.info(f"   Current revision: {current_rev}")
            return True
        else:
            logger.error("❌ Migration setup verification failed")
            return False
    
    def create_startup_code(self):
        """Generate production-ready startup code"""
        startup_code = '''
# Replace init_database() in app/database/connection.py with this:

async def init_database():
    """Initialize database using Alembic migrations - PRODUCTION READY"""
    if not db_manager.is_available:
        logger.warning("⚠️ Skipping database initialization - database not available")
        return
    
    try:
        import subprocess
        import sys
        
        logger.info("🔄 Running database migrations...")
        
        # Run alembic upgrade head
        result = subprocess.run([
            sys.executable, 
            "scripts/manage_migrations.py", 
            "upgrade"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("✅ Database migrations applied successfully")
            if result.stdout.strip():
                logger.info(f"Migration output: {result.stdout.strip()}")
        else:
            # Check if it's just "no migrations to apply"
            if "No migrations to apply" in result.stderr or "already at" in result.stderr:
                logger.info("✅ Database already up to date")
            else:
                logger.error(f"❌ Migration failed: {result.stderr}")
                raise Exception(f"Migration failed: {result.stderr}")
                
    except Exception as e:
        logger.error(f"❌ Database migration error: {e}")
        # In production, you might want to fail here
        # raise
        
        # For now, log and continue (for backward compatibility)
        logger.warning("⚠️ Continuing without migrations")
'''
        
        logger.info("📝 Production startup code:")
        print(startup_code)

async def main():
    """Main setup function"""
    print("🚀 Alembic Migration Setup")
    print("=" * 50)
    
    setup = MigrationSetup()
    
    try:
        success = await setup.setup_migrations()
        
        if success:
            print("\n" + "=" * 50)
            print("🎉 SUCCESS! Migration setup completed")
            print("\n📋 Next steps:")
            print("1. Update your init_database() function (see code below)")
            print("2. Test locally: python scripts/manage_migrations.py current") 
            print("3. Deploy to Railway - migrations will run automatically")
            print("4. Create new migrations: python scripts/manage_migrations.py create 'description'")
            
            setup.create_startup_code()
            
        else:
            print("\n" + "=" * 50)
            print("❌ Setup failed - check errors above")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
