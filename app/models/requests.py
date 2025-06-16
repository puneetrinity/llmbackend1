# app/models/requests.py
from pydantic import BaseModel, Field, validator
from typing import Optional

class SearchRequest(BaseModel):
    query: str = Field(
        ..., 
        min_length=1, 
        max_length=500,
        description="The search query to process"
    )
    max_results: int = Field(
        default=8, 
        ge=1, 
        le=20,
        description="Maximum number of sources to include"
    )
    include_sources: bool = Field(
        default=True,
        description="Whether to include source URLs in response"
    )
    
    @validator("query")
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()
