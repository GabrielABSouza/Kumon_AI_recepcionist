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
