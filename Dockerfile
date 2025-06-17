FROM python:3.11-slim as builder

# Build arguments
ARG BUILDTIME
ARG VERSION
ARG REVISION

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production

# Install runtime dependencies including Ollama requirements
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

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
