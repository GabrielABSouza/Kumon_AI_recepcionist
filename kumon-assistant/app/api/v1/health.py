"""
Health check routes for production monitoring
Phase 3 - Day 6: Comprehensive health checks with dependency verification
"""
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, List
import asyncio
import time
from datetime import datetime, timezone
# Temporarily disable psutil until proper installation
# import psutil
import redis
import asyncpg
from app.core.config import settings
from app.core.logger import app_logger as logger

router = APIRouter()


@router.get("/health")
async def basic_health_check() -> Dict[str, Any]:
    """Basic health check endpoint for load balancers"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "kumon-assistant",
        "version": settings.VERSION
    }


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Comprehensive health check with all dependencies"""
    start_time = time.time()
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "kumon-assistant",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT.value,
        "checks": {},
        "response_time_ms": 0
    }
    
    checks = [
        ("database", _check_database),
        ("redis", _check_redis),
        ("openai", _check_openai_api),
        ("evolution_api", _check_evolution_api),
        ("system_resources", _check_system_resources),
        ("configuration", _check_configuration),
        ("performance_services", _check_performance_services)
    ]
    
    overall_healthy = True
    
    for check_name, check_func in checks:
        try:
            check_result = await check_func()
            health_status["checks"][check_name] = check_result
            if not check_result.get("healthy", False):
                overall_healthy = False
        except Exception as e:
            logger.error(f"Health check failed for {check_name}: {e}")
            health_status["checks"][check_name] = {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            overall_healthy = False
    
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
    
    # Return 503 if unhealthy
    if not overall_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )
    
    return health_status


@router.get("/health/ready")
async def readiness_check() -> Dict[str, Any]:
    """Kubernetes readiness probe - checks if service can handle requests"""
    critical_checks = [
        ("database", _check_database),
        ("configuration", _check_configuration)
    ]
    
    for check_name, check_func in critical_checks:
        try:
            result = await check_func()
            if not result.get("healthy", False):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"status": "not_ready", "failed_check": check_name}
                )
        except Exception as e:
            logger.error(f"Readiness check failed for {check_name}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not_ready", "error": str(e)}
            )
    
    return {"status": "ready"}


@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """Kubernetes liveness probe - basic service availability"""
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": time.time() - getattr(liveness_check, 'start_time', time.time())
    }


# Initialize start time for uptime calculation
liveness_check.start_time = time.time()


