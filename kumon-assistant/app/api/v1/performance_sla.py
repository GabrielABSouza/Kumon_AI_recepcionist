"""
Performance SLA Monitoring API
Phase 3 - Day 7: Real-time response time tracking and SLA compliance
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from app.monitoring.performance_sla import sla_tracker, ResponseTimeMetric, SLAMetrics, SLAStatus, AlertSeverity
from app.api.v1.auth import require_assistant_scope, require_admin_scope
from app.core.logger import app_logger as logger

router = APIRouter()


class ResponseTimeRequest(BaseModel):
    endpoint: str
    method: str
    response_time_ms: float
    status_code: int
    user_agent: Optional[str] = None
    request_id: Optional[str] = None


class SLAMetricsResponse(BaseModel):
    current_avg_response_time: float
    sla_compliance_percentage: float
    total_requests: int
    sla_breaches: int
    fastest_response: float
    slowest_response: float
    p95_response_time: float
    p99_response_time: float
    status: str
    timestamp: datetime


@router.get("/sla/summary")
async def get_sla_summary(
    hours: int = Query(24, ge=1, le=168),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get comprehensive SLA performance summary
    
    Parameters:
    - hours: Number of hours to analyze (1-168)
    
    Returns detailed SLA metrics including:
    - Overall compliance statistics
    - Hourly breakdown
    - Endpoint performance
    - Breach events
    - Recent alerts
    """
    try:
        # Initialize SLA tracker if needed
        if not sla_tracker.db_pool:
            await sla_tracker.initialize()
        
        # Get SLA summary
        summary = await sla_tracker.get_sla_summary(hours=hours)
        
        if not summary:
            # Return default structure if no data
            summary = {
                "summary": {
                    "sla_threshold_ms": sla_tracker.sla_threshold_ms,
                    "warning_threshold_ms": sla_tracker.warning_threshold_ms,
                    "analysis_period_hours": hours,
                    "total_requests": 0,
                    "avg_response_time_ms": 0.0,
                    "sla_compliance_percentage": 100.0,
                    "status": "compliant"
                },
                "hourly_breakdown": [],
                "endpoint_performance": [],
                "breach_events": [],
                "recent_alerts": [],
                "realtime_metrics": {},
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Add compliance analysis
        summary["compliance_analysis"] = {
            "sla_target_ms": sla_tracker.sla_threshold_ms,
            "current_status": summary["summary"]["status"],
            "compliance_score": summary["summary"]["sla_compliance_percentage"],
            "improvement_needed": summary["summary"]["sla_compliance_percentage"] < 95,
            "critical_breaches": len([
                alert for alert in summary.get("recent_alerts", [])
                if alert.get("severity") in ["critical", "emergency"]
            ])
        }
        
        logger.info(f"SLA summary accessed by {user.get('client_id', 'unknown')}")
        
        return {
            "success": True,
            "data": summary
        }
        
    except Exception as e:
        logger.error(f"Failed to get SLA summary: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve SLA summary"
        )


@router.get("/sla/current", response_model=Dict[str, Any])
async def get_current_sla_metrics(
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """Get current real-time SLA metrics"""
    try:
        # Initialize SLA tracker if needed
        if not sla_tracker.db_pool:
            await sla_tracker.initialize()
        
        # Get current metrics
        metrics = await sla_tracker.get_current_metrics()
        
        return {
            "success": True,
            "metrics": {
                "current_avg_response_time_ms": metrics.current_avg_response_time,
                "sla_compliance_percentage": metrics.sla_compliance_percentage,
                "total_requests_analyzed": metrics.total_requests,
                "sla_breaches": metrics.sla_breaches,
                "performance_percentiles": {
                    "p95_ms": metrics.p95_response_time,
                    "p99_ms": metrics.p99_response_time,
                    "fastest_ms": metrics.fastest_response,
                    "slowest_ms": metrics.slowest_response
                },
                "sla_status": metrics.status.value,
                "in_breach": sla_tracker.is_in_breach(),
                "thresholds": {
                    "sla_target_ms": sla_tracker.sla_threshold_ms,
                    "warning_threshold_ms": sla_tracker.warning_threshold_ms
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get current SLA metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve current SLA metrics"
        )


@router.post("/sla/record")
async def record_response_time(
    request: ResponseTimeRequest,
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Record response time measurement
    
    This endpoint is called by application middleware to track response times
    """
    try:
        # Initialize SLA tracker if needed
        if not sla_tracker.db_pool:
            await sla_tracker.initialize()
        
        # Create metric object
        metric = ResponseTimeMetric(
            endpoint=request.endpoint,
            method=request.method,
            response_time_ms=request.response_time_ms,
            status_code=request.status_code,
            timestamp=datetime.utcnow(),
            user_agent=request.user_agent,
            request_id=request.request_id
        )
        
        # Record and get updated metrics
        current_metrics, alert = await sla_tracker.record_response_time(metric)
        
        response = {
            "success": True,
            "recorded": True,
            "response_time_ms": request.response_time_ms,
            "sla_compliant": request.response_time_ms <= sla_tracker.sla_threshold_ms,
            "current_metrics": {
                "avg_response_time_ms": current_metrics.current_avg_response_time,
                "sla_compliance_percentage": current_metrics.sla_compliance_percentage,
                "status": current_metrics.status.value
            }
        }
        
        # Include alert information if generated
        if alert:
            response["alert"] = {
                "severity": alert.severity.value,
                "message": alert.message,
                "action_required": alert.action_required,
                "breach_duration_minutes": alert.breach_duration_minutes
            }
        
        # Log significant events
        if request.response_time_ms > sla_tracker.sla_threshold_ms:
            logger.warning(f"SLA breach: {request.method} {request.endpoint} took {request.response_time_ms:.1f}ms")
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to record response time: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to record response time"
        )


@router.get("/sla/alerts")
async def get_sla_alerts(
    severity: Optional[AlertSeverity] = Query(None),
    hours: int = Query(24, ge=1, le=168),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get SLA alerts history
    
    Parameters:
    - severity: Filter by alert severity (optional)
    - hours: Number of hours to look back
    """
    try:
        # Initialize SLA tracker if needed
        if not sla_tracker.db_pool:
            await sla_tracker.initialize()
        
        # Get SLA summary which includes alerts
        summary = await sla_tracker.get_sla_summary(hours=hours)
        alerts = summary.get("recent_alerts", [])
        
        # Filter by severity if specified
        if severity:
            alerts = [alert for alert in alerts if alert.get("severity") == severity.value]
        
        # Sort by timestamp (most recent first)
        alerts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Add summary statistics
        alert_stats = {
            "total_alerts": len(alerts),
            "emergency_alerts": len([a for a in alerts if a.get("severity") == "emergency"]),
            "critical_alerts": len([a for a in alerts if a.get("severity") == "critical"]),
            "warning_alerts": len([a for a in alerts if a.get("severity") == "warning"]),
            "info_alerts": len([a for a in alerts if a.get("severity") == "info"])
        }
        
        return {
            "success": True,
            "alerts": alerts,
            "statistics": alert_stats,
            "filters": {
                "severity": severity.value if severity else None,
                "hours": hours
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get SLA alerts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve SLA alerts"
        )


@router.get("/sla/endpoints")
async def get_endpoint_performance(
    hours: int = Query(24, ge=1, le=168),
    sort_by: str = Query("avg_response_time", regex="^(avg_response_time|requests|breaches|compliance)$"),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get performance breakdown by endpoint
    
    Parameters:
    - hours: Number of hours to analyze
    - sort_by: Sort criteria (avg_response_time, requests, breaches, compliance)
    """
    try:
        # Initialize SLA tracker if needed
        if not sla_tracker.db_pool:
            await sla_tracker.initialize()
        
        # Get SLA summary
        summary = await sla_tracker.get_sla_summary(hours=hours)
        endpoint_performance = summary.get("endpoint_performance", [])
        
        # Sort by specified criteria
        if sort_by == "avg_response_time":
            endpoint_performance.sort(key=lambda x: x.get("avg_response_time_ms", 0), reverse=True)
        elif sort_by == "requests":
            endpoint_performance.sort(key=lambda x: x.get("requests", 0), reverse=True)
        elif sort_by == "breaches":
            endpoint_performance.sort(key=lambda x: x.get("breaches", 0), reverse=True)
        elif sort_by == "compliance":
            endpoint_performance.sort(key=lambda x: x.get("compliance_percentage", 100))
        
        # Add performance categorization
        for endpoint in endpoint_performance:
            avg_time = endpoint.get("avg_response_time_ms", 0)
            compliance = endpoint.get("compliance_percentage", 100)
            
            if avg_time > sla_tracker.sla_threshold_ms or compliance < 90:
                endpoint["performance_category"] = "poor"
            elif avg_time > sla_tracker.warning_threshold_ms or compliance < 95:
                endpoint["performance_category"] = "warning"
            else:
                endpoint["performance_category"] = "good"
        
        # Calculate summary statistics
        total_requests = sum(ep.get("requests", 0) for ep in endpoint_performance)
        total_breaches = sum(ep.get("breaches", 0) for ep in endpoint_performance)
        overall_compliance = ((total_requests - total_breaches) / max(total_requests, 1)) * 100
        
        stats = {
            "total_endpoints": len(endpoint_performance),
            "total_requests": total_requests,
            "total_breaches": total_breaches,
            "overall_compliance_percentage": round(overall_compliance, 2),
            "endpoints_by_category": {
                "good": len([ep for ep in endpoint_performance if ep.get("performance_category") == "good"]),
                "warning": len([ep for ep in endpoint_performance if ep.get("performance_category") == "warning"]),
                "poor": len([ep for ep in endpoint_performance if ep.get("performance_category") == "poor"])
            }
        }
        
        return {
            "success": True,
            "endpoint_performance": endpoint_performance,
            "statistics": stats,
            "analysis_config": {
                "hours_analyzed": hours,
                "sorted_by": sort_by,
                "sla_threshold_ms": sla_tracker.sla_threshold_ms,
                "warning_threshold_ms": sla_tracker.warning_threshold_ms
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get endpoint performance: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve endpoint performance"
        )


@router.get("/sla/trends")
async def get_sla_trends(
    hours: int = Query(24, ge=1, le=168),
    interval: str = Query("hour", regex="^(hour|day)$"),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get SLA performance trends over time
    
    Parameters:
    - hours: Number of hours to analyze
    - interval: Time interval for grouping (hour or day)
    """
    try:
        # Initialize SLA tracker if needed
        if not sla_tracker.db_pool:
            await sla_tracker.initialize()
        
        # Get SLA summary
        summary = await sla_tracker.get_sla_summary(hours=hours)
        
        if interval == "hour":
            trends = summary.get("hourly_breakdown", [])
        else:
            # Group hourly data by day
            hourly_data = summary.get("hourly_breakdown", [])
            daily_trends = {}
            
            for hour_data in hourly_data:
                date = hour_data["hour"][:10]  # Extract date part
                if date not in daily_trends:
                    daily_trends[date] = {
                        "date": date,
                        "requests": 0,
                        "total_response_time": 0,
                        "breaches": 0
                    }
                
                daily_trends[date]["requests"] += hour_data["requests"]
                daily_trends[date]["total_response_time"] += hour_data["avg_response_time_ms"] * hour_data["requests"]
                daily_trends[date]["breaches"] += hour_data["breaches"]
            
            # Calculate daily averages
            trends = []
            for date, data in daily_trends.items():
                avg_response_time = data["total_response_time"] / max(data["requests"], 1)
                compliance = ((data["requests"] - data["breaches"]) / max(data["requests"], 1)) * 100
                
                trends.append({
                    "period": date,
                    "requests": data["requests"],
                    "avg_response_time_ms": round(avg_response_time, 2),
                    "breaches": data["breaches"],
                    "compliance_percentage": round(compliance, 1)
                })
            
            trends.sort(key=lambda x: x["period"])
        
        # Calculate trend analysis
        if len(trends) >= 2:
            recent_compliance = trends[-1].get("compliance_percentage", 100)
            previous_compliance = trends[-2].get("compliance_percentage", 100)
            compliance_trend = "improving" if recent_compliance > previous_compliance else "declining" if recent_compliance < previous_compliance else "stable"
            
            recent_response_time = trends[-1].get("avg_response_time_ms", 0)
            previous_response_time = trends[-2].get("avg_response_time_ms", 0)
            response_time_trend = "improving" if recent_response_time < previous_response_time else "declining" if recent_response_time > previous_response_time else "stable"
        else:
            compliance_trend = "insufficient_data"
            response_time_trend = "insufficient_data"
        
        return {
            "success": True,
            "trends": trends,
            "analysis": {
                "compliance_trend": compliance_trend,
                "response_time_trend": response_time_trend,
                "data_points": len(trends),
                "interval": interval,
                "hours_analyzed": hours
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get SLA trends: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve SLA trends"
        )


@router.get("/sla/compliance-report")
async def get_compliance_report(
    user: Dict[str, Any] = Depends(require_admin_scope)
) -> Dict[str, Any]:
    """
    Get comprehensive SLA compliance report (admin only)
    
    Returns detailed compliance analysis for management reporting
    """
    try:
        # Initialize SLA tracker if needed
        if not sla_tracker.db_pool:
            await sla_tracker.initialize()
        
        # Get data for different time periods
        daily_summary = await sla_tracker.get_sla_summary(hours=24)
        weekly_summary = await sla_tracker.get_sla_summary(hours=168)  # 7 days
        
        # Extract key metrics
        daily_metrics = daily_summary.get("summary", {})
        weekly_metrics = weekly_summary.get("summary", {})
        
        # Calculate compliance grades
        def get_compliance_grade(percentage):
            if percentage >= 99:
                return "A+"
            elif percentage >= 95:
                return "A"
            elif percentage >= 90:
                return "B"
            elif percentage >= 85:
                return "C"
            else:
                return "F"
        
        report = {
            "compliance_overview": {
                "sla_target": "≤5s response time",
                "current_status": daily_metrics.get("status", "unknown"),
                "daily_compliance": {
                    "percentage": daily_metrics.get("sla_compliance_percentage", 0),
                    "grade": get_compliance_grade(daily_metrics.get("sla_compliance_percentage", 0)),
                    "total_requests": daily_metrics.get("total_requests", 0),
                    "breaches": daily_metrics.get("sla_breaches", 0)
                },
                "weekly_compliance": {
                    "percentage": weekly_metrics.get("sla_compliance_percentage", 0),
                    "grade": get_compliance_grade(weekly_metrics.get("sla_compliance_percentage", 0)),
                    "total_requests": weekly_metrics.get("total_requests", 0),
                    "breaches": weekly_metrics.get("sla_breaches", 0)
                }
            },
            "performance_summary": {
                "daily_avg_response_time_ms": daily_metrics.get("avg_response_time_ms", 0),
                "weekly_avg_response_time_ms": weekly_metrics.get("avg_response_time_ms", 0),
                "target_response_time_ms": sla_tracker.sla_threshold_ms,
                "performance_vs_target": {
                    "daily_variance_ms": daily_metrics.get("avg_response_time_ms", 0) - sla_tracker.sla_threshold_ms,
                    "weekly_variance_ms": weekly_metrics.get("avg_response_time_ms", 0) - sla_tracker.sla_threshold_ms
                }
            },
            "critical_incidents": {
                "daily_breach_events": len(daily_summary.get("breach_events", [])),
                "weekly_breach_events": len(weekly_summary.get("breach_events", [])),
                "critical_alerts_today": len([
                    alert for alert in daily_summary.get("recent_alerts", [])
                    if alert.get("severity") in ["critical", "emergency"]
                ])
            },
            "top_performance_issues": weekly_summary.get("endpoint_performance", [])[:5],  # Top 5 slowest endpoints
            "recommendations": [],
            "report_metadata": {
                "generated_by": user.get('client_id', 'admin'),
                "timestamp": datetime.utcnow().isoformat(),
                "data_freshness": "real-time"
            }
        }
        
        # Generate recommendations based on performance
        recommendations = []
        if daily_metrics.get("sla_compliance_percentage", 100) < 95:
            recommendations.append("SLA compliance below 95% - immediate performance optimization required")
        
        if daily_metrics.get("avg_response_time_ms", 0) > sla_tracker.sla_threshold_ms:
            recommendations.append("Average response time exceeds SLA target - investigate performance bottlenecks")
        
        if len(daily_summary.get("breach_events", [])) > 0:
            recommendations.append("Recent SLA breach events detected - implement performance monitoring alerts")
        
        if not recommendations:
            recommendations.append("Performance within acceptable parameters - continue monitoring")
        
        report["recommendations"] = recommendations
        
        logger.info(f"SLA compliance report generated by admin: {user.get('client_id', 'unknown')}")
        
        return {
            "success": True,
            "report": report
        }
        
    except Exception as e:
        logger.error(f"Failed to generate compliance report: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate compliance report"
        )