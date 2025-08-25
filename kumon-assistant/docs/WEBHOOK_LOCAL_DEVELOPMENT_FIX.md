# Webhook Configuration for Local Development

## Problem Description
When running Evolution API locally (not in Docker), the webhook configuration gets overwritten to Evolution API's own address, preventing message delivery to Kumon Assistant.

## Root Cause
Evolution API v1.7.1 forces webhooks to its own server address when not running in a proper Docker network environment.

## Solution

### For Local Development
1. **Use Docker Compose** (Recommended):
   ```bash
   docker-compose up -d
   ```
   - Evolution API and Kumon Assistant communicate via Docker network
   - Webhook URL: `http://kumon-assistant:8000/api/v1/evolution/webhook`

2. **Without Docker** (Limited):
   - Run Kumon Assistant on port 8000
   - Evolution API will override webhook settings
   - Manual webhook configuration won't persist

### For Production
- Railway deployment handles networking automatically
- Services communicate via internal URLs
- No manual webhook configuration needed

## Key Findings
- Port configuration: Kumon Assistant must run on port 8000
- Webhook endpoint: `/api/v1/evolution/webhook`
- Evolution API requires Docker network for proper webhook routing

## Verification Steps
1. Check Evolution API instances:
   ```bash
   curl -H "apikey: YOUR_API_KEY" http://localhost:8080/instance/fetchInstances
   ```

2. Test webhook endpoint:
   ```bash
   curl -X POST http://localhost:8000/api/v1/evolution/webhook \
        -H "Content-Type: application/json" \
        -d '{"test": "webhook"}'
   ```

## References
- Analysis report: `ANALISE_5_PORQUES_WHATSAPP_LOCAL.md`
- Docker configuration: `docker-compose.yml`