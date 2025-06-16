# app/core/exceptions.py
from fastapi import HTTPException

class CustomHTTPException(HTTPException):
    def __init__(self, status_code: int, detail: str, error_code: str = None):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code

class PipelineException(Exception):
    """Exception raised during pipeline processing"""
    pass

class QueryEnhancementException(Exception):
    """Exception raised during query enhancement"""
    pass

class SearchEngineException(Exception):
    """Exception raised during search engine operations"""
    pass

class ContentFetchException(Exception):
    """Exception raised during content fetching"""
    pass

class LLMAnalysisException(Exception):
    """Exception raised during LLM analysis"""
    pass

class CacheException(Exception):
    """Exception raised during cache operations"""
    pass

class RateLimitException(CustomHTTPException):
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(status_code=429, detail=detail, error_code="RATE_LIMIT_EXCEEDED")

class ValidationException(CustomHTTPException):
    def __init__(self, detail: str = "Validation error"):
        super().__init__(status_code=400, detail=detail, error_code="VALIDATION_ERROR")

class ServiceUnavailableException(CustomHTTPException):
    def __init__(self, detail: str = "Service temporarily unavailable"):
        super().__init__(status_code=503, detail=detail, error_code="SERVICE_UNAVAILABLE")
