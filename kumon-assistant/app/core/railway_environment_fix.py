"""
CRITICAL FIX: Railway Environment Detection and Configuration
Forces proper Railway environment detection and database configuration
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def detect_railway_environment() -> bool:
    """
    Detect if running on Railway platform using multiple indicators
    """
    indicators = [
        # Railway sets these environment variables
        "RAILWAY_ENVIRONMENT_ID",
        "RAILWAY_PROJECT_ID", 
        "RAILWAY_SERVICE_ID",
        "RAILWAY_DEPLOYMENT_ID",
        "RAILWAY_REPLICA_ID",
        "RAILWAY_VOLUME_MOUNT_PATH",
        "RAILWAY_TCP_PROXY_PORT",
        "RAILWAY_TCP_APPLICATION_PORT",
        # Railway also sets PORT and other deployment indicators
        "RAILWAY_GIT_COMMIT_SHA"
    ]
    
    # Check if any Railway-specific variables are present
    railway_vars_found = [var for var in indicators if os.getenv(var)]
    
    # Additional Railway detection methods
    is_railway = bool(railway_vars_found) or (
        # Railway typically sets PORT to 8080 or dynamic port
        (os.getenv("PORT") and os.getenv("PORT") in ["8080", "3000"]) and
        # Railway deployments often have these characteristics
        (os.getenv("NODE_ENV") == "production" or os.getenv("ENVIRONMENT") == "production") and
        # Check for Railway-style service names in hostname/paths
        any(keyword in os.getenv("HOSTNAME", "").lower() for keyword in ["railway", "app-"])
    )
    
    if railway_vars_found:
        logger.info(f"Railway environment detected via variables: {railway_vars_found}")
    
    return is_railway

def get_railway_database_url() -> Optional[str]:
    """
    Get Railway database URL with fallback strategies
    """
    # Try different Railway database URL variable names
    db_url_vars = [
        "DATABASE_URL",           # Standard Railway PostgreSQL
        "POSTGRES_URL",          # Alternative naming
        "POSTGRESQL_URL",        # Alternative naming  
        "DB_URL",                # Some Railway services use this
        "DATABASE_PRIVATE_URL",  # Railway private networking
        "DATABASE_PUBLIC_URL"    # Railway public URL
    ]
    
    for var in db_url_vars:
        url = os.getenv(var)
        if url and (url.startswith("postgresql://") or url.startswith("postgres://")):
            logger.info(f"Found Railway database URL via {var}")
            return url
    
    logger.warning("No valid Railway database URL found")
    return None

def get_railway_redis_url() -> Optional[str]:
    """
    Get Railway Redis URL with fallback strategies
    """
    redis_url_vars = [
        "REDIS_URL",              # Standard Railway Redis
        "REDISCLOUD_URL",         # RedisCloud addon
        "REDIS_PRIVATE_URL",      # Railway private networking
        "REDIS_PUBLIC_URL",       # Railway public URL
        "CACHE_URL"               # Generic cache URL
    ]
    
    for var in redis_url_vars:
        url = os.getenv(var)
        if url and (url.startswith("redis://") or url.startswith("rediss://")):
            logger.info(f"Found Railway Redis URL via {var}")
            return url
    
    logger.warning("No valid Railway Redis URL found")
    return None

def get_railway_qdrant_config() -> Dict[str, Any]:
    """
    Get Railway Qdrant configuration
    """
    # Try different Qdrant variable names
    qdrant_url_vars = [
        "QDRANT_URL",
        "QDRANT_HOST", 
        "VECTOR_DB_URL",
        "QDRANT_ENDPOINT"
    ]
    
    qdrant_key_vars = [
        "QDRANT_API_KEY",
        "QDRANT_KEY", 
        "VECTOR_DB_API_KEY",
        "QDRANT_TOKEN"
    ]
    
    # Find URL
    qdrant_url = None
    for var in qdrant_url_vars:
        url = os.getenv(var)
        if url and ("qdrant" in url.lower() or url.startswith("http")):
            qdrant_url = url
            logger.info(f"Found Railway Qdrant URL via {var}: {url}")
            break
    
    # Find API key
    qdrant_key = None
    for var in qdrant_key_vars:
        key = os.getenv(var)
        if key:
            qdrant_key = key
            logger.info(f"Found Railway Qdrant API key via {var}")
            break
    
    # Default to Railway-style Qdrant if no URL found
    if not qdrant_url:
        qdrant_url = "https://qdrant-production.up.railway.app"
        logger.warning(f"Using default Railway Qdrant URL: {qdrant_url}")
    
    return {
        "url": qdrant_url,
        "api_key": qdrant_key
    }

def apply_railway_environment_fixes():
    """
    Apply Railway environment fixes by setting missing environment variables
    """
    logger.info("🔧 Applying Railway environment fixes...")
    
    is_railway = detect_railway_environment()
    
    if is_railway:
        logger.info("🚀 Railway environment detected - applying fixes")
        
        # Force set RAILWAY_ENVIRONMENT if not set
        if not os.getenv("RAILWAY_ENVIRONMENT"):
            os.environ["RAILWAY_ENVIRONMENT"] = "1"
            logger.info("✅ Set RAILWAY_ENVIRONMENT=1")
        
        # Fix database URL
        if not os.getenv("DATABASE_URL"):
            railway_db_url = get_railway_database_url()
            if railway_db_url:
                os.environ["DATABASE_URL"] = railway_db_url
                logger.info("✅ Fixed DATABASE_URL")
        
        # Fix Redis URL  
        if not os.getenv("REDIS_URL"):
            railway_redis_url = get_railway_redis_url()
            if railway_redis_url:
                os.environ["REDIS_URL"] = railway_redis_url
                logger.info("✅ Fixed REDIS_URL")
        
        # Fix Qdrant configuration
        qdrant_config = get_railway_qdrant_config()
        if qdrant_config["url"] and not os.getenv("QDRANT_URL"):
            os.environ["QDRANT_URL"] = qdrant_config["url"]
            logger.info("✅ Fixed QDRANT_URL")
        
        if qdrant_config["api_key"] and not os.getenv("QDRANT_API_KEY"):
            os.environ["QDRANT_API_KEY"] = qdrant_config["api_key"] 
            logger.info("✅ Fixed QDRANT_API_KEY")
        
        # Set production environment
        if not os.getenv("ENVIRONMENT"):
            os.environ["ENVIRONMENT"] = "production"
            logger.info("✅ Set ENVIRONMENT=production")
        
        logger.info("🎯 Railway environment fixes applied successfully")
        
        # Verify fixes
        logger.info("🔍 Verification:")
        logger.info(f"DATABASE_URL present: {bool(os.getenv('DATABASE_URL'))}")
        logger.info(f"REDIS_URL present: {bool(os.getenv('REDIS_URL'))}")  
        logger.info(f"QDRANT_URL: {os.getenv('QDRANT_URL', 'Not set')}")
        logger.info(f"RAILWAY_ENVIRONMENT: {os.getenv('RAILWAY_ENVIRONMENT', 'Not set')}")
        
    else:
        logger.info("💻 Local development environment detected - no Railway fixes needed")

# Auto-apply fixes on import in production-like environments  
if __name__ != "__main__":
    # Only auto-apply if it looks like Railway
    if any(os.getenv(var) for var in ["PORT", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT_ID"]):
        apply_railway_environment_fixes()