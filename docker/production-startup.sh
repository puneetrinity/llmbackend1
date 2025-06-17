#!/bin/bash
# docker/production-startup.sh - FINAL FIXED VERSION

set -e

echo "🚀 Starting LLM Search Backend (Production Mode)"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check if a service is ready
wait_for_service() {
    local service=$1
    local url=$2
    local max_attempts=${3:-60}
    local attempt=1
    
    log "⏳ Waiting for $service to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$url" >/dev/null 2>&1; then
            log "✅ $service is ready!"
            return 0
        fi
        
        if [ $((attempt % 15)) -eq 0 ]; then
            log "🔄 Still waiting for $service... ($attempt/$max_attempts)"
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log "❌ $service failed to become ready after $max_attempts attempts"
    return 1
}

# Function to start Ollama service
start_ollama() {
    log "🤖 Starting Ollama service..."
    
    # Start Ollama in background as ollama user
    su ollama -c "OLLAMA_HOST=0.0.0.0:11434 OLLAMA_MODELS=/home/ollama/.ollama/models ollama serve" &
    OLLAMA_PID=$!
    
    # Wait for Ollama to be ready
    if wait_for_service "Ollama" "http://localhost:11434/api/version" 30; then
        log "📥 Checking for llama2:7b model..."
        
        # Check if model already exists
        if su ollama -c "ollama list | grep llama2:7b" >/dev/null 2>&1; then
            log "✅ Model llama2:7b already available!"
            return 0
        fi
        
        log "📥 Pulling llama2:7b model (first time setup, ~5-10 minutes)..."
        
        # Pull the model with timeout
        if timeout 900 su ollama -c "ollama pull llama2:7b" 2>&1; then
            log "✅ Model llama2:7b pulled successfully!"
            return 0
        else
            log "⚠️ Model pull failed, but continuing startup"
            return 0
        fi
    else
        log "❌ Ollama failed to start properly"
        return 1
    fi
}

# Function to run database migrations
run_migrations() {
    log "🔄 Running database migrations..."
    
    # Skip migrations to avoid circular import issues for now
    # They'll run automatically when the app starts
    log "ℹ️ Skipping migrations - will run automatically in app startup"
}

# Function to start the FastAPI application
start_app() {
    log "🌐 Starting FastAPI application (Production Mode)..."
    
    # FIXED: Use correct uvicorn parameters
    exec su appuser -c "uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 4 \
        --access-log \
        --log-level info"
}

# Function to handle cleanup
cleanup() {
    log "🧹 Shutting down services..."
    
    # Kill Ollama process if it exists
    if [ ! -z "$OLLAMA_PID" ] && kill -0 $OLLAMA_PID 2>/dev/null; then
        log "🛑 Stopping Ollama service..."
        kill -TERM $OLLAMA_PID 2>/dev/null || true
        
        # Wait for graceful shutdown
        for i in {1..10}; do
            if ! kill -0 $OLLAMA_PID 2>/dev/null; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        kill -KILL $OLLAMA_PID 2>/dev/null || true
    fi
    
    log "✅ Cleanup completed"
    exit 0
}

# Set up signal handlers for graceful shutdown
trap cleanup SIGTERM SIGINT SIGQUIT

# Main execution function
main() {
    log "🎬 Starting production deployment sequence..."
    
    # Start Ollama service (in background)
    if start_ollama; then
        log "✅ Ollama service setup completed"
    else
        log "⚠️ Ollama setup had issues, but continuing with app startup"
    fi
    
    # Run database migrations (simplified)
    run_migrations
    
    # Start the main FastAPI application (this becomes the main process)
    log "🚀 Starting main application..."
    start_app
}

# Execute main function
main "$@"
