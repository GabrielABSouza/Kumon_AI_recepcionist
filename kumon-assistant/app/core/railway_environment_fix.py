"""
CRITICAL FIX: Railway Environment Detection and Configuration
Forces proper Railway environment detection and database configuration
"""

import logging
import os
import tempfile
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Execution guard to prevent multiple executions
_execution_guard = threading.Lock()
_fixes_applied = False
_execution_count = 0
_process_lock_file = None


def _create_process_lock():
    """Create a process-level lock file to prevent multiple executions across restarts"""
    global _process_lock_file
    try:
        lock_dir = tempfile.gettempdir()
        lock_path = os.path.join(lock_dir, "railway_environment_fix.lock")

        # Create lock file if it doesn't exist
        _process_lock_file = open(lock_path, "w")
        _process_lock_file.write(f"pid:{os.getpid()}\ntime:{time.time()}\n")
        _process_lock_file.flush()

        # Try to acquire exclusive lock (non-blocking)
        try:
            import fcntl

            fcntl.flock(_process_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.debug(f"Process lock acquired: {lock_path}")
            return True
        except (ImportError, BlockingIOError):
            # fcntl not available (Windows) or lock already held
            _process_lock_file.close()
            _process_lock_file = None
            return False

    except Exception as e:
        logger.debug(f"Could not create process lock: {e}")
        if _process_lock_file:
            _process_lock_file.close()
            _process_lock_file = None
        return False


def _release_process_lock():
    """Release the process-level lock"""
    global _process_lock_file
    if _process_lock_file:
        try:
            _process_lock_file.close()
            _process_lock_file = None
            logger.debug("Process lock released")
        except Exception as e:
            logger.debug(f"Error releasing process lock: {e}")


def detect_railway_environment() -> bool:
    """
    Detect if running on Railway platform using multiple indicators
    """
    # Check for manual override first
    force_railway = os.getenv("FORCE_RAILWAY_DETECTION")
    if force_railway and force_railway.lower() in ["1", "true", "yes"]:
        logger.info("🔧 Railway environment detection manually forced via FORCE_RAILWAY_DETECTION")
        return True

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
        "RAILWAY_GIT_COMMIT_SHA",
    ]

    # Check if any Railway-specific variables are present
    railway_vars_found = [var for var in indicators if os.getenv(var)]

    # Additional Railway detection methods - more flexible approach
    is_railway = (
        bool(railway_vars_found)
        or (
            # Railway sets PORT environment variable
            os.getenv("PORT") is not None
            and
            # Railway deployments often have these characteristics
            (
                os.getenv("NODE_ENV") == "production"
                or os.getenv("ENVIRONMENT") == "production"
                or os.getenv("RAILWAY_ENVIRONMENT") is not None
            )
            and
            # Check for Railway-style service names in hostname/paths
            any(keyword in os.getenv("HOSTNAME", "").lower() for keyword in ["railway", "app-"])
        )
        or (
            # Fallback: if PORT is set and looks like production deployment
            os.getenv("PORT") is not None
            and os.getenv("NODE_ENV") != "development"
            and os.getenv("HOSTNAME") is not None
            and "localhost" not in os.getenv("HOSTNAME", "").lower()
        )
    )

    # Enhanced logging for debugging
    if railway_vars_found:
        logger.info(f"Railway environment detected via variables: {railway_vars_found}")
    else:
        logger.debug("No direct Railway environment variables found")

    # Debug logging for detection criteria
    logger.debug(f"Railway detection criteria:")
    logger.debug(f"  PORT: {os.getenv('PORT')}")
    logger.debug(f"  NODE_ENV: {os.getenv('NODE_ENV')}")
    logger.debug(f"  ENVIRONMENT: {os.getenv('ENVIRONMENT')}")
    logger.debug(f"  RAILWAY_ENVIRONMENT: {os.getenv('RAILWAY_ENVIRONMENT')}")
    logger.debug(f"  HOSTNAME: {os.getenv('HOSTNAME')}")
    logger.debug(f"  Final detection result: {is_railway}")

    if is_railway:
        logger.info("✅ Railway environment successfully detected")
    else:
        logger.warning("❌ Railway environment not detected - running in local mode")

    return is_railway


