# scripts/check_api_keys.py
"""Script to validate API keys - Updated for SerpApi migration"""

import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

async def check_brave_api():
    """Test Brave Search API"""
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return False, "API key not found"
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": api_key
            }
            params = {"q": "test", "count": 1}
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return True, "OK"
                else:
                    return False, f"HTTP {response.status}"
    except Exception as e:
        return False, str(e)

async def check_serpapi():
    """Test SerpApi (Google Search)"""
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return False, "API key not found"
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://serpapi.com/search"
            params = {
                "q": "test",
                "api_key": api_key,
                "engine": "google",
                "num": 1,
                "output": "json"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    # Check if we got organic results
                    if "organic_results" in data:
                        return True, f"OK - {len(data['organic_results'])} results"
                    else:
                        return False, "No organic results in response"
                elif response.status == 401:
                    return False, "Invalid API key"
                elif response.status == 429:
                    return False, "Rate limit exceeded"
                else:
                    error_text = await response.text()
                    return False, f"HTTP {response.status}: {error_text[:100]}"
    except Exception as e:
        return False, str(e)

async def check_google_autocomplete():
    """Test Google Autocomplete (free service)"""
    try:
        async with aiohttp.ClientSession() as session:
            url = "http://suggestqueries.google.com/complete/search"
            params = {
                "client": "chrome",
                "q": "test",
                "hl": "en"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if len(data) > 1 and isinstance(data[1], list):
                        return True, f"OK - {len(data[1])} suggestions"
                    else:
                        return True, "OK - No suggestions returned"
                else:
                    return False, f"HTTP {response.status}"
    except Exception as e:
        return False, str(e)

async def check_zenrows_api():
    """Test ZenRows API"""
    api_key = os.getenv("ZENROWS_API_KEY")
    if not api_key:
        return False, "API key not found"
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.zenrows.com/v1/"
            params = {
                "url": "https://httpbin.org/html",
                "apikey": api_key
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return True, "OK"
                else:
                    return False, f"HTTP {response.status}"
    except Exception as e:
        return False, str(e)

async def check_ollama():
    """Test Ollama connection"""
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ollama_host}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model["name"] for model in data.get("models", [])]
                    return True, f"Available models: {models}"
                else:
                    return False, f"HTTP {response.status}"
    except Exception as e:
        return False, str(e)

async def check_migration_status():
    """Check if migration from Bing to SerpApi is complete"""
    print("🔄 Checking migration status...\n")
    
    # Check if old Bing API keys are still present
    bing_search_key = os.getenv("BING_SEARCH_API_KEY")
    bing_autosuggest_key = os.getenv("BING_AUTOSUGGEST_API_KEY")
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    
    if bing_search_key or bing_autosuggest_key:
        print("⚠️  Warning: Old Bing API keys still present in environment")
        if bing_search_key:
            print(f"   - BING_SEARCH_API_KEY is set")
        if bing_autosuggest_key:
            print(f"   - BING_AUTOSUGGEST_API_KEY is set")
        print("   Consider removing these after confirming SerpApi works\n")
    
    if not serpapi_key:
        print("❌ Migration incomplete: SERPAPI_API_KEY not found")
        print("   Please add your SerpApi API key to the .env file\n")
        return False
    
    print("✅ Migration appears complete: SerpApi key is configured\n")
    return True

async def check_budget_configuration():
    """Check budget configuration"""
    print("💰 Checking budget configuration...\n")
    
    daily_budget = os.getenv("DAILY_BUDGET_USD")
    serpapi_budget = os.getenv("SERPAPI_MONTHLY_BUDGET")
    zenrows_budget = os.getenv("ZENROWS_MONTHLY_BUDGET")
    
    if not daily_budget:
        print("⚠️  DAILY_BUDGET_USD not set (default: $100)")
    else:
        print(f"💵 Daily budget: ${daily_budget}")
    
    if not serpapi_budget:
        print("⚠️  SERPAPI_MONTHLY_BUDGET not set (recommended)")
    else:
        print(f"🔍 SerpApi monthly budget: ${serpapi_budget}")
    
    if not zenrows_budget:
        print("⚠️  ZENROWS_MONTHLY_BUDGET not set (recommended)")
    else:
        print(f"🌐 ZenRows monthly budget: ${zenrows_budget}")
    
    print()

async def main():
    """Check all API connections and migration status"""
    print("🔍 Checking API Keys and Migration Status...\n")
    
    # Check migration status first
    migration_complete = await check_migration_status()
    
    # Check budget configuration
    await check_budget_configuration()
    
    # API checks
    checks = [
        ("Brave Search API", check_brave_api()),
        ("SerpApi (Google Search)", check_serpapi()),
        ("Google Autocomplete", check_google_autocomplete()),
        ("ZenRows API", check_zenrows_api()),
        ("Ollama Service", check_ollama())
    ]
    
    results = await asyncio.gather(*[check[1] for check in checks])
    
    print("📊 API Status Check Results:\n")
    for i, (name, _) in enumerate(checks):
        success, message = results[i]
        status = "✅" if success else "❌"
        print(f"{status} {name}: {message}")
    
    all_apis_good = all(result[0] for result in results)
    
    print(f"\n{'🎉 All APIs are working!' if all_apis_good else '⚠️  Some APIs need attention'}")
    
    if migration_complete and all_apis_good:
        print("\n🚀 Migration to SerpApi appears successful!")
        print("   You can now remove old Bing API keys from your environment")
    elif not migration_complete:
        print("\n🔄 Migration in progress...")
        print("   Complete the SerpApi setup and test again")
    
    if not all_apis_good:
        print("\n💡 Troubleshooting tips:")
        print("- Check your .env file for correct API keys")
        print("- Ensure Ollama is running: ollama serve")
        print("- Pull required model: ollama pull llama2:7b")
        print("- Verify network connectivity to external APIs")
        print("- Check API key permissions and billing status")

if __name__ == "__main__":
    asyncio.run(main())
