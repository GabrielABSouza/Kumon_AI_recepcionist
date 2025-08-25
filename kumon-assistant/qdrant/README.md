# Qdrant Vector Database for Kumon Assistant

This directory contains the Dockerfile and configuration for deploying Qdrant on Railway as a containerized service.

## 🚀 Quick Start

### 1. Deploy to Railway

1. In your Railway project, create a new service
2. Choose "Docker Image" as the source
3. Point to this directory (`/qdrant`)
4. Railway will automatically build and deploy using the Dockerfile

### 2. Configure Environment Variables

In Railway service settings, add these variables:

**Required:**
```bash
QDRANT__STORAGE__STORAGE_PATH=/qdrant/storage
QDRANT__STORAGE__SNAPSHOTS_PATH=/qdrant/snapshots
QDRANT__SERVICE__HTTP_PORT=6333
QDRANT__SERVICE__GRPC_PORT=6334
QDRANT__SERVICE__ENABLE_CORS=true
QDRANT__LOG_LEVEL=info
```

**Optional (but recommended for production):**
```bash
# Generate with: openssl rand -hex 32
QDRANT__SERVICE__API_KEY=your-secure-api-key-here
```

### 3. Connect kumon-assistant to Qdrant

In your `kumon-assistant` service, add:

**Using internal network (recommended):**
```bash
QDRANT_URL=http://qdrant.railway.internal:6333
QDRANT_API_KEY=your-secure-api-key-here  # If authentication is enabled
```

**Using public URL:**
```bash
QDRANT_URL=https://your-qdrant-service.up.railway.app
QDRANT_API_KEY=your-secure-api-key-here  # If authentication is enabled
```

## 📁 Directory Structure

```
qdrant/
├── Dockerfile          # Container configuration
├── config.yaml         # Qdrant configuration file
├── .env.example        # Environment variables template
└── README.md          # This file
```

## 🔧 Configuration Details

### Storage
- **Data Path**: `/qdrant/storage` - All vector data and indexes
- **Snapshots Path**: `/qdrant/snapshots` - Backup snapshots
- **Persistence**: Railway provides persistent volumes

### Networking
- **HTTP Port**: 6333 (REST API)
- **gRPC Port**: 6334 (High-performance protocol)
- **CORS**: Enabled for web access
- **Host**: 0.0.0.0 (listens on all interfaces)

### Performance
- **Vector Size**: 768 (OpenAI embeddings default)
- **Distance Metric**: Cosine (best for semantic similarity)
- **Max Workers**: Auto-detected based on CPU
- **Max Request Size**: 32MB

### Security
- **API Key**: Optional but recommended for production
- **TLS**: Disabled (Railway handles HTTPS)
- **Telemetry**: Disabled for privacy

## 🧪 Testing the Deployment

### 1. Health Check
```bash
curl https://your-qdrant-service.up.railway.app/health
```

Expected response:
```json
{
  "title": "qdrant - vector search engine",
  "version": "1.12.1",
  "status": "ok"
}
```

### 2. Collections Info
```bash
curl https://your-qdrant-service.up.railway.app/collections
```

### 3. Create Test Collection
```bash
curl -X PUT https://your-qdrant-service.up.railway.app/collections/test \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 768,
      "distance": "Cosine"
    }
  }'
```

## 🐛 Troubleshooting

### Connection Refused
- Check if the service is running: Look at Railway logs
- Verify the URL is correct
- Ensure CORS is enabled if accessing from browser
- Check if API key is required

### Storage Issues
- Ensure Railway volume is attached
- Check permissions on storage directories
- Verify paths match environment variables

### Performance Issues
- Increase `QDRANT__SERVICE__MAX_WORKERS`
- Adjust collection optimization settings
- Consider enabling quantization for large datasets

### Memory Issues
- Enable on-disk payload storage
- Use scalar quantization
- Reduce HNSW index parameters

## 📊 Monitoring

### Logs
View in Railway dashboard or use:
```bash
railway logs
```

### Metrics
Qdrant exposes metrics at:
```
https://your-qdrant-service.up.railway.app/metrics
```

## 🔄 Backup and Restore

### Create Snapshot
```bash
curl -X POST https://your-qdrant-service.up.railway.app/snapshots
```

### List Snapshots
```bash
curl https://your-qdrant-service.up.railway.app/snapshots
```

### Restore from Snapshot
Upload snapshot file to `/qdrant/snapshots` and restart service.

## 📚 Additional Resources

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Qdrant API Reference](https://qdrant.tech/documentation/quick-start/)
- [Railway Documentation](https://docs.railway.app/)
- [Docker Hub - Qdrant](https://hub.docker.com/r/qdrant/qdrant)

## 🤝 Support

For issues specific to this deployment:
1. Check Railway logs for errors
2. Verify environment variables
3. Test with curl commands above
4. Review Qdrant documentation

For Kumon Assistant integration issues:
1. Check `QDRANT_URL` in kumon-assistant service
2. Verify API key matches (if using authentication)
3. Test connection from kumon-assistant logs
4. Ensure both services are in the same Railway project
