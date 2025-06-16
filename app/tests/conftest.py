# tests/conftest.py
import pytest
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
import tempfile

from app.database.connection import Base
from app.database.models import *  # Import all models
from app.config.settings import settings

# Test database URL (use SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def test_session(test_engine):
    """Create test database session"""
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def sample_user(test_session):
    """Create a sample user for testing"""
    from app.database.repositories import UserRepository
    
    user_repo = UserRepository(test_session)
    user = await user_repo.create_user(
        user_identifier="test@example.com",
        user_type="test",
        api_key="test_api_key"
    )
    await test_session.commit()
    return user

@pytest.fixture
async def sample_search_request(test_session, sample_user):
    """Create a sample search request for testing"""
    from app.database.repositories import SearchRequestRepository
    
    search_repo = SearchRequestRepository(test_session)
    request = await search_repo.create_search_request(
        request_id="test_request_123",
        user_id=sample_user.id,
        original_query="test query",
        max_results=5
    )
    await test_session.commit()
    return request

# tests/database/test_models.py
import pytest
from datetime import datetime
from app.database.models import User, SearchRequest, ContentSource, CostRecord

class TestUserModel:
    """Test User model"""
    
    async def test_user_creation(self, test_session):
        """Test creating a user"""
        user = User(
            user_identifier="test@example.com",
            user_type="authenticated",
            api_key="test_key_123"
        )
        
        test_session.add(user)
        await test_session.commit()
        
        assert user.id is not None
        assert user.user_identifier == "test@example.com"
        assert user.user_type == "authenticated"
        assert user.is_active is True
        assert user.created_at is not None
    
    async def test_user_constraints(self, test_session):
        """Test user model constraints"""
        # Test unique constraint on user_identifier
        user1 = User(user_identifier="duplicate@example.com")
        user2 = User(user_identifier="duplicate@example.com")
        
        test_session.add(user1)
        await test_session.commit()
        
        test_session.add(user2)
        with pytest.raises(Exception):  # Should raise integrity error
            await test_session.commit()

class TestSearchRequestModel:
    """Test SearchRequest model"""
    
    async def test_search_request_creation(self, test_session, sample_user):
        """Test creating a search request"""
        request = SearchRequest(
            request_id="test_123",
            user_id=sample_user.id,
            original_query="test query",
            max_results=5,
            status="pending"
        )
        
        test_session.add(request)
        await test_session.commit()
        
        assert request.id is not None
        assert request.request_id == "test_123"
        assert request.user_id == sample_user.id
        assert request.status == "pending"
    
    async def test_search_request_relationships(self, test_session, sample_search_request):
        """Test search request relationships"""
        # Test user relationship
        assert sample_search_request.user is not None
        assert sample_search_request.user.user_identifier == "test@example.com"
