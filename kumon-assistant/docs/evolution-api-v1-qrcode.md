# Evolution API v1 - WhatsApp QR Code Configuration

## 🔍 QR Code Requirements for Evolution API v1.7.4

### Prerequisites

1. **Evolution API v1.7.4 running** (not v2.x)
2. **Authentication configured** with API key
3. **Database properly connected** for storing instance data
4. **Server URL correctly set** for callbacks

### Key Endpoints for WhatsApp Integration

#### 1. Create Instance
```bash
POST /instance/create
Headers:
  apikey: YOUR_API_KEY
  Content-Type: application/json
Body:
{
  "instanceName": "kumon-whatsapp",
  "integration": "WHATSAPP-BAILEYS",
  "token": "YOUR_INSTANCE_TOKEN"
}
```

#### 2. Get QR Code
```bash
GET /instance/connect/kumon-whatsapp
Headers:
  apikey: YOUR_API_KEY
```

This will return:
```json
{
  "instance": {
    "instanceName": "kumon-whatsapp", 
    "status": "qr"
  },
  "qrcode": {
    "code": "QR_CODE_STRING",
    "base64": "data:image/png;base64,..."
  }
}
```

#### 3. Check Instance Status
```bash
GET /instance/connectionState/kumon-whatsapp
Headers:
  apikey: YOUR_API_KEY
```

### Environment Variables for QR Code

Key variables that affect QR code generation:

```env
# Required for v1
AUTHENTICATION_TYPE=apikey
AUTHENTICATION_API_KEY=your-secure-key

# Instance management
DEL_INSTANCE=false  # Don't delete instances on disconnect
DATABASE_SAVE_DATA_INSTANCE=true  # Save instance data

# QR Code specific
QRCODE_EXPIRATION_TIME=60  # Seconds before QR expires
QRCODE_LIMIT=30  # Max QR codes per instance

# Webhook for status updates (optional)
WEBHOOK_GLOBAL_URL=https://your-app.com/webhook
WEBHOOK_GLOBAL_ENABLED=true
```

### Integration Flow

1. **Create WhatsApp instance** via API
2. **Request QR code** for the instance
3. **Display QR code** to user (base64 image)
4. **Monitor connection status** via webhook or polling
5. **Handle connected state** - save instance data

### Common Issues & Solutions

#### Issue 1: QR Code not generating
- Check if instance was created successfully
- Verify DATABASE_SAVE_DATA_INSTANCE=true
- Ensure Evolution API has write permissions to /evolution/store

#### Issue 2: QR Code expires too quickly
- Increase QRCODE_EXPIRATION_TIME
- Implement auto-refresh in frontend

#### Issue 3: Instance disconnects after scanning
- Check SERVER_URL is accessible externally
- Verify database is saving instance data
- Ensure DEL_INSTANCE=false

### Testing QR Code Locally

```bash
# 1. Create instance
curl -X POST http://localhost:8080/instance/create \
  -H "apikey: test123" \
  -H "Content-Type: application/json" \
  -d '{"instanceName": "test-whatsapp", "integration": "WHATSAPP-BAILEYS"}'

# 2. Get QR code
curl http://localhost:8080/instance/connect/test-whatsapp \
  -H "apikey: test123"

# 3. Check status
curl http://localhost:8080/instance/connectionState/test-whatsapp \
  -H "apikey: test123"
```

### Next Steps for Production

1. **Deploy Evolution API v1.7.4** with corrected configuration
2. **Create webhook endpoint** in Kumon Assistant for status updates
3. **Implement QR code display** in frontend
4. **Add instance management** endpoints to Kumon Assistant
5. **Test WhatsApp message flow** after connection

### Security Considerations

- Always use HTTPS in production
- Rotate API keys regularly
- Implement rate limiting on QR code generation
- Monitor for suspicious connection attempts
- Store instance tokens securely