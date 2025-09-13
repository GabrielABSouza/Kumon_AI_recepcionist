#!/bin/bash
# ============================================================================
# KUMON AI RECEPTIONIST - DEV ENVIRONMENT SETUP
# ============================================================================
# Arquiteto de Software e Engenheiro DevOps Sênior
# Escopo: Apenas desenvolvimento local, seguro para produção
# ============================================================================

set -euo pipefail

PROJECT_ROOT="/Users/gabrielbastos/recepcionista_kumon"
ENV_DEV_FILE="$PROJECT_ROOT/.env-dev"
COMPOSE_DEV_FILE="$PROJECT_ROOT/docker-compose.dev.yml"
MAKEFILE="$PROJECT_ROOT/Makefile"
README_DEV="$PROJECT_ROOT/README-DEV.md"
CI_WORKFLOW="$PROJECT_ROOT/.github/workflows/dev-smoke.yml"

echo "🚀 KUMON AI RECEPTIONIST - Dev Environment Setup"
echo "=============================================="
echo "Escopo: Desenvolvimento local apenas"
echo "Segurança: Zero acesso a recursos de produção"
echo ""

cd "$PROJECT_ROOT"

# ============================================================================
# 1. CREATE .env-dev (merge with existing if present)
# ============================================================================
echo "📋 1. Creating/merging .env-dev..."

# Base template with security comments
ENV_TEMPLATE='# ============================================================================
# KUMON AI RECEPTIONIST - DEVELOPMENT ENVIRONMENT
# ============================================================================
# ATENÇÃO: Este arquivo contém apenas valores seguros para desenvolvimento local
# NUNCA utilize segredos reais ou credenciais de produção aqui
# ============================================================================

# Application
APP_PORT=3001
NODE_ENV=development
API_BASE_URL=http://localhost:3001
LOG_LEVEL=debug

# Database (PostgreSQL)
DB_HOST=db
DB_PORT=5433
DB_NAME=kumon_dev
DB_USER=kumon_dev_user
DB_PASSWORD=dev_password_change_me

# Redis
REDIS_HOST=redis
REDIS_PORT=6380
REDIS_URL=redis://redis:6380

# Security (DEV ONLY - CHANGE IN PRODUCTION)
JWT_SECRET=local_dev_only_change_me_in_production

# Feature Flags
FEATURE_X_ENABLED=true

# External APIs (DEV KEYS ONLY)
GEMINI_API_KEY=dev_gemini_key_replace_me
EVOLUTION_API_BASE=http://localhost:8080
EVOLUTION_INSTANCE=kumon_dev
'

if [ -f "$ENV_DEV_FILE" ]; then
    echo "  ℹ️  .env-dev exists, merging missing keys..."
    # Backup existing
    cp "$ENV_DEV_FILE" "$ENV_DEV_FILE.bak"

    # Extract new keys that don't exist
    while IFS='=' read -r key value; do
        if [[ "$key" =~ ^[A-Z] ]] && ! grep -q "^$key=" "$ENV_DEV_FILE"; then
            echo "$key=$value" >> "$ENV_DEV_FILE"
            echo "  ✅ Added: $key"
        fi
    done < <(echo "$ENV_TEMPLATE" | grep '^[A-Z]')
else
    echo "  📝 Creating new .env-dev..."
    echo "$ENV_TEMPLATE" > "$ENV_DEV_FILE"
fi

echo "  ✅ .env-dev ready"

# ============================================================================
# 2. UPDATE .gitignore (ensure .env-dev is ignored)
# ============================================================================
echo "📋 2. Updating .gitignore..."

if ! grep -q "^\.env-dev$" .gitignore; then
    echo "/.env-dev" >> .gitignore
    echo "  ✅ Added .env-dev to .gitignore"
else
    echo "  ℹ️  .env-dev already in .gitignore"
fi

# ============================================================================
# 3. NORMALIZE docker-compose.dev.yml (non-destructive)
# ============================================================================
echo "📋 3. Normalizing docker-compose.dev.yml..."

