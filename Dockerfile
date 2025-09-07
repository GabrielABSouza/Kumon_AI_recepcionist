# Minimal Dockerfile for ONE_TURN architecture
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY app/ ./app/

# Expose port
EXPOSE ${PORT}

# Start command for Railway
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]