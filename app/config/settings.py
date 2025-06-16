# app/config/settings.py - Fixed Pydantic v2 imports
from pydantic_settings import BaseSettings  # ← FIXED: Import from pydantic_settings
from pydantic import field_validator          # ← FIXED: validator renamed to field_validator
from typing import List, Optional
import os

class Settings(BaseSettings):
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # External API Keys
    BRAVE_SEARCH_API_KEY: str = ""
    SERPAPI_API_KEY: str = ""  # Replaced BING_SEARCH_API_KEY and BING_AUTOSUGGEST_API_KEY
    ZENROWS_API_KEY: str = ""
    
    # LLM Configuration
    OLLAMA_HOST: str = "http://localhost:11434"
    LLM_MODEL: str = "llama2:7b"
    LLM_MAX_TOKENS: int = 500
    LLM_TEMPERATURE: float = 0.1
    LLM_TIMEOUT: int = 30
    
    # Cache Configuration
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL_QUERY_ENHANCEMENT: int = 3600  # 1 hour
    CACHE_TTL_SEARCH_RESULTS: int = 1800     # 30 minutes
    CACHE_TTL_FINAL_RESPONSE: int = 14400    # 4 hours
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
    SERPAPI_MONTHLY_BUDGET: float = 100.0  # New: SerpApi budget limit
    
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
    MAX_CONTENT_LENGTH: int = 5000  # Max chars per content fetch
    
    # FIXED: Updated for Pydantic v2
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]  # ✅ FIXED: Added missing closing parenthesis
        return v
    
    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return v
    
    # FIXED: Updated for Pydantic v2
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }

settings = Settings()
