#!/usr/bin/env python3
"""
Final Codebase Issues Auto-Fixer
================================

This script fixes the remaining critical issues discovered in the second analysis:
1. Missing admin import/router in main.py
2. SQLAlchemy text() import issues
3. Missing middleware implementations
4. Endpoints __init__.py missing admin
5. Database connection text() import

Usage:
    python fix_remaining_issues.py [--dry-run] [--backup]
"""

import os
import sys
import re
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class FinalCodebaseFixer:
    def __init__(self, dry_run=False, backup=False):
        self.dry_run = dry_run
        self.backup = backup
        self.base_path = Path.cwd()
        self.fixes_applied = []
        self.fixes_skipped = []
        
    def log_fix(self, action, details):
        """Log a fix that was applied"""
        self.fixes_applied.append(f"{action}: {details}")
        logger.info(f"✅ {action}: {details}")
        
    def log_skip(self, action, reason):
        """Log a fix that was skipped"""
        self.fixes_skipped.append(f"{action}: {reason}")
        logger.info(f"⏭️  {action}: {reason}")
        
    def create_backup(self, file_path):
        """Create a backup of a file"""
        if not self.backup or self.dry_run:
            return
        backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(file_path, backup_path)
        logger.info(f"📋 Created backup: {backup_path}")
        
    def write_file(self, file_path, content):
        """Write content to file"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would write to: {file_path}")
            return
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if file_path.exists() and self.backup:
            self.create_backup(file_path)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    def fix_main_py_admin_import(self):
        """Fix missing admin import and router in main.py"""
        logger.info("🔧 Fixing main.py admin import and router...")
        
        main_file = self.base_path / 'app/main.py'
        
        if not main_file.exists():
            self.log_skip("main.py not found", str(main_file))
            return
            
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        changes_made = False
        
        # Fix 1: Add admin to imports
        old_import = "from app.api.endpoints import search, health"
        new_import = "from app.api.endpoints import search, health, admin"
        
        if old_import in content and "admin" not in content:
            content = content.replace(old_import, new_import)
            changes_made = True
            self.log_fix("Added admin import", "to endpoints import")
        
        # Fix 2: Add admin router include
        health_router_line = 'app.include_router(health.router, prefix="/health", tags=["health"])'
        admin_router_line = 'app.include_router(admin.router, prefix="/admin", tags=["admin"])'
        
        if health_router_line in content and admin_router_line not in content:
            content = content.replace(
                health_router_line,
                health_router_line + '\n' + admin_router_line
            )
            changes_made = True
            self.log_fix("Added admin router", "to FastAPI app")
            
        # Fix 3: Remove missing middleware reference if it exists
        middleware_line = "from app.api.middleware import RequestLoggingMiddleware"
        if middleware_line in content:
            # Comment out the middleware import and usage since it doesn't exist
            content = content.replace(middleware_line, f"# {middleware_line}  # Disabled - not implemented")
            content = content.replace(
                "app.add_middleware(RequestLoggingMiddleware)",
                "# app.add_middleware(RequestLoggingMiddleware)  # Disabled - not implemented"
            )
            changes_made = True
            self.log_fix("Disabled missing middleware", "RequestLoggingMiddleware")
            
        if changes_made:
            if self.backup:
                self.create_backup(main_file)
                
            if not self.dry_run:
                with open(main_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
        else:
            self.log_skip("main.py already correct", "No changes needed")
            
    def fix_endpoints_init_py(self):
        """Fix endpoints __init__.py to include admin"""
        logger.info("🔧 Fixing endpoints __init__.py...")
        
        init_file = self.base_path / 'app/api/endpoints/__init__.py'
        
        if not init_file.exists():
            self.log_skip("endpoints __init__.py not found", str(init_file))
            return
            
        with open(init_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check if admin is already included
        if 'admin' in content:
            self.log_skip("Admin already in endpoints __init__.py", "No changes needed")
            return
            
        # Update the import and __all__
        old_import = "from . import search, health"
        new_import = "from . import search, health, admin"
        
        old_all = '__all__ = ["search", "health"]'
        new_all = '__all__ = ["search", "health", "admin"]'
        
        content = content.replace(old_import, new_import)
        content = content.replace(old_all, new_all)
        
        if self.backup:
            self.create_backup(init_file)
            
        if not self.dry_run:
            with open(init_file, 'w', encoding='utf-8') as f:
                f.write(content)
                
        self.log_fix("Added admin to endpoints __init__.py", "Import and __all__")
        
    def fix_sqlalchemy_text_import(self):
        """Fix SQLAlchemy text() import in database files"""
        logger.info("🔧 Fixing SQLAlchemy text() imports...")
        
        files_to_check = [
            'app/database/connection.py',
            'app/database/repositories.py'
        ]
        
        for file_path in files_to_check:
            full_path = self.base_path / file_path
            
            if not full_path.exists():
                self.log_skip(f"File not found", file_path)
                continue
                
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check if text() is used but not imported
            if 'text(' in content and 'from sqlalchemy import text' not in content:
                # Find SQLAlchemy imports section
                lines = content.split('\n')
                insert_line = -1
                
                for i, line in enumerate(lines):
                    if 'from sqlalchemy' in line:
                        insert_line = i + 1
                        break
                        
                if insert_line > -1:
                    lines.insert(insert_line, 'from sqlalchemy import text')
                    content = '\n'.join(lines)
                    
                    if self.backup:
                        self.create_backup(full_path)
                        
                    if not self.dry_run:
                        with open(full_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                            
                    self.log_fix(f"Added text import to {file_path}", "SQLAlchemy text() function")
                else:
                    self.log_skip(f"Could not find import location in {file_path}", "No SQLAlchemy imports found")
            else:
                self.log_skip(f"text() import not needed in {file_path}", "Already imported or not used")
                
    def create_missing_middleware(self):
        """Create missing RequestLoggingMiddleware"""
        logger.info("🔧 Creating missing RequestLoggingMiddleware...")
        
        middleware_file = self.base_path / 'app/api/middleware.py'
        
        if middleware_file.exists():
            self.log_skip("Middleware file exists", str(middleware_file))
            return
            
        content = '''"""
