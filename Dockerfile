# Dockerfile.fast - Optimized for fast builds and CI/CD
FROM python:3.11-slim

# Build arguments
ARG BUILDTIME
ARG VERSION
ARG REVISION

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install only runtime dependencies (minimal approach)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install Python dependencies from PyPI (prefer binary wheels)
# Use specific versions that have pre-built wheels available
RUN pip install --upgrade pip wheel && \
    pip install --only-binary=:all: \
        fastapi==0.104.1 \
        uvicorn[standard]==0.24.0 \
        pydantic==2.5.0 \
        pydantic-settings==2.1.0 \
        httpx==0.25.2 \
        requests==2.31.0 \
        sqlalchemy==2.0.23 \
        asyncpg==0.29.0 \
        redis==5.0.1 \
        beautifulsoup4==4.12.2 \
        python-dotenv==1.0.0 \
        python-multipart==0.0.6 \
        python-dateutil==2.8.2 \
        structlog==23.2.0 \
        cryptography \
        python-jose[cryptography] \
        passlib[bcrypt] \
    || pip install \
        fastapi==0.104.1 \
        uvicorn[standard]==0.24.0 \
        pydantic==2.5.0 \
        pydantic-settings==2.1.0 \
        httpx==0.25.2 \
        requests==2.31.0 \
        sqlalchemy==2.0.23 \
        asyncpg==0.29.0 \
        redis==5.0.1 \
        beautifulsoup4==4.12.2 \
        python-dotenv==1.0.0 \
        python-multipart==0.0.6 \
        python-dateutil==2.8.2 \
        structlog==23.2.0 \
        cryptography \
        python-jose[cryptography] \
        passlib[bcrypt]

# Copy application code
COPY --chown=appuser:appuser app/ ./app/

# Create necessary directories
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Labels
LABEL org.opencontainers.image.title="LLM Search Backend" \
      org.opencontainers.image.version="${VERSION:-latest}"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
