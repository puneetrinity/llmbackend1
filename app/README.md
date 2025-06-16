# LLM Search Backend

A production-ready LLM-powered search backend that processes user queries via REST API and returns intelligent, sourced responses in 3-8 seconds.

## 🎯 Features

- **Multi-Engine Search**: Integrates Brave Search and Bing Search APIs
- **Intelligent Content Fetching**: Uses ZenRows for robust web scraping
- **Local LLM Analysis**: Powered by Ollama for cost-effective AI processing
- **Advanced Caching**: Redis + memory caching for optimal performance
- **Cost Tracking**: Built-in budget monitoring and alerts
- **Production Ready**: Docker containerization, health checks, monitoring

## 🏗️ Architecture

```
Query → Enhancement → Multi-Search → Content Fetch → LLM Analysis → Response
```

- **Query Enhancement**: Expands queries using Bing Autosuggest and semantic patterns
- **Multi-Search**: Parallel search across multiple engines with deduplication
- **Content Fetching**: Smart content extraction using ZenRows + Trafilatura
- **LLM Analysis**: Local Ollama model synthesizes results into coherent responses
- **Caching**: Multi-layer caching reduces costs and improves speed

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- API Keys for external services

### 1. Clone and Setup

```bash
git clone <your-repo>
cd llm-search-backend

# Copy environment template
cp .env.example .env
```

### 2. Configure API Keys

Edit `.env` file with your API keys:

```bash
# Required API Keys
BRAVE_SEARCH_API_KEY=your_brave_api_key_here
BING_SEARCH_API_KEY=your_bing_api_key_here
BING_AUTOSUGGEST_API_KEY=your_bing_autosuggest_key_here
ZENROWS_API_KEY=your_zenrows_api_key_here

# Optional: Adjust settings
DAILY_BUDGET_USD=50.0
MAX_SOURCES_PER_QUERY=8
```

### 3. Start with Docker (Recommended)

```bash
# Start all services
make docker-up

# Or manually:
docker-compose up -d
```

### 4. Alternative: Local Development

```bash
# Setup Python environment
make setup
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
make install

# Start local services (Redis, PostgreSQL, Ollama)
docker-compose up redis db ollama -d

# Run development server
make dev
```

## 🔗 API Endpoints

### Search Query
```bash
POST /api/v1/search
Content-Type: application/json

{
  "query": "What are the latest developments in AI?",
  "max_results": 8,
  "include_sources": true
}
```