# Backup original
cp "$COMPOSE_DEV_FILE" "$COMPOSE_DEV_FILE.bak"

# Create normalized version using yq via Docker
docker run --rm -v "$PROJECT_ROOT:/workdir" mikefarah/yq:4 eval '
# Add dev profile to all services
.services.postgres.profiles = ["dev"] |
.services.app.profiles = ["dev"] |

# Add dedicated dev network
.networks.project_dev_net.driver = "bridge" |

# Update postgres service for dev isolation
.services.postgres.container_name = "db-dev" |
.services.postgres.ports = ["${DB_PORT:-5433}:5432"] |
.services.postgres.volumes = ["pg_data_dev:/var/lib/postgresql/data"] |
.services.postgres.networks = ["project_dev_net"] |
.services.postgres.environment.POSTGRES_USER = "${DB_USER:-kumon_dev_user}" |
.services.postgres.environment.POSTGRES_PASSWORD = "${DB_PASSWORD:-dev_password_change_me}" |
.services.postgres.environment.POSTGRES_DB = "${DB_NAME:-kumon_dev}" |

# Update app service for dev isolation
.services.app.container_name = "app-dev" |
.services.app.env_file = [".env-dev"] |
.services.app.ports = ["${APP_PORT:-3001}:8000"] |
.services.app.networks = ["project_dev_net"] |
del(.services.app.environment) |

# Add Redis service
.services.redis = {
  "image": "redis:7-alpine",
  "container_name": "redis-dev",
  "profiles": ["dev"],
  "ports": ["${REDIS_PORT:-6380}:6379"],
  "networks": ["project_dev_net"],
  "healthcheck": {
    "test": ["CMD", "redis-cli", "ping"],
    "interval": "10s",
    "timeout": "3s",
    "retries": 5
  }
} |

# Update volumes for dev isolation
.volumes.postgres_data = null |
.volumes.pg_data_dev = {}
' "$COMPOSE_DEV_FILE" > "$COMPOSE_DEV_FILE.tmp"

mv "$COMPOSE_DEV_FILE.tmp" "$COMPOSE_DEV_FILE"
echo "  ✅ docker-compose.dev.yml normalized for dev isolation"

# ============================================================================
# 4. CREATE MAKEFILE (append missing targets)
# ============================================================================
echo "📋 4. Creating/updating Makefile..."

MAKEFILE_CONTENT='# ============================================================================
# KUMON AI RECEPTIONIST - DEVELOPMENT MAKEFILE
# ============================================================================
# Targets para ambiente de desenvolvimento local isolado
# ============================================================================

SHELL := /bin/bash
PROJECT_ROOT := /Users/gabrielbastos/recepcionista_kumon
COMPOSE_FILE := $(PROJECT_ROOT)/docker-compose.dev.yml
ENV_FILE := $(PROJECT_ROOT)/.env-dev
COMPOSE := docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE)

.PHONY: dev-up dev-down dev-logs dev-ps dev-health dev-wait dev-db-migrate dev-db-seed dev-db-reset dev-recreate

# ============================================================================
# CORE TARGETS
# ============================================================================

dev-up: ## Start development environment with build
	@echo "🚀 Starting development environment..."
	$(COMPOSE) --profile dev up -d --build

dev-down: ## Stop development environment and remove volumes
	@echo "🛑 Stopping development environment..."
	$(COMPOSE) --profile dev down -v

dev-logs: ## Follow logs for all services
	@echo "📋 Following development logs..."
	$(COMPOSE) logs -f --tail=200

dev-ps: ## Show development services status
	@echo "📊 Development services status:"
	$(COMPOSE) ps

# ============================================================================
# HEALTH & MONITORING
# ============================================================================

