# tests/database/test_analytics_service.py
import pytest
from datetime import datetime, timedelta
from app.services.analytics_service import AnalyticsService

class TestAnalyticsService:
    """Test AnalyticsService"""
    
    async def test_get_dashboard_metrics(self, test_session):
        """Test getting dashboard metrics"""
        analytics = AnalyticsService(test_session)
        
        # This will return empty data for a fresh test database
        metrics = await analytics.get_dashboard_metrics(days=7)
        
        assert isinstance(metrics, dict)
        assert "period_days" in metrics
        assert metrics["period_days"] == 7
    
    async def test_get_performance_metrics(self, test_session, sample_search_request):
        """Test getting performance metrics"""
        analytics = AnalyticsService(test_session)
        
        # Update the sample request with some performance data
        from app.database.repositories import SearchRequestRepository
        search_repo = SearchRequestRepository(test_session)
        
        await search_repo.update_search_request(
            request_id=sample_search_request.request_id,
            status="completed",
            processing_time=4.5,
            confidence_score=0.8
        )
        await test_session.commit()
        
        metrics = await analytics.get_performance_metrics(hours=24)
        
        assert isinstance(metrics, dict)
        assert "period_hours" in metrics
        assert "total_requests" in metrics
