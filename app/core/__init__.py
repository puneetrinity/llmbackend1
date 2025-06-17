# app/core/__init__.py - MINIMAL VERSION TO AVOID ALL CIRCULAR IMPORTS

# Only import exceptions that don't have circular dependencies
try:
    from .exceptions import (
        PipelineException,
        QueryEnhancementException,
        SearchEngineException,
        ContentFetchException,
        LLMAnalysisException,
        CacheException
    )
except ImportError:
    # If exceptions import fails, define basic ones
    class PipelineException(Exception):
        pass
    
    class QueryEnhancementException(Exception):
        pass
    
    class SearchEngineException(Exception):
        pass
    
    class ContentFetchException(Exception):
        pass
    
    class LLMAnalysisException(Exception):
        pass
    
    class CacheException(Exception):
        pass

# DO NOT import SearchPipeline or any services here
# Import them directly where needed to avoid circular imports

__all__ = [
    "PipelineException",
    "QueryEnhancementException", 
    "SearchEngineException",
    "ContentFetchException",
    "LLMAnalysisException",
    "CacheException"
]
