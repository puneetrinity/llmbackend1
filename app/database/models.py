# app/database/models.py
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, JSON,
    ForeignKey, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from app.database.connection import Base

# Enums
class RequestStatus(PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

class ContentSourceType(PyEnum):
    NEWS = "news"
    ACADEMIC = "academic"
    SOCIAL = "social"
    ECOMMERCE = "ecommerce"
    GENERAL = "general"

class ApiProvider(PyEnum):
    BRAVE_SEARCH = "brave_search"
    BING_SEARCH = "bing_search"
    BING_AUTOSUGGEST = "bing_autosuggest"
    ZENROWS = "zenrows"
    OLLAMA = "ollama"

# Models
class User(Base):
    """User model for tracking usage and authentication"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_identifier = Column(String(255), unique=True, nullable=False, index=True)
    user_type = Column(String(50), default="anonymous")  # anonymous, api_key, authenticated
    api_key = Column(String(255), unique=True, nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    daily_request_limit = Column(Integer, default=1000)
    monthly_cost_limit = Column(Float, default=100.0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_request_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    search_requests = relationship("SearchRequest", back_populates="user", cascade="all, delete-orphan")
    cost_records = relationship("CostRecord", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_users_created_at', 'created_at'),
        Index('ix_users_last_request', 'last_request_at'),
    )

class SearchRequest(Base):
    """Model for logging search requests"""
    __tablename__ = "search_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Request data
    original_query = Column(Text, nullable=False)
    enhanced_queries = Column(JSON, nullable=True)  # List of enhanced queries
    max_results = Column(Integer, default=8)
    include_sources = Column(Boolean, default=True)
    
    # Response data
    status = Column(String(20), default=RequestStatus.PENDING.value)
    response_answer = Column(Text, nullable=True)
    response_sources = Column(JSON, nullable=True)  # List of source URLs
    confidence_score = Column(Float, nullable=True)
    
    # Performance metrics
    processing_time = Column(Float, nullable=True)  # Total processing time
    cache_hit = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    
    # Cost tracking
    total_cost = Column(Float, default=0.0)
    estimated_cost = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Client info
    client_ip = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="search_requests")
    content_sources = relationship("ContentSource", back_populates="search_request", cascade="all, delete-orphan")
    cost_records = relationship("CostRecord", back_populates="search_request", cascade="all, delete-orphan")
    api_usage_records = relationship("ApiUsage", back_populates="search_request", cascade="all, delete-orphan")
    
    # Indexes and constraints
    __table_args__ = (
        Index('ix_search_requests_created_at', 'created_at'),
        Index('ix_search_requests_status', 'status'),
        Index('ix_search_requests_user_created', 'user_id', 'created_at'),
        Index('ix_search_requests_cache_hit', 'cache_hit'),
        CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='check_confidence_score'),
        CheckConstraint('processing_time >= 0', name='check_processing_time'),
        CheckConstraint('total_cost >= 0', name='check_total_cost'),
    )

class ContentSource(Base):
    """Model for tracking fetched content sources"""
    __tablename__ = "content_sources"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_request_id = Column(UUID(as_uuid=True), ForeignKey("search_requests.id"), nullable=False)
    
    # Source information
    url = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    word_count = Column(Integer, default=0)
    
    # Metadata
    source_type = Column(String(20), default=ContentSourceType.GENERAL.value)
    extraction_method = Column(String(50), nullable=True)  # zenrows, beautifulsoup, etc.
    confidence_score = Column(Float, default=1.0)
    fetch_time = Column(Float, default=0.0)
    
    # Success/failure tracking
    fetch_successful = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    search_request = relationship("SearchRequest", back_populates="content_sources")
    
    # Indexes
    __table_args__ = (
        Index('ix_content_sources_search_request', 'search_request_id'),
        Index('ix_content_sources_url_hash', func.md5(url)),  # For deduplication
        Index('ix_content_sources_created_at', 'created_at'),
        CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='check_content_confidence_score'),
        CheckConstraint('word_count >= 0', name='check_word_count'),
        CheckConstraint('fetch_time >= 0', name='check_fetch_time'),
    )

class CostRecord(Base):
    """Model for detailed cost tracking"""
    __tablename__ = "cost_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_request_id = Column(UUID(as_uuid=True), ForeignKey("search_requests.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Cost breakdown
    brave_search_cost = Column(Float, default=0.0)
    bing_search_cost = Column(Float, default=0.0)
    bing_autosuggest_cost = Column(Float, default=0.0)
    zenrows_cost = Column(Float, default=0.0)
    llm_cost = Column(Float, default=0.0)  # Usually 0 for local Ollama
    total_cost = Column(Float, default=0.0)
    
    # Usage counts
    brave_searches = Column(Integer, default=0)
    bing_searches = Column(Integer, default=0)
    bing_autosuggest_calls = Column(Integer, default=0)
    zenrows_requests = Column(Integer, default=0)
    llm_tokens = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    search_request = relationship("SearchRequest", back_populates="cost_records")
    user = relationship("User", back_populates="cost_records")
    
    # Indexes
    __table_args__ = (
        Index('ix_cost_records_search_request', 'search_request_id'),
        Index('ix_cost_records_user_created', 'user_id', 'created_at'),
        Index('ix_cost_records_created_at', 'created_at'),
        CheckConstraint('total_cost >= 0', name='check_cost_records_total_cost'),
        CheckConstraint('brave_searches >= 0', name='check_brave_searches'),
        CheckConstraint('bing_searches >= 0', name='check_bing_searches'),
        CheckConstraint('zenrows_requests >= 0', name='check_zenrows_requests'),
    )

class ApiUsage(Base):
    """Model for tracking external API usage"""
    __tablename__ = "api_usage"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_request_id = Column(UUID(as_uuid=True), ForeignKey("search_requests.id"), nullable=True)
    
    # API information
    provider = Column(String(50), nullable=False)  # brave_search, bing_search, etc.
    endpoint = Column(String(255), nullable=True)
    method = Column(String(10), default="GET")
    
    # Request/Response data
    request_data = Column(JSON, nullable=True)  # Sanitized request data
    response_status = Column(Integer, nullable=True)
    response_time = Column(Float, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Cost tracking
    cost = Column(Float, default=0.0)
    tokens_used = Column(Integer, nullable=True)  # For LLM APIs
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    search_request = relationship("SearchRequest", back_populates="api_usage_records")
    
    # Indexes
    __table_args__ = (
        Index('ix_api_usage_provider_created', 'provider', 'created_at'),
        Index('ix_api_usage_search_request', 'search_request_id'),
        Index('ix_api_usage_created_at', 'created_at'),
        Index('ix_api_usage_success', 'success'),
        CheckConstraint('response_time >= 0', name='check_response_time'),
        CheckConstraint('cost >= 0', name='check_api_cost'),
    )

class CacheEntry(Base):
    """Model for tracking cache usage and analytics"""
    __tablename__ = "cache_entries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Cache key information
    cache_key = Column(String(255), nullable=False, index=True)
    cache_type = Column(String(50), nullable=False)  # response, enhancement, search, etc.
    
    # Cache data
    data_size = Column(Integer, nullable=True)  # Size in bytes
    ttl = Column(Integer, nullable=True)  # TTL in seconds
    hit_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('ix_cache_entries_type_created', 'cache_type', 'created_at'),
        Index('ix_cache_entries_expires_at', 'expires_at'),
        Index('ix_cache_entries_last_accessed', 'last_accessed'),
        UniqueConstraint('cache_key', 'cache_type', name='uq_cache_key_type'),
        CheckConstraint('hit_count >= 0', name='check_hit_count'),
        CheckConstraint('data_size >= 0', name='check_data_size'),
    )

class SystemMetric(Base):
    """Model for storing system metrics and monitoring data"""
    __tablename__ = "system_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Metric information
    metric_name = Column(String(100), nullable=False)
    metric_type = Column(String(50), nullable=False)  # counter, gauge, histogram
    value = Column(Float, nullable=False)
    
    # Labels/tags for metric
    labels = Column(JSON, nullable=True)  # Key-value pairs for metric labels
    
    # Optional additional data
    meta_data = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('ix_system_metrics_name_created', 'metric_name', 'created_at'),
        Index('ix_system_metrics_type', 'metric_type'),
        Index('ix_system_metrics_created_at', 'created_at'),
    )

class DailyStats(Base):
    """Model for daily aggregated statistics"""
    __tablename__ = "daily_stats"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Date
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Request statistics
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    cached_requests = Column(Integer, default=0)
    
    # Performance metrics
    avg_response_time = Column(Float, nullable=True)
    p95_response_time = Column(Float, nullable=True)
    avg_confidence_score = Column(Float, nullable=True)
    
    # Cost metrics
    total_cost = Column(Float, default=0.0)
    brave_search_cost = Column(Float, default=0.0)
    bing_search_cost = Column(Float, default=0.0)
    zenrows_cost = Column(Float, default=0.0)
    
    # Usage metrics
    total_api_calls = Column(Integer, default=0)
    total_content_fetched = Column(Integer, default=0)
    total_llm_tokens = Column(Integer, default=0)
    
    # Cache metrics
    cache_hit_rate = Column(Float, nullable=True)
    total_cache_hits = Column(Integer, default=0)
    total_cache_misses = Column(Integer, default=0)
    
    # Unique users
    unique_users = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('ix_daily_stats_date', 'date'),
        UniqueConstraint('date', name='uq_daily_stats_date'),
        CheckConstraint('total_requests >= 0', name='check_total_requests'),
        CheckConstraint('total_cost >= 0', name='check_daily_total_cost'),
        CheckConstraint('cache_hit_rate >= 0 AND cache_hit_rate <= 1', name='check_cache_hit_rate'),
    )

# Additional utility models
class ErrorLog(Base):
    """Model for logging application errors"""
    __tablename__ = "error_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Error information
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    
    # Context
    request_id = Column(String(255), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    endpoint = Column(String(255), nullable=True)
    
    # Additional data
    context_data = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('ix_error_logs_type_created', 'error_type', 'created_at'),
        Index('ix_error_logs_request_id', 'request_id'),
        Index('ix_error_logs_created_at', 'created_at'),
    )

class RateLimitRecord(Base):
    """Model for tracking rate limiting"""
    __tablename__ = "rate_limit_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Rate limit information
    identifier = Column(String(255), nullable=False, index=True)  # IP, user_id, etc.
    limit_type = Column(String(50), nullable=False)  # per_minute, per_hour, per_day
    requests_count = Column(Integer, default=1)
    limit_exceeded = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('ix_rate_limit_identifier_window', 'identifier', 'window_start', 'window_end'),
        Index('ix_rate_limit_created_at', 'created_at'),
        Index('ix_rate_limit_exceeded', 'limit_exceeded'),
        CheckConstraint('requests_count >= 0', name='check_requests_count'),
    )
