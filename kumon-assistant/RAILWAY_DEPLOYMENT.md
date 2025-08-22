# Railway Deployment Configuration

## Environment Detection

The system automatically detects Railway deployment through the `RAILWAY_ENVIRONMENT` environment variable.

## Optimized Settings for Railway

### Timeouts (Reduced for Railway)
- **LLM Request**: 15s (was 30s)
- **Database Pool**: 10s (was 30s)
- **PostgreSQL Command**: 10s (was 30s)
- **Statement Timeout**: 10s (was 30s)
- **Memory Service Init**: 10s (was 30s)
- **Circuit Breaker**: 10s (was 30s)
- **Health Checks**: 5s (was 10s)

### Connection Pools (Reduced for Railway Free Tier)
- **Database Pool Size**: 5 (was 20)
- **Database Max Overflow**: 5 (was 10)
- **PostgreSQL Min Pool**: 2 (was 5)
- **PostgreSQL Max Pool**: 10 (was 20)
- **Redis Max Connections**: 10 (was 20)

### Circuit Breakers (Fast Failure)
- **Failure Threshold**: 2 (fail fast)
- **Recovery Timeout**: 15s (quick recovery)
- **Success Threshold**: 1 (single success to close)

### Cache Configuration (Memory Optimized)
- **L1 Max Entries**: 500 (was 1000)
- **L1 TTL**: 3 minutes (was 5)
- **L1 Max Size**: 50MB (was 100MB)
- **L2 TTL**: 1 day (was 7)
- **L3 TTL**: 7 days (was 30)

## Environment Variables

Required for Railway deployment:
```bash
# Essential
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
OPENAI_API_KEY=sk-...
EVOLUTION_API_KEY=...

# Railway-specific
RAILWAY_ENVIRONMENT=production
PORT=8000

# Memory System
MEMORY_ENABLE_SYSTEM=true
MEMORY_POSTGRES_URL=$DATABASE_URL
MEMORY_REDIS_URL=$REDIS_URL
```

## Deployment Command

```bash
railway up
```

## Health Check Endpoint

Railway will check `/api/v1/health` with a 5-second timeout.

## Performance Expectations

With these optimizations:
- **Startup Time**: <25s (was >60s)
- **Memory Usage**: <512MB
- **Response Time**: <200ms for most operations
- **Circuit Breakers**: Prevent cascade failures
- **Graceful Degradation**: System remains functional even with service failures

## Monitoring

Check logs with:
```bash
railway logs
```

Look for:
- "Detected environment: railway"
- "Railway optimizations applied"
- Circuit breaker status
- Timeout configurations