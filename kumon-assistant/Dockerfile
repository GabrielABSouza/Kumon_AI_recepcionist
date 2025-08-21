# Railway Production Dockerfile - Simplified for Reliability
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements-production.txt .

# Install PyTorch CPU first for better caching and Railway compatibility
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.8.0 && \
    pip install --no-cache-dir -r requirements-production.txt

# Copy application code
COPY app/ ./app/

# Create necessary directories
RUN mkdir -p logs data cache temp

# Create Google credentials placeholder (to be mounted via Railway secrets)
# Note: The actual credentials file will be injected via Railway environment variables
RUN touch /app/google-service-account.json

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/v1/health || exit 1

# Expose port
EXPOSE ${PORT}

# Start command for Railway
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2