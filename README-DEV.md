# KUMON AI RECEPTIONIST - Development Environment

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

### Services Won't Start
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
