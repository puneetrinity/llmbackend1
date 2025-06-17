# app/config/settings.py - Debug Version
from pydantic_settings import BaseSettings  
from pydantic import field_validator          
from typing import List, Optional
import os
import logging

# Setup basic logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # External API Keys
    BRAVE_SEARCH_API_KEY: str = ""
    SERPAPI_API_KEY: str = ""  
    ZENROWS_API_KEY: str = ""
    
    # LLM Configuration
    OLLAMA_HOST: str = "http://localhost:11434"
    LLM_MODEL: str = "llama2:7b"
    LLM_MAX_TOKENS: int = 500
    LLM_TEMPERATURE: float = 0.1
    LLM_TIMEOUT: int = 30
    
    # Cache Configuration
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL_QUERY_ENHANCEMENT: int = 3600  
    CACHE_TTL_SEARCH_RESULTS: int = 1800     
    CACHE_TTL_FINAL_RESPONSE: int = 14400    
    MEMORY_CACHE_SIZE: int = 1000
    
    # Database
    DATABASE_URL: str = "postgresql://user:pass@localhost:5432/searchdb"
    
    # Security
    ALLOWED_ORIGINS: List[str] = ["*"]
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Cost Controls
    DAILY_BUDGET_USD: float = 100.0
    MAX_SOURCES_PER_QUERY: int = 8
    MAX_CONCURRENT_REQUESTS: int = 100
    ZENROWS_MONTHLY_BUDGET: float = 200.0
    SERPAPI_MONTHLY_BUDGET: float = 100.0  
    
    # Performance
    REQUEST_TIMEOUT: int = 30
    SEARCH_TIMEOUT: int = 10
    CONTENT_FETCH_TIMEOUT: int = 15
    
    # Monitoring
    LOG_LEVEL: str = "INFO"
    ENABLE_METRICS: bool = True
    HEALTH_CHECK_INTERVAL: int = 60
    
    # Search Configuration
    MAX_SEARCH_RESULTS: int = 10
    MAX_CONTENT_LENGTH: int = 5000  
    
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        logger.info(f"🔍 ALLOWED_ORIGINS raw value: {v!r} (type: {type(v)})")
        try:
            if isinstance(v, str):
                result = [origin.strip() for origin in v.split(",")]
                logger.info(f"✅ ALLOWED_ORIGINS parsed: {result}")
                return result
            logger.info(f"✅ ALLOWED_ORIGINS using as-is: {v}")
            return v
        except Exception as e:
            logger.error(f"❌ Error parsing ALLOWED_ORIGINS: {e}")
            return ["*"]  # Safe fallback
    
    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        logger.info(f"🔍 DEBUG raw value: {v!r} (type: {type(v)})")
        try:
            if isinstance(v, str):
                result = v.lower() in ("true", "1", "yes", "on")
                logger.info(f"✅ DEBUG parsed: {result}")
                return result
            return v
        except Exception as e:
            logger.error(f"❌ Error parsing DEBUG: {e}")
            return False
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"  # Ignore unknown env vars
    }

# Debug environment variables before creating settings
logger.info("🔍 Checking environment variables...")
for key in ["ALLOWED_ORIGINS", "DEBUG", "REDIS_URL", "DATABASE_URL"]:
    value = os.getenv(key)
    logger.info(f"   {key} = {value!r}")

# Create settings with error handling
try:
    logger.info("🚀 Creating Settings instance...")
    settings = Settings()
    logger.info("✅ Settings created successfully!")
except Exception as e:
    logger.error(f"❌ Settings creation failed: {e}")
    logger.error(f"   Error type: {type(e)}")
    # Create minimal fallback
    logger.warning("🔄 Creating fallback settings...")
    settings = Settings.model_validate({
        "ALLOWED_ORIGINS": ["*"],
        "DEBUG": False,
        "REDIS_URL": "redis://localhost:6379",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/searchdb"
    })
