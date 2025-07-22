# ============================================================================
# QDRANT - SELF-MANAGED VECTOR DATABASE DOCKERFILE
# Optimized for Google Cloud Run deployment
# ============================================================================

FROM qdrant/qdrant:v1.7.4

# Set working directory
WORKDIR /qdrant

# Install additional utilities for cloud deployment
USER root
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    && apt-get upgrade -y \
    && apt-get dist-upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create data directory with proper permissions
RUN mkdir -p /qdrant/data /qdrant/config /qdrant/logs
RUN chown -R 1000:1000 /qdrant

# Copy configuration files
COPY docker/qdrant/config/production.yaml /qdrant/config/production.yaml
COPY docker/qdrant/scripts/health-check.sh /qdrant/health-check.sh

# Make scripts executable
RUN chmod +x /qdrant/health-check.sh

# Switch to qdrant user
USER 1000

# Environment variables
ENV QDRANT__SERVICE__HOST=0.0.0.0
ENV QDRANT__SERVICE__PORT=6333
ENV QDRANT__SERVICE__GRPC_PORT=6334
ENV QDRANT__LOG_LEVEL=INFO
ENV QDRANT__STORAGE__STORAGE_PATH=/qdrant/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD /qdrant/health-check.sh || exit 1

# Expose ports
EXPOSE 6333 6334

# Start Qdrant with custom config
CMD ["./qdrant", "--config-path", "/qdrant/config/production.yaml"] 