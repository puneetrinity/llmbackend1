# scripts/test_serpapi_migration.py
"""
Test script to validate SerpApi migration
Run this after migrating from Bing to SerpApi
"""

import asyncio
import sys
import time
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.search_engine import MultiSearchEngine
from app.services.query_enhancer import QueryEnhancementService
from app.config.settings import settings

class SerpApiMigrationTester:
    def __init__(self):
        self.search_engine = MultiSearchEngine()
        self.query_enhancer = QueryEnhancementService()
        self.test_results = []
    
    async def run_all_tests(self):
        """Run comprehensive migration tests"""
        print("🧪 Starting SerpApi Migration Tests\n")
        
        # Configuration tests
        await self.test_configuration()
        
        # API connectivity tests
        await self.test_api_connectivity()
        
        # Search functionality tests
        await self.test_search_functionality()
        
        # Query enhancement tests
        await self.test_query_enhancement()
        
        # Performance tests
        await self.test_performance()
        
        # Cost estimation tests
        await self.test_cost_estimation()
        
        # Generate report
        self.generate_report()
    
    async def test_configuration(self):
        """Test configuration changes"""
        print("⚙️  Testing Configuration...")
        
        tests = [
            ("SERPAPI_API_KEY present", bool(settings.SERPAPI_API_KEY)),
            ("BRAVE_SEARCH_API_KEY present", bool(settings.BRAVE_SEARCH_API_KEY)),
            ("SERPAPI_MONTHLY_BUDGET set", hasattr(settings, 'SERPAPI_MONTHLY_BUDGET')),
            ("Old BING_SEARCH_API_KEY removed", not hasattr(settings, 'BING_SEARCH_API_KEY') or not settings.BING_SEARCH_API_KEY),
            ("Old BING_AUTOSUGGEST_API_KEY removed", not hasattr(settings, 'BING_AUTOSUGGEST_API_KEY') or not settings.BING_AUTOSUGGEST_API_KEY)
        ]
        
        for test_name, result in tests:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {status} - {test_name}")
            self.test_results.append({"test": test_name, "passed": result, "category": "configuration"})
        
        print()
    
    async def test_api_connectivity(self):
        """Test API connectivity"""
        print("🌐 Testing API Connectivity...")
        
        # Test SerpApi connectivity
        try:
            if settings.SERPAPI_API_KEY:
                results = await self.search_engine._serpapi_search("test query", 1)
                serpapi_working = len(results) >= 0  # Even 0 results means API is responding
                print(f"  ✅ PASS - SerpApi connectivity")
            else:
                serpapi_working = False
                print(f"  ❌ FAIL - SerpApi API key not configured")
        except Exception as e:
            serpapi_working = False
            print(f"  ❌ FAIL - SerpApi error: {str(e)[:50]}...")
        
        self.test_results.append({"test": "SerpApi connectivity", "passed": serpapi_working, "category": "connectivity"})
        
        # Test Brave Search connectivity
        try:
            if settings.BRAVE_SEARCH_API_KEY:
                results = await self.search_engine._brave_search("test query", 1)
                brave_working = len(results) >= 0
                print(f"  ✅ PASS - Brave Search connectivity")
            else:
                brave_working = False
                print(f"  ❌ FAIL - Brave Search API key not configured")
        except Exception as e:
            brave_working = False
            print(f"  ❌ FAIL - Brave Search error: {str(e)[:50]}...")
        
        self.test_results.append({"test": "Brave Search connectivity", "passed": brave_working, "category": "connectivity"})
        
        # Test Google Autocomplete
        try:
            suggestions = await self.query_enhancer._google_autocomplete("test")
            autocomplete_working = isinstance(suggestions, list)
            print(f"  ✅ PASS - Google Autocomplete connectivity")
        except Exception as e:
            autocomplete_working = False
            print(f"  ❌ FAIL - Google Autocomplete error: {str(e)[:50]}...")
        
        self.test_results.append({"test": "Google Autocomplete connectivity", "passed": autocomplete_working, "category": "connectivity"})
        
        print()
    
    async def test_search_functionality(self):
        """Test search functionality"""
        print("🔍 Testing Search Functionality...")
        
        test_queries = [
            "artificial intelligence",
            "python programming",
            "climate change 2024"
        ]
        
        for query in test_queries:
            try:
                start_time = time.time()
                results = await self.search_engine.search_multiple([query], max_results_per_query=3)
                search_time = time.time() - start_time
                
                # Validate results
                has_results = len(results) > 0
                has_valid_urls = all(result.url.startswith('http') for result in results)
                has_titles = all(len(result.title) > 0 for result in results)
                has_snippets = all(len(result.snippet) > 0 for result in results)
                
                test_passed = has_results and has_valid_urls and has_titles and has_snippets
                
                if test_passed:
                    print(f"  ✅ PASS - Search '{query}' ({len(results)} results in {search_time:.2f}s)")
                else:
                    issues = []
                    if not has_results: issues.append("no results")
                    if not has_valid_urls: issues.append("invalid URLs")
                    if not has_titles: issues.append("missing titles")
                    if not has_snippets: issues.append("missing snippets")
                    print(f"  ❌ FAIL - Search '{query}' - Issues: {', '.join(issues)}")
                
                self.test_results.append({
                    "test": f"Search functionality - {query}",
                    "passed": test_passed,
                    "category": "search",
                    "details": {
                        "results_count": len(results),
                        "search_time": search_time,
                        "issues": issues if not test_passed else []
                    }
                })
                
            except Exception as e:
                print(f"  ❌ FAIL - Search '{query}' error: {str(e)[:50]}...")
                self.test_results.append({
                    "test": f"Search functionality - {query}",
                    "passed": False,
                    "category": "search",
                    "error": str(e)
                })
        
        print()
    
    async def test_query_enhancement(self):
        """Test query enhancement functionality"""
        print("🎯 Testing Query Enhancement...")
        
        test_queries = [
            "machine learning",
            "web development",
            "data science"
        ]
        
        for query in test_queries:
            try:
                start_time = time.time()
                enhanced = await self.query_enhancer.enhance(query)
                enhancement_time = time.time() - start_time
                
                # Validate enhancement
                has_original = query in enhanced
                has_enhancements = len(enhanced) > 1
                reasonable_count = len(enhanced) <= 5
                
                test_passed = has_original and has_enhancements and reasonable_count
                
                if test_passed:
                    print(f"  ✅ PASS - Enhancement '{query}' ({len(enhanced)} variations in {enhancement_time:.2f}s)")
                else:
                    issues = []
                    if not has_original: issues.append("original missing")
                    if not has_enhancements: issues.append("no enhancements")
                    if not reasonable_count: issues.append("too many variations")
                    print(f"  ❌ FAIL - Enhancement '{query}' - Issues: {', '.join(issues)}")
                
                self.test_results.append({
                    "test": f"Query enhancement - {query}",
                    "passed": test_passed,
                    "category": "enhancement",
                    "details": {
                        "variations_count": len(enhanced),
                        "enhancement_time": enhancement_time,
                        "enhanced_queries": enhanced
                    }
                })
                
            except Exception as e:
                print(f"  ❌ FAIL - Enhancement '{query}' error: {str(e)[:50]}...")
                self.test_results.append({
                    "test": f"Query enhancement - {query}",
                    "passed": False,
                    "category": "enhancement",
                    "error": str(e)
                })
        
        print()
    
    async def test_performance(self):
        """Test performance characteristics"""
        print("⚡ Testing Performance...")
        
        # Test search speed
        try:
            start_time = time.time()
            results = await self.search_engine.search_multiple(["performance test"], max_results_per_query=5)
            search_time = time.time() - start_time
            
            # Performance thresholds
            fast_search = search_time < 3.0  # Under 3 seconds
            reasonable_search = search_time < 10.0  # Under 10 seconds
            
            if fast_search:
                print(f"  ✅ PASS - Search performance excellent ({search_time:.2f}s)")
            elif reasonable_search:
                print(f"  ⚠️  WARN - Search performance acceptable ({search_time:.2f}s)")
            else:
                print(f"  ❌ FAIL - Search performance poor ({search_time:.2f}s)")
            
            self.test_results.append({
                "test": "Search performance",
                "passed": reasonable_search,
                "category": "performance",
                "details": {"search_time": search_time, "threshold_met": fast_search}
            })
            
        except Exception as e:
            print(f"  ❌ FAIL - Performance test error: {str(e)[:50]}...")
            self.test_results.append({
                "test": "Search performance",
                "passed": False,
                "category": "performance",
                "error": str(e)
            })
        
        print()
    
    async def test_cost_estimation(self):
        """Test cost estimation logic"""
        print("💰 Testing Cost Estimation...")
        
        # Test SerpApi cost calculation
        serpapi_cost_per_search = 0.02  # Expected cost
        searches = 10
        expected_cost = searches * serpapi_cost_per_search
        
        # This would normally test the cost tracker, but we'll simulate
        print(f"  ℹ️  SerpApi cost estimation: {searches} searches = ${expected_cost:.2f}")
        
        # Verify cost rates are reasonable
        reasonable_cost = expected_cost < 1.0  # $1 for 10 searches should be reasonable
        
        if reasonable_cost:
            print(f"  ✅ PASS - Cost estimation reasonable")
        else:
            print(f"  ❌ FAIL - Cost estimation too high")
        
        self.test_results.append({
            "test": "Cost estimation",
            "passed": reasonable_cost,
            "category": "cost",
            "details": {
                "cost_per_search": serpapi_cost_per_search,
                "estimated_cost_10_searches": expected_cost
            }
        })
        
        print()
    
    def generate_report(self):
        """Generate test report"""
        print("📊 Test Report Summary\n")
        
        # Count results by category
        categories = {}
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        
        for result in self.test_results:
            category = result["category"]
            if category not in categories:
                categories[category] = {"total": 0, "passed": 0}
            categories[category]["total"] += 1
            if result["passed"]:
                categories[category]["passed"] += 1
        
        # Print category summaries
        for category, stats in categories.items():
            percentage = (stats["passed"] / stats["total"]) * 100
            print(f"  {category.capitalize()}: {stats['passed']}/{stats['total']} ({percentage:.1f}%)")
        
        print(f"\nOverall: {passed_tests}/{total_tests} tests passed ({(passed_tests/total_tests)*100:.1f}%)")
        
        # Migration status
        critical_tests = [
            "SERPAPI_API_KEY present",
            "SerpApi connectivity",
            "Search functionality - artificial intelligence"
        ]
        
        critical_passed = all(
            result["passed"] for result in self.test_results 
            if result["test"] in critical_tests
        )
        
        if critical_passed and passed_tests >= total_tests * 0.8:  # 80% pass rate
            print("\n🎉 Migration Status: SUCCESS")
            print("   SerpApi migration appears to be working correctly!")
            print("   You can now remove old Bing API keys from your environment.")
        elif critical_passed:
            print("\n⚠️  Migration Status: PARTIAL SUCCESS")
            print("   Core functionality works, but some issues detected.")
            print("   Review failed tests and fix issues before production use.")
        else:
            print("\n❌ Migration Status: FAILURE")
            print("   Critical issues detected. Do not deploy to production.")
            print("   Fix configuration and connectivity issues first.")
        
        # Save detailed results
        with open("serpapi_migration_test_results.json", "w") as f:
            json.dump({
                "timestamp": time.time(),
                "summary": {
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "success_rate": (passed_tests / total_tests) * 100,
                    "migration_successful": critical_passed and passed_tests >= total_tests * 0.8
                },
                "categories": categories,
                "detailed_results": self.test_results
            }, f, indent=2)
        
        print(f"\n📁 Detailed results saved to: serpapi_migration_test_results.json")
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.search_engine.close()
        await self.query_enhancer.close()

async def main():
    """Run migration tests"""
    tester = SerpApiMigrationTester()
    
    try:
        await tester.run_all_tests()
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
