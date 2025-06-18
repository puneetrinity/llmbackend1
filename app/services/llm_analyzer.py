# app/services/llm_analyzer.py - FIXED VERSION
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
        self.is_available = None
        self.last_availability_check = 0
        self.availability_cache_duration = 60  # Cache availability for 60 seconds
        
    async def _get_session(self, force_new: bool = False):
        """Lazy initialization of HTTP session with option to force recreation"""
        if self.session is None or force_new:
            if self.session:
                await self.session.close()
            
            # Create session with proper connector settings
            connector = aiohttp.TCPConnector(
                limit=20,
                limit_per_host=10,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
                force_close=True,
                raise_for_status=False  # We'll handle status codes manually
            )
            
            # Different timeouts for different operations
            timeout = aiohttp.ClientTimeout(
                total=self.timeout,
                connect=10,
                sock_read=self.timeout - 10 if self.timeout > 10 else self.timeout
            )
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
            
        return self.session
    
    async def _check_ollama_availability(self, force_check: bool = False) -> bool:
        """Check if Ollama is available with proper caching and error handling"""
        current_time = time.time()
        
        # Use cached result if not expired and not forced
        if (not force_check and 
            self.is_available is not None and 
            (current_time - self.last_availability_check) < self.availability_cache_duration):
            logger.debug(f"Using cached availability status: {self.is_available}")
            return self.is_available
        
        logger.info(f"Checking Ollama availability at {self.ollama_host}")
        
        try:
            session = await self._get_session()
            
            # Step 1: Quick version check with short timeout
            try:
                async with session.get(
                    f"{self.ollama_host}/api/version",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        version_data = await response.json()
                        logger.info(f"Ollama version: {version_data.get('version', 'unknown')}")
                    else:
                        logger.error(f"Ollama version check failed: HTTP {response.status}")
                        error_text = await response.text()
                        logger.error(f"Version check error response: {error_text}")
                        self._update_availability_cache(False, current_time)
                        return False
            except asyncio.TimeoutError:
                logger.error("Ollama version check timed out")
                self._update_availability_cache(False, current_time)
                return False
            except Exception as e:
                logger.error(f"Ollama version check failed: {type(e).__name__}: {str(e)}")
                self._update_availability_cache(False, current_time)
                return False
            
            # Step 2: Check available models
            try:
                async with session.get(
                    f"{self.ollama_host}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [model.get('name', '') for model in data.get('models', [])]
                        logger.info(f"Available models: {models}")
                        
                        if self.model in models:
                            logger.info(f"✅ Model {self.model} is available")
                            self._update_availability_cache(True, current_time)
                            return True
                        else:
                            logger.warning(f"⚠️ Model {self.model} not found. Available: {models}")
                            # Still mark as available if Ollama is running, model might be pulled later
                            self._update_availability_cache(True, current_time)
                            return True
                    else:
                        logger.error(f"Failed to get model list: HTTP {response.status}")
                        error_text = await response.text()
                        logger.error(f"Model list error response: {error_text}")
                        self._update_availability_cache(False, current_time)
                        return False
            except asyncio.TimeoutError:
                logger.error("Model list check timed out")
                self._update_availability_cache(False, current_time)
                return False
            except Exception as e:
                logger.error(f"Model list check failed: {type(e).__name__}: {str(e)}")
                self._update_availability_cache(False, current_time)
                return False
                
        except Exception as e:
            logger.error(f"Ollama availability check failed: {type(e).__name__}: {str(e)}")
            self._update_availability_cache(False, current_time)
            return False
    
    def _update_availability_cache(self, is_available: bool, timestamp: float):
        """Update availability cache with timestamp"""
        self.is_available = is_available
        self.last_availability_check = timestamp
        logger.debug(f"Updated availability cache: {is_available}")
    
    async def analyze(self, query: str, content_data: List[ContentData], request_id: str) -> SearchResponse:
        """Analyze content using LLM with comprehensive error handling"""
        start_time = time.time()
        logger.info(f"Starting LLM analysis for request {request_id}")
        
        try:
            if not content_data:
                logger.warning("No content data provided for analysis")
                return self._create_fallback_response(query, "No content available for analysis")
            
            # Check if Ollama is available (with force check if this is a retry scenario)
            force_check = hasattr(self, '_last_failed_time') and (time.time() - self._last_failed_time) > 30
            if not await self._check_ollama_availability(force_check=force_check):
                logger.info("Ollama not available, using simple summary")
                return self._create_simple_summary_response(query, content_data)
            
            # Prepare content for analysis
            prepared_content = self._prepare_content_for_analysis(content_data)
            logger.debug(f"Prepared content length: {len(prepared_content)} characters")
            
            # Generate LLM prompt
            prompt = self._create_analysis_prompt(query, prepared_content)
            logger.debug(f"Generated prompt length: {len(prompt)} characters")
            
            # Call LLM with retries
            llm_response = await self._call_ollama_with_retry(prompt, request_id)
            
            if not llm_response:
                logger.warning("LLM analysis failed after retries, using simple summary")
                self._last_failed_time = time.time()
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
            
            logger.info(f"LLM analysis completed successfully in {processing_time:.2f}s for request {request_id}")
            return response
            
        except Exception as e:
            logger.error(f"LLM analysis error for request {request_id}: {type(e).__name__}: {str(e)}", exc_info=True)
            self._last_failed_time = time.time()
            return self._create_simple_summary_response(query, content_data)
    
    async def _call_ollama_with_retry(self, prompt: str, request_id: str, max_retries: int = 2) -> Optional[str]:
        """Call Ollama with comprehensive retry logic and error handling"""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Ollama call attempt {attempt + 1}/{max_retries + 1} for request {request_id}")
                
                # Force new session on retry after first failure
                if attempt > 0:
                    logger.info("Creating new session for retry")
                    await self._get_session(force_new=True)
                
                result = await self._call_ollama(prompt)
                
                if result and len(result.strip()) > 0:
                    logger.info(f"Ollama call successful on attempt {attempt + 1}")
                    return result
                else:
                    logger.warning(f"Ollama returned empty response on attempt {attempt + 1}")
                    last_exception = Exception("Empty response from Ollama")
                    
            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(f"Ollama call attempt {attempt + 1} timed out after {self.timeout}s")
                
            except aiohttp.ClientError as e:
                last_exception = e
                logger.warning(f"Ollama call attempt {attempt + 1} failed with client error: {type(e).__name__}: {str(e)}")
                
            except json.JSONDecodeError as e:
                last_exception = e
                logger.warning(f"Ollama call attempt {attempt + 1} failed with JSON decode error: {str(e)}")
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Ollama call attempt {attempt + 1} failed with unexpected error: {type(e).__name__}: {str(e)}")
            
            # Wait before retry with exponential backoff
            if attempt < max_retries:
                wait_time = min(2 ** attempt, 8)  # Max 8 seconds
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
        
        # All attempts failed
        logger.error(f"All {max_retries + 1} Ollama attempts failed for request {request_id}. Last error: {type(last_exception).__name__}: {str(last_exception)}")
        
        # Mark as unavailable and force check next time
        self._update_availability_cache(False, time.time())
        return None
    
    async def _call_ollama(self, prompt: str) -> str:
        """Make actual call to Ollama API with detailed error handling"""
        session = await self._get_session()
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                "top_k": 40,
                "top_p": 0.9,
                "stop": ["\n\nHuman:", "\n\nUser:", "Human:", "User:"]
            }
        }
        
        logger.debug(f"Calling Ollama API: {self.ollama_host}/api/generate")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            async with session.post(f"{self.ollama_host}/api/generate", json=payload) as response:
                
                logger.debug(f"Ollama response status: {response.status}")
                
                if response.status == 200:
                    try:
                        data = await response.json()
                        response_text = data.get("response", "").strip()
                        
                        if not response_text:
                            logger.warning("Received empty response from Ollama")
                            return ""
                            
                        logger.debug(f"Ollama response length: {len(response_text)} characters")
                        logger.debug(f"Ollama response preview: {response_text[:200]}...")
                        return response_text
                        
                    except json.JSONDecodeError as e:
                        error_text = await response.text()
                        logger.error(f"Failed to parse Ollama JSON response: {e}")
                        logger.error(f"Raw response: {error_text}")
                        raise LLMAnalysisException(f"Invalid JSON response from Ollama: {e}")
                        
                else:
                    error_text = await response.text()
                    logger.error(f"Ollama API error: HTTP {response.status}")
                    logger.error(f"Error response: {error_text}")
                    
                    if response.status == 404:
                        raise LLMAnalysisException(f"Model {self.model} not found on Ollama server")
                    elif response.status == 500:
                        raise LLMAnalysisException(f"Ollama server internal error: {error_text}")
                    else:
                        raise LLMAnalysisException(f"Ollama API error {response.status}: {error_text}")
                        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error calling Ollama: {type(e).__name__}: {str(e)}")
            raise
        except asyncio.TimeoutError as e:
            logger.error(f"Timeout calling Ollama after {self.timeout}s")
            raise
    
    def _create_simple_summary_response(self, query: str, content_data: List[ContentData]) -> SearchResponse:
        """Create a comprehensive fallback response when LLM is unavailable"""
        start_time = time.time()
        
        summary_parts = []
        sources = []
        
        for i, content in enumerate(content_data[:5]):  # Use top 5 sources
            try:
                source_summary = ""
                
                if hasattr(content, 'title') and content.title:
                    source_summary = f"**{content.title}**"
                
                if hasattr(content, 'content') and content.content:
                    # Extract key sentences
                    sentences = content.content.split('.')[:2]  # First 2 sentences
                    content_snippet = '. '.join(s.strip() for s in sentences if s.strip())
                    if content_snippet:
                        if source_summary:
                            source_summary += f": {content_snippet}..."
                        else:
                            source_summary = f"{content_snippet}..."
                
                if source_summary:
                    summary_parts.append(f"{i+1}. {source_summary}")
                
                if hasattr(content, 'url'):
                    sources.append(content.url)
                    
            except Exception as e:
                logger.warning(f"Error processing content {i}: {e}")
                continue
        
        if summary_parts:
            answer = f"Based on the search results for '{query}':\n\n"
            answer += "\n\n".join(summary_parts)
            answer += "\n\n*Note: This is a structured summary. Advanced AI analysis is temporarily unavailable.*"
        else:
            answer = f"I found search results for '{query}' but couldn't process the content. Please check the sources below for detailed information."
        
        processing_time = time.time() - start_time
        
        return SearchResponse(
            query=query,
            answer=answer,
            sources=sources,
            confidence=0.7,  # Moderate confidence for structured summary
            processing_time=processing_time,
            cached=False,
            cost_estimate=0.0,
            timestamp=datetime.utcnow()
        )
    
    def _create_fallback_response(self, query: str, reason: str) -> SearchResponse:
        """Create fallback response when analysis fails"""
        return SearchResponse(
            query=query,
            answer=f"I apologize, but I couldn't analyze the search results for '{query}'. Reason: {reason}. Please try again or contact support if the issue persists.",
            sources=[],
            confidence=0.1,
            processing_time=0.0,
            cached=False,
            cost_estimate=0.0,
            timestamp=datetime.utcnow()
        )
    
    async def health_check(self) -> str:
        """Check health of LLM service with detailed status"""
        try:
            if await self._check_ollama_availability(force_check=True):
                return "healthy"
            else:
                return "unhealthy - ollama not available"
        except Exception as e:
            logger.error(f"LLM health check failed: {type(e).__name__}: {str(e)}")
            return f"unhealthy - {type(e).__name__}: {str(e)}"
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    # Helper methods (keeping your existing implementations)
    def _prepare_content_for_analysis(self, content_data: List[ContentData]) -> str:
        """Prepare content for LLM analysis"""
        content_parts = []
        for i, content in enumerate(content_data[:5]):  # Limit to first 5 sources
            if hasattr(content, 'content') and content.content:
                # Truncate content to avoid token limits
                truncated = content.content[:1000]
                content_parts.append(f"Source {i+1}: {truncated}")
        
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
