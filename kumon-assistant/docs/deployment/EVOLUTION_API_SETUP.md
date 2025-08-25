# 🚀 Evolution API Setup Guide - Kumon Assistant

This guide will help you set up the **Evolution API** for cost-free WhatsApp integration with your Kumon Assistant, replacing the expensive WhatsApp Business API.

## 🌟 Why Evolution API?

- **100% Free** - No monthly costs or per-message fees
- **Full-featured** - Supports text, media, buttons, and more
- **Multi-instance** - Connect multiple WhatsApp numbers
- **Real-time** - Instant message processing via webhooks
- **Easy setup** - Docker-based deployment

## 📋 Prerequisites

- Docker and Docker Compose installed
- A phone number for WhatsApp (can be personal or business)
- OpenAI API key for the AI responses

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Navigate to your Kumon Assistant directory
cd kumon-assistant

# Copy the environment configuration
cp evolution_config.env.example .env

# Edit the .env file with your settings
nano .env
```

### 2. Configure Environment Variables

Edit your `.env` file with these essential settings:

```bash
# Evolution API Configuration
EVOLUTION_API_URL=http://evolution-api:8080
EVOLUTION_GLOBAL_API_KEY=your_secure_api_key_here
AUTHENTICATION_API_KEY=your_auth_key_here
WEBHOOK_GLOBAL_URL=http://kumon-assistant:8000/api/v1/evolution/webhook

# OpenAI (for AI responses)
OPENAI_API_KEY=your_openai_api_key_here

# Qdrant (for semantic search)
QDRANT_URL=http://qdrant:6333

# Business Information
BUSINESS_NAME=Kumon Vila Madalena
BUSINESS_PHONE=+55 11 99999-9999
BUSINESS_EMAIL=contato@kumon.com
```

### 3. Start the Services

```bash
# Start all services (Evolution API, Qdrant, Kumon Assistant)
docker-compose up -d

# Check if services are running
docker-compose ps
```

### 4. Create WhatsApp Instance

```bash
# Create a new WhatsApp instance
curl -X POST "http://localhost:8000/api/v1/evolution/instances" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_name": "kumon_main",
    "webhook_url": "http://kumon-assistant:8000/api/v1/evolution/webhook"
  }'
```

### 5. Connect WhatsApp

```bash
# Get the QR code for connection
curl "http://localhost:8000/api/v1/evolution/instances/kumon_main/qr"
```

1. Copy the base64 QR code from the response
2. Decode it using any base64 to image converter (or browser console)
3. Open WhatsApp on your phone
4. Go to **Settings > Linked Devices > Link a Device**
5. Scan the QR code

### 6. Test the Connection

Send a message to your connected WhatsApp number and verify the AI responds!

## 🔧 Detailed Configuration

### Docker Compose Services

The `docker-compose.yml` includes:

- **evolution-api**: WhatsApp integration service
- **qdrant**: Vector database for semantic search
- **kumon-assistant**: Your AI receptionist application

### Environment Variables Explained

```bash
# Core Evolution API settings
EVOLUTION_API_URL=http://evolution-api:8080        # Evolution API endpoint
EVOLUTION_GLOBAL_API_KEY=your_secure_key          # Global access key
AUTHENTICATION_API_KEY=your_auth_key              # Instance authentication

# Webhook configuration
WEBHOOK_GLOBAL_URL=http://kumon-assistant:8000/api/v1/evolution/webhook
WEBHOOK_GLOBAL_ENABLED=true                       # Enable webhooks
WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=true            # Event-based webhooks

# Session settings
CONFIG_SESSION_PHONE_CLIENT=Kumon Assistant       # Client name shown in WhatsApp
CONFIG_SESSION_PHONE_NAME=Chrome                  # Browser name

# QR Code settings
QRCODE_LIMIT=30                                   # QR code expiry (seconds)
QRCODE_COLOR=#198754                              # QR code color
```

## 📱 Managing WhatsApp Instances

### Create Instance

```bash
curl -X POST "http://localhost:8000/api/v1/evolution/instances" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_name": "kumon_branch_1",
    "webhook_url": "http://kumon-assistant:8000/api/v1/evolution/webhook"
  }'
```

### List All Instances

```bash
curl "http://localhost:8000/api/v1/evolution/instances"
```

### Get Instance Status

```bash
curl "http://localhost:8000/api/v1/evolution/instances/kumon_main/status"
```

### Delete Instance

```bash
curl -X DELETE "http://localhost:8000/api/v1/evolution/instances/kumon_main"
```

### Restart Instance

```bash
curl -X PUT "http://localhost:8000/api/v1/evolution/instances/kumon_main/restart"
```

## 💬 Sending Messages

### Send Text Message

```bash
curl -X POST "http://localhost:8000/api/v1/evolution/messages/text" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_name": "kumon_main",
    "phone": "5511999999999",
    "message": "Olá! Como posso ajudá-lo hoje?"
  }'
```

### Send Media Message

```bash
curl -X POST "http://localhost:8000/api/v1/evolution/messages/media" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_name": "kumon_main",
    "phone": "5511999999999",
    "media_url": "https://example.com/image.jpg",
    "caption": "Confira nossa metodologia!",
    "media_type": "image"
  }'
