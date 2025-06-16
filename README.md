# 🔍 LLM Search Backend

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready LLM-powered search backend that processes user queries via REST API and returns intelligent, sourced responses in 3-8 seconds.

## 🎯 Overview

**Architecture**: Query → API Enhancement → Multi-Search → ZenRows Content → LLM Analysis → Response

This system combines multiple search engines with AI-powered content analysis to provide comprehensive, sourced answers to user queries. Built for scale with Docker, Redis caching, and production monitoring.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Git

### 1-Minute Setup

```bash
# Clone the repository
git clone <repository-url>
cd llm-search-backend

# Copy environment template
cp .env.example .env

# Start all services
make quick-start

# Test the API
curl "http://localhost:8000/api/v1/search?query=latest AI developments"
```

### Full Development Setup

```bash
# Install dependencies
make install

# Set up environment variables
make setup-env

# Start services
make docker-up

# Run initial setup
make setup-db
make health-check

# Run tests
make test
```

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │────│   API Gateway   │────│  Rate Limiter   │
│     (NGINX)     │    │    (FastAPI)    │    │    (Redis)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                    ┌─────────────────┐
                    │    Pipeline     │
                    │  Orchestrator   │
                    │   (AsyncIO)     │
                    └─────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │   Query     │    │   Search    │    │  Content    │
    │ Enhancement │    │   Engine    │    │  Fetcher    │
    │             │    │             │    │             │
    │ - Google    │    │ - Brave API │    │ - ZenRows   │
    │   Auto      │    │ - Bing API  │    │ - Smart     │
    │ - Patterns  │    │ - Parallel  │    │   Extract   │
    └─────────────┘    └─────────────┘    └─────────────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                ▼
                    ┌─────────────────┐
                    │      LLM        │
                    │    Analyzer     │
                    │                 │
                    │ - Ollama Local  │
                    │ - Fast Models   │
                    │ - Synthesis     │
                    └─────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │    Cache    │ │  Database   │ │ Monitoring  │
        │   (Redis)   │ │(PostgreSQL) │ │  & Alerts   │
        └─────────────┘ └─────────────┘ └─────────────┘
