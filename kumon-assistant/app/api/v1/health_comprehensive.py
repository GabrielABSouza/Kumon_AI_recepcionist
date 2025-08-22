"""
Wave 5: Comprehensive Health Check Endpoints
Railway-optimized health endpoints with detailed system monitoring
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any
import time
from datetime import datetime, timezone

from ...core.health_monitor import health_monitor, HealthStatus
from ...core.logger import app_logger
from ...core.railway_config import detect_environment, DeploymentEnvironment

router = APIRouter()

# Cache for health check results to avoid overwhelming system
_health_cache: Dict[str, Any] = {}
_cache_ttl = 30  # 30 seconds cache TTL
_last_cache_update = 0

def _get_cached_health() -> Dict[str, Any]:
    """Get cached health results if still valid"""
    global _health_cache, _last_cache_update
    
    current_time = time.time()
    
    if current_time - _last_cache_update < _cache_ttl and _health_cache:
        # Add cache info to response
        cached_response = _health_cache.copy()
        cached_response["cached"] = True
        cached_response["cache_age"] = round(current_time - _last_cache_update, 1)
        return cached_response
    
    return {}

def _update_health_cache(health_data: Dict[str, Any]):
    """Update health check cache"""
    global _health_cache, _last_cache_update
    
    _health_cache = health_data
    _last_cache_update = time.time()

@router.get("/health", tags=["health"])
async def basic_health_check():
    """
    Basic health check endpoint for Railway and load balancers
    Fast response optimized for Railway's 5-second health check timeout
    """
    start_time = time.time()
    
    try:
        # Check cached health first
        cached = _get_cached_health()
        if cached:
            response_time = time.time() - start_time
            cached["response_time"] = round(response_time * 1000, 1)  # ms
            
            # Return appropriate status code based on health
            status_code = 200
            if cached["overall_status"] in ["critical", "unhealthy"]:
                status_code = 503  # Service Unavailable
            elif cached["overall_status"] == "degraded":
                status_code = 200  # OK but with warnings
            
            return JSONResponse(content=cached, status_code=status_code)
        
        # Perform quick health summary without full checks
        summary = health_monitor.get_health_summary()
        response_time = time.time() - start_time
        
        response = {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": detect_environment().value,
            "overall_status": summary["overall_status"],
            "response_time": round(response_time * 1000, 1),  # ms
            "uptime": "healthy",
            "version": "2.0.0",
            "cached": False
        }
        
        # Return appropriate status code
        status_code = 200
        if summary["overall_status"] in ["critical", "unhealthy"]:
            status_code = 503
            response["status"] = "error"
        elif summary["overall_status"] == "degraded":
            response["status"] = "degraded"
        
        return JSONResponse(content=response, status_code=status_code)
        
    except Exception as e:
        response_time = time.time() - start_time
        app_logger.error(f"Basic health check failed: {e}")
        
        error_response = {
            "status": "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "critical",
            "error": str(e),
            "response_time": round(response_time * 1000, 1)
        }
        
        return JSONResponse(content=error_response, status_code=503)

@router.get("/health/detailed", tags=["health"])
async def detailed_health_check(background_tasks: BackgroundTasks):
    """
    Detailed health check with full system diagnostics
    Performs comprehensive checks of all components
    """
    try:
        # Check if we have recent cached results
        cached = _get_cached_health()
        if cached:
            app_logger.info("Returning cached detailed health check")
            return cached
        
        # Perform full health check
        app_logger.info("Performing detailed health check...")
        health_data = await health_monitor.perform_health_check()
        
        # Update cache in background
        background_tasks.add_task(_update_health_cache, health_data)
        
        # Add API metadata
        health_data["api_version"] = "2.0.0"
        health_data["cached"] = False
        
        return health_data
        
    except Exception as e:
        app_logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

@router.get("/health/components", tags=["health"])
async def components_health():
    """
    Individual component health status
    Lightweight endpoint showing component status without full checks
    """
    try:
        summary = health_monitor.get_health_summary()
        
        components_detail = {}
        for name, component in health_monitor.components.items():
            components_detail[name] = {
                "status": component.status.value,
                "message": component.message,
                "last_check": component.last_check.isoformat() if component.last_check else None,
                "error_count": component.error_count,
                "consecutive_failures": component.consecutive_failures,
                "response_time": round(component.response_time, 3)
            }
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": summary["overall_status"],
            "components": components_detail,
            "summary": {
                "total": summary["components_count"],
                "healthy": summary["healthy_components"],
                "degraded": summary["degraded_components"], 
                "unhealthy": summary["unhealthy_components"],
                "critical": summary["critical_components"]
            }
        }
        
    except Exception as e:
        app_logger.error(f"Component health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Component health check failed: {str(e)}")

@router.get("/health/metrics", tags=["health"])
async def health_metrics():
    """
    Health metrics and statistics
    Provides monitoring data for observability systems
    """
    try:
        summary = health_monitor.get_health_summary()
        
        # Calculate health score (0-100)
        total_components = summary["components_count"]
        if total_components == 0:
            health_score = 100
        else:
            healthy_weight = summary["healthy_components"] * 100
            degraded_weight = summary["degraded_components"] * 75
            unhealthy_weight = summary["unhealthy_components"] * 25
            critical_weight = summary["critical_components"] * 0
            
            health_score = (healthy_weight + degraded_weight + unhealthy_weight + critical_weight) / total_components
        
        # Get environment-specific metrics
        environment = detect_environment()
        
        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": environment.value,
            "health_score": round(health_score, 1),
            "overall_status": summary["overall_status"],
            "components": {
                "total": total_components,
                "healthy": summary["healthy_components"],
                "degraded": summary["degraded_components"],
                "unhealthy": summary["unhealthy_components"], 
                "critical": summary["critical_components"]
            },
            "cache": {
                "enabled": True,
                "ttl_seconds": _cache_ttl,
                "age_seconds": round(time.time() - _last_cache_update, 1) if _last_cache_update > 0 else 0
            },
            "configuration": {
                "check_interval": health_monitor.check_interval,
                "timeout": health_monitor.timeout,
                "monitoring_enabled": health_monitor.monitoring_enabled
            }
        }
        
        return metrics
        
    except Exception as e:
        app_logger.error(f"Health metrics failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health metrics failed: {str(e)}")

@router.post("/health/refresh", tags=["health"])
async def refresh_health_cache():
    """
    Force refresh of health check cache
    Useful for manual health verification
    """
    try:
        app_logger.info("Manually refreshing health check cache")
        
        # Perform fresh health check
        health_data = await health_monitor.perform_health_check()
        
        # Update cache
        _update_health_cache(health_data)
        
        return {
            "message": "Health cache refreshed successfully",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": health_data["overall_status"],
            "check_duration": health_data["check_duration"]
        }
        
    except Exception as e:
        app_logger.error(f"Health cache refresh failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health cache refresh failed: {str(e)}")

# Railway-specific endpoint (Railway checks /api/v1/health by default)
@router.get("/health/railway", tags=["health"])
async def railway_health_check():
    """
    Railway-optimized health check endpoint
    Ultra-fast response designed for Railway's infrastructure
    """
    start_time = time.time()
    
    try:
        # Use cached result if available for speed
        cached = _get_cached_health()
        if cached:
            response_time = time.time() - start_time
            
            # Railway expects 200 for healthy, 503 for unhealthy
            if cached["overall_status"] in ["healthy", "degraded"]:
                return JSONResponse(
                    content={
                        "status": "healthy",
                        "response_time_ms": round(response_time * 1000, 1)
                    },
                    status_code=200
                )
            else:
                return JSONResponse(
                    content={
                        "status": "unhealthy", 
                        "overall_status": cached["overall_status"],
                        "response_time_ms": round(response_time * 1000, 1)
                    },
                    status_code=503
                )
        
        # If no cache, return basic OK
        response_time = time.time() - start_time
        return JSONResponse(
            content={
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 1),
                "note": "basic_check"
            },
            status_code=200
        )
        
    except Exception as e:
        response_time = time.time() - start_time
        app_logger.error(f"Railway health check failed: {e}")
        
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": round(response_time * 1000, 1)
            },
            status_code=503
        )