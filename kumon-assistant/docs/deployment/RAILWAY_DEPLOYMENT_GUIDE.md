# Railway Production Deployment Guide

## Overview

Complete guide for deploying Kumon Assistant to Railway with production-ready configuration.

## Prerequisites

- Railway account with deployment permissions
- GitHub repository access
- All required API keys and credentials

## Step 1: Railway Project Setup

### 1.1 Create Project
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Create new project
railway init
```

### 1.2 Connect Repository
1. Go to Railway dashboard
2. Select "Deploy from GitHub repo"
3. Connect kumon-assistant repository
4. Select main branch for auto-deployment

## Step 2: Environment Variables Configuration

### 2.1 Required Variables (Critical)
Configure in Railway dashboard → Variables tab:

```bash
# Environment
ENVIRONMENT=production
DEBUG=false

# Critical APIs
OPENAI_API_KEY=sk-your-openai-key
EVOLUTION_API_KEY=your-evolution-key

# Business Configuration
BUSINESS_NAME=Kumon Vila A
BUSINESS_PHONE=51996921999
BUSINESS_EMAIL=kumonvilaa@gmail.com
```

### 2.2 Database URLs (Auto-generated)
Railway automatically provides:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string

### 2.3 Optional Variables (Recommended)
```bash
# LLM Fallback
ANTHROPIC_API_KEY=sk-ant-your-key

# WhatsApp/SMS Fallback
TWILIO_ACCOUNT_SID=your-sid
TWILIO_AUTH_TOKEN=your-token

# Observability
LANGSMITH_API_KEY=your-langsmith-key
LANGCHAIN_TRACING_V2=true
```

## Step 3: Service Configuration

### 3.1 Add PostgreSQL Database
1. Railway dashboard → Add Service → Database → PostgreSQL
2. Note the connection string (auto-populated to `DATABASE_URL`)

### 3.2 Add Redis Cache
1. Railway dashboard → Add Service → Database → Redis
2. Note the connection string (auto-populated to `REDIS_URL`)

### 3.3 Configure Networking
- Enable public networking for web service
- Configure custom domain (optional)

## Step 4: Deployment Validation

### 4.1 Pre-deployment Check
Before deploying, validate configuration:

```bash
# Local validation
curl http://localhost:8000/api/v1/config/validation

# Expected response
{
  "valid": true,
  "issues": [],
  "warnings": [],
  "deployment_ready": true
}
```

### 4.2 Deploy to Railway
```bash
# Deploy current branch
railway up

# Or use automatic deployment from main branch
git push origin main
```

### 4.3 Post-deployment Validation
```bash
# Check deployment health
curl https://your-app.up.railway.app/api/v1/config/health

# Validate all services
curl https://your-app.up.railway.app/api/v1/config/validate-deployment
```

## Step 5: Health Monitoring

### 5.1 Configuration Health
```bash
GET /api/v1/config/health
```
Returns:
- Configuration validation status
- Provider health
- Cost monitoring status
- System readiness

### 5.2 LLM Service Health
```bash
GET /api/v1/llm/health
```
Returns:
- Provider availability
- Circuit breaker status
- Performance metrics

### 5.3 Cost Monitoring
```bash
GET /api/v1/llm/cost
```
Returns:
- Daily spending vs budget
- Alert thresholds
- Provider cost breakdown

## Step 6: Production Monitoring

### 6.1 Key Metrics to Monitor
- Response times (<200ms first chunk)
- Cost consumption (target <R$5/day)
- Error rates (<1%)
- Provider failover events

### 6.2 Alerting Setup
Configure Railway alerts for:
- Application crashes
- High memory usage (>80%)
- High CPU usage (>80%)
- Database connection issues

### 6.3 Log Monitoring
Monitor application logs for:
- Configuration validation errors
- Provider failures
- Cost budget alerts
- Security incidents

## Step 7: Maintenance

### 7.1 Environment Updates
```bash
# Update single variable
railway variables set OPENAI_API_KEY=new-key

# Bulk update via Railway dashboard
```

### 7.2 Configuration Validation
Regular validation of production config:
```bash
curl https://your-app.up.railway.app/api/v1/config/validation
```

### 7.3 Provider Testing
Test individual providers:
```bash
curl -X POST https://your-app.up.railway.app/api/v1/llm/test-provider/openai
curl -X POST https://your-app.up.railway.app/api/v1/llm/test-provider/anthropic
```

## Troubleshooting

### Common Issues

**Configuration Validation Fails**
- Check all required environment variables are set
- Verify API keys are valid and have correct prefixes
- Ensure DATABASE_URL and REDIS_URL are properly configured

**Provider Connection Issues**
- Validate API keys in Railway dashboard
- Check rate limits and quotas
- Review provider-specific error logs

**Cost Budget Exceeded**
- Check daily spending: `GET /api/v1/llm/cost`
- Review usage patterns in logs
- Adjust budget if necessary: `LLM_DAILY_BUDGET_BRL`

**Database Connection Issues**
- Verify DATABASE_URL format
- Check PostgreSQL service status in Railway
- Review connection pool settings

### Support Endpoints

**Health Check**: `/api/v1/config/health`
**Validation**: `/api/v1/config/validation`
**Environment Info**: `/api/v1/config/environment`
**Deployment Check**: `/api/v1/config/validate-deployment`

## Security Considerations

### Production Security
- All API keys stored as Railway environment variables
- HTTPS enforced automatically by Railway
- Database connections encrypted
- Rate limiting enabled

### Monitoring Security
- Security events logged to application logs
- Failed authentication attempts tracked
- API key rotation supported

## Cost Management

### Expected Costs
- Railway: $5/month (Starter plan)
- OpenAI: ~R$150/month (R$5/day budget)
- Total: ~R$175/month

### Cost Optimization
- Circuit breakers prevent runaway costs
- Provider failover reduces reliance on expensive APIs
- Cost monitoring with real-time alerts

## Next Steps

1. **Monitor deployment health** for first 24 hours
2. **Validate business workflows** with test conversations
3. **Set up alerting** for critical metrics
4. **Document any environment-specific configuration**
5. **Plan backup and disaster recovery** procedures