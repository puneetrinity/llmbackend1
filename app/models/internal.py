# app/models/internal.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class ContentSource(str, Enum):
    NEWS = "news"
    ACADEMIC = "academic"
    SOCIAL = "social"
    ECOMMERCE = "ecommerce"
    GENERAL = "general"

class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source_engine: str
    relevance_score: float = Field(ge=0.0, le=1.0)

class ContentData(BaseModel):
    url: str
    title: str
    content: str
    word_count: int
    source_type: ContentSource = ContentSource.GENERAL
    extraction_method: str = "default"
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    fetch_time: float = 0.0

class QueryEnhancement(BaseModel):
    original_query: str
    enhanced_queries: List[str]
    enhancement_method: str
    processing_time: float = 0.0
