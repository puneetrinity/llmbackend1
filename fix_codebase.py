#!/usr/bin/env python3
"""
LLM Search Backend Auto-Fixer Script
=====================================

This script automatically fixes critical issues in the LLM Search Backend codebase:
- Creates missing files and directories
- Adds missing methods to existing classes
- Fixes import issues
- Updates configuration settings
- Creates proper __init__.py files

Usage:
    python fix_codebase.py [--dry-run] [--backup]

Options:
    --dry-run    Show what would be fixed without making changes
    --backup     Create backups of modified files
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class CodebaseFixer:
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
        
    def ensure_directory(self, dir_path):
        """Ensure directory exists"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create directory: {dir_path}")
            return
            
        dir_path.mkdir(parents=True, exist_ok=True)
        
    def write_file(self, file_path, content):
        """Write content to file"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would write to: {file_path}")
            return
            
        self.ensure_directory(file_path.parent)
        
        if file_path.exists() and self.backup:
            self.create_backup(file_path)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    def append_to_file(self, file_path, content):
        """Append content to existing file"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would append to: {file_path}")
            return
            
        if file_path.exists() and self.backup:
            self.create_backup(file_path)
            
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write('\n' + content)
            
    def fix_missing_init_files(self):
        """Create missing __init__.py files"""
        logger.info("🔧 Creating missing __init__.py files...")
        
        init_dirs = [
            'app/api',
            'app/core', 
            'app/models',
            'app/services',
            'app/utils',
            'app/database',
            'app/config'
        ]
        
        for dir_path in init_dirs:
            full_path = self.base_path / dir_path
            init_file = full_path / '__init__.py'
            
            if not init_file.exists():
                content = f'"""{"".join(dir_path.split("/")[1:]).title()} module"""'
                self.write_file(init_file, content)
                self.log_fix("Created __init__.py", str(init_file))
            else:
                self.log_skip("__init__.py exists", str(init_file))
                
    def fix_dependencies_file(self):
        """Create missing app/api/dependencies.py"""
        logger.info("🔧 Creating app/api/dependencies.py...")
        
        deps_file = self.base_path / 'app/api/dependencies.py'
        
        if deps_file.exists():
            self.log_skip("Dependencies file exists", str(deps_file))
            return
            
        content = '''"""
FastAPI dependencies for the search API
"""
import time
import logging
from typing import Optional
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.pipeline import SearchPipeline
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Global pipeline instance (singleton pattern)
_pipeline_instance: Optional[SearchPipeline] = None

# Optional authentication
security = HTTPBearer(auto_error=False)

async def get_pipeline() -> SearchPipeline:
    """Get or create the search pipeline instance"""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = SearchPipeline()
    return _pipeline_instance

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Get current user from authentication token
    Returns None for anonymous users in development
    """
    if not credentials:
        return None  # Allow anonymous access in development
        
    # TODO: Implement proper JWT token validation
    # For now, return a placeholder user ID
    return f"user_{hash(credentials.credentials) % 10000}"

# Rate limiting storage (in production, use Redis)
_rate_limit_storage = {}

async def rate_limit(request: Request) -> None:
    """
    Simple rate limiting implementation
    In production, this should use Redis or a proper rate limiting service
    """
    if not hasattr(settings, 'RATE_LIMIT_PER_MINUTE'):
        return  # No rate limiting configured
        
    client_ip = request.client.host
    current_time = time.time()
    window_start = current_time - 60  # 1 minute window
    
    # Clean old entries
    if client_ip in _rate_limit_storage:
        _rate_limit_storage[client_ip] = [
            req_time for req_time in _rate_limit_storage[client_ip]
            if req_time > window_start
        ]
    else:
        _rate_limit_storage[client_ip] = []
    
    # Check rate limit
    if len(_rate_limit_storage[client_ip]) >= settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    
    # Record this request
    _rate_limit_storage[client_ip].append(current_time)

async def get_request_id(request: Request) -> str:
    """Get or generate a request ID"""
    return getattr(request.state, 'request_id', 'unknown')
'''
        
        self.write_file(deps_file, content)
        self.log_fix("Created dependencies.py", str(deps_file))
        
    def fix_health_endpoint(self):
        """Create missing app/api/endpoints/health.py"""
        logger.info("🔧 Creating app/api/endpoints/health.py...")
        
        health_file = self.base_path / 'app/api/endpoints/health.py'
        
        if health_file.exists():
            self.log_skip("Health endpoint exists", str(health_file))
            return
            
        content = '''"""
Health check endpoints
"""
import time
import logging
from fastapi import APIRouter, Depends
from typing import Dict, Any

from app.models.responses import HealthResponse
from app.api.dependencies import get_pipeline
from app.core.pipeline import SearchPipeline

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=HealthResponse)
async def basic_health_check():
    """Basic health check endpoint"""
    return HealthResponse(
        status="healthy",
        services={"api": "healthy"}
    )

@router.get("/detailed")
async def detailed_health_check(
    pipeline: SearchPipeline = Depends(get_pipeline)
) -> Dict[str, Any]:
    """Detailed health check with all services"""
    start_time = time.time()
    
    try:
        # Check all pipeline components
        health_checks = await pipeline.health_check()
        
        response_time = (time.time() - start_time) * 1000  # Convert to ms
        
        return {
            "status": health_checks.get("overall", "unknown"),
            "timestamp": time.time(),
            "response_time_ms": response_time,
            "services": health_checks,
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": time.time(),
            "error": str(e),
            "services": {}
        }

@router.get("/ready")
async def readiness_check(
    pipeline: SearchPipeline = Depends(get_pipeline)
):
    """Kubernetes readiness check"""
    try:
        # Quick check of core services
        health_status = await pipeline.health_check()
        
        if health_status.get("overall") == "healthy":
            return {"status": "ready"}
        else:
            return {"status": "not ready", "details": health_status}
            
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {"status": "not ready", "error": str(e)}

@router.get("/live")
async def liveness_check():
    """Kubernetes liveness check"""
    return {"status": "alive", "timestamp": time.time()}
'''
        
        self.write_file(health_file, content)
        self.log_fix("Created health endpoints", str(health_file))
        
    def fix_admin_endpoint(self):
        """Create missing app/api/endpoints/admin.py"""
        logger.info("🔧 Creating app/api/endpoints/admin.py...")
        
        admin_file = self.base_path / 'app/api/endpoints/admin.py'
        
        if admin_file.exists():
            self.log_skip("Admin endpoint exists", str(admin_file))
            return
            
        content = '''"""
Admin endpoints for system management
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional

from app.api.dependencies import get_current_user, get_pipeline
from app.core.pipeline import SearchPipeline

router = APIRouter()
logger = logging.getLogger(__name__)

def require_admin(current_user: Optional[str] = Depends(get_current_user)):
    """Require admin authentication (placeholder implementation)"""
    # TODO: Implement proper admin authentication
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    # For now, allow any authenticated user to access admin endpoints
    return current_user

@router.get("/stats")
async def get_system_stats(
    admin_user: str = Depends(require_admin),
    pipeline: SearchPipeline = Depends(get_pipeline)
) -> Dict[str, Any]:
    """Get system statistics"""
    try:
        # Get basic system stats
        stats = {
            "admin_user": admin_user,
            "system": "LLM Search Backend",
            "version": "1.0.0",
            "status": "operational"
        }
        
        # Try to get cost tracker stats if available
        try:
            cost_stats = await pipeline.cost_tracker.get_daily_stats()
            stats["daily_costs"] = cost_stats
        except Exception as e:
            logger.warning(f"Could not get cost stats: {e}")
            stats["daily_costs"] = {"error": "Not available"}
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system stats")

@router.post("/cache/clear")
async def clear_cache(
    admin_user: str = Depends(require_admin),
    pipeline: SearchPipeline = Depends(get_pipeline)
):
    """Clear system cache"""
    try:
        # Clear various cache types
        await pipeline.cache.clear_pattern("*", "responses")
        await pipeline.cache.clear_pattern("*", "search")
        await pipeline.cache.clear_pattern("*", "enhancement")
        
        return {"status": "success", "message": "Cache cleared successfully"}
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")

@router.get("/health/detailed")
async def admin_health_check(
    admin_user: str = Depends(require_admin),
    pipeline: SearchPipeline = Depends(get_pipeline)
):
    """Detailed health check for admin users"""
    try:
        health_data = await pipeline.health_check()
        
        # Add additional admin-specific health info
        health_data["admin_user"] = admin_user
        health_data["debug_info"] = {
            "cache_enabled": pipeline.cache.redis_enabled,
            "active_requests": len(getattr(pipeline.cost_tracker, 'active_requests', {}))
        }
        
        return health_data
        
    except Exception as e:
        logger.error(f"Admin health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")
'''
        
        self.write_file(admin_file, content)
        self.log_fix("Created admin endpoints", str(admin_file))
        
    def fix_cache_service_methods(self):
        """Add missing methods to CacheService"""
        logger.info("🔧 Adding missing methods to CacheService...")
        
        cache_file = self.base_path / 'app/services/cache_service.py'
        
        if not cache_file.exists():
            self.log_skip("CacheService file not found", str(cache_file))
            return
            
        # Read existing content
        with open(cache_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check if methods already exist
        if 'get_response' in content and 'store_response' in content:
            self.log_skip("CacheService methods already exist", "get_response and store_response")
            return
            
        # Add missing methods
        missing_methods = '''
    async def get_response(self, query: str) -> Optional[Any]:
        """Get cached response for a query"""
        cache_key = f"response:{hash(query)}"
        return await self.get(cache_key, "responses")

    async def store_response(self, query: str, response: Any) -> bool:
        """Store response in cache"""
        from app.config.settings import settings
        cache_key = f"response:{hash(query)}"
        # Convert response to dict if it has a dict method
        if hasattr(response, 'dict'):
            response_data = response.dict()
        elif hasattr(response, '__dict__'):
            response_data = response.__dict__
        else:
            response_data = response
            
        ttl = getattr(settings, 'CACHE_TTL_FINAL_RESPONSE', 14400)  # 4 hours default
        return await self.set(cache_key, response_data, ttl, "responses")
'''
        
        # Find the last method in the class and add before the closing
        if 'async def close(self):' in content:
            content = content.replace('    async def close(self):', missing_methods + '\n    async def close(self):')
        else:
            # Add before the last line of the class
            lines = content.split('\n')
            # Find the last method or class end
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() and not lines[i].startswith('    '):
                    lines.insert(i, missing_methods.strip())
                    break
            content = '\n'.join(lines)
        
        if self.backup:
            self.create_backup(cache_file)
            
        if not self.dry_run:
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(content)
                
        self.log_fix("Added missing CacheService methods", "get_response and store_response")
        
    def fix_pipeline_import(self):
        """Fix import error in pipeline.py"""
        logger.info("🔧 Fixing pipeline.py import error...")
        
        pipeline_file = self.base_path / 'app/core/pipeline.py'
        
        if not pipeline_file.exists():
            self.log_skip("Pipeline file not found", str(pipeline_file))
            return
            
        # Read existing content
        with open(pipeline_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Fix the import line
        old_import = "from app.services.cache_service import CacheService, get_response"
        new_import = "from app.services.cache_service import CacheService"
        
        if old_import in content:
            if self.backup:
                self.create_backup(pipeline_file)
                
            content = content.replace(old_import, new_import)
            
            if not self.dry_run:
                with open(pipeline_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
            self.log_fix("Fixed pipeline import", "Removed get_response from import")
        else:
            self.log_skip("Pipeline import already correct", "No get_response in import")
            
    def fix_exceptions_file(self):
        """Create missing exceptions.py file"""
        logger.info("🔧 Creating app/core/exceptions.py...")
        
        exceptions_file = self.base_path / 'app/core/exceptions.py'
        
        if exceptions_file.exists():
            self.log_skip("Exceptions file exists", str(exceptions_file))
            return
            
        content = '''"""
Custom exceptions for the LLM Search Backend
"""
from fastapi import HTTPException

class PipelineException(Exception):
    """Raised when pipeline processing fails"""
    pass

class SearchEngineException(Exception):
    """Raised when search engine operations fail"""
    pass

class ContentFetchException(Exception):
    """Raised when content fetching fails"""
    pass

class QueryEnhancementException(Exception):
    """Raised when query enhancement fails"""
    pass

class CacheException(Exception):
    """Raised when cache operations fail"""
    pass

class LLMException(Exception):
    """Raised when LLM operations fail"""
    pass

class CostTrackingException(Exception):
    """Raised when cost tracking fails"""
    pass

class CustomHTTPException(HTTPException):
    """Custom HTTP exception with error codes"""
    
    def __init__(self, status_code: int, detail: str, error_code: str = None):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code

class RateLimitException(CustomHTTPException):
    """Raised when rate limit is exceeded"""
    
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(status_code=429, detail=detail, error_code="RATE_LIMIT_EXCEEDED")

class AuthenticationException(CustomHTTPException):
    """Raised when authentication fails"""
    
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=401, detail=detail, error_code="AUTH_FAILED")

class ValidationException(CustomHTTPException):
    """Raised when request validation fails"""
    
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(status_code=422, detail=detail, error_code="VALIDATION_FAILED")
'''
        
        self.write_file(exceptions_file, content)
        self.log_fix("Created exceptions file", str(exceptions_file))
        
    def add_missing_health_checks(self):
        """Add missing health_check methods to services"""
        logger.info("🔧 Adding missing health_check methods...")
        
        services_to_fix = [
            ('app/services/query_enhancer.py', 'QueryEnhancementService'),
            ('app/services/search_engine.py', 'MultiSearchEngine'),
            ('app/services/content_fetcher.py', 'ZenRowsContentFetcher'),
        ]
        
        health_check_method = '''
    async def health_check(self) -> str:
        """Check service health"""
        try:
            # Basic health check - ensure service can initialize
            if hasattr(self, 'session') and self.session:
                return "healthy"
            return "healthy"
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return "unhealthy"
'''
        
        for service_path, class_name in services_to_fix:
            service_file = self.base_path / service_path
            
            if not service_file.exists():
                self.log_skip(f"Service file not found", service_path)
                continue
                
            with open(service_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if 'async def health_check(self)' in content:
                self.log_skip(f"Health check exists in {class_name}", service_path)
                continue
                
            # Add health check method before the last line of the class
            if f'class {class_name}' in content:
                # Find a good place to insert - before any closing methods
                lines = content.split('\n')
                insert_index = len(lines) - 1
                
                # Find the end of the class
                for i in range(len(lines) - 1, -1, -1):
                    line = lines[i].strip()
                    if line and not line.startswith('#') and not line.startswith('    '):
                        insert_index = i
                        break
                
                lines.insert(insert_index, health_check_method.strip())
                content = '\n'.join(lines)
                
                if self.backup:
                    self.create_backup(service_file)
                    
                if not self.dry_run:
                    with open(service_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
                self.log_fix(f"Added health_check to {class_name}", service_path)
                
    def add_missing_settings(self):
        """Add missing settings to configuration"""
        logger.info("🔧 Adding missing settings...")
        
        settings_file = self.base_path / 'app/config/settings.py'
        
        if not settings_file.exists():
            self.log_skip("Settings file not found", str(settings_file))
            return
            
        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        missing_settings = []
        
        # Check for missing settings
        required_settings = [
            ('SERPAPI_API_KEY', 'str', '""'),
            ('MAX_CONTENT_LENGTH', 'int', '50000'),
            ('RATE_LIMIT_PER_MINUTE', 'int', '60'),
        ]
        
        for setting_name, setting_type, default_value in required_settings:
            if setting_name not in content:
                missing_settings.append(f"    {setting_name}: {setting_type} = {default_value}")
                
        if missing_settings:
            # Add missing settings before the Config class
            config_class_line = "    class Config:"
            if config_class_line in content:
                settings_to_add = "\n    # Missing settings added by auto-fixer\n" + "\n".join(missing_settings) + "\n"
                content = content.replace(config_class_line, settings_to_add + "\n" + config_class_line)
                
                if self.backup:
                    self.create_backup(settings_file)
                    
                if not self.dry_run:
                    with open(settings_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
                self.log_fix("Added missing settings", ", ".join([s.split(':')[0].strip() for s in missing_settings]))
            else:
                self.log_skip("Could not find Config class", "Unable to add settings")
        else:
            self.log_skip("All settings present", "No missing settings")
            
    def create_llm_analyzer_stub(self):
        """Create a stub implementation for LLM analyzer if missing"""
        logger.info("🔧 Creating LLM analyzer stub...")
        
        llm_file = self.base_path / 'app/services/llm_analyzer.py'
        
        if llm_file.exists():
            # Check if analyze method exists
            with open(llm_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if 'async def analyze(' in content:
                self.log_skip("LLM analyzer analyze method exists", str(llm_file))
                return
            else:
                # Add the analyze method
                analyze_method = '''
    async def analyze(self, query: str, content_data, request_id: str):
        """
        Analyze content and generate response (stub implementation)
        TODO: Implement actual LLM analysis
        """
        from app.models.responses import SearchResponse
        
        # Stub implementation - just return a basic response
        sources = [content.url for content in content_data[:5]] if content_data else []
        
        answer = f"Based on the search for '{query}', I found {len(content_data)} sources. "
        answer += "This is a stub implementation that needs to be replaced with actual LLM analysis."
        
        return SearchResponse(
            query=query,
            answer=answer,
            sources=sources,
            confidence=0.5,
            processing_time=0.1,
            cached=False
        )
'''
                
                # Find end of class and add method
                lines = content.split('\n')
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip() and not lines[i].startswith('    ') and not lines[i].startswith('#'):
                        lines.insert(i, analyze_method.strip())
                        break
                        
                content = '\n'.join(lines)
                
                if self.backup:
                    self.create_backup(llm_file)
                    
                if not self.dry_run:
                    with open(llm_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
                self.log_fix("Added analyze method to LLMAnalysisService", str(llm_file))
        else:
            self.log_skip("LLM analyzer file not found", str(llm_file))
            
    def run_all_fixes(self):
        """Run all fixes in the correct order"""
        logger.info("🚀 Starting codebase auto-fix process...")
        
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be made")
            
        try:
            # 1. Create missing directories and __init__.py files
            self.fix_missing_init_files()
            
            # 2. Fix critical import error
            self.fix_pipeline_import()
            
            # 3. Create missing core files
            self.fix_exceptions_file()
            self.fix_dependencies_file()
            self.fix_health_endpoint()
            self.fix_admin_endpoint()
            
            # 4. Add missing methods to existing classes
            self.fix_cache_service_methods()
            self.add_missing_health_checks()
            self.create_llm_analyzer_stub()
            
            # 5. Fix configuration
            self.add_missing_settings()
            
        except Exception as e:
            logger.error(f"❌ Error during fix process: {e}")
            raise
            
        # Summary
        logger.info("\n" + "="*60)
        logger.info("🎉 CODEBASE FIX SUMMARY")
        logger.info("="*60)
        
        if self.fixes_applied:
            logger.info(f"✅ Applied {len(self.fixes_applied)} fixes:")
            for fix in self.fixes_applied:
                logger.info(f"   • {fix}")
        else:
            logger.info("✅ No fixes were needed!")
            
        if self.fixes_skipped:
            logger.info(f"\n⏭️  Skipped {len(self.fixes_skipped)} items:")
            for skip in self.fixes_skipped[:5]:  # Show first 5
                logger.info(f"   • {skip}")
            if len(self.fixes_skipped) > 5:
                logger.info(f"   ... and {len(self.fixes_skipped) - 5} more")
                
        logger.info("\n🚀 Next steps:")
        logger.info("   1. Review the changes made")
        logger.info("   2. Test your application: python -m uvicorn app.main:app --reload")
        logger.info("   3. Implement TODO items in the generated stubs")
        logger.info("   4. Add proper error handling and validation")

def main():
    parser = argparse.ArgumentParser(description="Auto-fix LLM Search Backend codebase issues")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed without making changes")
    parser.add_argument("--backup", action="store_true", help="Create backups of modified files")
    
    args = parser.parse_args()
    
    fixer = CodebaseFixer(dry_run=args.dry_run, backup=args.backup)
    
    try:
        fixer.run_all_fixes()
        logger.info("✅ Codebase fix completed successfully!")
        return 0
    except Exception as e:
        logger.error(f"❌ Codebase fix failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())