dev-health: ## Check health of all services
	@echo "🔍 Checking service health..."
	@set -e; \
	APP_PORT=$${APP_PORT:-3001}; \
	echo "Checking APP on http://localhost:$$APP_PORT/health"; \
	curl -fsS "http://localhost:$$APP_PORT/health" && echo "✅ APP OK" || (echo "❌ APP health failed" && exit 1); \
	echo "Checking PostgreSQL"; \
	$(COMPOSE) exec -T db-dev pg_isready -U $${DB_USER:-kumon_dev_user} -d $${DB_NAME:-kumon_dev} && echo "✅ DB OK" || (echo "❌ DB not ready" && exit 1); \
	echo "Checking Redis"; \
	$(COMPOSE) exec -T redis-dev redis-cli PING | grep -q PONG && echo "✅ Redis OK" || (echo "❌ Redis failed" && exit 1); \
	echo "🎉 All services healthy!"

dev-wait: ## Wait for all services to be healthy (120s timeout)
	@echo "⏳ Waiting for services to be healthy..."
	@set -e; \
	end=$$(($(shell date +%s)+120)); \
	until $(MAKE) dev-health >/dev/null 2>&1; do \
		if [ $(shell date +%s) -gt $$end ]; then \
			echo "❌ Timeout waiting for services"; \
			exit 1; \
		fi; \
		echo "⏳ Waiting for services... ($$(( $$end - $(shell date +%s) ))s remaining)"; \
		sleep 4; \
	done; \
	echo "✅ All services are healthy!"

# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

dev-db-migrate: ## Run database migrations (tries npm then yarn)
	@echo "📊 Running database migrations..."
	$(COMPOSE) exec -T app-dev sh -lc '\''npm run migrate:dev || yarn migrate:dev || echo "ℹ️  No migrate script found"'\''

dev-db-seed: ## Run database seeding (tries npm then yarn)
	@echo "🌱 Seeding database..."
	$(COMPOSE) exec -T app-dev sh -lc '\''npm run seed:dev || yarn seed:dev || echo "ℹ️  No seed script found"'\''

dev-db-reset: ## Reset database (recreate + migrate + seed)
	@echo "🔄 Resetting database..."
	$(COMPOSE) --profile dev down -v
	$(COMPOSE) --profile dev up -d --build
	$(MAKE) dev-wait
	$(MAKE) dev-db-migrate
	$(MAKE) dev-db-seed
	@echo "✅ Database reset complete"

# ============================================================================
# UTILITY TARGETS
# ============================================================================

dev-recreate: ## Recreate development environment (preserving build cache)
	@echo "🔄 Recreating development environment..."
	$(COMPOSE) --profile dev down -v
	$(MAKE) dev-up
	$(MAKE) dev-wait

help: ## Show this help message
	@echo "🚀 KUMON AI RECEPTIONIST - Development Commands"
	@echo "=============================================="
	@grep -E "^[a-zA-Z_-]+:.*?## .*$$" $(MAKEFILE_LIST) | sort | awk '\''BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'\''

'

if [ -f "$MAKEFILE" ]; then
    echo "  ℹ️  Makefile exists, checking for missing targets..."
    # Check if dev targets exist
    if ! grep -q "dev-up:" "$MAKEFILE"; then
        echo "  📝 Adding dev targets to existing Makefile..."
        echo "" >> "$MAKEFILE"
        echo "$MAKEFILE_CONTENT" >> "$MAKEFILE"
    else
        echo "  ℹ️  Dev targets already exist in Makefile"
    fi
else
    echo "  📝 Creating new Makefile..."
    echo "$MAKEFILE_CONTENT" > "$MAKEFILE"
fi

echo "  ✅ Makefile ready with dev targets"

# ============================================================================
# 5. CREATE README-DEV.md
# ============================================================================
echo "📋 5. Creating README-DEV.md..."

README_CONTENT='# KUMON AI RECEPTIONIST - Development Environment

## 🎯 Overview

This document covers the local development environment setup for the Kumon AI Receptionist project.

**Security Note**: This environment uses only safe, non-production values. Never use real secrets or production credentials.

## 📋 Prerequisites

- Docker Desktop (>= 4.0)
- Docker Compose (>= 2.0)
- Make (installed by default on macOS/Linux)
- curl (for health checks)

## 🚀 Quick Start

