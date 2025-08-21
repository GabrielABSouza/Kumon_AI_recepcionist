"""
Railway Metrics Integration API
Phase 3 - Day 7: Railway platform metrics and deployment monitoring
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import os
import psutil
import asyncio
from pydantic import BaseModel

from app.monitoring.business_kpis import kpi_tracker
from app.monitoring.cost_monitor import cost_tracker
from app.monitoring.performance_sla import sla_tracker
from app.monitoring.error_alerting import error_alerting
from app.api.v1.auth import require_assistant_scope, require_admin_scope
from app.core.config import settings
from app.core.logger import app_logger as logger

router = APIRouter()


class RailwayMetricsResponse(BaseModel):
    deployment_info: Dict[str, Any]
    system_metrics: Dict[str, Any]
    business_metrics: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    cost_metrics: Dict[str, Any]
    error_metrics: Dict[str, Any]
    health_status: Dict[str, Any]
    timestamp: datetime


@router.get("/overview")
async def get_railway_overview(
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get comprehensive Railway deployment overview
    
    Returns unified metrics from all monitoring systems
    """
    try:
        # Initialize all tracking systems
        await _initialize_trackers()
        
        # Get deployment info from Railway environment variables
        deployment_info = _get_railway_deployment_info()
        
        # Get system metrics
        system_metrics = await _get_system_metrics()
        
        # Get business metrics
        business_kpis = await kpi_tracker.get_current_kpis()
        
        # Get performance metrics
        sla_metrics = await sla_tracker.get_current_metrics()
        
        # Get cost metrics
        cost_summary = await cost_tracker.get_cost_summary(days=1)
        
        # Get error metrics
        error_summary = await error_alerting.get_error_summary(hours=24)
        
        # Calculate overall health status
        health_status = _calculate_health_status({
            "business": business_kpis,
            "performance": sla_metrics,
            "cost": cost_summary,
            "errors": error_summary,
            "system": system_metrics
        })
        
        return {
            "success": True,
            "data": {
                "deployment_info": deployment_info,
                "system_metrics": system_metrics,
                "business_metrics": {
                    "appointments_today": business_kpis.appointments_today,
                    "conversion_rate": business_kpis.appointment_conversion_rate,
                    "revenue_today": business_kpis.potential_revenue_today,
                    "active_conversations": business_kpis.active_conversations,
                    "customer_satisfaction": business_kpis.customer_satisfaction
                },
                "performance_metrics": {
                    "avg_response_time_ms": sla_metrics.current_avg_response_time,
                    "sla_compliance_percentage": sla_metrics.sla_compliance_percentage,
                    "p95_response_time_ms": sla_metrics.p95_response_time,
                    "sla_breaches": sla_metrics.sla_breaches,
                    "status": sla_metrics.status.value
                },
                "cost_metrics": {
                    "daily_total_brl": cost_summary.get("summary", {}).get("current_total", 0),
                    "budget_remaining_brl": cost_summary.get("summary", {}).get("budget_remaining", 0),
                    "percentage_used": cost_summary.get("summary", {}).get("percentage_used", 0),
                    "circuit_breaker_active": cost_summary.get("summary", {}).get("circuit_breaker_active", False)
                },
                "error_metrics": {
                    "total_errors_24h": error_summary.get("summary", {}).get("total_errors", 0),
                    "critical_errors": error_summary.get("summary", {}).get("error_breakdown", {}).get("critical", 0),
                    "active_alerts": len(error_summary.get("active_alerts", [])),
                    "error_rate_per_hour": error_summary.get("summary", {}).get("error_rate_per_hour", 0)
                },
                "health_status": health_status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get Railway overview: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve Railway metrics overview"
        )


@router.get("/deployment")
async def get_deployment_info(
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """Get Railway deployment information"""
    try:
        deployment_info = _get_railway_deployment_info()
        
        # Add application-specific deployment info
        app_info = {
            "application_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT.value,
            "debug_mode": settings.DEBUG,
            "uptime_seconds": _get_uptime_seconds(),
            "python_version": _get_python_version(),
            "process_id": os.getpid(),
            "working_directory": os.getcwd()
        }
        
        deployment_info.update(app_info)
        
        return {
            "success": True,
            "deployment_info": deployment_info,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get deployment info: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve deployment information"
        )


@router.get("/system")
async def get_system_metrics(
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """Get detailed system metrics"""
    try:
        system_metrics = await _get_system_metrics()
        
        # Add Railway-specific system information
        railway_info = {
            "container_memory_limit": _get_memory_limit(),
            "container_cpu_limit": _get_cpu_limit(),
            "network_interfaces": _get_network_info(),
            "environment_variables": _get_safe_env_vars()
        }
        
        system_metrics.update(railway_info)
        
        return {
            "success": True,
            "system_metrics": system_metrics,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve system metrics"
        )


@router.get("/health")
async def get_health_summary(
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """Get comprehensive health summary for Railway monitoring"""
    try:
        await _initialize_trackers()
        
        # Get all metrics for health calculation
        business_kpis = await kpi_tracker.get_current_kpis()
        sla_metrics = await sla_tracker.get_current_metrics()
        cost_summary = await cost_tracker.get_cost_summary(days=1)
        error_summary = await error_alerting.get_error_summary(hours=24)
        system_metrics = await _get_system_metrics()
        
        # Calculate detailed health status
        health_details = {
            "business_health": {
                "status": "healthy" if business_kpis.appointment_conversion_rate > 10 else "degraded",
                "score": min(100, business_kpis.appointment_conversion_rate * 5),  # Max 100
                "issues": []
            },
            "performance_health": {
                "status": "healthy" if sla_metrics.current_avg_response_time <= 5000 else "degraded",
                "score": max(0, 100 - (sla_metrics.current_avg_response_time / 50)),  # 5s = 100 score
                "issues": []
            },
            "cost_health": {
                "status": "healthy" if cost_summary.get("summary", {}).get("percentage_used", 0) < 80 else "warning",
                "score": max(0, 100 - cost_summary.get("summary", {}).get("percentage_used", 0)),
                "issues": []
            },
            "system_health": {
                "status": "healthy" if system_metrics["cpu_percent"] < 80 and system_metrics["memory_percent"] < 80 else "warning",
                "score": max(0, 100 - max(system_metrics["cpu_percent"], system_metrics["memory_percent"])),
                "issues": []
            },
            "error_health": {
                "status": "healthy" if error_summary.get("summary", {}).get("error_rate_per_hour", 0) < 10 else "degraded",
                "score": max(0, 100 - error_summary.get("summary", {}).get("error_rate_per_hour", 0)),
                "issues": []
            }
        }
        
        # Add specific issues
        if business_kpis.appointment_conversion_rate < 5:
            health_details["business_health"]["issues"].append("Very low conversion rate")
        
        if sla_metrics.current_avg_response_time > 5000:
            health_details["performance_health"]["issues"].append("SLA breach: Response time > 5s")
        
        if cost_summary.get("summary", {}).get("circuit_breaker_active", False):
            health_details["cost_health"]["issues"].append("Cost circuit breaker active")
        
        if len(error_summary.get("active_alerts", [])) > 0:
            health_details["error_health"]["issues"].append(f"{len(error_summary.get('active_alerts', []))} active error alerts")
        
        # Calculate overall health score
        scores = [health["score"] for health in health_details.values()]
        overall_score = sum(scores) / len(scores)
        overall_status = "healthy" if overall_score >= 80 else "warning" if overall_score >= 60 else "critical"
        
        return {
            "success": True,
            "health_summary": {
                "overall_status": overall_status,
                "overall_score": round(overall_score, 1),
                "component_health": health_details,
                "critical_issues": sum(1 for h in health_details.values() if h["status"] == "critical"),
                "warnings": sum(1 for h in health_details.values() if h["status"] == "warning"),
                "healthy_components": sum(1 for h in health_details.values() if h["status"] == "healthy"),
                "total_components": len(health_details)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get health summary: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve health summary"
        )


@router.get("/compliance")
async def get_compliance_status(
    user: Dict[str, Any] = Depends(require_admin_scope)
) -> Dict[str, Any]:
    """Get comprehensive compliance status (admin only)"""
    try:
        await _initialize_trackers()
        
        # Business compliance checks
        business_kpis = await kpi_tracker.get_current_kpis()
        sla_metrics = await sla_tracker.get_current_metrics()
        cost_summary = await cost_tracker.get_cost_summary(days=1)
        
        compliance_status = {
            "business_hours_compliance": {
                "requirement": "8h-12h, 14h-18h",
                "current_config": f"{settings.BUSINESS_HOURS_START}h-{settings.BUSINESS_HOURS_END_MORNING}h, {settings.BUSINESS_HOURS_START_AFTERNOON}h-{settings.BUSINESS_HOURS_END}h",
                "compliant": (settings.BUSINESS_HOURS_START == 8 and 
                            settings.BUSINESS_HOURS_END_MORNING == 12 and
                            settings.BUSINESS_HOURS_START_AFTERNOON == 14 and
                            settings.BUSINESS_HOURS_END == 18)
            },
            "response_time_compliance": {
                "requirement": "≤5s response time",
                "current_avg_ms": sla_metrics.current_avg_response_time,
                "compliant": sla_metrics.current_avg_response_time <= 5000,
                "sla_compliance_percentage": sla_metrics.sla_compliance_percentage
            },
            "rate_limit_compliance": {
                "requirement": "50 req/min rate limit",
                "current_config": settings.SECURITY_RATE_LIMIT_PER_MINUTE,
                "compliant": settings.SECURITY_RATE_LIMIT_PER_MINUTE == 50
            },
            "pricing_compliance": {
                "requirement": "R$ 375 + R$ 100",
                "current_config": f"R$ {settings.PRICE_PER_SUBJECT} + R$ {settings.ENROLLMENT_FEE}",
                "compliant": (settings.PRICE_PER_SUBJECT == 375.0 and 
                            settings.ENROLLMENT_FEE == 100.0)
            },
            "cost_budget_compliance": {
                "requirement": "R$5/day budget with R$4/day alerts",
                "daily_budget": cost_summary.get("summary", {}).get("daily_budget", 0),
                "alert_threshold": cost_summary.get("summary", {}).get("alert_threshold", 0),
                "current_usage": cost_summary.get("summary", {}).get("current_total", 0),
                "compliant": (cost_summary.get("summary", {}).get("current_total", 0) <= 5.0 and
                            cost_summary.get("summary", {}).get("alert_threshold", 0) == 4.0)
            },
            "lgpd_compliance": {
                "requirement": "LGPD compliance enabled",
                "data_retention_policy": "7 days conversation history",
                "privacy_headers_enabled": True,
                "compliant": business_kpis.lgpd_compliance_score >= 90
            }
        }
        
        # Calculate overall compliance
        total_requirements = len(compliance_status)
        compliant_requirements = sum(1 for req in compliance_status.values() if req.get("compliant", False))
        compliance_percentage = (compliant_requirements / total_requirements) * 100
        
        return {
            "success": True,
            "compliance_report": {
                "overall_compliance_percentage": round(compliance_percentage, 1),
                "compliant_requirements": compliant_requirements,
                "total_requirements": total_requirements,
                "compliance_grade": "A" if compliance_percentage >= 95 else "B" if compliance_percentage >= 85 else "C" if compliance_percentage >= 75 else "F",
                "detailed_compliance": compliance_status,
                "non_compliant_items": [
                    key for key, value in compliance_status.items() 
                    if not value.get("compliant", False)
                ]
            },
            "report_metadata": {
                "generated_by": user.get('client_id', 'admin'),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "railway_environment": os.getenv("RAILWAY_ENVIRONMENT", "unknown")
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get compliance status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve compliance status"
        )


# Helper functions
async def _initialize_trackers():
    """Initialize all monitoring trackers"""
    try:
        if not kpi_tracker.db_pool:
            await kpi_tracker.initialize()
        if not cost_tracker.db_pool:
            await cost_tracker.initialize()
        if not sla_tracker.db_pool:
            await sla_tracker.initialize()
        if not error_alerting.db_pool:
            await error_alerting.initialize()
    except Exception as e:
        logger.warning(f"Some trackers failed to initialize: {e}")


def _get_railway_deployment_info() -> Dict[str, Any]:
    """Get Railway-specific deployment information"""
    return {
        "railway_environment": os.getenv("RAILWAY_ENVIRONMENT", "unknown"),
        "railway_project_id": os.getenv("RAILWAY_PROJECT_ID", "unknown"),
        "railway_service_id": os.getenv("RAILWAY_SERVICE_ID", "unknown"),
        "railway_public_domain": os.getenv("RAILWAY_PUBLIC_DOMAIN", "unknown"),
        "railway_database_url": "configured" if os.getenv("RAILWAY_DATABASE_URL") else "not_configured",
        "railway_redis_url": "configured" if os.getenv("RAILWAY_REDIS_URL") else "not_configured",
        "port": os.getenv("PORT", "8000"),
        "deployment_timestamp": datetime.now(timezone.utc).isoformat()
    }


async def _get_system_metrics() -> Dict[str, Any]:
    """Get detailed system metrics"""
    try:
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        
        # Network metrics (basic)
        network = psutil.net_io_counters()
        
        # Process metrics
        process = psutil.Process()
        
        return {
            "cpu_percent": round(cpu_percent, 1),
            "cpu_count": cpu_count,
            "memory_percent": round(memory.percent, 1),
            "memory_total_mb": round(memory.total / 1024 / 1024, 1),
            "memory_available_mb": round(memory.available / 1024 / 1024, 1),
            "memory_used_mb": round(memory.used / 1024 / 1024, 1),
            "disk_percent": round(disk.percent, 1),
            "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
            "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 1),
            "network_bytes_sent": network.bytes_sent,
            "network_bytes_recv": network.bytes_recv,
            "process_memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
            "process_cpu_percent": round(process.cpu_percent(), 1),
            "process_threads": process.num_threads(),
            "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
        }
        
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        return {}


def _calculate_health_status(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate overall health status from all metrics"""
    health_factors = []
    
    # Business health
    business = metrics.get("business")
    if business and business.appointment_conversion_rate > 5:
        health_factors.append(("business", "good"))
    else:
        health_factors.append(("business", "poor"))
    
    # Performance health
    performance = metrics.get("performance")
    if performance and performance.current_avg_response_time <= 5000:
        health_factors.append(("performance", "good"))
    else:
        health_factors.append(("performance", "poor"))
    
    # Cost health
    cost = metrics.get("cost", {})
    if cost.get("summary", {}).get("percentage_used", 0) < 80:
        health_factors.append(("cost", "good"))
    else:
        health_factors.append(("cost", "warning"))
    
    # Error health
    errors = metrics.get("errors", {})
    if errors.get("summary", {}).get("error_rate_per_hour", 0) < 10:
        health_factors.append(("errors", "good"))
    else:
        health_factors.append(("errors", "poor"))
    
    # System health
    system = metrics.get("system", {})
    if system.get("cpu_percent", 0) < 80 and system.get("memory_percent", 0) < 80:
        health_factors.append(("system", "good"))
    else:
        health_factors.append(("system", "warning"))
    
    # Calculate overall status
    good_count = sum(1 for _, status in health_factors if status == "good")
    warning_count = sum(1 for _, status in health_factors if status == "warning")
    poor_count = sum(1 for _, status in health_factors if status == "poor")
    
    if poor_count > 0:
        overall_status = "critical"
    elif warning_count > good_count:
        overall_status = "warning"
    else:
        overall_status = "healthy"
    
    return {
        "overall_status": overall_status,
        "health_factors": dict(health_factors),
        "score": round((good_count / len(health_factors)) * 100, 1),
        "good_components": good_count,
        "warning_components": warning_count,
        "critical_components": poor_count,
        "total_components": len(health_factors)
    }


def _get_memory_limit() -> str:
    """Get container memory limit"""
    try:
        with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r") as f:
            limit_bytes = int(f.read().strip())
            if limit_bytes < 9223372036854775807:  # Not unlimited
                return f"{round(limit_bytes / 1024 / 1024, 1)} MB"
    except:
        pass
    return "unlimited"


def _get_cpu_limit() -> str:
    """Get container CPU limit"""
    try:
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "r") as f:
            quota = int(f.read().strip())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", "r") as f:
            period = int(f.read().strip())
        if quota > 0:
            return f"{round(quota / period, 2)} cores"
    except:
        pass
    return "unlimited"


def _get_network_info() -> List[str]:
    """Get network interface information"""
    try:
        return list(psutil.net_if_addrs().keys())
    except:
        return ["unknown"]


def _get_safe_env_vars() -> Dict[str, str]:
    """Get safe environment variables (no secrets)"""
    safe_vars = {}
    safe_keys = [
        "PORT", "RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", 
        "RAILWAY_SERVICE_ID", "RAILWAY_PUBLIC_DOMAIN", "ENVIRONMENT"
    ]
    
    for key in safe_keys:
        value = os.getenv(key)
        if value:
            safe_vars[key] = value
    
    return safe_vars


def _get_uptime_seconds() -> float:
    """Get application uptime in seconds"""
    try:
        import time
        return time.time() - psutil.Process().create_time()
    except:
        return 0.0


def _get_python_version() -> str:
    """Get Python version"""
    import sys
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"