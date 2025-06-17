# app/core/__init__.py - FIXED: Remove circular import

# Import only exceptions and utilities, not the pipeline
from .exceptions import (
    PipelineException,
    QueryEnhancementException,
    SearchEngineException,
    ContentFetchException,
    LLMAnalysisException,
    CacheException
)

from .security import (
    get_current_user,
    verify_api_key,
    hash_api_key
)

# DO NOT import SearchPipeline here - it causes circular imports
# Import SearchPipeline directly where needed instead

__all__ = [
    # Exceptions
    "PipelineException",
    "QueryEnhancementException", 
    "SearchEngineException",
    "ContentFetchException",
    "LLMAnalysisException",
    "CacheException",
    
    # Security
    "get_current_user",
    "verify_api_key", 
    "hash_api_key"
]
