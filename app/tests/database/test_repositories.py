# tests/database/test_repositories.py
import pytest
from datetime import datetime, timedelta
from app.database.repositories import (
    UserRepository, SearchRequestRepository, ContentSourceRepository,
    CostRecordRepository, ApiUsageRepository
)
from app.database.models import RequestStatus


class TestUserRepository:
    """Test UserRepository"""

    async def test_create_user(self, test_session):
        """Test creating a user via repository"""
        user_repo = UserRepository(test_session)

        user = await user_repo.create_user(
            user_identifier="repo_test@example.com",
            user_type="api_user",
            api_key="repo_test_key"
        )

        assert user.user_identifier == "repo_test@example.com"
        assert user.user_type == "api_user"
        assert user.api_key == "repo_test_key"

    async def test_get_user_by_identifier(self, test_session, sample_user):
        """Test getting user by identifier"""
        user_repo = UserRepository(test_session)

        found_user = await user_repo.get_user_by_identifier("test@example.com")

        assert found_user is not None
        assert found_user.id == sample_user.id
        assert found_user.user_identifier == "test@example.com"

    async def test_get_user_by_api_key(self, test_session, sample_user):
        """Test getting user by API key"""
        user_repo = UserRepository(test_session)

        found_user = await user_repo.get_user_by_api_key("test_api_key")

        assert found_user is not None
        assert found_user.id == sample_user.id


class TestSearchRequestRepository:
    """Test SearchRequestRepository"""

    async def test_create_search_request(self, test_session, sample_user):
        """Test creating search request via repository"""
        search_repo = SearchRequestRepository(test_session)

        request = await search_repo.create_search_request(
            request_id="repo_test_456",
            user_id=sample_user.id,
            original_query="repository test query",
            max_results=8
        )

        assert request.request_id == "repo_test_456"
        assert request.user_id == sample_user.id
        assert request.original_query == "repository test query"
        assert request.max_results == 8

    async def test_update_search_request(self, test_session, sample_search_request):
        """Test updating search request"""
        search_repo = SearchRequestRepository(test_session)

        updated_request = await search_repo.update_search_request(
            request_id=sample_search_request.request_id,
            status="completed",
            response_answer="Test answer",
            confidence_score=0.85,
            processing_time=2.5
        )

        assert updated_request.status == "completed"
        assert updated_request.response_answer == "Test answer"
        assert updated_request.confidence_score == 0.85
        assert updated_request.processing_time == 2.5

    async def test_get_user_requests(self, test_session, sample_user):
        """Test getting user's requests"""
        search_repo = SearchRequestRepository(test_session)

        # Create multiple requests for the user
        for i in range(3):
            await search_repo.create_search_request(
                request_id=f"user_req_{i}",
                user_id=sample_user.id,
                original_query=f"query {i}",
                max_results=5
            )

        await test_session.commit()

        requests = await search_repo.get_user_requests(sample_user.id, limit=10)

        assert len(requests) >= 3  # At least the 3 we created (plus any from fixtures)


class TestContentSourceRepository:
    """Test ContentSourceRepository"""

    async def test_create_content_source(self, test_session, sample_search_request):
        """Test creating content source"""
        content_repo = ContentSourceRepository(test_session)

        content = await content_repo.create_content_source(
            search_request_id=sample_search_request.id,
            url="https://example.com/test",
            title="Test Article",
            content="This is test content",
            word_count=4,
            source_type="general",
            confidence_score=0.9
        )

        assert content.url == "https://example.com/test"
        assert content.title == "Test Article"
        assert content.word_count == 4
        assert content.confidence_score == 0.9

    async def test_get_sources_by_request(self, test_session, sample_search_request):
        """Test getting content sources for a request"""
        content_repo = ContentSourceRepository(test_session)

        # Create multiple content sources
        for i in range(3):
            await content_repo.create_content_source(
                search_request_id=sample_search_request.id,
                url=f"https://example.com/test_{i}",
                title=f"Test Article {i}",
                content=f"Test content {i}",
                confidence_score=0.8 + (i * 0.05)  # Varying confidence scores
            )

        await test_session.commit()

        sources = await content_repo.get_sources_by_request(sample_search_request.id)

        assert len(sources) == 3
        # Should be ordered by confidence score descending
        assert sources[0].confidence_score >= sources[1].confidence_score


class TestCostRecordRepository:
    """Test CostRecordRepository"""

    async def test_create_cost_record(self, test_session, sample_search_request):
        """Test creating cost record"""
        cost_repo = CostRecordRepository(test_session)

        cost_record = await cost_repo.create_cost_record(
            search_request_id=sample_search_request.id,
            service_name="serpapi",
            operation_type="search",
            cost_usd=0.005,
            details={"query_count": 1, "api_type": "google"}
        )

        assert cost_record.service_name == "serpapi"
        assert cost_record.operation_type == "search"
        assert cost_record.cost_usd == 0.005
        assert cost_record.details["query_count"] == 1

    async def test_get_costs_by_date_range(self, test_session, sample_search_request):
        """Test getting costs by date range"""
        cost_repo = CostRecordRepository(test_session)

        # Create test cost records
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow() + timedelta(days=1)

        await cost_repo.create_cost_record(
            search_request_id=sample_search_request.id,
            service_name="serpapi",
            operation_type="search",
            cost_usd=0.01
        )

        await test_session.commit()

        costs = await cost_repo.get_costs_by_date_range(start_date, end_date)

        assert len(costs) >= 1
        assert any(cost.service_name == "serpapi" for cost in costs)


class TestApiUsageRepository:
    """Test ApiUsageRepository"""

    async def test_create_api_usage(self, test_session, sample_search_request):
        """Test creating API usage record"""
        api_repo = ApiUsageRepository(test_session)

        usage = await api_repo.create_api_usage(
            search_request_id=sample_search_request.id,
            api_name="serpapi",
            endpoint="google_search",
            request_count=1,
            response_time=1.25,
            success=True
        )

        assert usage.api_name == "serpapi"
        assert usage.endpoint == "google_search"
        assert usage.request_count == 1
        assert usage.response_time == 1.25
        assert usage.success is True

    async def test_get_usage_stats(self, test_session, sample_search_request):
        """Test getting API usage statistics"""
        api_repo = ApiUsageRepository(test_session)

        # Create test usage records
        for i in range(3):
            await api_repo.create_api_usage(
                search_request_id=sample_search_request.id,
                api_name="serpapi",
                endpoint="google_search",
                request_count=1,
                response_time=1.0 + (i * 0.1),
                success=True
            )

        await test_session.commit()

        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow() + timedelta(days=1)

        stats = await api_repo.get_usage_stats("serpapi", start_date, end_date)

        assert stats is not None
        assert stats.total_requests >= 3
        assert stats.average_response_time > 0
