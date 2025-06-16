# app/services/search_engine.py
import asyncio
import aiohttp
import logging
import time
from typing import List, Dict, Optional, Union
from urllib.parse import quote
import json

from app.config.settings import settings
from app.models.internal import SearchResult
from app.services.cache_service import CacheService
from app.core.exceptions import SearchEngineException

logger = logging.getLogger(__name__)

class MultiSearchEngine:
    def __init__(self):
        self.cache = CacheService()
        self.session = None
        self.search_engines = {
            "brave": self._brave_search,
            "serpapi": self._serpapi_search  # Replaced bing with serpapi
        }
        
    async def _get_session(self):
        """Lazy initialization of HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=settings.SEARCH_TIMEOUT)
            )
        return self.session
    
    async def search_multiple(self, queries: List[str], max_results_per_query: int = 8) -> List[SearchResult]:
        """
        Search multiple queries across multiple engines
        Returns deduplicated and ranked results
        """
        start_time = time.time()
        all_results = []
        
        try:
            # Create tasks for all query-engine combinations
            tasks = []
            
            for query in queries:
                # Check cache first
                cache_key = f"search:{hash(query)}"
                cached_results = await self.cache.get(cache_key, "search")
                
                if cached_results:
                    logger.info(f"Cache hit for search query: {query[:30]}...")
                    # Convert cached data back to SearchResult objects
                    for result_data in cached_results:
                        all_results.append(SearchResult(**result_data))
                    continue
                
                # Add search tasks for this query
                if settings.BRAVE_SEARCH_API_KEY:
                    tasks.append(self._search_with_engine("brave", query, max_results_per_query))
                
                if settings.SERPAPI_API_KEY:  # Changed from BING_SEARCH_API_KEY
                    tasks.append(self._search_with_engine("serpapi", query, max_results_per_query))
            
            # Execute all search tasks in parallel
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results and cache them
                query_results = {}
                for i, result in enumerate(results):
                    query_idx = i // len([k for k in self.search_engines.keys() if getattr(settings, f"{k.upper()}_SEARCH_API_KEY" if k != "serpapi" else "SERPAPI_API_KEY")])
                    query = queries[query_idx] if query_idx < len(queries) else queries[0]
                    
                    if isinstance(result, list):
                        if query not in query_results:
                            query_results[query] = []
                        query_results[query].extend(result)
                        all_results.extend(result)
                    elif isinstance(result, Exception):
                        logger.warning(f"Search task failed: {result}")
                
                # Cache results for each query
                for query, results in query_results.items():
                    cache_key = f"search:{hash(query)}"
                    result_dicts = [result.dict() for result in results]
                    await self.cache.set(cache_key, result_dicts, prefix="search")
            
            # Deduplicate and rank results
            final_results = self._deduplicate_and_rank(all_results, max_results_per_query * len(queries))
            
            processing_time = time.time() - start_time
            logger.info(f"Search completed: {len(final_results)} results in {processing_time:.2f}s")
            
            return final_results
            
        except Exception as e:
            logger.error(f"Multi-search error: {e}")
            raise SearchEngineException(f"Search failed: {str(e)}")
    
    async def _search_with_engine(self, engine: str, query: str, max_results: int) -> List[SearchResult]:
        """Search with a specific engine"""
        try:
            search_func = self.search_engines.get(engine)
            if search_func:
                return await search_func(query, max_results)
            else:
                logger.warning(f"Unknown search engine: {engine}")
                return []
        except Exception as e:
            logger.error(f"Search engine {engine} failed for query '{query}': {e}")
            return []
    
    async def _brave_search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using Brave Search API"""
        if not settings.BRAVE_SEARCH_API_KEY:
            return []
            
        try:
            session = await self._get_session()
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": settings.BRAVE_SEARCH_API_KEY
            }
            params = {
                "q": query,
                "count": min(max_results, 20),  # Brave API max is 20
                "search_lang": "en",
                "country": "US",
                "safesearch": "moderate"
            }
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    
                    web_results = data.get("web", {}).get("results", [])
                    for item in web_results:
                        result = SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            snippet=item.get("description", ""),
                            source_engine="brave",
                            relevance_score=self._calculate_relevance_score(item, query)
                        )
                        results.append(result)
                    
                    logger.info(f"Brave search returned {len(results)} results for: {query[:30]}...")
                    return results
                    
                else:
                    logger.warning(f"Brave Search API returned status {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Brave search error: {e}")
            return []
    
    async def _serpapi_search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using SerpApi (Google Search)"""
        if not settings.SERPAPI_API_KEY:
            return []
            
        try:
            session = await self._get_session()
            url = "https://serpapi.com/search"
            params = {
                "q": query,
                "api_key": settings.SERPAPI_API_KEY,
                "engine": "google",  # Use Google as the search engine
                "num": min(max_results, 20),  # Number of results
                "hl": "en",  # Language
                "gl": "us",  # Country
                "safe": "active",  # Safe search
                "output": "json"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    
                    # SerpApi returns results in 'organic_results'
                    organic_results = data.get("organic_results", [])
                    for item in organic_results:
                        result = SearchResult(
                            title=item.get("title", ""),
                            url=item.get("link", ""),
                            snippet=item.get("snippet", ""),
                            source_engine="serpapi",
                            relevance_score=self._calculate_relevance_score(item, query)
                        )
                        results.append(result)
                    
                    logger.info(f"SerpApi search returned {len(results)} results for: {query[:30]}...")
                    return results
                    
                else:
                    logger.warning(f"SerpApi returned status {response.status}")
                    # Log response text for debugging
                    error_text = await response.text()
                    logger.warning(f"SerpApi error response: {error_text[:200]}...")
                    return []
                    
        except Exception as e:
            logger.error(f"SerpApi search error: {e}")
            return []
    
    def _calculate_relevance_score(self, item: Dict, query: str) -> float:
        """Calculate relevance score for a search result"""
        try:
            score = 0.5  # Base score
            
            # Handle different field names for different APIs
            title = ""
            snippet = ""
            
            # Brave API uses 'title' and 'description'
            if "title" in item:
                title = item.get("title", "").lower()
            if "description" in item:
                snippet = item.get("description", "").lower()
            
            # SerpApi uses 'title' and 'snippet'
            if "snippet" in item:
                snippet = item.get("snippet", "").lower()
            
            query_lower = query.lower()
            
            # Title relevance (higher weight)
            if query_lower in title:
                score += 0.3
            
            # Snippet relevance
            if query_lower in snippet:
                score += 0.2
            
            # Query term coverage
            query_terms = query_lower.split()
            title_snippet = f"{title} {snippet}"
            
            matching_terms = sum(1 for term in query_terms if term in title_snippet)
            if query_terms:
                coverage = matching_terms / len(query_terms)
                score += coverage * 0.2
            
            # SerpApi specific: Check for position (higher positions get bonus)
            if "position" in item:
                position = item.get("position", 10)
                # Give bonus for top 3 results
                if position <= 3:
                    score += 0.1
                elif position <= 5:
                    score += 0.05
            
            # Ensure score is between 0 and 1
            return min(max(score, 0.0), 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating relevance score: {e}")
            return 0.5
    
    def _deduplicate_and_rank(self, results: List[SearchResult], max_results: int) -> List[SearchResult]:
        """Remove duplicates and rank results by relevance"""
        try:
            # Deduplicate by URL
            seen_urls = set()
            unique_results = []
            
            for result in results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    unique_results.append(result)
            
            # Sort by relevance score (descending)
            unique_results.sort(key=lambda x: x.relevance_score, reverse=True)
            
            # Limit to max results
            return unique_results[:max_results]
            
        except Exception as e:
            logger.error(f"Error deduplicating and ranking results: {e}")
            return results[:max_results]
    
    async def health_check(self) -> str:
        """Check search engine service health"""
        try:
            # Test search with a simple query
            test_results = await self.search_multiple(["test"], max_results_per_query=1)
            
            if len(test_results) > 0:
                return "healthy"
            else:
                return "degraded"
                
        except Exception as e:
            logger.error(f"Search engine health check failed: {e}")
            return "unhealthy"
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
