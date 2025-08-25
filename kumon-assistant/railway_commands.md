# Railway Commands & Common Issues Reference

## Working Railway CLI Commands

### Environment Management
```bash
# Switch environments
railway environment staging
railway environment production

# Check current status
railway status
```

### Service Management
```bash
# Add services (databases)
railway add --database redis
railway add --database postgres

# Add empty services
railway add --service <service-name>

# Link to existing service (via Dashboard is more reliable)
# CLI linking often fails with TTY errors
```

### Deployment
```bash
# Deploy current code
railway up

# Deploy with specific options
railway up --detach
```

## Critical Issues & Solutions

### 1. Deploying to Wrong Service
**Problem**: CLI connects to last created service instead of main application service
**Symptom**: Deploying Evolution API or other auxiliary services instead of main app
**Solution**: 
- Always check `railway status` before deploying
- Use Railway Dashboard to manually connect to correct service
- Main service is usually named `Kumon_AI_recepcionist` or similar

### 2. Dockerfile Not Found in Staging
**Problem**: Railway staging uses Nixpacks instead of Dockerfile
**Root Cause**: Staging environment doesn't inherit build configurations from production
**Failed Solutions**:
- Trying to change Builder (field is read-only when set via railway.json)
- Using `--dockerfile` flag (doesn't exist)
- Trying to set custom Dockerfile path (not available in Nixpacks)

**Working Solution**: Create Dockerfile in repository root that copies from subdirectory

### 3. Railway Config File Path Issues
**Problem**: Railway can't find railway.json when using subdirectories
**Symptom**: "Railway config file not found" errors
**Solution**: Use full path `kumon-assistant/railway.json` in Railway Config File setting

### 4. Service Creation Confusion
**Problem**: Creating duplicate services when they already exist
**Impact**: Wrong configurations, deployment to wrong targets
**Prevention**: Always check Dashboard before creating new services

### 5. CLI TTY Errors
**Problem**: Railway CLI fails with "The input device is not a TTY" 
**Affected Commands**: `railway service`, `railway link`
**Solution**: Use Railway Dashboard for service management instead of CLI

### 6. Builder Configuration Lock
**Problem**: Cannot change Builder field when it's set via railway.json
**Symptom**: Grayed out Builder field in Dashboard
**Key Insight**: railway.json controls build configuration, manual changes are blocked
**Solution**: Either use railway.json OR manual config, not both

## Environment-Specific Notes

### Staging Environment
- Requires manual service creation (Redis, PostgreSQL, Evolution API)
- Does not inherit configurations from production
- Needs separate variable configuration
- May require Dockerfile in repository root for proper detection

### Production Environment  
- Uses railway.json configuration successfully
- Dockerfile in subdirectory works correctly
- All services properly configured

## Best Practices

1. **Always check `railway status`** before any operation
2. **Use Dashboard for service management** - more reliable than CLI
3. **Verify service connection** before deploying
4. **Don't create duplicate services** - check existing ones first
5. **When in doubt, use Dashboard** - CLI has many TTY-related issues

## Railway File Structure Requirements

```
repository-root/
├── Dockerfile (for staging compatibility)
├── kumon-assistant/
│   ├── railway.json
│   ├── Dockerfile (for production)
│   ├── app/
│   └── requirements-production.txt
```

## Common Error Messages & Solutions

- **"No start command could be found"** → Nixpacks detection, need proper Dockerfile setup
- **"Service name must be unique"** → Service already exists, don't create duplicate
- **"The input device is not a TTY"** → Use Dashboard instead of CLI
- **"Railway config file not found"** → Use full path with subdirectory
- **"Dockerfile does not exist"** → File in wrong location relative to build context
- **"Could not find root directory: kumon-assistant"** → Missing staging environment configuration in railway.json causing fallback behavior. Solution: Add explicit staging environment with RAILWAY_ENVIRONMENT=1 and FORCE_RAILWAY_DETECTION=1