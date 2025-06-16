# tests/database/test_database_logger.py
import pytest
from app.services.database_logger import DatabaseLogger
from app.models.responses import SearchResponse
from app.models.internal import ContentData, ContentSource
from app.database.models import RequestStatus

class TestDatabaseLogger:
    """Test DatabaseLogger service"""
    
    async def test_log_search_request(self, test_session):
        """Test logging a search request"""
        db_logger = DatabaseLogger(test_session)
        
        search_id = await db_logger.log_search_request(
            request_id="logger_test_123",
            user_identifier="logger_test@example.com",
            original_query="logger test query",
            max_results=5
        )
        
        assert search_id is not None
        
        # Verify the request was logged
        from app.database.repositories import SearchRequestRepository
        search_repo = SearchRequestRepository(test_session)
        
        request = await search_repo.get_search_request_by_id("logger_test_123")
        assert request is not None
        assert request.original_query == "logger test query"
    
    async def test_update_search_response(self, test_session, sample_search_request):
        """Test updating search response"""
        db_logger = DatabaseLogger(test_session)
        
        # Create a mock response
        response = SearchResponse(
            query="test query",
            answer="test answer",
            sources=["https://example.com"],
            confidence=0.85,
            processing_time=3.2,
            cached=False
        )
        
        await db_logger.update_search_response(
            request_id=sample_search_request.request_id,
            response=response,
            status=RequestStatus.COMPLETED
        )
        
        await test_session.commit()
        
        # Verify the update
        from app.database.repositories import SearchRequestRepository
        search_repo = SearchRequestRepository(test_session)
        
        updated_request = await search_repo.get_search_request_by_id(sample_search_request.request_id)
        assert updated_request.status == RequestStatus.COMPLETED.value
        assert updated_request.response_answer == "test answer"
        assert updated_request.confidence_score == 0.85
    
    async def test_log_content_sources(self, test_session, sample_search_request):
        """Test logging content sources"""
        db_logger = DatabaseLogger(test_session)
        
        # Create mock content data
        content_data = [
            ContentData(
                url="https://example1.com",
                title="Example 1",
                content="Content 1",
                word_count=10,
                source_type=ContentSource.GENERAL,
                extraction_method="test",
                confidence_score=0.9,
                fetch_time=1.2
            ),
            ContentData(
                url="https://example2.com", 
                title="Example 2",
                content="Content 2",
                word_count=15,
                source_type=ContentSource.NEWS,
                extraction_method="test",
                confidence_score=0.8,
                fetch_time=1.5
            )
        ]
        
        await db_logger.log_content_sources(sample_search_request.id, content_data)
        await test_session.commit()
        
        # Verify content sources were logged
        from app.database.repositories import ContentSourceRepository
        content_repo = ContentSourceRepository(test_session)
        
        sources = await content_repo.get_sources_by_request(sample_search_request.id)
        assert len(sources) == 2
        assert sources[0].url in ["https://example1.com", "https://example2.com"]