def get_railway_database_url() -> Optional[str]:
    """
    Get Railway database URL with fallback strategies
    """
    # Try different Railway database URL variable names
    db_url_vars = [
        "DATABASE_URL",  # Standard Railway PostgreSQL
        "POSTGRES_URL",  # Alternative naming
        "POSTGRESQL_URL",  # Alternative naming
        "DB_URL",  # Some Railway services use this
        "DATABASE_PRIVATE_URL",  # Railway private networking
        "DATABASE_PUBLIC_URL",  # Railway public URL
        # Railway PostgreSQL plugin specific names
        "PGHOST",  # PostgreSQL host (we'll construct URL)
        "PGDATABASE",  # PostgreSQL database name
        "PGUSER",  # PostgreSQL user
        "PGPASSWORD",  # PostgreSQL password
        "PGPORT",  # PostgreSQL port
    ]

    # First try direct URL variables
    url_vars = [
        "DATABASE_URL",
        "POSTGRES_URL",
        "POSTGRESQL_URL",
        "DB_URL",
        "DATABASE_PRIVATE_URL",
        "DATABASE_PUBLIC_URL",
    ]

    # First try direct URL variables
    for var in url_vars:
        url = os.getenv(var)
        if url and (url.startswith("postgresql://") or url.startswith("postgres://")):
            logger.info(f"Found Railway database URL via {var}")
            return url

    # Try to construct URL from individual components (Railway PostgreSQL plugin style)
    pghost = os.getenv("PGHOST")
    pgdatabase = os.getenv("PGDATABASE")
    pguser = os.getenv("PGUSER")
    pgpassword = os.getenv("PGPASSWORD")
    pgport = os.getenv("PGPORT", "5432")

    if all([pghost, pgdatabase, pguser, pgpassword]):
        constructed_url = f"postgresql://{pguser}:{pgpassword}@{pghost}:{pgport}/{pgdatabase}"
        logger.info(f"Constructed Railway database URL from PG* variables")
        return constructed_url

    # Debug: List ALL environment variables that might be database-related
    logger.warning("No valid Railway database URL found. Debugging environment variables:")
    all_vars = sorted(os.environ.keys())
    db_related = [
        var
        for var in all_vars
        if any(keyword in var.upper() for keyword in ["DATABASE", "POSTGRES", "PG", "DB"])
    ]

    for var in db_related:
        value = os.getenv(var, "")
        # Don't log full credentials, just show if present
        if any(keyword in var.upper() for keyword in ["PASSWORD", "PASS", "SECRET", "KEY"]):
            logger.info(f"  {var}: {'[PRESENT]' if value else '[MISSING]'}")
        else:
            logger.info(f"  {var}: {value[:50]}{'...' if len(value) > 50 else ''}")

    logger.warning("No valid Railway database URL found")
    return None


