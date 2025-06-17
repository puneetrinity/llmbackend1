# app/services/database_logger.py
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import update, func
from app.database.models import SearchRequest, RequestStatus

logger = logging.getLogger(__name__)

class DatabaseLogger:
    def __init__(self, session=None):
        self.session = session
        self.enabled = session is not None

    async def log_search_request(
        self, 
        request_id: str, 
        user_identifier: Optional[str] = None, 
        query: str = "", 
        max_results: int = 8, 
        **kwargs
    ) -> Optional[UUID]:
        logger.debug(f"📝 Search request: {request_id} - {query[:50]}...")
        return None

    async def update_search_request_status(
        self, 
        search_request_id: UUID, 
        status: str, 
        processing_time: Optional[float] = None, 
        error_message: Optional[str] = None
    ):
        logger.debug(f"📝 Status update: {status}")

    async def log_content_sources(
        self, 
        search_request_id: UUID, 
        content_sources: List[Dict[str, Any]]
    ):
        logger.debug(f"📝 {len(content_sources)} content sources logged")

    async def log_error(
        self, 
        request_id: str, 
        error_type: str, 
        error_message: str, 
        context_data: Optional[Dict[str, Any]] = None
    ):
        logger.error(f"📝 Error: {error_type} - {error_message}")

    async def get_user_id(self, user_identifier: str) -> Optional[UUID]:
        return None

    async def health_check(self) -> str:
        return "healthy"

    # ✅ New method added
    async def mark_request_failed(
        self, 
        request_id: str, 
        error_message: str, 
        error_type: str = "unknown"
    ):
        """Mark a request as failed in the database"""
        if not self.enabled or self.session is None:
            logger.warning(f"Skipping DB failure log (session unavailable): {error_message}")
            return

        try:
            query = (
                update(SearchRequest)
                .where(SearchRequest.id == request_id)
                .values(
                    status=RequestStatus.FAILED,
                    error_message=error_message,
                    completed_at=func.now()
                )
            )
            await self.session.execute(query)
            await self.session.commit()
            logger.info(f"✅ Request {request_id} marked as failed")
        except Exception as e:
            logger.error(f"❌ Failed to mark request as failed: {e}")
            await self.session.rollback()
