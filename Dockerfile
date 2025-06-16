# Dockerfile - Fixed version with robust package installation
FROM python:3.11-slim as builder

# Build arguments
ARG BUILDTIME
ARG VERSION  
ARG REVISION

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install build dependencies with retry logic and proper error handling
RUN set -ex && \
    apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libc6-dev \
        make \
        curl \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
        && apt-get autoremove -y

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install wheel for faster builds
RUN pip install --upgrade pip setuptools wheel

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies (minimal set)
RUN set -ex && \
    apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
        && apt-get autoremove -y

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user with specific UID/GID
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -d /app -s /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy application code with proper ownership
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser scripts/ ./scripts/

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data /app/tmp && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Add comprehensive labels
LABEL org.opencontainers.image.title="LLM Search Backend" \
      org.opencontainers.image.description="Production-ready LLM Search Backend" \
      org.opencontainers.image.version="${VERSION:-latest}" \
      org.opencontainers.image.created="${BUILDTIME}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.source="https://github.com/yourusername/llm-search-backend" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="LLM Search Backend Team"

# Enhanced health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Use exec form for proper signal handling
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