Custom middleware for the FastAPI application
"""
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log request details and timing
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Start timing
        start_time = time.time()
        
        # Get request info
        method = request.method
        url = str(request.url)
        client_ip = request.client.host if request.client else "unknown"
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log successful request
            logger.info(
                f"{method} {url} - {response.status_code} - "
                f"{process_time:.3f}s - IP: {client_ip}"
            )
            
            # Add timing header
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except Exception as e:
            # Calculate processing time for failed requests
            process_time = time.time() - start_time
            
            # Log failed request
            logger.error(
                f"{method} {url} - ERROR: {str(e)} - "
                f"{process_time:.3f}s - IP: {client_ip}"
            )
            
            # Re-raise the exception
            raise

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
'''
        
        self.write_file(middleware_file, content)
        self.log_fix("Created middleware.py", "RequestLoggingMiddleware and SecurityHeadersMiddleware")
        
    def fix_query_enhancer_missing_method(self):
        """Add missing get_suggestions_only method to QueryEnhancementService"""
        logger.info("🔧 Adding get_suggestions_only method to QueryEnhancementService...")
        
        enhancer_file = self.base_path / 'app/services/query_enhancer.py'
        
        if not enhancer_file.exists():
            self.log_skip("QueryEnhancementService file not found", str(enhancer_file))
            return
            
        with open(enhancer_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'async def get_suggestions_only(' in content:
            self.log_skip("get_suggestions_only method exists", "Already implemented")
            return
            
        # Add the missing method
        missing_method = '''
    async def get_suggestions_only(self, query: str) -> List[str]:
        """
        Get query suggestions without full enhancement
        Used by the suggestions endpoint
        """
        try:
            # Use the google autocomplete strategy
            suggestions = await self._google_autocomplete_suggestions(query)
            
            # Return top 5 suggestions
            return suggestions[:5] if suggestions else [query]
            
        except Exception as e:
            logger.warning(f"Failed to get suggestions for '{query}': {e}")
            return [query]  # Return original query as fallback
            
    async def _google_autocomplete_suggestions(self, query: str) -> List[str]:
        """Get suggestions from Google Autocomplete"""
        try:
            session = await self._get_session()
            
            url = "http://suggestqueries.google.com/complete/search"
            params = {
                "client": "chrome",
                "q": query,
                "hl": "en"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if len(data) > 1 and isinstance(data[1], list):
                        return data[1][:10]  # Return top 10 suggestions
                        
        except Exception as e:
            logger.warning(f"Google autocomplete failed: {e}")
            
        return []
'''
        
        # Find the end of the class and add the method
        lines = content.split('\n')
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line and not line.startswith('#') and not line.startswith('    '):
                lines.insert(i, missing_method.strip())
                break
                
        content = '\n'.join(lines)
        
        if self.backup:
            self.create_backup(enhancer_file)
            
        if not self.dry_run:
            with open(enhancer_file, 'w', encoding='utf-8') as f:
                f.write(content)
                
        self.log_fix("Added get_suggestions_only method", "QueryEnhancementService")
        
    def fix_settings_validation(self):
        """Fix settings validation and add missing imports"""
        logger.info("🔧 Fixing settings validation...")
        
        settings_file = self.base_path / 'app/config/settings.py'
        
        if not settings_file.exists():
            self.log_skip("Settings file not found", str(settings_file))
            return
            
        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        changes_made = False
        
        # Fix import for BaseSettings (Pydantic v2)
        if 'from pydantic import BaseSettings' in content:
            content = content.replace(
                'from pydantic import BaseSettings',
                'from pydantic_settings import BaseSettings'
            )
            changes_made = True
            self.log_fix("Fixed BaseSettings import", "Updated for Pydantic v2")
            
        # Add missing LOG_LEVEL setting if not present
        if 'LOG_LEVEL:' not in content:
            config_line = "    class Config:"
            if config_line in content:
                log_level_setting = "    LOG_LEVEL: str = \"INFO\"\n"
                content = content.replace(config_line, log_level_setting + "\n" + config_line)
                changes_made = True
                self.log_fix("Added LOG_LEVEL setting", "Default INFO level")
                
        if changes_made:
            if self.backup:
                self.create_backup(settings_file)
                
            if not self.dry_run:
                with open(settings_file, 'w', encoding='utf-8') as f:
                    f.write(content)
        else:
            self.log_skip("Settings file already correct", "No changes needed")
            
    def run_final_fixes(self):
        """Run all final fixes"""
        logger.info("🚀 Starting final codebase fixes...")
        
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be made")
            
        try:
            # Critical fixes for startup
            self.fix_main_py_admin_import()
            self.fix_endpoints_init_py()
            self.fix_sqlalchemy_text_import()
            
            # Missing implementations
            self.create_missing_middleware()
            self.fix_query_enhancer_missing_method()
            
            # Configuration fixes
            self.fix_settings_validation()
            
        except Exception as e:
            logger.error(f"❌ Error during final fix process: {e}")
            raise
            
        # Summary
        logger.info("\n" + "="*60)
        logger.info("🎉 FINAL FIXES SUMMARY")
        logger.info("="*60)
        
        if self.fixes_applied:
            logger.info(f"✅ Applied {len(self.fixes_applied)} final fixes:")
            for fix in self.fixes_applied:
                logger.info(f"   • {fix}")
        else:
            logger.info("✅ No final fixes were needed!")
            
        if self.fixes_skipped:
            logger.info(f"\n⏭️  Skipped {len(self.fixes_skipped)} items:")
            for skip in self.fixes_skipped[:5]:
                logger.info(f"   • {skip}")
            if len(self.fixes_skipped) > 5:
                logger.info(f"   ... and {len(self.fixes_skipped) - 5} more")
                
        logger.info("\n🚀 Ready to test!")
        logger.info("   Run: python -m uvicorn app.main:app --reload")
        logger.info("   Test: curl http://localhost:8000/health")

def main():
    parser = argparse.ArgumentParser(description="Fix remaining codebase issues")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed")
    parser.add_argument("--backup", action="store_true", help="Create backups of modified files")
    
    args = parser.parse_args()
    
    fixer = FinalCodebaseFixer(dry_run=args.dry_run, backup=args.backup)
    
    try:
        fixer.run_final_fixes()
        logger.info("✅ Final fixes completed successfully!")
        return 0
    except Exception as e:
        logger.error(f"❌ Final fixes failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())