def get_railway_redis_url() -> Optional[str]:
    """
    Get Railway Redis URL with fallback strategies
    """
    redis_url_vars = [
        "REDIS_URL",  # Standard Railway Redis
        "REDISCLOUD_URL",  # RedisCloud addon
        "REDIS_PRIVATE_URL",  # Railway private networking
        "REDIS_PUBLIC_URL",  # Railway public URL
        "CACHE_URL",  # Generic cache URL
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
    qdrant_url_vars = ["QDRANT_URL", "QDRANT_HOST", "VECTOR_DB_URL", "QDRANT_ENDPOINT"]

    qdrant_key_vars = ["QDRANT_API_KEY", "QDRANT_KEY", "VECTOR_DB_API_KEY", "QDRANT_TOKEN"]

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
        # Try Railway internal networking
        # Format: http://{service-name}.railway.internal:{port}
        qdrant_service_name = os.getenv("QDRANT_SERVICE_NAME", "qdrant")
        qdrant_url = f"http://{qdrant_service_name}.railway.internal:6333"
        logger.warning(f"Using Railway internal networking URL: {qdrant_url}")

    return {"url": qdrant_url, "api_key": qdrant_key}


def apply_railway_environment_fixes():
    """
    Apply Railway environment fixes by setting missing environment variables
    EXECUTION GUARD: Ensures fixes are applied only ONCE per application startup
    """
    global _fixes_applied, _execution_count

    with _execution_guard:
        _execution_count += 1

        # Execution guard - prevent multiple executions
        if _fixes_applied:
            logger.info(
                f"🔒 Railway environment fixes already applied (execution #{_execution_count})"
            )
            logger.debug(f"Previous execution completed successfully - skipping duplicate call")
            return

        # Additional process-level guard for extra safety
        process_lock_acquired = _create_process_lock()
        if not process_lock_acquired:
            logger.debug("Process lock not acquired - continuing with thread-level guard only")

        logger.info(f"🔧 Applying Railway environment fixes (execution #{_execution_count})...")

    is_railway = detect_railway_environment()

    if is_railway:
        logger.info("🚀 Railway environment detected - applying fixes")

        # Force set RAILWAY_ENVIRONMENT if not set
        if not os.getenv("RAILWAY_ENVIRONMENT"):
            os.environ["RAILWAY_ENVIRONMENT"] = "1"
            logger.info("✅ Set RAILWAY_ENVIRONMENT=1")

        # Fix database URL - always try to get Railway DB URL
        railway_db_url = get_railway_database_url()
        if railway_db_url:
            # Set DATABASE_URL if not set, or log if already set
            current_db_url = os.getenv("DATABASE_URL")
            if not current_db_url:
                os.environ["DATABASE_URL"] = railway_db_url
                logger.info("✅ Fixed DATABASE_URL from Railway detection")
            else:
                logger.info(f"ℹ️ DATABASE_URL already set: {current_db_url[:50]}...")
                # Verify if it's a valid PostgreSQL URL
                if not (
                    current_db_url.startswith("postgresql://")
                    or current_db_url.startswith("postgres://")
                ):
                    logger.warning(
                        f"⚠️ Existing DATABASE_URL doesn't look like PostgreSQL - replacing"
                    )
                    os.environ["DATABASE_URL"] = railway_db_url
                    logger.info("✅ Replaced invalid DATABASE_URL with Railway URL")
        else:
            logger.error("❌ Could not determine Railway DATABASE_URL")

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

        # Mark fixes as applied BEFORE verification to prevent race conditions
        _fixes_applied = True

        # Verify fixes
        logger.info("🔍 Verification:")
        logger.info(f"DATABASE_URL present: {bool(os.getenv('DATABASE_URL'))}")
        logger.info(f"REDIS_URL present: {bool(os.getenv('REDIS_URL'))}")
        logger.info(f"QDRANT_URL: {os.getenv('QDRANT_URL', 'Not set')}")
        logger.info(f"RAILWAY_ENVIRONMENT: {os.getenv('RAILWAY_ENVIRONMENT', 'Not set')}")
        logger.info(f"✅ Railway environment fixes completed and marked as applied")

        # Release process lock
        _release_process_lock()

    else:
        logger.info("💻 Local development environment detected - no Railway fixes needed")
        # Mark as applied even for local development to prevent future executions
        _fixes_applied = True

        # Release process lock
        _release_process_lock()


# REMOVED: Auto-execution on import to prevent multiple executions
# Railway environment fixes should ONLY be called explicitly from main.py
# This prevents the critical issue of 3x execution causing config corruption


# Debug function to check if fixes were applied
def get_execution_status():
    """Get current execution status for debugging"""
    return {
        "fixes_applied": _fixes_applied,
        "execution_count": _execution_count,
        "thread_safe": True,
    }


# Utility function to force reset (for testing only)
def _reset_execution_guard():
    """TESTING ONLY: Reset execution guard - DO NOT USE IN PRODUCTION"""
    global _fixes_applied, _execution_count
    if __name__ == "__main__":  # Only allow in direct script execution
        with _execution_guard:
            _fixes_applied = False
            _execution_count = 0
            logger.warning("⚠️ TESTING: Execution guard reset")