```

### Send Button Message

```bash
curl -X POST "http://localhost:8000/api/v1/evolution/messages/buttons" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_name": "kumon_main",
    "phone": "5511999999999",
    "text": "Como posso ajudá-lo?",
    "buttons": [
      {"text": "📋 Informações"},
      {"text": "📅 Agendar"},
      {"text": "💰 Preços"}
    ]
  }'
```

## 🔍 Monitoring and Health Checks

### System Health

```bash
# Check Evolution API integration health
curl "http://localhost:8000/api/v1/evolution/health"

# Check embedding system health
curl "http://localhost:8000/api/v1/embeddings/health"

# Check overall application health
curl "http://localhost:8000/api/v1/health"
```

### View Logs

```bash
# Evolution API logs
docker-compose logs evolution-api

# Kumon Assistant logs
docker-compose logs kumon-assistant

# Qdrant logs
docker-compose logs qdrant

# All service logs
docker-compose logs -f
```

## 🧪 Testing

### Test Message Processing

```bash
curl -X POST "http://localhost:8000/api/v1/evolution/test/message" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_name": "kumon_main",
    "phone": "5511999999999",
    "message": "Como funciona o método Kumon?"
  }'
```

### Setup Embedding System

```bash
# Initialize and test the embedding system
docker-compose exec kumon-assistant python scripts/setup_embeddings.py
```

## 🔧 Troubleshooting

### Common Issues

#### 1. QR Code Not Appearing

```bash
# Check instance status
curl "http://localhost:8000/api/v1/evolution/instances/kumon_main/status"

# Restart instance if needed
curl -X PUT "http://localhost:8000/api/v1/evolution/instances/kumon_main/restart"
```

#### 2. Messages Not Being Received

```bash
# Check webhook configuration
curl "http://localhost:8000/api/v1/evolution/instances/kumon_main"

# Verify webhook URL is correct
# Should be: http://kumon-assistant:8000/api/v1/evolution/webhook
```

#### 3. Evolution API Not Accessible

```bash
# Check if Evolution API is running
docker-compose ps evolution-api

# Check Evolution API logs
docker-compose logs evolution-api

# Restart Evolution API
docker-compose restart evolution-api
```

#### 4. AI Not Responding

```bash
# Check OpenAI API key
curl "http://localhost:8000/api/v1/embeddings/health"

# Test the embedding system
curl -X POST "http://localhost:8000/api/v1/evolution/test/message"
```

### Phone Number Format

Evolution API expects phone numbers in international format:

- ✅ Correct: `5511999999999` (Brazil mobile)
- ✅ Correct: `5511987654321` (São Paulo mobile)
- ❌ Wrong: `11999999999` (missing country code)
- ❌ Wrong: `+55 11 99999-9999` (formatted text)

### Webhook URL Configuration

Make sure your webhook URL is accessible:

- If running locally: `http://localhost:8000/api/v1/evolution/webhook`
- If using Docker Compose: `http://kumon-assistant:8000/api/v1/evolution/webhook`
- If using external server: `https://yourdomain.com/api/v1/evolution/webhook`

## 🎯 Production Deployment

### Security Considerations

1. **Use strong API keys**:

   ```bash
   EVOLUTION_GLOBAL_API_KEY=$(openssl rand -hex 32)
   AUTHENTICATION_API_KEY=$(openssl rand -hex 32)
   ```

2. **Configure CORS properly**:

   ```python
   # In app/main.py
   allow_origins=["https://yourdomain.com"]  # Replace * with your domain
   ```

3. **Use HTTPS**:
   - Set up SSL certificates
   - Use reverse proxy (nginx)
   - Update webhook URLs to use HTTPS

### Scaling

For high-volume deployments:

1. **Multiple instances**: Create separate instances for different units
2. **Load balancing**: Use nginx to distribute requests
3. **Database**: Consider PostgreSQL for persistence
4. **Monitoring**: Set up logging and monitoring services

### Backup and Recovery

```bash
# Backup Evolution API data
docker-compose exec evolution-api tar -czf /backup/evolution_$(date +%Y%m%d).tar.gz /evolution/store

# Backup Qdrant data
docker-compose exec qdrant tar -czf /backup/qdrant_$(date +%Y%m%d).tar.gz /qdrant/storage
```

## 📚 API Documentation

Visit your running application for complete API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Setup Guide**: http://localhost:8000/api/v1/evolution/setup/guide

## 🎉 Success!

Once everything is set up:

1. ✅ Evolution API is running
2. ✅ WhatsApp instance is connected
3. ✅ Kumon Assistant is responding to messages
4. ✅ Semantic search is working
5. ✅ Webhooks are processing messages

Send a message to your WhatsApp number and enjoy your cost-free AI receptionist!

## 🆘 Support

If you encounter issues:

1. Check the logs: `docker-compose logs -f`
2. Verify health endpoints: `curl http://localhost:8000/api/v1/evolution/health`
3. Test the embedding system: `python scripts/setup_embeddings.py`
4. Review this guide for common solutions

---

**🎊 Congratulations! You now have a fully functional, cost-free WhatsApp AI receptionist for your Kumon business!**
