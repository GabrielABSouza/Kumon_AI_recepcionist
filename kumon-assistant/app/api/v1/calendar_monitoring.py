"""
Calendar Service Monitoring and Analytics API
Enterprise monitoring for Google Calendar integration
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any
from datetime import datetime

from ...core.logger import app_logger
from ...clients.google_calendar_hardened import google_calendar_client_hardened
from ...services.calendar_circuit_breaker import calendar_circuit_breaker
from ...services.calendar_cache_service import calendar_cache_service
from ...services.calendar_rate_limiter import calendar_rate_limiter

router = APIRouter()


@router.get("/health")
async def calendar_service_health() -> Dict[str, Any]:
    """
    Comprehensive Google Calendar service health check
    
    Returns detailed health metrics for:
    - Calendar service initialization
    - Circuit breaker status
    - Rate limiting status
    - Cache performance
    - Overall service availability
    """
    try:
        health_status = await google_calendar_client_hardened.get_health_status()
        
        # Determine HTTP status code based on health
        if not health_status.get("overall_healthy", False):
            # Return 503 if service is unhealthy but include details
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Calendar service degraded",
                    "health_status": health_status,
                    "recommendations": await _get_health_recommendations(health_status)
                }
            )
        
        return {
            "status": "healthy",
            "message": "Calendar service operating normally",
            "health_status": health_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Health check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Health check failed", "error": str(e)}
        )


@router.get("/metrics")
async def calendar_service_metrics() -> Dict[str, Any]:
    """
    Comprehensive calendar service performance metrics
    
    Returns:
    - Circuit breaker statistics
    - Rate limiting analytics
    - Cache performance metrics
    - API response times
    - Error rates and patterns
    """
    try:
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "service_status": "operational"
        }
        
        # Circuit breaker metrics
        try:
            metrics["circuit_breaker"] = calendar_circuit_breaker.get_metrics()
        except Exception as e:
            metrics["circuit_breaker_error"] = str(e)
        
        # Rate limiting analytics
        try:
            metrics["rate_limiter"] = await calendar_rate_limiter.get_analytics()
        except Exception as e:
            metrics["rate_limiter_error"] = str(e)
        
        # Cache performance metrics
        try:
            metrics["cache"] = await calendar_cache_service.get_cache_stats()
        except Exception as e:
            metrics["cache_error"] = str(e)
        
        # Calculate composite metrics
        metrics["composite_metrics"] = await _calculate_composite_metrics(metrics)
        
        return metrics
        
    except Exception as e:
        app_logger.error(f"Metrics collection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Metrics collection failed", "error": str(e)}
        )


@router.get("/analytics")
async def calendar_service_analytics() -> Dict[str, Any]:
    """
    Advanced calendar service analytics
    
    Returns:
    - Performance trends
    - Usage patterns
    - Error analysis
    - Capacity planning data
    - Optimization recommendations
    """
    try:
        analytics = {
            "timestamp": datetime.now().isoformat(),
            "analysis_period": "current_session"
        }
        
        # Get base metrics
        metrics = {
            "circuit_breaker": calendar_circuit_breaker.get_metrics(),
            "rate_limiter": await calendar_rate_limiter.get_analytics(),
            "cache": await calendar_cache_service.get_cache_stats()
        }
        
        # Performance analysis
        analytics["performance_analysis"] = await _analyze_performance(metrics)
        
        # Usage patterns
        analytics["usage_patterns"] = await _analyze_usage_patterns(metrics)
        
        # Error analysis
        analytics["error_analysis"] = await _analyze_errors(metrics)
        
        # Capacity planning
        analytics["capacity_planning"] = await _analyze_capacity(metrics)
        
        # Optimization recommendations
        analytics["optimization_recommendations"] = await _generate_optimization_recommendations(metrics)
        
        return analytics
        
    except Exception as e:
        app_logger.error(f"Analytics generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Analytics generation failed", "error": str(e)}
        )


@router.post("/cache/clear")
async def clear_calendar_cache() -> Dict[str, Any]:
    """
    Clear calendar cache (admin operation)
    
    Clears both memory and Redis cache layers
    Useful for troubleshooting and testing
    """
    try:
        # Clear cache
        await calendar_cache_service.clear_all_cache()
        
        app_logger.info("Calendar cache cleared via API request")
        
        return {
            "status": "success",
            "message": "Calendar cache cleared successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        app_logger.error(f"Cache clear error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Cache clear failed", "error": str(e)}
        )


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker() -> Dict[str, Any]:
    """
    Reset circuit breaker (admin operation)
    
    Forces circuit breaker back to CLOSED state
    Use with caution - only when underlying issues are resolved
    """
    try:
        calendar_circuit_breaker.reset()
        
        app_logger.warning("Circuit breaker manually reset via API request")
        
        return {
            "status": "success",
            "message": "Circuit breaker reset to CLOSED state",
            "timestamp": datetime.now().isoformat(),
            "metrics": calendar_circuit_breaker.get_metrics()
        }
        
    except Exception as e:
        app_logger.error(f"Circuit breaker reset error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Circuit breaker reset failed", "error": str(e)}
        )


@router.get("/backoff-recommendation")
async def get_backoff_recommendation() -> Dict[str, Any]:
    """
    Get intelligent backoff recommendations
    
    Returns recommendations for request pacing based on:
    - Current quota usage
    - Rate limit utilization
    - API performance metrics
    - Circuit breaker state
    """
    try:
        recommendation = await calendar_rate_limiter.get_backoff_recommendation()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "recommendation": recommendation,
            "circuit_breaker_state": calendar_circuit_breaker.get_metrics()["state"]
        }
        
    except Exception as e:
        app_logger.error(f"Backoff recommendation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Backoff recommendation failed", "error": str(e)}
        )


# Helper functions for analytics

async def _get_health_recommendations(health_status: Dict[str, Any]) -> List[str]:
    """Generate health improvement recommendations"""
    recommendations = []
    
    if not health_status.get("service_initialized", False):
        recommendations.append("Check Google service account credentials configuration")
    
    if not health_status.get("calendar_id_configured", False):
        recommendations.append("Configure GOOGLE_CALENDAR_ID environment variable")
    
    circuit_breaker_data = health_status.get("circuit_breaker", {})
    if circuit_breaker_data.get("state") == "open":
        recommendations.append("Circuit breaker is open - wait for automatic recovery or check Google API status")
    
    rate_limiter_data = health_status.get("rate_limiter", {})
    if not rate_limiter_data.get("health", {}).get("quota_healthy", True):
        recommendations.append("Google API quota usage is high - consider implementing request throttling")
    
    return recommendations


async def _calculate_composite_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate composite performance metrics"""
    composite = {}
    
    # Overall health score (0-100)
    health_factors = []
    
    # Circuit breaker health (0-100)
    cb_data = metrics.get("circuit_breaker", {})
    if cb_data.get("state") == "closed":
        cb_health = 100
    elif cb_data.get("state") == "half_open":
        cb_health = 50
    else:
        cb_health = 0
    health_factors.append(cb_health)
    
    # Rate limiter health (0-100)
    rl_data = metrics.get("rate_limiter", {})
    quota_pct = rl_data.get("quota_status", {}).get("daily_percentage", 0)
    rl_health = max(0, 100 - quota_pct)
    health_factors.append(rl_health)
    
    # Cache performance (0-100)
    cache_data = metrics.get("cache", {})
    hit_rate = cache_data.get("hit_rate_percentage", 0)
    health_factors.append(hit_rate)
    
    composite["overall_health_score"] = sum(health_factors) / len(health_factors) if health_factors else 0
    
    # Performance score
    perf_factors = []
    
    # Request success rate
    cb_total = cb_data.get("total_requests", 1)
    cb_success = cb_data.get("total_successes", 0)
    success_rate = (cb_success / cb_total) * 100 if cb_total > 0 else 100
    perf_factors.append(success_rate)
    
    # Cache efficiency
    perf_factors.append(hit_rate)
    
    composite["performance_score"] = sum(perf_factors) / len(perf_factors) if perf_factors else 0
    
    return composite