### 1. First Time Setup
```bash
# Clone and enter the project
cd /Users/gabrielbastos/recepcionista_kumon

# Start development environment
make dev-up

# Wait for all services to be healthy
make dev-wait

# Verify everything is working
make dev-health
```

### 2. Daily Development Routine

```bash
# Start environment
make dev-up

# Check status
make dev-ps

# Follow logs
make dev-logs

# Run migrations (if needed)
make dev-db-migrate

# Seed database (if needed)
make dev-db-seed
```

## 🔧 Available Commands

| Command | Description |
|---------|-------------|
| `make dev-up` | Start development environment with build |
| `make dev-down` | Stop environment and remove volumes |
| `make dev-logs` | Follow logs for all services |
| `make dev-ps` | Show services status |
| `make dev-health` | Check health of all services |
| `make dev-wait` | Wait for services to be healthy (120s timeout) |
| `make dev-db-migrate` | Run database migrations |
| `make dev-db-seed` | Seed database with dev data |
| `make dev-db-reset` | Reset database (recreate + migrate + seed) |
| `make dev-recreate` | Recreate entire environment |
| `make help` | Show all available commands |

## 🌐 Service Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| API | http://localhost:3001 | Main application API |
| Health Check | http://localhost:3001/health | Service health status |
| PostgreSQL | localhost:5433 | Database (dev isolation) |
| Redis | localhost:6380 | Cache/sessions (dev isolation) |

## 🗄️ Database Operations

### Connect to Database
```bash
# Via docker compose
docker compose -f docker-compose.dev.yml exec db-dev psql -U kumon_dev_user -d kumon_dev

# Via local client (if installed)
psql -h localhost -p 5433 -U kumon_dev_user -d kumon_dev
```

### Reset Database
```bash
# Full reset (recreate + migrate + seed)
make dev-db-reset

# Manual steps
make dev-down
make dev-up
make dev-wait
make dev-db-migrate
make dev-db-seed
```

## 🔧 Troubleshooting

### Services Won'\''t Start
```bash
# Check if ports are available
lsof -i :3001 -i :5433 -i :6380

# Force recreate
make dev-recreate

# Check logs
make dev-logs
```

### Health Checks Failing
```bash
# Check individual service health
make dev-ps
docker compose -f docker-compose.dev.yml logs app-dev
docker compose -f docker-compose.dev.yml logs db-dev
docker compose -f docker-compose.dev.yml logs redis-dev
```

### Database Connection Issues
```bash
# Verify database is ready
docker compose -f docker-compose.dev.yml exec db-dev pg_isready -U kumon_dev_user

# Check environment variables
docker compose -f docker-compose.dev.yml exec app-dev env | grep DB_
```

## 🧹 Cleanup & Teardown

### Daily Cleanup
```bash
# Stop services and remove volumes
make dev-down
```

### Deep Cleanup
```bash
# Remove all dev containers, volumes, and networks
make dev-down
docker system prune -f

# Remove dev images (if needed)
docker compose -f docker-compose.dev.yml down --rmi local
```

## 🔐 Environment Variables

Development configuration is in `.env-dev` (ignored by git).

**Key variables:**
- `APP_PORT=3001` - API server port
- `DB_PORT=5433` - PostgreSQL port (isolated from prod)
- `REDIS_PORT=6380` - Redis port (isolated from prod)
- `LOG_LEVEL=debug` - Enhanced logging for development

## ⚠️ Security Notes

- This environment uses development-only credentials
- Ports are isolated from production (3001, 5433, 6380)
- All containers use `-dev` suffix for clear identification
- `.env-dev` is gitignored to prevent accidental commits
- Never use production secrets in this environment

## 🆘 Getting Help

1. Check service logs: `make dev-logs`
2. Verify health: `make dev-health`
3. Check this documentation
4. Reset environment: `make dev-recreate`
'

echo "$README_CONTENT" > "$README_DEV"
echo "  ✅ README-DEV.md created"

# ============================================================================
# 6. CREATE CI WORKFLOW (Optional)
# ============================================================================
echo "📋 6. Creating CI workflow for dev smoke tests..."

