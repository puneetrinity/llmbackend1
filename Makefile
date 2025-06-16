# Makefile for LLM Search Backend with SerpApi Migration Support

.PHONY: help setup install dev test lint format clean docker-build docker-up docker-down docker-logs backup

# Default target
help:
	@echo "LLM Search Backend with SerpApi Migration - Available Commands:"
	@echo ""
	@echo "Setup & Development:"
	@echo "  setup          - Setup development environment"
	@echo "  install        - Install Python dependencies"
	@echo "  dev            - Run development server"
	@echo "  test           - Run tests"
	@echo "  lint           - Run code linting"
	@echo "  format         - Format code with black and isort"
	@echo ""
	@echo "SerpApi Migration Commands:"
	@echo "  migrate-serpapi      - Run SerpApi migration tests"
	@echo "  migrate-serpapi-docker - Run migration tests in Docker"
	@echo "  check-apis           - Check all API connections"
	@echo "  migrate-db-serpapi   - Apply SerpApi database migration"
	@echo "  migration-status     - Check migration status"
	@echo ""
	@echo "Docker Commands:"
	@echo "  docker-build   - Build Docker images"
	@echo "  docker-up      - Start all services"
	@echo "  docker-down    - Stop all services"
	@echo "  docker-logs    - View logs"
	@echo "  docker-clean   - Clean Docker resources"
	@echo ""
	@echo "Database Commands (Alembic):"
	@echo "  db-init        - Initialize database with migrations"
	@echo "  db-migrate     - Create new migration"
	@echo "  db-upgrade     - Apply pending migrations"
	@echo "  db-downgrade   - Downgrade to specific revision"
	@echo "  db-status      - Show current migration status"
	@echo "  db-history     - Show migration history"
	@echo "  db-validate    - Validate migration scripts"
	@echo "  db-backup      - Create database backup"
	@echo "  db-restore     - Restore database from backup"
	@echo ""
	@echo "Services Management:"
	@echo "  services-up    - Start support services (DB, Redis, Ollama)"
	@echo "  services-down  - Stop support services"
	@echo "  services-logs  - View service logs"

# Setup development environment
setup:
	@echo "Setting up development environment..."
	python -m venv venv
	@echo "Virtual environment created. Activate with:"
	@echo "  source venv/bin/activate  # Linux/Mac"
	@echo "  venv\\Scripts\\activate     # Windows"
	@echo "Then run: make install"

# Install dependencies
install:
	pip install --upgrade pip
	pip install -r requirements.txt
	@echo "Dependencies installed successfully!"

# Install development dependencies
install-dev: install
	pip install pytest pytest-asyncio pytest-cov pytest-mock
	pip install black isort flake8 mypy bandit
	@echo "Development dependencies installed!"

# Run development server
dev:
	@echo "Starting development server..."
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# SerpApi Migration Commands
migrate-serpapi:
	@echo "🔄 Running SerpApi migration tests..."
	python scripts/test_serpapi_migration.py

migrate-serpapi-docker:
	@echo "🔄 Running SerpApi migration tests in Docker..."
	docker-compose --profile test run --rm migration-test

check-apis:
	@echo "🔍 Checking all API connections..."
	python scripts/check_api_keys.py

migrate-db-serpapi:
	@echo "🗃️ Applying SerpApi database migration..."
	python scripts/manage_migrations.py upgrade
	@echo "✅ Database migration completed"

migration-status:
	@echo "📊 Checking migration status..."
	@python -c "import os; print('SERPAPI_API_KEY:', '✅ Set' if os.getenv('SERPAPI_API_KEY') else '❌ Missing'); print('BING_SEARCH_API_KEY:', '⚠️ Still present' if os.getenv('BING_SEARCH_API_KEY') else '✅ Removed'); print('BING_AUTOSUGGEST_API_KEY:', '⚠️ Still present' if os.getenv('BING_AUTOSUGGEST_API_KEY') else '✅ Removed')"