async def _analyze_performance(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze performance metrics"""
    analysis = {}
    
    # Circuit breaker analysis
    cb_data = metrics.get("circuit_breaker", {})
    analysis["circuit_breaker_analysis"] = {
        "state": cb_data.get("state", "unknown"),
        "failure_rate": cb_data.get("failure_rate", 0),
        "total_opens": cb_data.get("total_circuit_opens", 0),
        "health_assessment": "healthy" if cb_data.get("state") == "closed" else "degraded"
    }
    
    # Rate limiter analysis
    rl_data = metrics.get("rate_limiter", {})
    analysis["rate_limiter_analysis"] = {
        "quota_utilization": rl_data.get("quota_status", {}).get("daily_percentage", 0),
        "rejection_rate": rl_data.get("performance", {}).get("rejection_rate", 0),
        "avg_response_time": rl_data.get("performance", {}).get("average_request_duration_ms", 0)
    }
    
    # Cache analysis
    cache_data = metrics.get("cache", {})
    analysis["cache_analysis"] = {
        "hit_rate": cache_data.get("hit_rate_percentage", 0),
        "memory_utilization": (cache_data.get("memory_cache_size", 0) / cache_data.get("memory_cache_max_size", 1)) * 100,
        "redis_connected": cache_data.get("redis_connected", False)
    }
    
    return analysis


async def _analyze_usage_patterns(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze usage patterns"""
    # This would be more sophisticated with historical data
    return {
        "current_load": "normal",
        "peak_usage_indicator": False,
        "pattern_analysis": "insufficient_data"
    }


async def _analyze_errors(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze error patterns"""
    cb_data = metrics.get("circuit_breaker", {})
    
    return {
        "total_failures": cb_data.get("total_failures", 0),
        "failure_rate": cb_data.get("failure_rate", 0),
        "circuit_opens": cb_data.get("total_circuit_opens", 0),
        "error_trend": "stable" if cb_data.get("failure_rate", 0) < 5 else "increasing"
    }


async def _analyze_capacity(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze capacity and scaling needs"""
    rl_data = metrics.get("rate_limiter", {})
    quota_usage = rl_data.get("quota_status", {}).get("daily_percentage", 0)
    
    return {
        "quota_usage_trend": "normal" if quota_usage < 50 else "high",
        "scaling_recommendation": "none" if quota_usage < 80 else "consider_caching",
        "capacity_headroom": max(0, 100 - quota_usage)
    }


async def _generate_optimization_recommendations(metrics: Dict[str, Any]) -> List[str]:
    """Generate optimization recommendations"""
    recommendations = []
    
    cache_data = metrics.get("cache", {})
    hit_rate = cache_data.get("hit_rate_percentage", 0)
    
    if hit_rate < 50:
        recommendations.append("Low cache hit rate - consider increasing cache TTL or warming strategies")
    
    rl_data = metrics.get("rate_limiter", {})
    quota_usage = rl_data.get("quota_status", {}).get("daily_percentage", 0)
    
    if quota_usage > 70:
        recommendations.append("High quota usage - implement more aggressive caching")
    
    cb_data = metrics.get("circuit_breaker", {})
    if cb_data.get("total_circuit_opens", 0) > 0:
        recommendations.append("Circuit breaker has opened - review Google API connectivity and error handling")
    
    return recommendations