```

## 📁 Project Structure

```
llm-search-backend/
├── app/
│   ├── main.py                     # FastAPI application entry
│   ├── config/
│   │   ├── settings.py             # Environment configuration
│   │   └── logging_config.py       # Logging setup
│   ├── api/
│   │   ├── dependencies.py         # FastAPI dependencies
│   │   ├── middleware.py           # Custom middleware
│   │   └── endpoints/
│   │       ├── search.py           # Main search endpoint
│   │       ├── health.py           # Health checks
│   │       └── admin.py            # Admin endpoints
│   ├── core/
│   │   ├── pipeline.py             # Main pipeline orchestrator
│   │   ├── exceptions.py           # Custom exceptions
│   │   ├── security.py             # Security utilities
│   │   └── monitoring.py           # System monitoring
│   ├── services/
│   │   ├── query_enhancer.py       # Query enhancement service
│   │   ├── search_engine.py        # Multi-search engine
│   │   ├── content_fetcher.py      # ZenRows integration
│   │   ├── llm_analyzer.py         # LLM analysis service
│   │   ├── cache_service.py        # Caching layer
│   │   └── cost_tracker.py         # Cost monitoring
│   ├── models/
│   │   ├── requests.py             # API request models
│   │   ├── responses.py            # API response models
│   │   └── internal.py             # Internal data models
│   ├── utils/
│   │   ├── text_processing.py      # Text cleaning utilities
│   │   ├── url_utils.py            # URL handling
│   │   ├── validators.py           # Input validation
│   │   └── circuit_breaker.py      # Circuit breaker pattern
│   └── database/
│       ├── connection.py           # DB connection setup
│       ├── models.py               # SQLAlchemy models
│       └── repositories.py         # Data access layer
├── tests/
│   ├── conftest.py                 # Pytest configuration
│   ├── unit/                       # Unit tests
│   ├── integration/                # Integration tests
│   └── load/                       # Load tests
├── scripts/
│   ├── setup_database.py          # Database initialization
│   ├── setup_ollama.py             # LLM model setup
│   ├── health_check.py             # System health monitoring
│   └── deployment/
│       ├── deploy.sh               # Deployment script
│       └── backup.sh               # Backup script
├── docker/
│   ├── Dockerfile                 # Main application container
│   ├── Dockerfile.nginx           # NGINX container
│   ├── docker-compose.yml         # Development setup
│   ├── docker-compose.prod.yml    # Production setup
│   └── nginx.conf                 # NGINX configuration
├── kubernetes/                    # K8s deployment manifests
├── docs/                          # Documentation
├── alembic/                       # Database migrations
├── .env.example                   # Environment variables template
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Project configuration
└── Makefile                       # Common commands
```

## 🔌 API Documentation

### Main Search Endpoint

**POST** `/api/v1/search`

#### Request
```json
{
  "query": "What are the latest developments in AI?",
  "max_results": 8,
  "include_sources": true
}
```

#### Response
```json
{
  "query": "What are the latest developments in AI?",
  "answer": "Recent developments in AI include breakthrough advances in large language models, improved multimodal capabilities, and significant progress in AI alignment research...",
  "sources": [
    "https://example.com/ai-news-1",
    "https://example.com/ai-research-2"
  ],
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
- `GET /docs` - Interactive API documentation

## 🔑 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# API Keys
BRAVE_SEARCH_API_KEY=your_brave_api_key
BING_SEARCH_API_KEY=your_bing_api_key
ZENROWS_API_KEY=your_zenrows_api_key

# Database
DATABASE_URL=postgresql+asyncpg://searchuser:searchpass@localhost:5432/searchdb

# Redis Cache
REDIS_URL=redis://localhost:6379/0

# LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama2:7b

# Performance Settings
WORKER_COUNT=4
CACHE_TTL=3600
MAX_CONCURRENT_REQUESTS=100
REQUEST_TIMEOUT=30

# Security
SECRET_KEY=your_secret_key_here
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
```

### API Key Setup

#### 1. Brave Search API
1. Sign up at [Brave Search API](https://api.search.brave.com/)
2. Get your API key from the dashboard
3. Add to `.env`: `BRAVE_SEARCH_API_KEY=your_key`

#### 2. Bing Search API
1. Create account at [Azure Cognitive Services](https://portal.azure.com/)
2. Create "Bing Search v7" resource
3. Add keys to `.env`: `BING_SEARCH_API_KEY=your_key`

#### 3. ZenRows API
1. Sign up at [ZenRows](https://www.zenrows.com/)
2. Get API key from dashboard
3. Add to `.env`: `ZENROWS_API_KEY=your_key`

## 🐳 Docker Deployment

### Development
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production
```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d

# Scale API service
docker-compose -f docker-compose.prod.yml up -d --scale api=3

# Health check
curl http://localhost/health
```

### Kubernetes Deployment
```bash
# Deploy to Kubernetes
kubectl apply -f kubernetes/

# Check status
kubectl get pods -n llm-search

# View logs
kubectl logs -f deployment/api -n llm-search
```

## 🛠️ Development

### Available Commands

```bash
make help              # Show all available commands
make dev               # Start development server
make install           # Install dependencies
make test              # Run all tests
make test-unit         # Run unit tests only
make test-integration  # Run integration tests
make test-load         # Run load tests
make lint              # Run code linting
make format            # Format code
make type-check        # Run type checking
make docker-up         # Start all services
make docker-down       # Stop all services
make docker-logs       # View logs
make db-migrate        # Run database migrations
make db-upgrade        # Upgrade database
make db-downgrade      # Downgrade database
make clean             # Clean temporary files
make setup-env         # Setup environment
make health-check      # Run health checks
```

### Development Workflow

1. **Setup Development Environment**
   ```bash
   make install
   make setup-env
   make docker-up
   ```

2. **Make Changes & Test**
   ```bash
   make test
   make lint
   make type-check
   ```

3. **Test Integration**
   ```bash
   make test-integration
   make health-check
   ```

4. **Performance Testing**
   ```bash
   make test-load
   ```

## 🧪 Testing

### Test Suite Coverage

- **Unit Tests**: Individual service testing
- **Integration Tests**: End-to-end pipeline testing
- **Load Tests**: Performance and scalability
- **API Tests**: Endpoint validation
- **Database Tests**: Data persistence and queries

### Running Tests

```bash
# All tests
make test

# Specific test categories
make test-unit
make test-integration
make test-load

# With coverage
make test-coverage

# Specific test file
pytest tests/unit/test_query_enhancer.py -v
```

## 📊 Monitoring & Observability

### Health Checks
- `/health` - Basic service health
- `/health/detailed` - Detailed component status
- Database connectivity
- Redis connectivity
- Ollama service status
- External API availability

### Metrics
- Request count and latency
- Cache hit/miss ratios
- LLM processing times
- Cost tracking per request
- Error rates by service
- Memory and CPU usage

### Logging
- Structured JSON logging
- Request/response logging
- Error tracking with stack traces
- Performance metrics
- Cost tracking

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

## 📈 Performance & Scaling

### Performance Tuning
- Adjust worker counts in Docker
- Tune cache TTL values
- Optimize LLM model size
- Implement request queuing
- Configure connection pools

### Horizontal Scaling
- Use Docker Swarm or Kubernetes
- Add load balancer (NGINX included)
- Scale API service instances
- Use Redis Cluster for caching
- Database read replicas

### Benchmarks
- **Target Response Time**: 3-8 seconds
- **Throughput**: 100+ concurrent requests
- **Cache Hit Rate**: 70%+
- **Uptime**: 99.9%

## 🔒 Security

### API Security
- Rate limiting per user/IP
- Request size limits
- Input validation and sanitization
- API key authentication (extensible)
- CORS configuration

### Production Security
- Use secrets management
- Enable HTTPS/TLS
- Network isolation
- Regular security updates
- Dependency vulnerability scanning

### Data Privacy
- No persistent storage of user queries
- Configurable data retention
- API key encryption
- Audit logging

## 💰 Cost Management

### Cost Tracking
- Per-request cost calculation
- Daily/monthly budget monitoring
- API usage analytics
- Cost optimization recommendations

### Budget Controls
- Request rate limiting
- Cache-first strategies
- Model selection optimization
- Alert thresholds

## 📚 Additional Resources

### Documentation
- [API Documentation](./docs/api_documentation.md)
- [Deployment Guide](./docs/deployment_guide.md)
- [Performance Tuning](./docs/performance_tuning.md)
- [Troubleshooting Guide](./docs/troubleshooting.md)

### External Documentation
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

### Code Standards
- Follow PEP 8 style guidelines
- Add type hints to all functions
- Write comprehensive tests
- Update documentation
- Add docstrings to all classes/functions

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🎯 Roadmap

### Phase 1 (Completed)
- ✅ Core pipeline implementation
- ✅ Multi-search engine integration
- ✅ LLM analysis and synthesis
- ✅ Caching and optimization
- ✅ Docker deployment

### Phase 2 (In Progress)
- 🔄 Advanced query understanding
- 🔄 Multi-language support
- 🔄 Enhanced monitoring
- 🔄 Cost optimization

### Phase 3 (Planned)
- 📋 Real-time search updates
- 📋 Custom model fine-tuning
- 📋 Advanced analytics dashboard
- 📋 Enterprise features

---

**Ready to get started?** Run `make quick-start` and follow the setup instructions!

For questions or support, please open an issue or check our [documentation](./docs/).
