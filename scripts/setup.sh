#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    local missing_deps=()
    
    if ! command_exists docker; then
        missing_deps+=("docker")
    fi
    
    if ! command_exists docker-compose; then
        missing_deps+=("docker-compose")
    fi
    
    if ! command_exists python3; then
        missing_deps+=("python3")
    fi
    
    if ! command_exists curl; then
        missing_deps+=("curl")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        error "Missing required dependencies: ${missing_deps[*]}"
        error "Please install the missing dependencies and run this script again."
        exit 1
    fi
    
    log "All prerequisites are installed."
}

# Setup environment files
setup_environment() {
    log "Setting up environment files..."
    
    # Development environment
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            log "Created .env from .env.example"
        else
            warn ".env.example not found. You'll need to create .env manually."
        fi
    else
        info ".env already exists, skipping..."
    fi
    
    # Production environment
    if [ ! -f .env.prod ]; then
        if [ -f .env.prod.example ]; then
            cp .env.prod.example .env.prod
            log "Created .env.prod from .env.prod.example"
            warn "Please edit .env.prod with your production values!"
        else
            warn ".env.prod.example not found."
        fi
    else
        info ".env.prod already exists, skipping..."
    fi
}

# Setup Python virtual environment
setup_python_env() {
    log "Setting up Python virtual environment..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log "Created Python virtual environment"
    else
        info "Virtual environment already exists, skipping..."
    fi
    
    # Activate virtual environment and install dependencies
    source venv/bin/activate
    pip install --upgrade pip
    
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt
        log "Installed Python dependencies"
    fi
    
    if [ -f requirements-test.txt ]; then
        pip install -r requirements-test.txt
        log "Installed test dependencies"
    fi
}

# Setup Docker environment
setup_docker() {
    log "Setting up Docker environment..."
    
    # Build Docker images
    docker-compose build
    log "Built Docker images"
    
    # Create necessary directories
    mkdir -p logs backups nginx/ssl monitoring/grafana/dashboards monitoring/grafana/datasources
    log "Created necessary directories"
    
    # Set proper permissions
    chmod +x scripts/*.sh 2>/dev/null || true
    log "Set script permissions"
}

# Initialize database
init_database() {
    log "Initializing database..."
    
    # Start database services
    docker-compose up -d db redis
    
    # Wait for database to be ready
    log "Waiting for database to be ready..."
    sleep 30
    
    # Run database migrations
    if [ -f scripts/manage_migrations.py ]; then
        python scripts/manage_migrations.py init
        log "Database migrations completed"
    else
        warn "Migration script not found, skipping database initialization"
    fi
}

# Setup Ollama
setup_ollama() {
    log "Setting up Ollama..."
    
    # Start Ollama service
    docker-compose up -d ollama
    
    # Wait for Ollama to be ready
    log "Waiting for Ollama to be ready..."
    sleep 60
    
    # Pull required model
    docker-compose exec ollama ollama pull llama2:7b || warn "Failed to pull LLM model, you may need to do this manually"
    
    log "Ollama setup completed"
}

# Verify installation
verify_installation() {
    log "Verifying installation..."
    
    # Start all services
    docker-compose up -d
    
    # Wait for services to start
    sleep 30
    
    # Test API health
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        log "✅ API health check passed"
    else
        warn "⚠️  API health check failed"
    fi
    
    # Test database connection
    if docker-compose exec -T db psql -U searchuser -d searchdb -c "SELECT 1;" >/dev/null 2>&1; then
        log "✅ Database connection successful"
    else
        warn "⚠️  Database connection failed"
    fi
    
    # Test Redis connection
    if docker-compose exec -T redis redis-cli ping >/dev/null 2>&1; then
        log "✅ Redis connection successful"
    else
        warn "⚠️  Redis connection failed"
    fi
    
    log "Installation verification completed"
}

# Main setup function
main() {
    log "🚀 Starting LLM Search Backend setup..."
    
    check_prerequisites
    setup_environment
    setup_python_env
    setup_docker
    init_database
    setup_ollama
    verify_installation
    
    log "🎉 Setup completed successfully!"
    echo ""
    info "Next steps:"
    info "1. Edit .env and .env.prod with your API keys and configuration"
    info "2. Run 'make check-apis' to verify your API keys"
    info "3. Run 'make migrate-serpapi' to test SerpApi migration"
    info "4. Visit http://localhost:8000/docs to see the API documentation"
    echo ""
    info "Useful commands:"
    info "- make dev              # Start development server"
    info "- make docker-up        # Start all services"
    info "- make test            # Run tests"
    info "- make docker-logs     # View logs"
    info "- make help           # See all available commands"
}

# Run main function
main "$@"
