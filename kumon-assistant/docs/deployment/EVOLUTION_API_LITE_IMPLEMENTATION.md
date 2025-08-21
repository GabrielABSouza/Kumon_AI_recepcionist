# Evolution API Lite Implementation for Google Cloud Platform

## Overview

This document describes the comprehensive implementation of Evolution API Lite on Google Cloud Platform with enhanced security and stability configurations. This solution addresses the previous challenges with Evolution API v1.x and provides a streamlined, production-ready WhatsApp integration.

## Architecture

### Components

1. **Evolution API Lite Container** - Lightweight WhatsApp integration API
2. **PostgreSQL Database** - Cloud SQL instance with SSL enforcement
3. **Secret Manager** - Secure credential storage
4. **Cloud Monitoring** - Comprehensive logging and alerting
5. **Cloud Run Gen2** - Enhanced container runtime with security features

### Key Features

- **No Redis Dependency** - Uses local caching to eliminate external dependencies
- **Optimized for Cloud Run** - Designed specifically for serverless container environments
- **Enhanced Security** - SSL-enforced database, Secret Manager, custom IAM roles
- **Comprehensive Monitoring** - Cloud Logging, Monitoring, and Error Reporting
- **Session Persistence** - Maintains WhatsApp sessions across container restarts

## Security Implementations

### 1. Database Security
```yaml
# SSL-enforced Cloud SQL
gcloud sql instances patch evolution-postgres --require-ssl
```

### 2. Secret Management
```bash
# API keys stored in Secret Manager
gcloud secrets create evolution-api-key --data-file=-
gcloud secrets create openai-api-key --data-file=-
```

### 3. Custom IAM Roles
```yaml
permissions:
  - cloudsql.instances.connect
  - secretmanager.versions.access
  - logging.logEntries.create
  - monitoring.metricDescriptors.create
  - monitoring.timeSeries.create
```

### 4. Cloud Run Security Features
- **Gen2 Execution Environment** - Enhanced security sandbox
- **Startup CPU Boost** - Faster container initialization
- **Session Affinity** - Consistent routing for WebSocket connections
- **VPC Egress Control** - Network security controls

## Configuration Details

### Environment Variables

#### Core Configuration
```bash
NODE_ENV=production
SERVER_TYPE=http
SERVER_PORT=8080
LOG_LEVEL=INFO
LOG_COLOR=true
LOG_BAILEYS=error
```

#### Database Configuration
```bash
DATABASE_PROVIDER=postgresql
DATABASE_CONNECTION_CLIENT_NAME=evolution_lite_gcp
DATABASE_SAVE_DATA_INSTANCE=true
DATABASE_SAVE_DATA_NEW_MESSAGE=true
DATABASE_SAVE_DATA_CONTACTS=true
DATABASE_SAVE_DATA_CHATS=true
```

#### Performance Optimization
```bash
CACHE_REDIS_ENABLED=false
CACHE_LOCAL_ENABLED=true
WEBSOCKET_ENABLED=false
RABBITMQ_ENABLED=false
PUSHER_ENABLED=false
EVENT_EMITTER_MAX_LISTENERS=50
```

### Docker Configuration

The custom Dockerfile extends the official Evolution API Lite image with:

- **Platform Specification** - Ensures AMD64 compatibility for GCP
- **Security Updates** - Automated package updates
- **Non-root User** - Runs as dedicated `evolution` user
- **Health Checks** - Comprehensive service monitoring
- **Custom Scripts** - Initialization and health check scripts

## Monitoring and Observability

### Cloud Monitoring
- **Service Health Alerts** - Automated alerting for high error rates
- **Performance Metrics** - CPU, memory, and request monitoring
- **Custom Dashboards** - WhatsApp-specific metrics tracking

### Cloud Logging
- **Structured Logs** - JSON-formatted application logs
- **Error Tracking** - Automatic error aggregation and alerting
- **Audit Trails** - Complete API request/response logging

### Health Checks
```bash
# Custom health check endpoints
GET /health          # Basic service health
GET /manager         # Manager interface availability
GET /instance/fetchInstances  # API functionality check
```

## Deployment Process

### Prerequisites
1. Google Cloud Project with billing enabled
2. gcloud CLI installed and authenticated
3. Required environment variables set:
   - `OPENAI_API_KEY`
   - `EVOLUTION_API_KEY` (optional, auto-generated)

### Quick Deployment
```bash
# Set environment variables
export OPENAI_API_KEY="your-openai-key"
export EVOLUTION_API_KEY="your-evolution-key"

# Run deployment script
./scripts/deployment/deploy_evolution_lite.sh
```

### Manual Deployment
```bash
# Build and deploy via Cloud Build
gcloud builds submit \
  --config=infrastructure/gcp/cloudbuild.yaml \
  --substitutions="_OPENAI_API_KEY=$OPENAI_API_KEY,_EVOLUTION_API_KEY=$EVOLUTION_API_KEY"
```

## Testing and Validation

### Automated Testing
```bash
# Run comprehensive tests
./scripts/deployment/test_evolution_lite.sh
```

### Manual Testing Steps

1. **Access Manager Interface**
   ```
   URL: https://your-evolution-api-url/manager
   API Key: [from Secret Manager]
   ```

