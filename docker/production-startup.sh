#!/bin/bash
# docker/production-startup.sh - FINAL PRODUCTION VERSION

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
        if curl -fs "$url" >/dev/null 2>&1; then
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

# Start Ollama service in background
start_ollama() {
    log "🤖 Starting Ollama service..."
    su ollama -c "OLLAMA_HOST=0.0.0.0:11434 OLLAMA_MODELS=/home/ollama/.ollama/models ollama serve" &
    OLLAMA_PID=$!

    # Wait for Ollama API to be ready
    if wait_for_service "Ollama" "http://localhost:11434/api/version" 30; then
        log "📥 Checking for llama2:7b model..."

        if su ollama -c "ollama list | grep 'llama2:7b'" >/dev/null 2>&1; then
            log "✅ Model llama2:7b already available!"
        else
            log "📥 Pulling llama2:7b model (~5-10 min)..."
            if timeout 900 su ollama -c "ollama pull llama2:7b" 2>&1; then
                log "✅ Model llama2:7b pulled successfully!"
            else
                log "⚠️ Model pull failed — continuing with startup anyway"
            fi
        fi
    else
        log "❌ Ollama failed to start properly"
        return 1
    fi
}

# Run the one-time setup script (migrations + optional seeding)
run_setup() {
    log "⚙️ Running setup.sh..."
    if bash /app/docker/setup.sh; then
        log "✅ Setup completed"
    else
        log "⚠️ Setup failed, continuing with application startup"
    fi
}

# Start the FastAPI app
start_app() {
    log "🌐 Launching FastAPI application (Production Mode)..."
    exec su appuser -c "uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 4 \
        --access-log \
        --log-level info"
}

# Graceful shutdown handler
cleanup() {
    log "🧹 Shutting down services..."

    if [ ! -z "$OLLAMA_PID" ] && kill -0 $OLLAMA_PID 2>/dev/null; then
        log "🛑 Stopping Ollama service..."
        kill -TERM $OLLAMA_PID 2>/dev/null || true
        for i in {1..10}; do
            if ! kill -0 $OLLAMA_PID 2>/dev/null; then
                break
            fi
            sleep 1
        done
        kill -KILL $OLLAMA_PID 2>/dev/null || true
    fi

    log "✅ Cleanup completed"
    exit 0
}

# Set traps
trap cleanup SIGTERM SIGINT SIGQUIT

# Run startup sequence
main() {
    log "🎬 Production startup initiated..."
    start_ollama || log "⚠️ Ollama setup failed or incomplete"
    run_setup
    log "🚀 Starting main application process..."
    start_app
}

main "$@"
