# app/models/responses.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class SearchResponse(BaseModel):
    query: str = Field(..., description="Original search query")
    answer: str = Field(..., description="AI-generated response")
    sources: List[str] = Field(..., description="Source URLs used")
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0,
        description="Confidence score (0.0-1.0)"
    )
    processing_time: float = Field(..., description="Processing time in seconds")
    cached: bool = Field(default=False, description="Whether response was cached")
    cost_estimate: Optional[float] = Field(None, description="Estimated cost in USD")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = Field(..., description="Individual service statuses")
    response_time_ms: Optional[float] = Field(None, description="Health check response time")

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