# Run tests
test:
	@echo "Running tests..."
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term

# Test database operations
test-db:
	@echo "Running database tests..."
	pytest tests/database/ -v

# Test SerpApi integration specifically
test-serpapi:
	@echo "Running SerpApi integration tests..."
	pytest tests/ -v -k "serpapi or search_engine"

# Run linting
lint:
	@echo "Running linting..."
	flake8 app tests --max-line-length=100 --ignore=E203,W503
	mypy app --ignore-missing-imports
	bandit -r app -f json -o security-report.json

# Format code
format:
	@echo "Formatting code..."
	black app tests --line-length=100
	isort app tests --profile=black

# Docker commands
docker-build:
	@echo "Building Docker images..."
	docker-compose build

docker-up:
	@echo "Starting all services..."
	docker-compose up -d

docker-up-with-tools:
	@echo "Starting all services with management tools..."
	docker-compose --profile tools up -d

docker-up-with-monitoring:
	@echo "Starting all services with monitoring..."
	docker-compose --profile tools --profile monitoring up -d

docker-down:
	@echo "Stopping all services..."
	docker-compose down

docker-logs:
	@echo "Viewing logs..."
	docker-compose logs -f

docker-logs-api:
	@echo "Viewing API logs..."
	docker-compose logs -f api

docker-clean:
	@echo "Cleaning Docker resources..."
	docker-compose down -v
	docker system prune -f

# Database commands (Alembic Integration)
db-init:
	@echo "Initializing database with migrations..."
	python scripts/manage_migrations.py init

db-init-docker:
	@echo "Initializing database in Docker..."
	docker-compose exec api python scripts/manage_migrations.py init

db-migrate:
	@echo "Creating new database migration..."
	@read -p "Enter migration message: " message; \
	python scripts/manage_migrations.py create "$$message"

db-upgrade:
	@echo "Upgrading database to latest migration..."
	python scripts/manage_migrations.py upgrade

db-downgrade:
	@echo "Downgrading database..."
	python scripts/manage_migrations.py downgrade $(REV)

db-status:
	@echo "Checking database migration status..."
	python scripts/manage_migrations.py current

db-history:
	@echo "Showing migration history..."
	python scripts/manage_migrations.py history

db-validate:
	@echo "Validating migration scripts..."
	python scripts/manage_migrations.py validate

db-backup:
	@echo "Creating database backup..."
	mkdir -p backups
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose exec -T db pg_dump -U searchuser searchdb > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql; \
	else \
		pg_dump -h localhost -U searchuser searchdb > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql; \
	fi
	@echo "Backup created in backups/ directory"

db-restore:
	@echo "Restoring database from backup..."
	@read -p "Enter backup file path: " filepath; \
	if [ -f "$$filepath" ]; then \
		if command -v docker-compose >/dev/null 2>&1; then \
			docker-compose exec -T db psql -U searchuser -d searchdb < "$$filepath"; \
		else \
			psql -h localhost -U searchuser -d searchdb < "$$filepath"; \
		fi; \
		echo "Database restored from $$filepath"; \
	else \
		echo "Backup file not found: $$filepath"; \
	fi

# Services management
services-up:
	@echo "Starting support services (DB, Redis, Ollama)..."
	docker-compose up -d db redis ollama

services-down:
	@echo "Stopping support services..."
	docker-compose stop db redis ollama

services-logs:
	@echo "Viewing service logs..."
	docker-compose logs -f db redis ollama

# Development utilities
install-ollama:
	@echo "Installing Ollama locally..."
	curl -fsSL https://ollama.ai/install.sh | sh
	ollama pull llama2:7b

# Cache management
clean-cache:
	@echo "Clearing application cache..."
	curl -X POST http://localhost:8000/api/v1/search/clear-cache || echo "Cache clear failed - is the API running?"

