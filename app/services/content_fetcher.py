# app/services/content_fetcher.py
import asyncio
import aiohttp
import logging
import time
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import trafilatura

from app.config.settings import settings
from app.models.internal import SearchResult, ContentData, ContentSource
from app.services.cache_service import CacheService
from app.core.exceptions import ContentFetchException

logger = logging.getLogger(__name__)

class ZenRowsContentFetcher:
    def __init__(self):
        self.cache = CacheService()
        self.session = None
        self.zenrows_api_key = settings.ZENROWS_API_KEY
        self.max_content_length = settings.MAX_CONTENT_LENGTH
        
    async def _get_session(self):
        """Lazy initialization of HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=settings.CONTENT_FETCH_TIMEOUT)
            )
        return self.session
    
    async def fetch_content(self, search_results: List[SearchResult], max_urls: int = 8) -> List[ContentData]:
        """
        Fetch content from search result URLs using ZenRows
        Returns list of ContentData objects
        """
        start_time = time.time()
        
        if not search_results:
            return []
        
        # Limit the number of URLs to fetch
        urls_to_fetch = search_results[:max_urls]
        
        try:
            # Create tasks for parallel content fetching
            tasks = []
            for result in urls_to_fetch:
                tasks.append(self._fetch_single_content(result))
            
            # Execute all fetch tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            content_data = []
            for result in results:
                if isinstance(result, ContentData):
                    content_data.append(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Content fetch failed: {result}")
            
            processing_time = time.time() - start_time
            logger.info(f"Content fetching completed: {len(content_data)}/{len(urls_to_fetch)} successful in {processing_time:.2f}s")
            
            return content_data
            
        except Exception as e:
            logger.error(f"Content fetching error: {e}")
            raise ContentFetchException(f"Content fetching failed: {str(e)}")
    
    async def _fetch_single_content(self, search_result: SearchResult) -> Optional[ContentData]:
        """Fetch content from a single URL"""
        url = search_result.url
        
        try:
            # Check cache first
            cache_key = f"content:{hash(url)}"
            cached_content = await self.cache.get(cache_key, "content")
            
            if cached_content:
                logger.info(f"Cache hit for content: {url[:50]}...")
                return ContentData(**cached_content)
            
            fetch_start = time.time()
            
            # Try ZenRows first, then fallback to direct fetch
            content = await self._fetch_with_zenrows(url)
            if not content:
                content = await self._fetch_direct(url)
            
            if not content:
                logger.warning(f"Failed to fetch content from: {url}")
                return None
            
            # Extract main content using trafilatura
            extracted_content = trafilatura.extract(content, 
                                                   include_comments=False,
                                                   include_tables=True,
                                                   include_formatting=False)
            
            if not extracted_content:
                # Fallback to BeautifulSoup extraction
                extracted_content = self._extract_with_beautifulsoup(content)
            
            if not extracted_content:
                logger.warning(f"No content extracted from: {url}")
                return None
            
            # Clean and truncate content
            cleaned_content = self._clean_content(extracted_content)
            
            # Determine content source type
            source_type = self._determine_source_type(url, search_result.title)
            
            fetch_time = time.time() - fetch_start
            
            # Create ContentData object
            content_data = ContentData(
                url=url,
                title=search_result.title,
                content=cleaned_content,
                word_count=len(cleaned_content.split()),
                source_type=source_type,
                extraction_method="trafilatura" if trafilatura.extract(content) else "beautifulsoup",
                confidence_score=self._calculate_content_confidence(cleaned_content, search_result),
                fetch_time=fetch_time
            )
            
            # Cache the result
            await self.cache.set(cache_key, content_data.dict(), ttl=7200, prefix="content")  # 2 hour cache
            
            logger.info(f"Successfully fetched content from: {url[:50]}... ({content_data.word_count} words)")
            return content_data
            
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {e}")
            return None
    
    async def _fetch_with_zenrows(self, url: str) -> Optional[str]:
        """Fetch content using ZenRows proxy service"""
        if not self.zenrows_api_key:
            return None
            
        try:
            session = await self._get_session()
            
            # ZenRows API endpoint
            zenrows_url = "https://api.zenrows.com/v1/"
            
            params = {
                "url": url,
                "apikey": self.zenrows_api_key,
                "js_render": "true",  # Enable JavaScript rendering
                "premium_proxy": "true",  # Use premium proxies
                "proxy_country": "US",  # Use US proxies
                "wait": "2"  # Wait 2 seconds after page load
            }
            
            async with session.get(zenrows_url, params=params) as response:
                if response.status == 200:
                    content = await response.text()
                    logger.info(f"ZenRows fetch successful for: {url[:50]}...")
                    return content
                else:
                    logger.warning(f"ZenRows fetch failed with status {response.status} for: {url}")
                    return None
                    
        except Exception as e:
            logger.warning(f"ZenRows fetch error for {url}: {e}")
            return None
    
    async def _fetch_direct(self, url: str) -> Optional[str]:
        """Direct fetch as fallback when ZenRows fails"""
        try:
            session = await self._get_session()
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    content = await response.text()
                    logger.info(f"Direct fetch successful for: {url[:50]}...")
                    return content
                else:
                    logger.warning(f"Direct fetch failed with status {response.status} for: {url}")
                    return None
                    
        except Exception as e:
            logger.warning(f"Direct fetch error for {url}: {e}")
            return None
    
    def _extract_with_beautifulsoup(self, html_content: str) -> Optional[str]:
        """Extract content using BeautifulSoup as fallback"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # Find main content areas
            content_selectors = [
                'main', 'article', '[role="main"]', '.content', '#content',
                '.post-content', '.entry-content', '.article-content'
            ]
            
            main_content = None
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    main_content = elements[0]
                    break
            
            if not main_content:
                # Fallback to body
                main_content = soup.find('body') or soup
            
            # Extract text
            text = main_content.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            logger.error(f"BeautifulSoup extraction error: {e}")
            return None
    
    def _clean_content(self, content: str) -> str:
        """Clean and truncate content"""
        try:
            # Remove excessive whitespace
            content = re.sub(r'\s+', ' ', content)
            
            # Remove common footer/header text patterns
            patterns_to_remove = [
                r'(?i)cookie\s+policy.*?(?=\.|$)',
                r'(?i)privacy\s+policy.*?(?=\.|$)',
                r'(?i)terms\s+of\s+service.*?(?=\.|$)',
                r'(?i)subscribe\s+to.*?(?=\.|$)',
                r'(?i)follow\s+us.*?(?=\.|$)',
                r'(?i)share\s+this.*?(?=\.|$)',
            ]
            
            for pattern in patterns_to_remove:
                content = re.sub(pattern, '', content)
            
            # Truncate to max length
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length] + "..."
            
            return content.strip()
            
        except Exception as e:
            logger.error(f"Content cleaning error: {e}")
            return content[:self.max_content_length] if content else ""
    
    def _determine_source_type(self, url: str, title: str) -> ContentSource:
        """Determine the type of content source"""
        try:
            url_lower = url.lower()
            title_lower = title.lower()
            
            # News sites
            news_domains = ['cnn.com', 'bbc.com', 'reuters.com', 'ap.org', 'npr.org', 'news.']
            if any(domain in url_lower for domain in news_domains) or 'news' in url_lower:
                return ContentSource.NEWS
            
            # Academic sources
            academic_domains = ['.edu', 'scholar.google', 'arxiv.org', 'researchgate', 'jstor']
            academic_keywords = ['research', 'study', 'journal', 'paper', 'academic']
            if (any(domain in url_lower for domain in academic_domains) or 
                any(keyword in title_lower for keyword in academic_keywords)):
                return ContentSource.ACADEMIC
            
            # Social media
            social_domains = ['twitter.com', 'facebook.com', 'linkedin.com', 'reddit.com', 'youtube.com']
            if any(domain in url_lower for domain in social_domains):
                return ContentSource.SOCIAL
            
            # E-commerce
            ecommerce_domains = ['amazon.com', 'ebay.com', 'shop', 'store', 'buy']
            if any(domain in url_lower for domain in ecommerce_domains):
                return ContentSource.ECOMMERCE
            
            return ContentSource.GENERAL
            
        except Exception as e:
            logger.warning(f"Error determining source type: {e}")
            return ContentSource.GENERAL
    
    def _calculate_content_confidence(self, content: str, search_result: SearchResult) -> float:
        """Calculate confidence score for extracted content"""
        try:
            score = 0.5  # Base score
            
            # Content length factor
            word_count = len(content.split())
            if word_count > 100:
                score += 0.2
            elif word_count > 50:
                score += 0.1
            
            # Title presence in content
            if search_result.title.lower() in content.lower():
                score += 0.1
            
            # Content quality indicators
            if '.' in content and len(content) > 200:  # Has sentences and reasonable length
                score += 0.1
            
            # Penalize if content seems like navigation/menu
            navigation_keywords = ['home', 'about', 'contact', 'menu', 'navigation']
            nav_count = sum(1 for keyword in navigation_keywords if keyword in content.lower())
            if nav_count > 3:
                score -= 0.2
            
            return min(max(score, 0.0), 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating content confidence: {e}")
            return 0.5
    
    async def health_check(self) -> str:
        """Check content fetcher service health"""
        try:
            # Test with a simple URL (you might want to use a test endpoint)
            test_url = "https://httpbin.org/html"
            
            # Create a mock search result for testing
            test_result = SearchResult(
                title="Test",
                url=test_url,
                snippet="Test content",
                source_engine="test",
                relevance_score=1.0
            )
            
            content = await self._fetch_single_content(test_result)
            
            if content and content.word_count > 0:
                return "healthy"
            else:
                return "degraded"
                
        except Exception as e:
            logger.error(f"Content fetcher health check failed: {e}")
            return "unhealthy"
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
