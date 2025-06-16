# app/services/llm_analyzer.py
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
        
    async def _get_session(self):
        """Lazy initialization of HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self.session
    
    async def analyze(self, query: str, content_data: List[ContentData], request_id: str) -> SearchResponse:
        """
        Analyze content using LLM to generate intelligent response
        """
        start_time = time.time()
        
        try:
            if not content_data:
                return self._create_fallback_response(query, "No content available for analysis")
            
            # Prepare content for analysis
            prepared_content = self._prepare_content_for_analysis(content_data)
            
            # Generate LLM prompt
            prompt = self._create_analysis_prompt(query, prepared_content)
            
            # Call LLM
            llm_response = await self._call_ollama(prompt)
            
            if not llm_response:
                return self._create_fallback_response(query, "LLM analysis failed")
            
            # Parse LLM response
            analysis_result = self._parse_llm_response(llm_response)
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(analysis_result, content_data)
            
            # Extract sources
            sources = [content.url for content in content_data]
            
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
            logger.error(f"LLM analysis error: {e}")
            return self._create_fallback_response(query, f"Analysis error: {str(e)}")
    
    def _prepare_content_for_analysis(self, content_data: List[ContentData]) -> str:
        """Prepare and combine content for LLM analysis"""
        try:
            prepared_sections = []
            
            for i, content in enumerate(content_data[:5]):  # Limit to top 5 sources
                # Truncate individual content pieces
                max_content_per_source = 800  # Characters per source
                truncated_content = content.content[:max_content_per_source]
                if len(content.content) > max_content_per_source:
                    truncated_content += "..."
                
                section = f"Source {i+1} ({content.source_type.value}):\nTitle: {content.title}\nURL: {content.url}\nContent: {truncated_content}\n"
                prepared_sections.append(section)
            
            return "\n---\n".join(prepared_sections)
            
        except Exception as e:
            logger.error(f"Error preparing content for analysis: {e}")
            return "Error processing content for analysis"
    
    def _create_analysis_prompt(self, query: str, content: str) -> str:
        """Create a structured prompt for the LLM"""
        prompt = f"""You are an AI assistant that provides accurate, helpful responses based on web search results. 

USER QUERY: {query}

SEARCH RESULTS:
{content}

INSTRUCTIONS:
1. Provide a comprehensive, accurate answer to the user's query based on the search results above
2. Synthesize information from multiple sources when possible
3. Be factual and cite information appropriately
4. If the search results don't fully answer the query, acknowledge what's missing
5. Keep your response focused and relevant to the specific query
6. Aim for 2-4 paragraphs unless a shorter or longer response is more appropriate
7. Use clear, accessible language

RESPONSE:"""
        
        return prompt
    
    async def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call Ollama API for LLM inference"""
        try:
            session = await self._get_session()
            
            url = f"{self.ollama_host}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                    "top_p": 0.9,
                    "top_k": 40
                }
            }
            
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    llm_response = data.get("response", "").strip()
                    
                    if llm_response:
                        logger.info(f"LLM response generated ({len(llm_response)} chars)")
                        return llm_response
                    else:
                        logger.warning("LLM returned empty response")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"Ollama API error {response.status}: {error_text}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error("LLM request timed out")
            return None
        except Exception as e:
            logger.error(f"Ollama API call error: {e}")
            return None
    
    def _parse_llm_response(self, response: str) -> str:
        """Parse and clean LLM response"""
        try:
            # Remove any system messages or artifacts
            cleaned_response = response.strip()
            
            # Remove common LLM artifacts
            artifacts_to_remove = [
                "RESPONSE:",
                "Answer:",
                "Based on the search results:",
                "According to the provided information:"
            ]
            
            for artifact in artifacts_to_remove:
                if cleaned_response.startswith(artifact):
                    cleaned_response = cleaned_response[len(artifact):].strip()
            
            # Ensure reasonable length
            if len(cleaned_response) < 50:
                return "The analysis generated a response that was too short to be meaningful."
            
            if len(cleaned_response) > 2000:  # Truncate very long responses
                cleaned_response = cleaned_response[:2000] + "..."
            
            return cleaned_response
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return response  # Return original if parsing fails
    
    def _calculate_confidence_score(self, analysis: str, content_data: List[ContentData]) -> float:
        """Calculate confidence score for the analysis"""
        try:
            score = 0.5  # Base score
            
            # Content quality factor
            avg_content_confidence = sum(content.confidence_score for content in content_data) / len(content_data)
            score += avg_content_confidence * 0.3
            
            # Response length factor (reasonable length indicates better analysis)
            response_length = len(analysis.split())
            if 50 <= response_length <= 300:
                score += 0.2
            elif response_length > 20:
                score += 0.1
            
            # Source diversity factor
            unique_domains = len(set(content.url.split('/')[2] for content in content_data if '/' in content.url))
            if unique_domains > 1:
                score += 0.1
            
            # Penalize if response seems generic or error-like
            generic_indicators = ['error', 'unable to', 'cannot provide', 'insufficient information']
            if any(indicator in analysis.lower() for indicator in generic_indicators):
                score -= 0.2
            
            return min(max(score, 0.0), 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating confidence score: {e}")
            return 0.5
    
    def _estimate_cost(self, prompt: str, response: str) -> float:
        """Estimate the cost of the LLM call (Ollama is free, but good to track)"""
        try:
            # Ollama is free to run locally, but we can estimate computational cost
            prompt_tokens = len(prompt.split()) * 1.3  # Rough token estimation
            response_tokens = len(response.split()) * 1.3
            total_tokens = prompt_tokens + response_tokens
            
            # Estimated cost per 1k tokens (fictional cost for tracking)
            cost_per_1k_tokens = 0.001  # $0.001 per 1k tokens
            estimated_cost = (total_tokens / 1000) * cost_per_1k_tokens
            
            return round(estimated_cost, 6)
            
        except Exception as e:
            logger.warning(f"Error estimating cost: {e}")
            return 0.0
    
    def _create_fallback_response(self, query: str, error_message: str) -> SearchResponse:
        """Create a fallback response when analysis fails"""
        return SearchResponse(
            query=query,
            answer=f"I apologize, but I encountered an issue while analyzing the search results for your query. {error_message}. Please try rephrasing your question or try again later.",
            sources=[],
            confidence=0.1,
            processing_time=0.0,
            cached=False,
            cost_estimate=0.0,
            timestamp=datetime.utcnow()
        )
    
    async def health_check(self) -> str:
        """Check LLM service health"""
        try:
            # Test with a simple prompt
            test_prompt = "Hello, please respond with 'Health check successful' if you can process this message."
            
            response = await self._call_ollama(test_prompt)
            
            if response and "successful" in response.lower():
                return "healthy"
            elif response:
                return "degraded"  # LLM is responding but not correctly
            else:
                return "unhealthy"
                
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return "unhealthy"
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
