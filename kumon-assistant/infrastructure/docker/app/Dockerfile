# ============================================================================
# KUMON ASSISTANT - OPTIMIZED PRODUCTION DOCKERFILE
# Lightweight build using GCP managed services instead of heavy ML libs
# ============================================================================

# ============================================================================
# STAGE 1: Build Dependencies (Now much lighter!)
# ============================================================================
FROM python:3.11.11-slim AS builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    git \
    curl \
    && apt-get upgrade -y \
    && apt-get dist-upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /build

# Create virtual environment for cleaner installs
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install wheel for faster builds
RUN pip install --no-cache-dir --upgrade pip wheel setuptools

# Copy hybrid requirements (ML optional, with fallbacks)
COPY infrastructure/config/requirements-hybrid.txt ./requirements.txt

# Install Python dependencies in virtual environment
# Hybrid approach: ML libs for best performance, fallbacks available
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================================
# STAGE 2: Production Runtime (Much smaller now!)
# ============================================================================
FROM python:3.11.11-slim AS runtime

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && apt-get upgrade -y \
    && apt-get dist-upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash kumon

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Create necessary directories with proper permissions
RUN mkdir -p /app/cache/embeddings \
    /app/data \
    /app/logs \
    && chown -R kumon:kumon /app

# Copy application code with proper ownership
COPY --chown=kumon:kumon ./app ./app

# Copy Google service account credentials (temporary for build)
COPY --chown=kumon:kumon ./temp/credentials/google-service-account.json ./google-service-account.json

# Switch to non-root user
USER kumon

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Start the application (production mode - no reload)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
