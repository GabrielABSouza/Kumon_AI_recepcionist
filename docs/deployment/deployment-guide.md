# 🚀 Google Cloud Deployment Guide

## Prerequisites

1. **Google Cloud Project**

   - Create a new project in Google Cloud Console
   - Enable billing for the project

2. **Required APIs**

   ```bash
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable containerregistry.googleapis.com
   ```

3. **Install Google Cloud SDK**

   ```bash
   # macOS
   brew install google-cloud-sdk

   # Or download from: https://cloud.google.com/sdk/docs/install
   ```

## 🛠️ Step-by-Step Deployment

### 1. Initialize Google Cloud

```bash
# Login to Google Cloud
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required services
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com
```

### 2. Deploy to Cloud Run

```bash
# Deploy using Cloud Build
gcloud builds submit --config cloudbuild.yaml

# Or deploy directly
gcloud run deploy kumon-assistant \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000 \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10
```

### 3. Set Environment Variables

```bash
# Set sensitive environment variables
gcloud run services update kumon-assistant \
  --region us-central1 \
  --set-env-vars WHATSAPP_TOKEN="your_actual_token_here" \
  --set-env-vars WHATSAPP_PHONE_NUMBER_ID="your_phone_id_here" \
  --set-env-vars WHATSAPP_BUSINESS_ACCOUNT_ID="your_business_id_here" \
  --set-env-vars OPENAI_API_KEY="your_openai_key_here" \
  --set-env-vars BUSINESS_PHONE="+55 11 99999-9999" \
  --set-env-vars BUSINESS_ADDRESS="Your business address"
```

### 4. Get Your Webhook URL

```bash
# Get the service URL
gcloud run services describe kumon-assistant --region us-central1 --format 'value(status.url)'

# Your webhook URL will be:
# https://kumon-assistant-xxxxx-uc.a.run.app
```

### 5. Configure WhatsApp Webhook

1. Go to **Facebook Developer Console**
2. Navigate to **Your App → WhatsApp → Configuration**
3. Set **Webhook URL**: `https://your-cloud-run-url.com/api/v1/whatsapp/webhook`
4. Set **Verify Token**: `kumon_verify_token_2024`
5. Subscribe to **messages** and **messaging_postbacks**

### 6. Test Your Deployment

```bash
# Test health endpoint
curl https://your-cloud-run-url.com/api/v1/health

# Test webhook verification
curl "https://your-cloud-run-url.com/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.challenge=test&hub.verify_token=kumon_verify_token_2024"
```

## 🔒 Security Considerations

### Environment Variables

```bash
# Use Google Secret Manager for sensitive data
gcloud secrets create whatsapp-token --data-file=token.txt
gcloud secrets create openai-key --data-file=openai.txt

# Update Cloud Run to use secrets
gcloud run services update kumon-assistant \
  --region us-central1 \
  --set-secrets WHATSAPP_TOKEN=whatsapp-token:latest \
  --set-secrets OPENAI_API_KEY=openai-key:latest
```

### Custom Domain (Optional)

```bash
# Map custom domain
gcloud run domain-mappings create \
  --service kumon-assistant \
  --domain your-domain.com \
  --region us-central1
```

## 📊 Monitoring & Logging

### View Logs

```bash
# View application logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=kumon-assistant" --limit 50

# Follow logs in real-time
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=kumon-assistant"
```

### Set Up Monitoring

```bash
# Enable monitoring
gcloud services enable monitoring.googleapis.com

# Create uptime check
gcloud alpha monitoring uptime create \
  --display-name="Kumon Assistant Health Check" \
  --resource-type=uptime-url \
  --resource-labels=project_id=YOUR_PROJECT_ID \
  --http-check-path="/api/v1/health" \
  --hostname="your-cloud-run-url.com"
```

## 🔄 Continuous Deployment

### GitHub Actions (Optional)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup Cloud SDK
        uses: google-github-actions/setup-gcloud@v0
        with:
          project_id: ${{ secrets.GCP_PROJECT_ID }}
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          export_default_credentials: true

      - name: Deploy to Cloud Run
        run: gcloud builds submit --config cloudbuild.yaml
```

## 🎯 Post-Deployment Checklist

- [ ] Service is running and accessible
- [ ] Health check endpoint works
- [ ] Webhook verification successful
- [ ] Environment variables configured
- [ ] WhatsApp webhook configured
- [ ] Test message flow end-to-end
- [ ] Monitoring and logging enabled
- [ ] Custom domain configured (if needed)

## 📞 Testing Your Live System

```bash
# Test with curl
curl -X POST https://your-cloud-run-url.com/api/v1/whatsapp/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "id": "test",
      "changes": [{
        "value": {
          "messaging_product": "whatsapp",
          "messages": [{
            "from": "5511999999999",
            "id": "test_msg",
            "timestamp": "1234567890",
            "text": {"body": "Olá! Teste de integração"},
            "type": "text"
          }]
        },
        "field": "messages"
      }]
    }]
  }'
```

Your Kumon AI Receptionist is now live on Google Cloud! 🎉
