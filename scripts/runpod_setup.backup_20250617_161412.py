# scripts/runpod_setup.py
"""
RunPod deployment setup script
Handles database initialization and service startup for RunPod environment
"""

import asyncio
import os
import sys
import logging
import time
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.config.settings import settings
from app.database.connection import db_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_database_connection(max_retries=5, delay=5):
    """Check database connection with retries"""
    for attempt in range(max_retries):
        try:
            logger.info(f"🔍 Checking database connection (attempt {attempt + 1}/{max_retries})...")
            
            # Test connection
            async with db_manager.get_session() as session:
                await session.execute("SELECT 1")
            
            logger.info("✅ Database connection successful!")
            return True
            
        except Exception as e:
            logger.warning(f"❌ Database connection failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"⏳ Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error("💥 Database connection failed after all retries")
                return False
    
    return False

async def initialize_database():
    """Initialize database tables and initial data"""
    try:
        logger.info("🔧 Initializing database schema...")
        
        # Initialize database connection
        await db_manager.initialize()
        
        # Create tables
        await db_manager.create_tables()
        
        # Create initial admin user if specified
        admin_email = os.getenv("ADMIN_EMAIL")
        if admin_email:
            await create_admin_user(admin_email)
        
        logger.info("✅ Database initialization completed!")
        
    except Exception as e:
        logger.error(f"💥 Database initialization failed: {e}")
        raise

async def create_admin_user(email: str):
    """Create admin user for the system"""
    try:
        from app.database.repositories import UserRepository
        
        async with db_manager.get_session() as session:
            user_repo = UserRepository(session)
            
            # Check if admin user already exists
            existing_user = await user_repo.get_user_by_identifier(email)
            if existing_user:
                logger.info(f"👤 Admin user already exists: {email}")
                return
            
            # Create admin user
            admin_user = await user_repo.create_user(
                user_identifier=email,
                user_type="admin",
                api_key=f"admin_{int(time.time())}"
            )
            await session.commit()
            
            logger.info(f"👑 Created admin user: {email}")
            logger.info(f"🔑 Admin API key: {admin_user.api_key}")
            
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")

async def health_check():
    """Perform comprehensive health check"""
    try:
        logger.info("🏥 Performing health check...")
        
        # Check database
        db_healthy = await check_database_connection(max_retries=1)
        
        # Check environment variables
        required_vars = [
            "DATABASE_URL",
            "BRAVE_SEARCH_API_KEY", 
            "BING_SEARCH_API_KEY",
            "ZENROWS_API_KEY"
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.warning(f"⚠️  Missing environment variables: {missing_vars}")
        else:
            logger.info("✅ All required environment variables present")
        
        # Overall health
        overall_healthy = db_healthy and not missing_vars
        
        if overall_healthy:
            logger.info("🎉 System is healthy and ready!")
        else:
            logger.error("💥 System health check failed")
        
        return overall_healthy
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False

def print_system_info():
    """Print system information for debugging"""
    logger.info("📋 System Information:")
    logger.info(f"  🐍 Python: {sys.version}")
    logger.info(f"  🌐 Database URL: {settings.DATABASE_URL[:50]}...")
    logger.info(f"  ⚡ Redis URL: {settings.REDIS_URL}")
    logger.info(f"  🤖 Ollama Host: {settings.OLLAMA_HOST}")
    logger.info(f"  🔧 Debug Mode: {settings.DEBUG}")
    logger.info(f"  📊 Log Level: {settings.LOG_LEVEL}")

async def runpod_startup():
    """Main RunPod startup sequence"""
    logger.info("🚀 Starting LLM Search Backend on RunPod...")
    
    print_system_info()
    
    # Step 1: Check database connection
    if not await check_database_connection():
        logger.error("💥 Cannot proceed without database connection")
        sys.exit(1)
    
    # Step 2: Initialize database
    await initialize_database()
    
    # Step 3: Health check
    if not await health_check():
        logger.error("💥 Health check failed")
        sys.exit(1)
    
    logger.info("🎉 RunPod startup completed successfully!")
    logger.info("🌐 Ready to start API server...")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RunPod setup and management")
    parser.add_argument("--startup", action="store_true", help="Run full startup sequence")
    parser.add_argument("--check-db", action="store_true", help="Check database connection only")
    parser.add_argument("--init-db", action="store_true", help="Initialize database only")
    parser.add_argument("--health", action="store_true", help="Run health check only")
    parser.add_argument("--admin-email", type=str, help="Create admin user with email")
    
    args = parser.parse_args()
    
    if args.check_db:
        success = asyncio.run(check_database_connection())
        sys.exit(0 if success else 1)
    elif args.init_db:
        asyncio.run(initialize_database())
    elif args.health:
        success = asyncio.run(health_check())
        sys.exit(0 if success else 1)
    elif args.admin_email:
        os.environ["ADMIN_EMAIL"] = args.admin_email
        asyncio.run(runpod_startup())
    elif args.startup:
        asyncio.run(runpod_startup())
    else:
        parser.print_help()

# scripts/runpod_startup.sh
#!/bin/bash

# RunPod startup script for LLM Search Backend
set -e

echo "🚀 Starting LLM Search Backend on RunPod..."

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check if a service is running
check_service() {
    local service=$1
    local host=$2
    local port=$3
    local max_attempts=${4:-30}
    local attempt=1
    
    log "⏳ Waiting for $service to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$host:$port" >/dev/null 2>&1; then
            log "✅ $service is ready!"
            return 0
        fi
        
        log "🔄 Attempt $attempt/$max_attempts - $service not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log "❌ $service failed to become ready after $max_attempts attempts"
    return 1
}

# Function to start Ollama in background
start_ollama() {
    log "🤖 Starting Ollama service..."
    
    # Start Ollama server in background
    ollama serve &
    OLLAMA_PID=$!
    
    # Wait for Ollama to be ready
    if check_service "Ollama" "http://localhost" "11434"; then
        log "📥 Pulling LLM model..."
        ollama pull llama2:7b || {
            log "⚠️  Failed to pull model, continuing anyway..."
        }
    else
        log "❌ Ollama failed to start"
        return 1
    fi
}

# Function to check environment variables
check_environment() {
    log "🔍 Checking environment variables..."
    
    required_vars=(
        "DATABASE_URL"
        "BRAVE_SEARCH_API_KEY"
        "BING_SEARCH_API_KEY"
        "ZENROWS_API_KEY"
    )
    
    missing_vars=()
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log "❌ Missing required environment variables:"
        printf '%s\n' "${missing_vars[@]}"
        return 1
    else
        log "✅ All required environment variables are set"
        return 0
    fi
}

# Function to setup database
setup_database() {
    log "🗃️ Setting up database..."
    
    # Run database setup
    python scripts/runpod_setup.py --startup || {
        log "❌ Database setup failed"
        return 1
    }
    
    log "✅ Database setup completed"
}

# Function to start the main application
start_application() {
    log "🌐 Starting API server..."
    
    # Start the FastAPI application
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 1 \
        --access-log \
        --log-level info
}

# Function to cleanup on exit
cleanup() {
    log "🧹 Cleaning up..."
    if [[ -n "$OLLAMA_PID" ]]; then
        kill $OLLAMA_PID 2>/dev/null || true
    fi
}

# Set trap for cleanup
trap cleanup EXIT

# Main execution
main() {
    log "🎬 Starting RunPod deployment sequence..."
    
    # Step 1: Check environment
    if ! check_environment; then
        log "💥 Environment check failed"
        exit 1
    fi
    
    # Step 2: Start Ollama
    if ! start_ollama; then
        log "💥 Ollama startup failed"
        exit 1
    fi
    
    # Step 3: Setup database
    if ! setup_database; then
        log "💥 Database setup failed"
        exit 1
    fi
    
    # Step 4: Start application
    log "🎉 All services ready! Starting application..."
    start_application
}

# Run main function
main "$@"

# Dockerfile.runpod
# Optimized Dockerfile for RunPod deployment
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg2 \
    software-properties-common \
    postgresql-client \
    redis-tools \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Copy RunPod specific files
COPY scripts/runpod_startup.sh ./startup.sh
COPY scripts/runpod_setup.py ./scripts/

# Make scripts executable
RUN chmod +x startup.sh
RUN chmod +x scripts/runpod_setup.py

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Use startup script as entrypoint
CMD ["./startup.sh"]

# docker-compose.runpod.yml
# Docker Compose configuration optimized for RunPod
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.runpod
    ports:
      - "8000:8000"
      - "11434:11434"  # Ollama port
    environment:
      # Database connection (use external DB)
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL:-redis://localhost:6379}
      
      # API Keys
      - BRAVE_SEARCH_API_KEY=${BRAVE_SEARCH_API_KEY}
      - BING_SEARCH_API_KEY=${BING_SEARCH_API_KEY}
      - BING_AUTOSUGGEST_API_KEY=${BING_AUTOSUGGEST_API_KEY}
      - ZENROWS_API_KEY=${ZENROWS_API_KEY}
      
      # Application settings
      - OLLAMA_HOST=http://localhost:11434
      - DEBUG=${DEBUG:-false}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - SECRET_KEY=${SECRET_KEY}
      
      # Performance settings
      - RATE_LIMIT_PER_MINUTE=${RATE_LIMIT_PER_MINUTE:-100}
      - DAILY_BUDGET_USD=${DAILY_BUDGET_USD:-200.0}
      - MAX_SOURCES_PER_QUERY=${MAX_SOURCES_PER_QUERY:-8}
      
      # Admin settings
      - ADMIN_EMAIL=${ADMIN_EMAIL}
      
    volumes:
      # Mount RunPod volume for persistence (if available)
      - ${RUNPOD_VOLUME_PATH:-./data}:/app/data
      - ${RUNPOD_VOLUME_PATH:-./logs}:/app/logs
    
    restart: unless-stopped
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s

# .env.runpod.example
# RunPod Environment Variables Template

# Database Configuration (use external managed database)
DATABASE_URL=postgresql://postgres:password@db.supabase.co:5432/postgres

# Cache Configuration (use external Redis or disable)
REDIS_URL=redis://username:password@redis-cloud-endpoint:12345
# Or disable Redis and use memory cache only:
# REDIS_URL=

# API Keys (REQUIRED)
BRAVE_SEARCH_API_KEY=your_brave_search_api_key
BING_SEARCH_API_KEY=your_bing_search_api_key
BING_AUTOSUGGEST_API_KEY=your_bing_autosuggest_api_key
ZENROWS_API_KEY=your_zenrows_api_key

# Application Settings
SECRET_KEY=your-super-secret-key-change-this-in-production
DEBUG=false
LOG_LEVEL=INFO

# Performance Settings
RATE_LIMIT_PER_MINUTE=100
DAILY_BUDGET_USD=200.0
MAX_SOURCES_PER_QUERY=8
MAX_CONCURRENT_REQUESTS=50

# Cost Controls
ZENROWS_MONTHLY_BUDGET=300.0

# Admin Configuration
ADMIN_EMAIL=admin@yourdomain.com

# Service Configuration
OLLAMA_HOST=http://localhost:11434
LLM_MODEL=llama2:7b
LLM_MAX_TOKENS=500
LLM_TEMPERATURE=0.1

# Cache Settings (when using Redis)
CACHE_TTL_FINAL_RESPONSE=14400
MEMORY_CACHE_SIZE=1000

# RunPod Specific
RUNPOD_VOLUME_PATH=/runpod-volume