clear-redis:
	@echo "Clearing Redis cache..."
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose exec redis redis-cli FLUSHALL; \
	else \
		redis-cli FLUSHALL; \
	fi

# Clean up
clean:
	@echo "Cleaning temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf dist/
	rm -rf build/
	rm -f serpapi_migration_test_results.json

# Production deployment
deploy-prod:
	@echo "Deploying to production..."
	docker-compose -f docker-compose.yml --profile production up -d

# Quick development setup with SerpApi
quick-start-serpapi:
	@echo "Quick start with SerpApi setup..."
	cp .env.example .env
	@echo "✅ Environment file created (.env)"
	@echo ""
	@echo "⚠️  IMPORTANT: Add your SerpApi API key to .env file:"
	@echo "   SERPAPI_API_KEY=your_serpapi_key_here"
	@echo ""
	@echo "Next steps:"
	@echo "1. Get SerpApi key from https://serpapi.com/"
	@echo "2. Edit .env file with your API keys"
	@echo "3. Run: make docker-up"
	@echo "4. Run: make migrate-db-serpapi"
	@echo "5. Run: make migrate-serpapi-docker"
	@echo "6. Visit: http://localhost:8000/docs"

# Comprehensive migration workflow
migrate-complete:
	@echo "🚀 Running complete SerpApi migration workflow..."
	@echo ""
	@echo "Step 1: Checking current setup..."
	make migration-status
	@echo ""
	@echo "Step 2: Checking API connectivity..."
	make check-apis
	@echo ""
	@echo "Step 3: Applying database migrations..."
	make migrate-db-serpapi
	@echo ""
	@echo "Step 4: Running comprehensive tests..."
	make migrate-serpapi
	@echo ""
	@echo "✅ Migration workflow completed!"
	@echo "Check the test results and resolve any issues before production use."

# Development helpers
sample-request-serpapi:
	@echo "Making sample search request to test SerpApi integration..."
	curl -X POST http://localhost:8000/api/v1/search \
		-H "Content-Type: application/json" \
		-d '{"query": "SerpApi vs Bing Search API", "max_results": 5}' | jq '.'

health-check-serpapi:
	@echo "Checking system health after SerpApi migration..."
	curl -s http://localhost:8000/health/detailed | jq '.' || curl -s http://localhost:8000/health/detailed

cost-analysis-serpapi:
	@echo "Analyzing costs after SerpApi migration..."
	curl -s http://localhost:8000/api/v1/search/analytics/costs | jq '.' || curl -s http://localhost:8000/api/v1/search/analytics/costs

# Migration verification
verify-migration:
	@echo "🔍 Verifying SerpApi migration..."
	@echo ""
	@echo "1. Configuration check:"
	make migration-status
	@echo ""
	@echo "2. API connectivity:"
	make check-apis
	@echo ""
	@echo "3. Health check:"
	make health-check-serpapi
	@echo ""
	@echo "4. Sample request:"
	make sample-request-serpapi
	@echo ""
	@echo "5. Cost analysis:"
	make cost-analysis-serpapi

# Help for specific categories
help-migration:
	@echo "SerpApi Migration Commands:"
	@echo "  migrate-serpapi           - Run comprehensive migration tests"
	@echo "  migrate-serpapi-docker    - Run migration tests in Docker"
	@echo "  check-apis                - Check all API connections"
	@echo "  migrate-db-serpapi        - Apply database migration for SerpApi"
	@echo "  migration-status          - Check current migration status"
	@echo "  quick-start-serpapi       - Quick setup guide for SerpApi"
	@echo "  migrate-complete          - Run complete migration workflow"
	@echo "  verify-migration          - Verify migration success"
	@echo "  sample-request-serpapi    - Test with sample request"
	@echo "  health-check-serpapi      - Check system health"
	@echo "  cost-analysis-serpapi     - Analyze costs after migration"

# Variables for parameterized commands
REV ?= -1
ENV ?= development
