# app/config/settings.py - RAILWAY PROPER VERSION
from pydantic_settings import BaseSettings  
from pydantic import field_validator
from typing import List, Optional, Union
import os
import logging

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
    
    # Cache Configuration - RAILWAY TEMPLATE VARIABLE
    REDIS_URL: str = "${{ Redis.REDIS_URL }}"  # ✅ Railway template variable
    CACHE_TTL_QUERY_ENHANCEMENT: int = 3600  
    CACHE_TTL_SEARCH_RESULTS: int = 1800     
    CACHE_TTL_FINAL_RESPONSE: int = 14400    
    MEMORY_CACHE_SIZE: int = 1000
    
    # Database - RAILWAY TEMPLATE VARIABLE  
    DATABASE_URL: str = "${{ Postgres.DATABASE_URL }}"  # ✅ Railway template variable
    
    # Security
    ALLOWED_ORIGINS: Union[str, List[str]] = "*"
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
        """Parse CORS origins safely"""
        if v is None:
            return ["*"]
        
        if isinstance(v, str):
            if v.strip() == "":
                return ["*"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        
        if isinstance(v, list):
            return v
        
        return ["*"]
    
    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        """Parse DEBUG boolean safely"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }

# ✅ Proper BaseSettings instantiation
settings = Settings()
logger.info("✅ Settings loaded with Railway template variables")
