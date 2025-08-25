# Qdrant Vector Database Dockerfile for Railway Deployment
# Official Qdrant image with production-ready configuration
# Version: 1.12.1 (latest stable as of 2024)

FROM qdrant/qdrant:v1.12.1

# Set working directory
WORKDIR /qdrant

# Create necessary directories with proper permissions
RUN mkdir -p /qdrant/storage && \
    mkdir -p /qdrant/snapshots && \
    chmod -R 777 /qdrant/storage && \
    chmod -R 777 /qdrant/snapshots

# Railway uses dynamic ports, so we need to expose the correct ones
# HTTP API port (REST API)
EXPOSE 6333
# gRPC port (for high-performance operations)
EXPOSE 6334

# Set Qdrant configuration via environment variables
# These can be overridden in Railway environment variables

# Storage Configuration
ENV QDRANT__STORAGE__STORAGE_PATH=/qdrant/storage
ENV QDRANT__STORAGE__SNAPSHOTS_PATH=/qdrant/snapshots

# Service Configuration
ENV QDRANT__SERVICE__HTTP_PORT=6333
ENV QDRANT__SERVICE__GRPC_PORT=6334
ENV QDRANT__SERVICE__ENABLE_CORS=true
ENV QDRANT__SERVICE__ENABLE_TLS=false

# Performance Configuration
ENV QDRANT__SERVICE__MAX_REQUEST_SIZE_MB=32
ENV QDRANT__SERVICE__MAX_WORKERS=0

# Logging Configuration
ENV QDRANT__LOG_LEVEL=info

# Security Configuration (for production)
# API key will be set via Railway environment variable
# ENV QDRANT__SERVICE__API_KEY=${QDRANT_API_KEY}

# Telemetry (disable for privacy)
ENV QDRANT__TELEMETRY_DISABLED=true

# Health check to ensure Qdrant is running
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:6333/health || exit 1

# Use the default Qdrant entrypoint
ENTRYPOINT ["./qdrant"]

# Default command (can be overridden)
CMD ["--config-path", "/qdrant/config/config.yaml"]
