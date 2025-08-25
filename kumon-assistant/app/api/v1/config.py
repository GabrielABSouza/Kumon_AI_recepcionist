"""
Configuration Health Check API
Production-ready configuration validation and health monitoring
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from datetime import datetime
import asyncio

from ...core.config import settings
from ...core.logger import app_logger
from ...services.production_llm_service import production_llm_service
from ...services.cost_monitor import cost_monitor

router = APIRouter(prefix="/config", tags=["Configuration"])


@router.get("/health")
async def get_configuration_health() -> Dict[str, Any]:
    """
    Comprehensive configuration health check
    
    Returns:
        - Environment validation status
        - Critical configuration issues
        - Provider availability
        - System readiness assessment
    """
    try:
        # Validate configuration
        config_validation = settings.validate_production_config()
        
        # Check provider health
        provider_health = {}
        if production_llm_service.is_initialized:
            provider_health = await _check_provider_health()
        else:
            provider_health = {"status": "not_initialized", "providers": {}}
        
        # Check cost monitoring
        cost_health = await _check_cost_monitoring_health()
        
        # Overall system readiness
        is_ready = (
            config_validation["valid"] and
            provider_health.get("status") == "healthy" and
            cost_health.get("status") == "operational"
        )
        
        return {
            "status": "ready" if is_ready else "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": settings.ENVIRONMENT.value,
            "configuration": config_validation,
            "providers": provider_health,
            "cost_monitoring": cost_health,
            "system_ready": is_ready,
            "deployment_safe": config_validation["valid"] and len(config_validation["missing_critical_vars"]) == 0
        }
        
    except Exception as e:
        app_logger.error(f"Configuration health check error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Configuration health check failed: {str(e)}"
        )


@router.get("/validation")
async def get_configuration_validation() -> Dict[str, Any]:
    """
    Detailed configuration validation report
    
    Returns:
        - Environment variable validation
        - Missing critical variables
        - Configuration warnings
        - Deployment readiness assessment
    """
    try:
        validation_result = settings.validate_production_config()
        
        # Add deployment guidance
        deployment_guidance = []
        
        if validation_result["missing_critical_vars"]:
            deployment_guidance.append({
                "type": "critical",
                "message": "Configure missing environment variables before deployment",
                "variables": validation_result["missing_critical_vars"]
            })
        
        if validation_result["warnings"]:
            deployment_guidance.append({
                "type": "warning", 
                "message": "Recommended configurations missing - may impact functionality",
                "details": validation_result["warnings"]
            })
        
        if validation_result["valid"] and not validation_result["warnings"]:
            deployment_guidance.append({
                "type": "success",
                "message": "Configuration is production-ready",
                "details": ["All critical variables configured", "No configuration warnings"]
            })
        
        return {
            **validation_result,
            "timestamp": datetime.utcnow().isoformat(),
            "deployment_guidance": deployment_guidance,
            "next_steps": _get_configuration_next_steps(validation_result)
        }
        
    except Exception as e:
        app_logger.error(f"Configuration validation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Configuration validation failed: {str(e)}"
        )


@router.get("/environment")
async def get_environment_info() -> Dict[str, Any]:
    """
    Environment information and settings overview
    
    Returns:
        - Current environment details
        - Key configuration values (sanitized)
        - Feature toggles status
        - Service configuration summary
    """
    try:
        # Sanitize sensitive information
        sanitized_config = {
            "environment": settings.ENVIRONMENT.value,
            "project_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "debug": settings.DEBUG,
            "timezone": settings.TIMEZONE,
            
            # API Configuration (sanitized)
            "apis_configured": {
                "openai": bool(settings.OPENAI_API_KEY),
                "anthropic": bool(settings.ANTHROPIC_API_KEY),
                "evolution": bool(settings.EVOLUTION_API_KEY),
                "twilio": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN),
                "langsmith": bool(settings.LANGSMITH_API_KEY)
            },
            
            # Database Configuration (sanitized)
            "databases_configured": {
                "postgresql": bool(settings.DATABASE_URL and not settings.DATABASE_URL.startswith("postgresql://user:password")),
                "redis": bool(settings.MEMORY_REDIS_URL and not "localhost" in settings.MEMORY_REDIS_URL),
                "qdrant": bool(settings.QDRANT_URL)
            },
            
            # Feature Toggles
            "features": {
                "enhanced_cache": settings.USE_ENHANCED_CACHE,
                "langgraph_workflow": settings.USE_LANGGRAPH_WORKFLOW,
                "secure_processing": settings.USE_SECURE_PROCESSING,
                "streaming_responses": settings.STREAMING_FALLBACK_ENABLED,
                "security_monitoring": settings.SECURITY_MONITORING_ENABLED
            },
            
            # Business Configuration
            "business": {
                "name": settings.BUSINESS_NAME,
                "phone": settings.BUSINESS_PHONE,
                "hours": settings.BUSINESS_HOURS,
                "timezone": settings.TIMEZONE
            },
            
            # LLM Configuration
            "llm": {
                "daily_budget_brl": settings.LLM_DAILY_BUDGET_BRL,
                "alert_threshold_brl": settings.LLM_COST_ALERT_THRESHOLD_BRL,
                "circuit_breaker_threshold": settings.LLM_CIRCUIT_BREAKER_THRESHOLD,
                "request_timeout": settings.LLM_REQUEST_TIMEOUT_SECONDS
            }
        }
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": sanitized_config,
            "production_ready": settings.is_production() and settings.validate_production_config()["valid"]
        }
        
    except Exception as e:
        app_logger.error(f"Environment info error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Environment info retrieval failed: {str(e)}"
        )


@router.post("/validate-deployment")
async def validate_deployment_readiness() -> Dict[str, Any]:
    """
    Comprehensive deployment readiness validation
    
    Returns:
        - Configuration validation
        - Service health checks
        - Deployment safety assessment
        - Pre-deployment checklist
    """
    try:
        # Configuration validation
        config_result = settings.validate_production_config()
        
        # Service health checks
        services_health = {}
        
        # Check LLM service
        try:
            if not production_llm_service.is_initialized:
                await production_llm_service.initialize()
            llm_health = await production_llm_service.get_health_status()
            services_health["llm_service"] = {"status": "healthy", "details": llm_health}
        except Exception as e:
            services_health["llm_service"] = {"status": "unhealthy", "error": str(e)}
        
        # Check cost monitoring
        try:
            await cost_monitor.initialize()
            cost_summary = await cost_monitor.get_daily_summary()
            services_health["cost_monitor"] = {"status": "operational", "summary": cost_summary}
        except Exception as e:
            services_health["cost_monitor"] = {"status": "failed", "error": str(e)}
        
        # Deployment safety assessment
        deployment_safe = (
            config_result["valid"] and
            all(service.get("status") in ["healthy", "operational"] for service in services_health.values())
        )
        
        # Pre-deployment checklist
        checklist = _generate_deployment_checklist(config_result, services_health)
        
        return {
            "deployment_ready": deployment_safe,
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": config_result,
            "services": services_health,
            "checklist": checklist,
            "recommendation": "PROCEED" if deployment_safe else "BLOCKED",
            "next_actions": _get_deployment_next_actions(deployment_safe, config_result, services_health)
        }
        
    except Exception as e:
        app_logger.error(f"Deployment validation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Deployment validation failed: {str(e)}"
        )


async def _check_provider_health() -> Dict[str, Any]:
    """Check health of all configured LLM providers"""
    try:
        health_status = await production_llm_service.get_health_status()
        
        provider_summary = {}
        for provider_name, provider_health in health_status.get("providers", {}).items():
            provider_summary[provider_name] = {
                "available": provider_health.get("available", False),
                "failure_count": provider_health.get("failure_count", 0),
                "has_metrics": bool(provider_health.get("performance_metrics"))
            }
        
        return {
            "status": "healthy" if health_status.get("status") == "healthy" else "degraded",
            "providers": provider_summary,
            "default_provider": health_status.get("default_provider"),
            "total_providers": len(provider_summary)
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "providers": {}
        }


async def _check_cost_monitoring_health() -> Dict[str, Any]:
    """Check cost monitoring system health"""
    try:
        daily_summary = await cost_monitor.get_daily_summary()
        
        return {
            "status": "operational",
            "daily_budget": daily_summary.get("budget_brl", 0),
            "daily_spent": daily_summary.get("spent_brl", 0),
            "usage_percentage": daily_summary.get("usage_percentage", 0),
            "alert_level": daily_summary.get("alert_level", "info"),
            "requests_today": daily_summary.get("request_count", 0)
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }


def _get_configuration_next_steps(validation_result: Dict[str, Any]) -> List[str]:
    """Generate next steps based on configuration validation"""
    next_steps = []
    
    if validation_result["missing_critical_vars"]:
        next_steps.append("Configure missing environment variables in Railway dashboard")
        next_steps.append("Verify API keys are valid and have proper permissions")
    
    if validation_result["warnings"]:
        next_steps.append("Review configuration warnings and add recommended settings")
    
    if validation_result["valid"]:
        next_steps.append("Configuration is ready - proceed with deployment")
        next_steps.append("Monitor application logs and health endpoints after deployment")
    
    return next_steps


def _generate_deployment_checklist(config_result: Dict[str, Any], services_health: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate deployment readiness checklist"""
    checklist = []
    
    # Configuration checks
    checklist.append({
        "item": "Critical environment variables configured",
        "status": "pass" if config_result["valid"] else "fail",
        "details": f"Missing: {config_result['missing_critical_vars']}" if config_result["missing_critical_vars"] else "All configured"
    })
    
    # Service checks
    for service_name, service_health in services_health.items():
        checklist.append({
            "item": f"{service_name.replace('_', ' ').title()} operational",
            "status": "pass" if service_health.get("status") in ["healthy", "operational"] else "fail",
            "details": service_health.get("error", "Service ready")
        })
    
    # Security checks
    checklist.append({
        "item": "Security configuration enabled",
        "status": "pass" if settings.USE_SECURE_PROCESSING else "warning",
        "details": "Secure processing enabled" if settings.USE_SECURE_PROCESSING else "Consider enabling secure processing"
    })
    
    return checklist


def _get_deployment_next_actions(deployment_safe: bool, config_result: Dict[str, Any], services_health: Dict[str, Any]) -> List[str]:
    """Get next actions for deployment"""
    if deployment_safe:
        return [
            "Deployment is approved - proceed with Railway deployment",
            "Monitor health endpoints after deployment",
            "Verify all services are operational in production"
        ]
    else:
        actions = []
        
        if not config_result["valid"]:
            actions.append("Fix configuration issues before deployment")
            if config_result["missing_critical_vars"]:
                actions.append(f"Configure environment variables: {', '.join(config_result['missing_critical_vars'])}")
        
        for service_name, service_health in services_health.items():
            if service_health.get("status") not in ["healthy", "operational"]:
                actions.append(f"Fix {service_name} issues: {service_health.get('error', 'Unknown error')}")
        
        actions.append("Re-run deployment validation after fixes")
        
        return actions