FROM python:3.11-slim AS builder

# Build arguments
ARG BUILDTIME="unknown"
ARG VERSION="latest"
ARG REVISION="unknown"

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install build dependencies with robust error handling
RUN apt-get clean && \
    apt-get autoclean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        build-essential && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim AS production

# Re-declare build arguments for this stage
ARG BUILDTIME="unknown"
ARG VERSION="latest"
ARG REVISION="unknown"

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies with robust error handling
RUN apt-get clean && \
    apt-get autoclean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        curl \
        wget \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Install Ollama with error handling
RUN curl -fsSL https://ollama.ai/install.sh | sh || \
    (echo "Ollama install failed, but continuing..." && true)

# Create users - appuser for app, ollama for ollama service
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    useradd -m -u 1001 ollama && \
    mkdir -p /home/ollama/.ollama && \
    chown -R ollama:ollama /home/ollama/.ollama

# Set working directory
WORKDIR /app

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create startup script
COPY docker/production-startup.sh /app/production-startup.sh
RUN chmod +x /app/production-startup.sh

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Change ownership to appuser (app files only)
RUN chown -R appuser:appuser /app

# Add labels for better image management
LABEL org.opencontainers.image.title="LLM Search Backend"
LABEL org.opencontainers.image.description="Production-ready LLM Search Backend with Ollama LLM support"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.created="${BUILDTIME}"
LABEL org.opencontainers.image.revision="${REVISION}"
LABEL org.opencontainers.image.source="https://github.com/yourusername/llm-search-backend"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose ports - FastAPI and Ollama
EXPOSE 8000 11434

# Use startup script for proper service orchestration
CMD ["/app/production-startup.sh"]