2. **Create WhatsApp Instance**
   ```bash
   curl -X POST "https://your-evolution-api-url/instance/create" \
     -H "apikey: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{
       "instanceName": "test_instance",
       "qrcode": true,
       "integration": "WHATSAPP-BAILEYS"
     }'
   ```

3. **Generate QR Code**
   ```bash
   curl "https://your-evolution-api-url/instance/connect/test_instance" \
     -H "apikey: your-api-key"
   ```

4. **Check Instance Status**
   ```bash
   curl "https://your-evolution-api-url/instance/connectionState/test_instance" \
     -H "apikey: your-api-key"
   ```

## Performance Characteristics

### Resource Allocation
- **Memory**: 1GB (scalable to 4GB)
- **CPU**: 1 vCPU (with startup boost)
- **Instances**: 1-3 (auto-scaling)
- **Concurrency**: 80 requests per instance

### Expected Performance
- **QR Code Generation**: < 5 seconds
- **Message Processing**: < 100ms
- **Instance Creation**: < 30 seconds
- **Cold Start**: < 10 seconds (with boost)

## Cost Optimization

### Monthly Cost Estimate (USD)
- **Cloud Run**: $15-25 (based on usage)
- **Cloud SQL**: $20-30 (db-f1-micro)
- **Secret Manager**: $1-2
- **Monitoring**: $5-10
- **Total**: $41-67/month

### Cost Reduction Strategies
1. **Local Caching** - Eliminates Redis costs
2. **Minimal Database** - 6 essential tables only
3. **Efficient Scaling** - Min instances = 1
4. **Optimized Resources** - Right-sized for workload

## Troubleshooting

### Common Issues

#### QR Code Generation Fails
```bash
# Check instance status
curl "https://your-api-url/instance/connectionState/instance_name" \
  -H "apikey: your-key"

# Check logs
gcloud logs read "projects/your-project/logs/run.googleapis.com"
```

#### Database Connection Issues
```bash
# Verify Cloud SQL instance
gcloud sql instances describe evolution-postgres

# Check SSL configuration
gcloud sql instances describe evolution-postgres --format="value(settings.ipConfiguration.requireSsl)"
```

#### Authentication Problems
```bash
# Verify secret exists
gcloud secrets describe evolution-api-key

# Get current API key
gcloud secrets versions access latest --secret="evolution-api-key"
```

### Debug Commands

```bash
# View service logs
gcloud logs tail "projects/YOUR_PROJECT/logs/run.googleapis.com" --filter="resource.labels.service_name=kumon-evolution-api"

# Check service status
gcloud run services describe kumon-evolution-api --region=us-central1

# Monitor database connections
gcloud sql operations list --instance=evolution-postgres
```

## Migration from Evolution API v1

### Key Differences
1. **No External Dependencies** - Redis/MongoDB optional
2. **Streamlined Configuration** - Fewer environment variables
3. **Better Cloud Run Support** - Optimized for serverless
4. **Enhanced Logging** - Structured JSON logs
5. **Improved Performance** - Faster startup and execution

### Migration Steps
1. Deploy Evolution API Lite alongside existing v1
2. Test QR code generation and messaging
3. Migrate instances to new API
4. Decommission v1 infrastructure

## Security Best Practices

### Implemented Security Measures
1. ✅ **SSL-Enforced Database** - All connections encrypted
2. ✅ **Secret Manager** - No credentials in environment
3. ✅ **Custom IAM Roles** - Principle of least privilege
4. ✅ **VPC Controls** - Network-level security
5. ✅ **Container Security** - Non-root user, minimal attack surface
6. ✅ **Monitoring** - Comprehensive logging and alerting

### Additional Recommendations
1. **API Rate Limiting** - Implement request throttling
2. **IP Whitelisting** - Restrict manager access
3. **Regular Updates** - Automated security patching
4. **Backup Strategy** - Database backup retention
5. **Incident Response** - Defined procedures for security events

## API Reference

### Core Endpoints

#### Instance Management
```bash
POST   /instance/create           # Create new instance
GET    /instance/fetchInstances   # List all instances
DELETE /instance/delete/{name}    # Delete instance
GET    /instance/connect/{name}   # Get QR code
GET    /instance/connectionState/{name}  # Check status
```

#### Messaging
```bash
POST   /message/sendText/{name}     # Send text message
POST   /message/sendMedia/{name}    # Send media message
POST   /message/sendLocation/{name} # Send location
```

#### Webhook Configuration
```bash
POST   /webhook/set/{name}     # Configure webhook
GET    /webhook/find/{name}    # Get webhook config
DELETE /webhook/delete/{name}  # Remove webhook
```

## Support and Maintenance

### Regular Maintenance Tasks
1. **Monitor Resource Usage** - Weekly review of metrics
2. **Update Dependencies** - Monthly security updates
3. **Backup Verification** - Weekly backup tests
4. **Performance Tuning** - Monthly optimization review
5. **Cost Analysis** - Monthly cost optimization

### Support Resources
- **GCP Support** - For infrastructure issues
- **Evolution API Community** - For API-specific questions
- **Internal Documentation** - Team-specific procedures
- **Monitoring Dashboards** - Real-time status monitoring

---

This implementation provides a robust, secure, and cost-effective solution for WhatsApp integration using Evolution API Lite on Google Cloud Platform. The configuration ensures high availability, comprehensive monitoring, and enterprise-grade security while maintaining simplicity and ease of management.