# app/services/query_enhancer.py
import asyncio
import aiohttp
import logging
import re
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import quote

from app.config.settings import settings
from app.services.cache_service import CacheService
from app.models.internal import QueryEnhancement
from app.core.exceptions import QueryEnhancementException

logger = logging.getLogger(__name__)

@dataclass
class EnhancementStrategy:
    name: str
    weight: float
    enabled: bool = True

class QueryEnhancementService:
    def __init__(self):
        self.cache = CacheService()
        self.strategies = [
            EnhancementStrategy("google_autocomplete", 0.4),  # Replaced bing_autosuggest
            EnhancementStrategy("semantic_expansion", 0.3),
            EnhancementStrategy("domain_specific", 0.2),
            EnhancementStrategy("temporal_aware", 0.1)
        ]
        self.session = None
        
    async def _get_session(self):
        """Lazy initialization of HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5.0)
            )
        return self.session
        
    async def enhance(self, query: str) -> List[str]:
        """
        Enhance a query using multiple strategies
        Returns list of enhanced queries including original
        """
        start_time = time.time()
        
        # Check cache first
        cache_key = f"enhancement:{hash(query)}"
        cached = await self.cache.get(cache_key, "enhancement")
        if cached and isinstance(cached, dict):
            logger.info(f"Cache hit for query enhancement: {query[:30]}...")
            return cached.get("enhanced_queries", [query])
            
        enhanced_queries = [query]  # Always include original
        
        try:
            # Run enhancement strategies in parallel
            tasks = []
            
            if self._is_strategy_enabled("google_autocomplete"):
                tasks.append(self._google_autocomplete(query))
                
            if self._is_strategy_enabled("semantic_expansion"):
                tasks.append(self._semantic_expansion(query))
                
            if self._is_strategy_enabled("domain_specific"):
                tasks.append(self._domain_specific_enhancement(query))
                
            if self._is_strategy_enabled("temporal_aware"):
                tasks.append(self._temporal_aware_enhancement(query))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Collect all enhancements
                for result in results:
                    if isinstance(result, list):
                        enhanced_queries.extend(result)
                    elif isinstance(result, Exception):
                        logger.warning(f"Enhancement strategy failed: {result}")
            
            # Remove duplicates while preserving order
            enhanced_queries = list(dict.fromkeys(enhanced_queries))
            
            # Limit to max 5 queries for performance
            enhanced_queries = enhanced_queries[:5]
            
            # Cache result
            processing_time = time.time() - start_time
            enhancement_data = {
                "original_query": query,
                "enhanced_queries": enhanced_queries,
                "enhancement_method": "multi_strategy",
                "processing_time": processing_time
            }
            
            await self.cache.set(cache_key, enhancement_data, namespace="enhancement")
            
            logger.info(f"Enhanced query '{query}' -> {len(enhanced_queries)} variations in {processing_time:.2f}s")
            return enhanced_queries
            
        except Exception as e:
            logger.error(f"Query enhancement failed: {e}")
            return [query]  # Fallback to original query
    
    async def _google_autocomplete(self, query: str) -> List[str]:
        """Get suggestions from Google Autocomplete API (free, no API key needed)"""
        try:
            session = await self._get_session()
            
            # Use Google's public autocomplete API (used by Google Search)
            url = "http://suggestqueries.google.com/complete/search"
            params = {
                "client": "chrome",  # Chrome client for JSON response
                "q": query,
                "hl": "en",  # Language
                "gl": "us"   # Country
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    suggestions = []
                    
                    # Google autocomplete returns array with suggestions in second element
                    if len(data) > 1 and isinstance(data[1], list):
                        for suggestion in data[1][:3]:  # Take top 3 suggestions
                            if isinstance(suggestion, str) and suggestion.lower() != query.lower():
                                suggestions.append(suggestion)
                    
                    logger.info(f"Google autocomplete returned {len(suggestions)} suggestions for: {query[:30]}...")
                    return suggestions
                else:
                    logger.warning(f"Google Autocomplete returned status {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Google autocomplete error: {e}")
            return []
    
    async def _semantic_expansion(self, query: str) -> List[str]:
        """Expand query with semantic variations"""
        try:
            expansions = []
            
            # Add question variations
            if not query.strip().endswith('?'):
                expansions.extend([
                    f"what is {query}",
                    f"how to {query}",
                    f"{query} explained"
                ])
            
            # Add specificity variations
            words = query.split()
            if len(words) > 1:
                # Add broader version
                broader = " ".join(words[:-1]) if len(words) > 2 else words[0]
                expansions.append(broader)
                
                # Add more specific version
                specific_terms = ["guide", "tutorial", "examples", "best practices"]
                for term in specific_terms[:1]:  # Just add one
                    expansions.append(f"{query} {term}")
            
            return expansions[:2]  # Limit to 2 semantic expansions
            
        except Exception as e:
            logger.error(f"Semantic expansion error: {e}")
            return []
    
    async def _domain_specific_enhancement(self, query: str) -> List[str]:
        """Add domain-specific enhancements based on query content"""
        try:
            enhancements = []
            query_lower = query.lower()
            
            # Tech domain
            tech_keywords = ["api", "code", "programming", "software", "algorithm", "tech"]
            if any(keyword in query_lower for keyword in tech_keywords):
                enhancements.append(f"{query} programming guide")
            
            # Business domain
            business_keywords = ["business", "strategy", "market", "company", "revenue"]
            if any(keyword in query_lower for keyword in business_keywords):
                enhancements.append(f"{query} analysis")
            
            # Academic domain
            academic_keywords = ["research", "study", "analysis", "theory", "academic"]
            if any(keyword in query_lower for keyword in academic_keywords):
                enhancements.append(f"{query} research paper")
            
            # Health domain
            health_keywords = ["health", "medical", "disease", "treatment", "symptoms"]
            if any(keyword in query_lower for keyword in health_keywords):
                enhancements.append(f"{query} medical information")
            
            return enhancements[:1]  # Limit to 1 domain-specific enhancement
            
        except Exception as e:
            logger.error(f"Domain-specific enhancement error: {e}")
            return []
    
    async def _temporal_aware_enhancement(self, query: str) -> List[str]:
        """Add temporal context to queries"""
        try:
            enhancements = []
            query_lower = query.lower()
            
            # Check if query already has temporal context
            temporal_words = ["2024", "2025", "recent", "latest", "current", "now", "today"]
            has_temporal = any(word in query_lower for word in temporal_words)
            
            if not has_temporal:
                # Add current year context for relevant queries
                relevant_keywords = ["trends", "news", "updates", "development", "technology"]
                if any(keyword in query_lower for keyword in relevant_keywords):
                    enhancements.append(f"{query} 2024")
                    enhancements.append(f"latest {query}")
            
            return enhancements[:1]  # Limit to 1 temporal enhancement
            
        except Exception as e:
            logger.error(f"Temporal enhancement error: {e}")
            return []
    
    def _is_strategy_enabled(self, strategy_name: str) -> bool:
        """Check if enhancement strategy is enabled"""
        for strategy in self.strategies:
            if strategy.name == strategy_name:
                return strategy.enabled
        return False
    
    async def get_suggestions_only(self, query: str) -> List[str]:
        """Get only autocomplete suggestions without full enhancement"""
        return await self._google_autocomplete(query)
    
    async def health_check(self) -> str:
        """Check query enhancement service health"""
        try:
            # Test with a simple query
            test_query = "test query"
            enhanced = await self.enhance(test_query)
            
            if len(enhanced) > 0 and test_query in enhanced:
                return "healthy"
            else:
                return "degraded"
                
        except Exception as e:
            logger.error(f"Query enhancement health check failed: {e}")
            return "unhealthy"
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
