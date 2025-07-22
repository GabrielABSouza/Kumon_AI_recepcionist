# ============================================================================
# EVOLUTION API - CUSTOM PRODUCTION DOCKERFILE
# Extends official Evolution API with custom configurations
# ============================================================================

FROM atendai/evolution-api:latest AS base

# Set working directory
WORKDIR /evolution

# Install minimal required utilities and security updates
USER root
RUN if command -v apt-get >/dev/null 2>&1; then \
        apt-get update && apt-get install -y curl && \
        apt-get upgrade -y && apt-get dist-upgrade -y && \
        rm -rf /var/lib/apt/lists/* && apt-get clean; \
    elif command -v apk >/dev/null 2>&1; then \
        apk add --no-cache curl && apk upgrade && apk update; \
    elif command -v yum >/dev/null 2>&1; then \
        yum install -y curl && yum update -y && yum upgrade -y; \
    fi

# Create custom scripts directory
RUN mkdir -p /evolution/scripts

# Copy custom initialization and health check scripts
COPY docker/evolution/scripts/ /evolution/scripts/
COPY docker/evolution/config/ /evolution/config/

# Make scripts executable
RUN chmod +x /evolution/scripts/*.sh

# Create non-root user for security (if not exists)
RUN if ! id evolution >/dev/null 2>&1; then \
        if command -v useradd >/dev/null 2>&1; then \
        useradd --create-home --shell /bin/bash evolution; \
        elif command -v adduser >/dev/null 2>&1; then \
            adduser -D -s /bin/bash evolution; \
        fi; \
    fi

# Set proper ownership
RUN chown -R evolution:evolution /evolution

# Switch to non-root user
USER evolution

# Environment variables for Evolution API
ENV NODE_ENV=production
ENV PORT=8080
ENV SERVER_URL=http://0.0.0.0:8080
ENV CORS_ORIGIN=*
ENV CORS_CREDENTIALS=true
ENV DATABASE_CONNECTION_TIMEOUT=60000
ENV DATABASE_CONNECTION_RETRY_DELAY=5000
ENV DATABASE_CONNECTION_MAX_RETRIES=12

# Health check with custom script
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /evolution/scripts/health-check.sh || exit 1

# Custom entrypoint that handles initialization
ENTRYPOINT ["/evolution/scripts/entrypoint.sh"]

# Default command - use the correct start command for Evolution API
CMD ["npm", "run", "start:prod"]
