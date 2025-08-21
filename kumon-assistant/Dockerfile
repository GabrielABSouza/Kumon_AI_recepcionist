# Railway-optimized Production Dockerfile for Kumon Assistant
# Phase 3 - Day 6: Production Configuration
# Compliance: Business hours 8h-12h, 14h-18h | Response time ≤5s | Rate limits 50 req/min

# Stage 1: Python dependencies builder
FROM python:3.11-slim as builder

# Set build environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies including crypto support
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    libffi-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create wheels directory
WORKDIR /wheels

# Copy requirements first for better caching
COPY requirements-production.txt .

# Build wheels for all dependencies
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements-production.txt

# Stage 2: Runtime image
FROM python:3.11-slim

# Security: Run as non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

# Set runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUTF8=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    # Application settings
    PORT=8000 \
    # Performance optimization
    WEB_CONCURRENCY=2 \
    # Railway-specific
    RAILWAY_ENVIRONMENT=production

# Install runtime dependencies including system libs for cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create application directory
WORKDIR /app

# Copy wheels and requirements from builder
COPY --from=builder /wheels /wheels
COPY --from=builder /wheels/requirements-production.txt /tmp/requirements-production.txt

# Install Python dependencies from wheels and requirements
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
    $(find /wheels -name "*.whl" | tr '\n' ' ') \
    && pip install --no-cache-dir -r /tmp/requirements-production.txt || true \
    && rm -rf /wheels /tmp/requirements-production.txt

# Copy application code
COPY --chown=appuser:appuser app/ ./app/

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data /app/cache /app/temp \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app

# Security hardening
RUN find /app -type f -name "*.py" -exec chmod 644 {} \; \
    && find /app -type d -exec chmod 755 {} \;

# Switch to non-root user
USER appuser

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/v1/health || exit 1

# Expose port (Railway will override this)
EXPOSE ${PORT}

# Railway uses PORT environment variable
# Start FastAPI with optimized settings for production
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --loop uvloop --access-log --log-level warning"]