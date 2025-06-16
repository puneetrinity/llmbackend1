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