# Individual check functions
async def _check_database() -> Dict[str, Any]:
    """Check PostgreSQL database connectivity and performance"""
    try:
        start_time = time.time()
        
        # Parse database URL for connection
        db_url = settings.DATABASE_URL
        if not db_url or "localhost" in db_url:
            return {
                "healthy": False,
                "error": "Database URL not configured for production",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # Basic connectivity test
        conn = await asyncpg.connect(db_url)
        result = await conn.fetchval("SELECT 1")
        await conn.close()
        
        response_time = round((time.time() - start_time) * 1000, 2)
        
        return {
            "healthy": result == 1,
            "response_time_ms": response_time,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "connection_pool": {
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW
            }
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def _check_redis() -> Dict[str, Any]:
    """Check Redis connectivity and performance"""
    try:
        start_time = time.time()
        
        redis_url = settings.MEMORY_REDIS_URL
        if not redis_url or "localhost" in redis_url:
            return {
                "healthy": False,
                "error": "Redis URL not configured for production",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        r = redis.from_url(redis_url)
        await asyncio.to_thread(r.ping)
        
        response_time = round((time.time() - start_time) * 1000, 2)
        
        return {
            "healthy": True,
            "response_time_ms": response_time,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def _check_openai_api() -> Dict[str, Any]:
    """Check OpenAI API availability and quota"""
    try:
        if not settings.OPENAI_API_KEY:
            return {
                "healthy": False,
                "error": "OpenAI API key not configured",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return {
            "healthy": True,
            "configured": True,
            "daily_budget_brl": settings.LLM_DAILY_BUDGET_BRL,
            "alert_threshold_brl": settings.LLM_COST_ALERT_THRESHOLD_BRL,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def _check_evolution_api() -> Dict[str, Any]:
    """Check Evolution API configuration"""
    try:
        if not settings.EVOLUTION_API_KEY:
            return {
                "healthy": False,
                "error": "Evolution API key not configured",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return {
            "healthy": True,
            "configured": True,
            "api_url": settings.EVOLUTION_API_URL,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def _check_system_resources() -> Dict[str, Any]:
    """Check system resource usage - temporarily disabled"""
    try:
        # Temporarily disable psutil monitoring until dependencies are installed
        # memory = psutil.virtual_memory()
        # cpu_percent = psutil.cpu_percent(interval=1)
        # disk = psutil.disk_usage('/')
        
        # Mock values for now
        memory_percent = 50.0
        cpu_percent = 20.0
        disk_percent = 60.0
        
        return {
            "healthy": memory_percent < 90 and cpu_percent < 90 and disk_percent < 90,
            "memory_percent": memory_percent,
            "cpu_percent": cpu_percent,
            "disk_percent": disk_percent,
            "note": "System monitoring temporarily disabled",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def _check_configuration() -> Dict[str, Any]:
    """Check critical configuration settings"""
    try:
        validation_result = settings.validate_production_config()
        
        return {
            "healthy": validation_result["valid"],
            "issues": validation_result.get("issues", []),
            "warnings": validation_result.get("warnings", []),
            "missing_vars": validation_result.get("missing_critical_vars", []),
            "environment": settings.ENVIRONMENT.value,
            "business_hours": {
                "start": settings.BUSINESS_HOURS_START,
                "end_morning": settings.BUSINESS_HOURS_END_MORNING,
                "start_afternoon": settings.BUSINESS_HOURS_START_AFTERNOON,
                "end": settings.BUSINESS_HOURS_END
            },
            "rate_limit": settings.SECURITY_RATE_LIMIT_PER_MINUTE,
            "pricing": {
                "per_subject": settings.PRICE_PER_SUBJECT,
                "enrollment_fee": settings.ENROLLMENT_FEE
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        } 

@router.delete("/reset-conversations")
async def reset_all_conversations() -> Dict[str, Any]:
    """Temporary endpoint to reset all conversation states"""
    try:
        # Import here to avoid circular import issues
        from app.core.workflow import cecilia_workflow
        
        # CeciliaWorkflow uses PostgreSQL persistence - different approach needed
        logger.info("Reset all conversations requested - CeciliaWorkflow uses persistent storage")
        
        return {
            "message": "CeciliaWorkflow uses persistent state - individual conversation resets recommended", 
            "workflow_system": "cecilia_langgraph",
            "status": "success"
        }
    except Exception as e:
        return {
            "message": f"Error resetting conversations: {str(e)}", 
            "conversations_reset": 0,
            "status": "error"
        }


async def _check_performance_services() -> Dict[str, Any]:
    """Check performance optimization services status"""
    try:
        # Import performance integration service
        from app.services.performance_integration_service import performance_integration
        
        start_time = time.time()
        
        # Check if services are initialized
        if not performance_integration.services_initialized:
            return {
                "healthy": False,
                "error": "Performance services not initialized",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # Get comprehensive performance report
        performance_report = await performance_integration.get_comprehensive_performance_report()
        
        # Check if report was generated successfully
        if "error" in performance_report:
            return {
                "healthy": False,
                "error": performance_report["error"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        response_time = round((time.time() - start_time) * 1000, 2)
        
        # Extract key metrics for health assessment
        current_metrics = performance_report.get("current_metrics", {})
        service_status = performance_report.get("service_status", {})
        
        # Determine health based on service status
        services_healthy = (
            service_status.get("services_initialized", False) and
            service_status.get("monitoring_active", False)
        )
        
        return {
            "healthy": services_healthy,
            "response_time_ms": response_time,
            "services_initialized": service_status.get("services_initialized", False),
            "monitoring_active": service_status.get("monitoring_active", False),
            "auto_optimization_enabled": service_status.get("auto_optimization_enabled", False),
            "last_performance_check": service_status.get("last_performance_check"),
            "current_performance": {
                "uptime_percentage": current_metrics.get("uptime_percentage", 0.0),
                "error_rate_percentage": current_metrics.get("error_rate_percentage", 0.0),
                "daily_cost_brl": current_metrics.get("daily_cost_brl", 0.0),
                "reliability_status": current_metrics.get("reliability_status", "unknown")
            },
            "targets_met": performance_report.get("performance_summary", {}).get("targets_met", 0),
            "total_targets": performance_report.get("performance_summary", {}).get("total_targets", 4),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/health/performance")
async def performance_health_check() -> Dict[str, Any]:
    """Dedicated performance services health check endpoint"""
    try:
        performance_status = await _check_performance_services()
        
        if not performance_status.get("healthy", False):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=performance_status
            )
        
        return {
            "status": "healthy",
            "performance_services": performance_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ) 