### Response Example
```json
{
  "query": "What are the latest developments in AI?",
  "answer": "Recent developments in AI include...",
  "sources": ["https://example.com/ai-news", "..."],
  "confidence": 0.87,
  "processing_time": 4.2,
  "cached": false,
  "cost_estimate": 0.045,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Other Endpoints
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed system health
- `GET /api/v1/search/suggestions?q=query` - Get search suggestions
- `GET /api/v1/search/stats` - Pipeline statistics
- `GET /docs` - API documentation (development mode)

## 🛠️ Development

### Available Commands

```bash
make help              # Show all available commands
make dev               # Start development server
make test              # Run tests
make lint              # Run code linting
make format            # Format code
make docker-up         # Start all services
make docker-logs       # View logs
make clean             # Clean temporary files
```

### Project Structure

```
app/
├── main.py                    # FastAPI application entry
├── config/settings.py         # Configuration management
├── core/pipeline.py           # Main pipeline orchestrator
├── services/                  # Business logic services
│   ├── query_enhancer.py      # Query enhancement
│   ├── search_engine.py       # Multi-search engine
│   ├── content_fetcher.py     # Content fetching
│   ├── llm_analyzer.py        # LLM analysis
│   ├── cache_service.py       # Caching layer
│   └── cost_tracker.py        # Cost monitoring
├── api/endpoints/             # API endpoints
├── models/                    # Data models
└── utils/                     # Utility functions
```

## 🔑 API Key Setup

### 1. Brave Search API
- Sign up at [Brave Search API](https://api.search.brave.com/)
- Get your API key from the dashboard
- Add to `.env`: `BRAVE_SEARCH_API_KEY=your_key`

### 2. Bing Search API
- Create account at [Azure Cognitive Services](https://portal.azure.com/)
- Create "Bing Search v7" resource
- Add keys to `.env`:
  - `BING_SEARCH_API_KEY=your_key`
  - `BING_AUTOSUGGEST_API_KEY=your_key`

### 3. ZenRows API
- Sign up at [ZenRows](https://www.zenrows.com/)
- Get API key from dashboard
- Add to `.env`: `ZENROWS_API_KEY=your_key`

## 🐳 Docker Deployment

### Development
```bash
docker-compose up -d
```

### Production
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### With Management Tools
```bash
docker-compose --profile tools up -d
# Access pgAdmin: http://localhost:8080
# Access Redis Commander: http://localhost:8081
```

## 📊 Monitoring & Cost Management

### Cost Tracking
The system tracks costs for all external API calls:

- **Brave Search**: ~$0.005 per search
- **Bing Search**: ~$0.003 per search
- **ZenRows**: ~$0.01 per request
- **LLM**: Free (local Ollama)

### Monitoring Endpoints
- `GET /health/detailed` - Component health status
- `GET /api/v1/search/stats` - Usage statistics
- `GET /api/v1/search/cost/{request_id}` - Request cost breakdown

### Budget Controls
Set daily limits in `.env`:
```bash
DAILY_BUDGET_USD=50.0
ZENROWS_MONTHLY_BUDGET=200.0
MAX_SOURCES_PER_QUERY=8
RATE_LIMIT_PER_MINUTE=60
```

## ⚡ Performance Optimization

### Caching Strategy
- **Memory Cache**: Immediate responses for repeated queries
- **Redis Cache**: Distributed caching across instances
- **Query Enhancement Cache**: 1 hour TTL
- **Search Results Cache**: 30 minutes TTL
- **Final Responses Cache**: 4 hours TTL

### Performance Targets
- **Fresh requests**: 5-8 seconds
- **Cached responses**: 100-500ms
- **Average (70% cache hit)**: 2-3 seconds
- **Concurrent users**: 500+

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_HOST` | API server host | `0.0.0.0` |
| `API_PORT` | API server port | `8000` |
| `DEBUG` | Debug mode | `false` |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `LLM_MODEL` | LLM model name | `llama2:7b` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `RATE_LIMIT_PER_MINUTE` | API rate limit | `60` |

### LLM Configuration

```bash
# Ollama settings
OLLAMA_HOST=http://localhost:11434
LLM_MODEL=llama2:7b           # or mistral:7b, codellama:7b
LLM_MAX_TOKENS=500
LLM_TEMPERATURE=0.1
LLM_TIMEOUT=30
```

## 🧪 Testing

### Run Tests
```bash
make test                     # Run all tests
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests only
```

### Manual Testing
```bash
# Test basic search
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Python programming", "max_results": 5}'

# Test health check
curl http://localhost:8000/health/detailed
```

## 🚨 Troubleshooting

### Common Issues

1. **Ollama Connection Failed**
   ```bash
   # Check if Ollama is running
   curl http://localhost:11434/api/tags
   
   # Pull required model
   ollama pull llama2:7b
   ```

2. **Redis Connection Error**
   ```bash
   # Check Redis status
   docker-compose logs redis
   
   # Restart Redis
   docker-compose restart redis
   ```

3. **API Key Issues**
   ```bash
   # Test API keys
   python scripts/check_api_keys.py
   ```

4. **High Memory Usage**
   ```bash
   # Reduce cache size in .env
   MEMORY_CACHE_SIZE=500
   MAX_CONTENT_LENGTH=3000
   ```

### Logs
```bash
# View all logs
make docker-logs

# View API logs only
make docker-logs-api

# View specific service logs
docker-compose logs -f redis
docker-compose logs -f ollama
```

## 📈 Scaling

### Horizontal Scaling
- Use Docker Swarm or Kubernetes
- Add load balancer (NGINX included)
- Scale API service instances
- Use Redis Cluster for caching

### Performance Tuning
- Adjust worker counts in Docker
- Tune cache TTL values
- Optimize LLM model size
- Implement request queuing

## 🔒 Security

### API Security
- Rate limiting per user/IP
- Request size limits
- Input validation
- API key authentication (extensible)

### Production Security
- Use secrets management
- Enable HTTPS
- Network isolation
- Regular security updates

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Ollama Documentation](https://ollama.ai/docs)
- [ZenRows Documentation](https://www.zenrows.com/docs)
- [Brave Search API Docs](https://api.search.brave.com/app/documentation)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Ready to get started?** Run `make quick-start` and follow the setup instructions!
