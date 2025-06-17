# app/services/llm_analyzer.py - Railway-compatible version
import asyncio
import aiohttp
import logging
import time
import json
from typing import List, Dict, Optional
from datetime import datetime

from app.config.settings import settings
from app.models.internal import ContentData
from app.models.responses import SearchResponse
from app.core.exceptions import LLMAnalysisException

logger = logging.getLogger(__name__)

class LLMAnalysisService:
    def __init__(self):
        self.ollama_host = settings.OLLAMA_HOST
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        self.timeout = settings.LLM_TIMEOUT
        self.session = None
        self.is_available = None  # Cache availability status
        
    async def _get_session(self):
        """Lazy initialization of HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self.session
    
    async def _check_ollama_availability(self) -> bool:
        """Check if Ollama is available and has the required model"""
        if self.is_available is not None:
            return self.is_available  # Use cached result
        
        try:
            session = await self._get_session()
            
            # Check if Ollama is running
            async with session.get(f"{self.ollama_host}/api/version") as response:
                if response.status != 200:
                    logger.warning(f"Ollama not responding: HTTP {response.status}")
                    self.is_available = False
                    return False
            
            # Check if model is available
            async with session.get(f"{self.ollama_host}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model.get('name', '') for model in data.get('models', [])]
                    
                    if self.model in models:
                        logger.info(f"✅ Ollama is available with model {self.model}")
                        self.is_available = True
                        return True
                    else:
                        logger.warning(f"⚠️ Model {self.model} not found. Available models: {models}")
                        self.is_available = False
                        return False
                else:
                    logger.warning(f"Failed to get model list: HTTP {response.status}")
                    self.is_available = False
                    return False
                    
        except Exception as e:
            logger.warning(f"Ollama availability check failed: {e}")
            self.is_available = False
            return False
    
    async def analyze(self, query: str, content_data: List[ContentData], request_id: str) -> SearchResponse:
        """
        Analyze content using LLM with Railway-compatible fallbacks
        """
        start_time = time.time()
        
        try:
            if not content_data:
                return self._create_fallback_response(query, "No content available for analysis")
            
            # Check if Ollama is available
            if not await self._check_ollama_availability():
                logger.info("Ollama not available, using simple summary")
                return self._create_simple_summary_response(query, content_data)
            
            # Prepare content for analysis
            prepared_content = self._prepare_content_for_analysis(content_data)
            
            # Generate LLM prompt
            prompt = self._create_analysis_prompt(query, prepared_content)
            
            # Call LLM with retries
            llm_response = await self._call_ollama_with_retry(prompt)
            
            if not llm_response:
                logger.warning("LLM analysis failed, using simple summary")
                return self._create_simple_summary_response(query, content_data)
            
            # Parse LLM response
            analysis_result = self._parse_llm_response(llm_response)
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(analysis_result, content_data)
            
            # Extract sources
            sources = [content.url for content in content_data if hasattr(content, 'url')]
            
            processing_time = time.time() - start_time
            
            # Create final response
            response = SearchResponse(
                query=query,
                answer=analysis_result,
                sources=sources,
                confidence=confidence,
                processing_time=processing_time,
                cached=False,
                cost_estimate=self._estimate_cost(prompt, llm_response),
                timestamp=datetime.utcnow()
            )
            
            logger.info(f"LLM analysis completed in {processing_time:.2f}s for query: {query[:30]}...")
            return response
            
        except Exception as e:
            logger.error(f"LLM analysis error: {str(e)}")
            return self._create_simple_summary_response(query, content_data)
    
    async def _call_ollama_with_retry(self, prompt: str, max_retries: int = 2) -> Optional[str]:
        """Call Ollama with retry logic for Railway deployment"""
        for attempt in range(max_retries + 1):
            try:
                return await self._call_ollama(prompt)
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Ollama call attempt {attempt + 1} failed: {e}, retrying...")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All Ollama call attempts failed: {e}")
                    return None
    
    async def _call_ollama(self, prompt: str) -> str:
        """Make actual call to Ollama API"""
        session = await self._get_session()
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens
            }
        }
        
        async with session.post(f"{self.ollama_host}/api/generate", json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("response", "")
            else:
                error_text = await response.text()
                raise LLMAnalysisException(f"Ollama API error: {response.status} - {error_text}")
    
    def _create_simple_summary_response(self, query: str, content_data: List[ContentData]) -> SearchResponse:
        """Create a simple summary response when LLM is not available"""
        start_time = time.time()
        
        # Create a basic summary from the content
        summary_parts = []
        sources = []
        
        for i, content in enumerate(content_data[:3]):  # Use first 3 sources
            if hasattr(content, 'title') and content.title:
                summary_parts.append(f"• {content.title}")
            elif hasattr(content, 'content') and content.content:
                # Take first sentence of content
                first_sentence = content.content.split('.')[0][:200]
                summary_parts.append(f"• {first_sentence}...")
            
            if hasattr(content, 'url'):
                sources.append(content.url)
        
        if summary_parts:
            answer = f"Based on the search results:\n\n" + "\n".join(summary_parts)
            answer += f"\n\nThis summary is based on {len(content_data)} sources. For detailed analysis, please ensure the LLM service is available."
        else:
            answer = "Search results were found but could not be processed. Please try again or contact support."
        
        processing_time = time.time() - start_time
        
        return SearchResponse(
            query=query,
            answer=answer,
            sources=sources,
            confidence=0.6,  # Lower confidence for simple summary
            processing_time=processing_time,
            cached=False,
            cost_estimate=0.0,  # No LLM cost
            timestamp=datetime.utcnow()
        )
    
    def _create_fallback_response(self, query: str, reason: str) -> SearchResponse:
        """Create fallback response when analysis fails"""
        return SearchResponse(
            query=query,
            answer=f"Sorry, I couldn't analyze the search results. Reason: {reason}",
            sources=[],
            confidence=0.1,
            processing_time=0.0,
            cached=False,
            cost_estimate=0.0,
            timestamp=datetime.utcnow()
        )
    
    async def health_check(self) -> str:
        """Check health of LLM service"""
        try:
            if await self._check_ollama_availability():
                return "healthy"
            else:
                return "unhealthy - ollama not available"
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return "unhealthy"
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
    
    # Helper methods (implement these based on your existing code)
    def _prepare_content_for_analysis(self, content_data: List[ContentData]) -> str:
        """Prepare content for LLM analysis"""
        content_parts = []
        for content in content_data[:5]:  # Limit to first 5 sources
            if hasattr(content, 'content') and content.content:
                # Truncate content to avoid token limits
                truncated = content.content[:1000]
                content_parts.append(f"Source: {truncated}")
        
        return "\n\n".join(content_parts)
    
    def _create_analysis_prompt(self, query: str, content: str) -> str:
        """Create prompt for LLM analysis"""
        return f"""Based on the following search results, provide a comprehensive answer to the query: "{query}"

Search Results:
{content}

Please provide a clear, accurate, and well-structured answer based on the search results. If the search results don't contain enough information to answer the query, mention that limitation.

Answer:"""
    
    def _parse_llm_response(self, response: str) -> str:
        """Parse and clean LLM response"""
        return response.strip()
    
    def _calculate_confidence_score(self, answer: str, content_data: List[ContentData]) -> float:
        """Calculate confidence score based on answer and content quality"""
        base_score = 0.8
        
        # Adjust based on content quantity
        if len(content_data) >= 3:
            base_score += 0.1
        elif len(content_data) == 1:
            base_score -= 0.2
        
        # Adjust based on answer length (longer = more comprehensive)
        if len(answer) > 200:
            base_score += 0.1
        elif len(answer) < 50:
            base_score -= 0.2
        
        return min(max(base_score, 0.1), 1.0)
    
    def _estimate_cost(self, prompt: str, response: str) -> float:
        """Estimate cost based on token usage"""
        # Rough estimation: 4 characters = 1 token
        total_chars = len(prompt) + len(response)
        estimated_tokens = total_chars / 4
        
        # Assume $0.0001 per 1000 tokens for local LLM
        return (estimated_tokens / 1000) * 0.0001
