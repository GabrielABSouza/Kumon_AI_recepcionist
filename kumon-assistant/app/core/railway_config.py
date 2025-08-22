"""
Railway-Optimized Configuration Module

Provides environment-aware configuration with Railway-specific optimizations:
- Reduced timeouts for cloud deployment
- Appropriate pool sizes for Railway limits
- Graceful degradation settings
- Circuit breaker configurations
"""

import os
from typing import Dict, Any
from enum import Enum

from .logger import app_logger


class DeploymentEnvironment(str, Enum):
    """Deployment environment detection"""
    RAILWAY = "railway"
    LOCAL = "local"
    DOCKER = "docker"
    PRODUCTION = "production"


def detect_environment() -> DeploymentEnvironment:
    """Detect current deployment environment"""
    # Railway detection
    if os.getenv("RAILWAY_ENVIRONMENT"):
        return DeploymentEnvironment.RAILWAY
    
    # Docker detection
    if os.path.exists("/.dockerenv"):
        return DeploymentEnvironment.DOCKER
    
    # Production detection (generic)
    if os.getenv("ENVIRONMENT") == "production":
        return DeploymentEnvironment.PRODUCTION
    
    # Default to local
    return DeploymentEnvironment.LOCAL


class RailwayOptimizedConfig:
    """Railway-optimized configuration settings"""
    
    def __init__(self):
        self.environment = detect_environment()
        app_logger.info(f"Detected environment: {self.environment.value}")
    
    def get_timeout_config(self) -> Dict[str, int]:
        """Get environment-aware timeout configuration"""
        if self.environment == DeploymentEnvironment.RAILWAY:
            return {
                # Railway-optimized timeouts
                "llm_request_timeout": 15,          # Was 30s
                "db_pool_timeout": 10,              # Was 30s
                "db_connection_timeout": 10,        # Was 30s
                "db_statement_timeout": 10000,      # Was 30000ms
                "memory_postgres_timeout": 10,      # Was 30s
                "health_check_timeout": 5,          # Quick health checks
                "circuit_breaker_timeout": 10,      # Was 30s
                "redis_socket_timeout": 5,          # Quick Redis
                "webhook_timeout": 15,              # External calls
                "cache_operation_timeout": 3,       # Fast cache ops
            }
        elif self.environment == DeploymentEnvironment.LOCAL:
            return {
                # Local development - more forgiving
                "llm_request_timeout": 30,
                "db_pool_timeout": 30,
                "db_connection_timeout": 30,
                "db_statement_timeout": 30000,
                "memory_postgres_timeout": 30,
                "health_check_timeout": 10,
                "circuit_breaker_timeout": 30,
                "redis_socket_timeout": 10,
                "webhook_timeout": 30,
                "cache_operation_timeout": 10,
            }
        else:
            return {
                # Production/Docker - balanced
                "llm_request_timeout": 20,
                "db_pool_timeout": 15,
                "db_connection_timeout": 15,
                "db_statement_timeout": 20000,
                "memory_postgres_timeout": 15,
                "health_check_timeout": 8,
                "circuit_breaker_timeout": 15,
                "redis_socket_timeout": 8,
                "webhook_timeout": 20,
                "cache_operation_timeout": 5,
            }
    
    def get_pool_config(self) -> Dict[str, int]:
        """Get environment-aware connection pool configuration"""
        if self.environment == DeploymentEnvironment.RAILWAY:
            return {
                # Railway free tier limits
                "db_pool_size": 5,                  # Was 20
                "db_max_overflow": 5,               # Was 10
                "memory_postgres_min_pool": 2,      # Was 5
                "memory_postgres_max_pool": 10,     # Was 20
                "redis_max_connections": 10,        # Was 20
                "max_workers": 2,                   # Thread pool size
                "max_concurrent_requests": 10,      # Rate limiting
            }
        elif self.environment == DeploymentEnvironment.LOCAL:
            return {
                # Local development - generous
                "db_pool_size": 20,
                "db_max_overflow": 10,
                "memory_postgres_min_pool": 5,
                "memory_postgres_max_pool": 20,
                "redis_max_connections": 20,
                "max_workers": 4,
                "max_concurrent_requests": 50,
            }
        else:
            return {
                # Production - balanced
                "db_pool_size": 10,
                "db_max_overflow": 8,
                "memory_postgres_min_pool": 3,
                "memory_postgres_max_pool": 15,
                "redis_max_connections": 15,
                "max_workers": 3,
                "max_concurrent_requests": 25,
            }
    
    def get_circuit_breaker_config(self) -> Dict[str, Any]:
        """Get environment-aware circuit breaker configuration"""
        if self.environment == DeploymentEnvironment.RAILWAY:
            return {
                # Fast failure for Railway
                "failure_threshold": 2,              # Fail fast
                "recovery_timeout": 15,              # Quick recovery
                "success_threshold": 1,              # Single success to close
                "timeout": 10,                       # Operation timeout
            }
        else:
            return {
                # More forgiving for local/production
                "failure_threshold": 3,
                "recovery_timeout": 30,
                "success_threshold": 2,
                "timeout": 30,
            }
    
    def get_cache_config(self) -> Dict[str, Any]:
        """Get environment-aware cache configuration"""
        if self.environment == DeploymentEnvironment.RAILWAY:
            return {
                # Reduced cache sizes for Railway
                "l1_max_entries": 500,               # Was 1000
                "l1_ttl": 180,                       # 3 minutes (was 5)
                "l1_max_size_mb": 50,                # Was 100MB
                "l2_ttl": 86400,                     # 1 day (was 7)
                "l3_ttl": 604800,                    # 7 days (was 30)
            }
        else:
            return {
                # Normal cache sizes
                "l1_max_entries": 1000,
                "l1_ttl": 300,
                "l1_max_size_mb": 100,
                "l2_ttl": 604800,
                "l3_ttl": 2592000,
            }
    
    def get_retry_config(self) -> Dict[str, Any]:
        """Get environment-aware retry configuration"""
        if self.environment == DeploymentEnvironment.RAILWAY:
            return {
                "max_retries": 2,                    # Less retries
                "retry_delay": 1,                    # 1 second
                "retry_backoff": 2,                  # Exponential backoff
                "retry_max_delay": 5,                # Max 5 seconds
            }
        else:
            return {
                "max_retries": 3,
                "retry_delay": 2,
                "retry_backoff": 2,
                "retry_max_delay": 10,
            }
    
    def apply_to_settings(self, settings: Any) -> None:
        """Apply Railway optimizations to existing settings"""
        timeout_config = self.get_timeout_config()
        pool_config = self.get_pool_config()
        circuit_config = self.get_circuit_breaker_config()
        
        # Apply timeout optimizations
        settings.LLM_REQUEST_TIMEOUT_SECONDS = timeout_config["llm_request_timeout"]
        settings.DB_POOL_TIMEOUT = timeout_config["db_pool_timeout"]
        settings.MEMORY_POSTGRES_COMMAND_TIMEOUT = timeout_config["memory_postgres_timeout"]
        
        # Apply pool optimizations
        settings.DB_POOL_SIZE = pool_config["db_pool_size"]
        settings.DB_MAX_OVERFLOW = pool_config["db_max_overflow"]
        settings.MEMORY_POSTGRES_MIN_POOL_SIZE = pool_config["memory_postgres_min_pool"]
        settings.MEMORY_POSTGRES_MAX_POOL_SIZE = pool_config["memory_postgres_max_pool"]
        
        # Apply circuit breaker optimizations
        settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD = circuit_config["failure_threshold"]
        settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT = circuit_config["recovery_timeout"]
        settings.CIRCUIT_BREAKER_SUCCESS_THRESHOLD = circuit_config["success_threshold"]
        settings.CIRCUIT_BREAKER_TIMEOUT = circuit_config["timeout"]
        
        app_logger.info("Railway optimizations applied", extra={
            "environment": self.environment.value,
            "timeouts": timeout_config,
            "pools": pool_config,
            "circuit_breakers": circuit_config
        })
    
    def get_health_check_config(self) -> Dict[str, Any]:
        """Get health check configuration"""
        return {
            "startup_timeout": 10 if self.environment == DeploymentEnvironment.RAILWAY else 30,
            "liveness_timeout": 5 if self.environment == DeploymentEnvironment.RAILWAY else 10,
            "readiness_timeout": 5 if self.environment == DeploymentEnvironment.RAILWAY else 10,
            "check_interval": 30,
            "failure_threshold": 3,
        }


# Global instance
railway_config = RailwayOptimizedConfig()


def get_optimized_settings():
    """Get settings optimized for current environment"""
    from .config import settings
    
    # Apply Railway optimizations if needed
    railway_config.apply_to_settings(settings)
    
    return settings