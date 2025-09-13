# Makefile for Kumon Assistant project

.PHONY: help
help:
	@echo "Available commands:"
	@echo "  make test-deploy     - Run deployment readiness tests"
	@echo "  make test-all        - Run all tests"
	@echo "  make install         - Install dependencies"
	@echo "  make install-dev     - Install dev dependencies"
	@echo "  make clean           - Clean cache files"
	@echo "  make docker-build    - Build Docker image locally"
	@echo "  make docker-run      - Run Docker container locally"

.PHONY: test-deploy
test-deploy:
	@echo "🧪 Running deployment readiness tests..."
	pytest -q tests/deploy -k "requirements or import or startup or env" --maxfail=1 --disable-warnings

.PHONY: test-all
test-all:
	@echo "🧪 Running all tests..."
	pytest tests/ -v

.PHONY: install
install:
	@echo "📦 Installing production dependencies..."
	pip install -r requirements.txt

.PHONY: install-dev
install-dev:
	@echo "📦 Installing development dependencies..."
	pip install -r requirements.txt
	pip install -r requirements-test.txt

.PHONY: clean
clean:
	@echo "🧹 Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

.PHONY: docker-build
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t kumon-assistant:local .

.PHONY: docker-run
docker-run:
	@echo "🐳 Running Docker container..."
	docker run -p 8000:8000 \
		-e EVOLUTION_API_URL=https://example.com \
		-e EVOLUTION_API_INSTANCE=local \
		-e EVOLUTION_API_TOKEN=local-token \
		kumon-assistant:local

.PHONY: pre-deploy-check
pre-deploy-check: clean test-deploy
	@echo "✅ Pre-deploy checks passed!"

# ============================================================================
# DEVELOPMENT ENVIRONMENT TARGETS
# ============================================================================

SHELL := /bin/bash
PROJECT_ROOT := /Users/gabrielbastos/recepcionista_kumon
COMPOSE_FILE := $(PROJECT_ROOT)/docker-compose.dev.yml
ENV_FILE := $(PROJECT_ROOT)/.env-dev
COMPOSE := docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE)

.PHONY: dev-up dev-down dev-logs dev-ps dev-health dev-wait dev-db-migrate dev-db-seed dev-db-reset dev-recreate

# ============================================================================
# CORE DEV TARGETS
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
	$(COMPOSE) exec -T app-dev sh -lc 'npm run migrate:dev || yarn migrate:dev || echo "ℹ️  No migrate script found"'

dev-db-seed: ## Run database seeding (tries npm then yarn)
	@echo "🌱 Seeding database..."
	$(COMPOSE) exec -T app-dev sh -lc 'npm run seed:dev || yarn seed:dev || echo "ℹ️  No seed script found"'

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