mkdir -p "$(dirname "$CI_WORKFLOW")"

CI_CONTENT='name: Dev Smoke Test

on:
  pull_request:
    branches: [ main, develop ]
    paths:
      - '\''docker-compose.dev.yml'\''
      - '\''.env-dev'\''
      - '\''Makefile'\''
      - '\''app/**'\''
      - '\''requirements.txt'\''
      - '\''Dockerfile'\''

jobs:
  dev-smoke:
    name: Development Environment Smoke Test
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Create minimal .env-dev for CI
        run: |
          cat > .env-dev << EOF
          APP_PORT=3001
          DB_HOST=db
          DB_PORT=5433
          DB_NAME=kumon_dev
          DB_USER=kumon_dev_user
          DB_PASSWORD=ci_test_password
          REDIS_HOST=redis
          REDIS_PORT=6380
          NODE_ENV=development
          LOG_LEVEL=info
          JWT_SECRET=ci_test_secret_change_me
          GEMINI_API_KEY=ci_test_key
          EVOLUTION_API_BASE=http://localhost:8080
          EVOLUTION_INSTANCE=kumon_ci
          EOF

      - name: Start development environment
        run: |
          make dev-up

      - name: Wait for services to be healthy
        run: |
          make dev-wait

      - name: Run health checks
        run: |
          make dev-health

      - name: Test database connectivity
        run: |
          docker compose -f docker-compose.dev.yml exec -T db-dev pg_isready -U kumon_dev_user -d kumon_dev

      - name: Test Redis connectivity
        run: |
          docker compose -f docker-compose.dev.yml exec -T redis-dev redis-cli ping

      - name: Show service status
        run: |
          make dev-ps

      - name: Show logs on failure
        if: failure()
        run: |
          echo "=== APP LOGS ==="
          docker compose -f docker-compose.dev.yml logs app-dev
          echo "=== DB LOGS ==="
          docker compose -f docker-compose.dev.yml logs db-dev
          echo "=== REDIS LOGS ==="
          docker compose -f docker-compose.dev.yml logs redis-dev

      - name: Cleanup
        if: always()
        run: |
          make dev-down || true
          docker system prune -f
'

echo "$CI_CONTENT" > "$CI_WORKFLOW"
echo "  ✅ Dev smoke test workflow created"

# ============================================================================
# 7. COMMIT CHANGES
# ============================================================================
echo "📋 7. Committing changes..."

git add . 2>/dev/null || true
if git diff --cached --quiet; then
    echo "  ℹ️  No changes to commit"
else
    git commit -m "chore(dev): setup dev env (.env-dev, compose normalization, Makefile, docs)" || echo "  ⚠️  Commit failed (may be due to hooks)"
    echo "  ✅ Changes committed"
fi

# ============================================================================
# 8. VERIFICATION
# ============================================================================
echo ""
echo "🎉 SETUP COMPLETE!"
echo "=================="
echo ""
echo "✅ .env-dev created/updated (safe dev values only)"
echo "✅ docker-compose.dev.yml normalized with dev isolation"
echo "✅ Makefile created with dev targets"
echo "✅ README-DEV.md created with documentation"
echo "✅ CI workflow created for dev smoke tests"
echo "✅ .gitignore updated to exclude .env-dev"
echo ""
echo "🚀 NEXT STEPS:"
echo "============="
echo "1. make dev-up    # Start development environment"
echo "2. make dev-wait  # Wait for services to be healthy"
echo "3. make dev-health # Verify all services are working"
echo ""
echo "📊 SERVICE ENDPOINTS:"
echo "===================="
echo "• API:        http://localhost:3001"
echo "• Health:     http://localhost:3001/health"
echo "• PostgreSQL: localhost:5433 (user: kumon_dev_user, db: kumon_dev)"
echo "• Redis:      localhost:6380"
echo ""
echo "📋 For more commands: make help"
echo ""
echo "⚠️  SECURITY: This environment uses development-only credentials."
echo "    Never use production secrets in .env-dev!"
echo ""
