"""
Alert Management API Endpoints

Real-time alert management and incident response APIs:
- Alert dashboard with active incident overview
- Alert acknowledgment and resolution
- Alert statistics and analytics
- Alert rule management
- Notification channel configuration
- Incident response workflows
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from ...core.logger import app_logger
from ...monitoring.alert_manager import alert_manager, AlertStatus, AlertSeverity, NotificationChannel

router = APIRouter()


class AlertAcknowledgmentRequest(BaseModel):
    alert_id: str
    acknowledged_by: str = "api_user"
    notes: Optional[str] = None


class AlertResolutionRequest(BaseModel):
    alert_id: str
    resolved_by: str = "api_user"
    resolution_notes: Optional[str] = None


class AlertRuleUpdateRequest(BaseModel):
    rule_id: str
    enabled: bool
    notification_channels: Optional[List[str]] = None
    escalation_timeout_minutes: Optional[int] = None


@router.get("/dashboard", summary="Alert Management Dashboard")
async def get_alert_dashboard():
    """
    Get comprehensive alert management dashboard
    
    Returns:
        Real-time alert overview with statistics, active alerts,
        critical incidents, and management actions
    """
    
    try:
        # Get alert statistics
        stats = alert_manager.get_alert_statistics()
        
        # Get active alerts
        active_alerts = [
            {
                "alert_id": alert.alert_id,
                "rule_id": alert.rule_id,
                "title": alert.title,
                "description": alert.description,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "source_type": alert.source_type,
                "created_at": alert.created_at.isoformat(),
                "updated_at": alert.updated_at.isoformat(),
                "escalation_count": alert.escalation_count,
                "next_escalation": alert.next_escalation.isoformat() if alert.next_escalation else None,
                "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                "correlation_key": alert.correlation_key
            }
            for alert in alert_manager.managed_alerts.values()
        ]
        
        # Sort by severity and creation time
        active_alerts.sort(key=lambda x: (
            {"critical": 0, "warning": 1, "info": 2}.get(x["severity"], 3),
            x["created_at"]
        ))
        
        # Get recent alert history (last 24 hours)
        recent_resolved = [
            {
                "alert_id": alert.alert_id,
                "title": alert.title,
                "severity": alert.severity.value,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                "resolution_time_minutes": (
                    (alert.resolved_at - alert.created_at).total_seconds() / 60
                    if alert.resolved_at else 0
                )
            }
            for alert in alert_manager.alert_history[-20:]  # Last 20 resolved alerts
            if alert.status == AlertStatus.RESOLVED
        ]
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "statistics": {
                "total_alerts_24h": stats.total_alerts_24h,
                "active_alerts": stats.active_alerts,
                "critical_alerts": stats.critical_alerts,
                "resolved_alerts_24h": stats.resolved_alerts_24h,
                "avg_resolution_time_minutes": round(stats.avg_resolution_time_minutes, 2),
                "escalation_rate": round(stats.escalation_rate, 3),
                "notification_success_rate": round(stats.notification_success_rate, 3),
                "top_alert_sources": stats.top_alert_sources
            },
            "active_alerts": active_alerts,
            "recent_resolved": recent_resolved,
            "system_health": {
                "alert_system_operational": alert_manager._processing_active,
                "suppressed_alert_count": len(alert_manager.suppressed_alerts),
                "alert_rules_active": len([r for r in alert_manager.alert_rules.values() if r.enabled])
            }
        }
        
    except Exception as e:
        app_logger.error(f"Alert dashboard error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate alert dashboard")


@router.get("/active", summary="Active Alerts")
async def get_active_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity (info, warning, critical)"),
    source_type: Optional[str] = Query(None, description="Filter by source type (performance, security)")
):
    """
    Get current active alerts with optional filtering
    
    Args:
        severity: Filter by alert severity
        source_type: Filter by alert source type
    
    Returns:
        List of active alerts with full details
    """
    
    try:
        active_alerts = list(alert_manager.managed_alerts.values())
        
        # Apply filters
        if severity:
            severity_enum = AlertSeverity(severity)
            active_alerts = [a for a in active_alerts if a.severity == severity_enum]
        
        if source_type:
            active_alerts = [a for a in active_alerts if a.source_type == source_type]
        
        # Format response
        formatted_alerts = [
            {
                "alert_id": alert.alert_id,
                "rule_id": alert.rule_id,
                "title": alert.title,
                "description": alert.description,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "source_type": alert.source_type,
                "created_at": alert.created_at.isoformat(),
                "updated_at": alert.updated_at.isoformat(),
                "escalation_count": alert.escalation_count,
                "next_escalation": alert.next_escalation.isoformat() if alert.next_escalation else None,
                "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                "metadata": alert.metadata,
                "notification_log": alert.notification_log,
                "correlation_key": alert.correlation_key
            }
            for alert in active_alerts
        ]
        
        # Sort by priority (critical first, then by creation time)
        formatted_alerts.sort(key=lambda x: (
            {"critical": 0, "warning": 1, "info": 2}.get(x["severity"], 3),
            x["created_at"]
        ))
        
        return {
            "status": "success",
            "alert_count": len(formatted_alerts),
            "filters_applied": {
                "severity": severity,
                "source_type": source_type
            },
            "alerts": formatted_alerts
        }
        
    except Exception as e:
        app_logger.error(f"Active alerts error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve active alerts")


@router.post("/acknowledge", summary="Acknowledge Alert")
async def acknowledge_alert(request: AlertAcknowledgmentRequest):
    """
    Acknowledge an active alert
    
    Args:
        request: Alert acknowledgment details
    
    Returns:
        Success confirmation with updated alert status
    """
    
    try:
        success = await alert_manager.acknowledge_alert(
            alert_id=request.alert_id,
            acknowledged_by=request.acknowledged_by
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found or already acknowledged")
        
        # Get updated alert details
        alert = alert_manager.managed_alerts.get(request.alert_id)
        
        return {
            "status": "success",
            "message": f"Alert {request.alert_id} acknowledged successfully",
            "alert": {
                "alert_id": alert.alert_id if alert else request.alert_id,
                "status": alert.status.value if alert else "acknowledged",
                "acknowledged_at": alert.acknowledged_at.isoformat() if alert and alert.acknowledged_at else datetime.now().isoformat(),
                "acknowledged_by": request.acknowledged_by
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Alert acknowledgment error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to acknowledge alert")


@router.post("/resolve", summary="Resolve Alert")
async def resolve_alert(request: AlertResolutionRequest):
    """
    Resolve an active alert
    
    Args:
        request: Alert resolution details
    
    Returns:
        Success confirmation with resolution details
    """
    
    try:
        # Get alert details before resolution for metrics
        alert = alert_manager.managed_alerts.get(request.alert_id)
        creation_time = alert.created_at if alert else datetime.now()
        
        success = await alert_manager.resolve_alert(
            alert_id=request.alert_id,
            resolved_by=request.resolved_by
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found or already resolved")
        
        # Calculate resolution time
        resolution_time = datetime.now()
        resolution_duration_minutes = (resolution_time - creation_time).total_seconds() / 60
        
        return {
            "status": "success",
            "message": f"Alert {request.alert_id} resolved successfully",
            "resolution": {
                "alert_id": request.alert_id,
                "resolved_at": resolution_time.isoformat(),
                "resolved_by": request.resolved_by,
                "resolution_time_minutes": round(resolution_duration_minutes, 2),
                "resolution_notes": request.resolution_notes
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Alert resolution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resolve alert")


@router.get("/statistics", summary="Alert Statistics")
async def get_alert_statistics(
    hours: int = Query(24, ge=1, le=168, description="Hours of statistics to analyze")
):
    """
    Get comprehensive alert management statistics
    
    Args:
        hours: Time window for statistics analysis
    
    Returns:
        Detailed alert statistics and analytics
    """
    
    try:
        stats = alert_manager.get_alert_statistics()
        
        # Additional analytics
        current_time = datetime.now()
        time_window_start = current_time - timedelta(hours=hours)
        
        # Get alerts within time window
        windowed_alerts = [
            alert for alert in 
            list(alert_manager.managed_alerts.values()) + alert_manager.alert_history
            if alert.created_at > time_window_start
        ]
        
        # Alert frequency analysis
        hourly_counts = {}
        for alert in windowed_alerts:
            hour_key = alert.created_at.replace(minute=0, second=0, microsecond=0)
            hourly_counts[hour_key] = hourly_counts.get(hour_key, 0) + 1
        
        # Severity distribution
        severity_counts = {"critical": 0, "warning": 0, "info": 0}
        for alert in windowed_alerts:
            severity_counts[alert.severity.value] += 1
        
        # Source type analysis
        source_counts = {"performance": 0, "security": 0, "other": 0}
        for alert in windowed_alerts:
            source_counts[alert.source_type] += 1
        
        return {
            "status": "success",
            "time_window": {
                "hours": hours,
                "start": time_window_start.isoformat(),
                "end": current_time.isoformat()
            },
            "overall_statistics": {
                "total_alerts_24h": stats.total_alerts_24h,
                "active_alerts": stats.active_alerts,
                "critical_alerts": stats.critical_alerts,
                "resolved_alerts_24h": stats.resolved_alerts_24h,
                "avg_resolution_time_minutes": round(stats.avg_resolution_time_minutes, 2),
                "escalation_rate": round(stats.escalation_rate, 3),
                "notification_success_rate": round(stats.notification_success_rate, 3)
            },
            "windowed_analysis": {
                "total_alerts": len(windowed_alerts),
                "alerts_per_hour": len(windowed_alerts) / hours,
                "severity_distribution": severity_counts,
                "source_distribution": source_counts,
                "hourly_trend": [
                    {
                        "hour": hour.isoformat(),
                        "alert_count": count
                    }
                    for hour, count in sorted(hourly_counts.items())
                ]
            },
            "top_alert_sources": stats.top_alert_sources
        }
        
    except Exception as e:
        app_logger.error(f"Alert statistics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve alert statistics")


@router.get("/rules", summary="Alert Rules Configuration")
async def get_alert_rules():
    """
    Get current alert rules configuration
    
    Returns:
        List of all alert rules with their configuration
    """
    
    try:
        rules = []
        
        for rule_id, rule in alert_manager.alert_rules.items():
            rules.append({
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "severity": rule.severity.value,
                "enabled": rule.enabled,
                "conditions": rule.conditions,
                "notification_channels": [ch.value for ch in rule.notification_channels],
                "escalation_timeout_minutes": rule.escalation_timeout_minutes,
                "max_escalations": rule.max_escalations,
                "suppress_duration_minutes": rule.suppress_duration_minutes
            })
        
        # Sort by severity and name
        rules.sort(key=lambda x: (
            {"critical": 0, "warning": 1, "info": 2}.get(x["severity"], 3),
            x["name"]
        ))
        
        return {
            "status": "success",
            "rule_count": len(rules),
            "rules": rules
        }
        
    except Exception as e:
        app_logger.error(f"Alert rules error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve alert rules")


@router.put("/rules/{rule_id}", summary="Update Alert Rule")
async def update_alert_rule(rule_id: str, request: AlertRuleUpdateRequest):
    """
    Update an existing alert rule configuration
    
    Args:
        rule_id: ID of the rule to update
        request: Updated rule configuration
    
    Returns:
        Success confirmation with updated rule details
    """
    
    try:
        rule = alert_manager.alert_rules.get(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        
        # Update rule properties
        if request.enabled is not None:
            rule.enabled = request.enabled
        
        if request.notification_channels:
            try:
                rule.notification_channels = [
                    NotificationChannel(ch) for ch in request.notification_channels
                ]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid notification channel: {e}")
        
        if request.escalation_timeout_minutes is not None:
            if request.escalation_timeout_minutes < 1 or request.escalation_timeout_minutes > 1440:
                raise HTTPException(status_code=400, detail="Escalation timeout must be between 1 and 1440 minutes")
            rule.escalation_timeout_minutes = request.escalation_timeout_minutes
        
        app_logger.info(f"Alert rule {rule_id} updated successfully")
        
        return {
            "status": "success",
            "message": f"Alert rule {rule_id} updated successfully",
            "rule": {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "enabled": rule.enabled,
                "notification_channels": [ch.value for ch in rule.notification_channels],
                "escalation_timeout_minutes": rule.escalation_timeout_minutes
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Alert rule update error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update alert rule")


@router.get("/history", summary="Alert History")
async def get_alert_history(
    hours: int = Query(168, ge=1, le=720, description="Hours of history to retrieve"),
    status: Optional[str] = Query(None, description="Filter by status (active, acknowledged, resolved)"),
    severity: Optional[str] = Query(None, description="Filter by severity (info, warning, critical)")
):
    """
    Get alert history with optional filtering
    
    Args:
        hours: Hours of history to retrieve
        status: Filter by alert status  
        severity: Filter by alert severity
    
    Returns:
        Historical alert data with filtering applied
    """
    
    try:
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=hours)
        
        # Get all alerts within time range
        historical_alerts = [
            alert for alert in 
            list(alert_manager.managed_alerts.values()) + alert_manager.alert_history
            if alert.created_at > cutoff_time
        ]
        
        # Apply filters
        if status:
            try:
                status_enum = AlertStatus(status)
                historical_alerts = [a for a in historical_alerts if a.status == status_enum]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid status filter")
        
        if severity:
            try:
                severity_enum = AlertSeverity(severity)
                historical_alerts = [a for a in historical_alerts if a.severity == severity_enum]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid severity filter")
        
        # Format alerts
        formatted_alerts = []
        for alert in historical_alerts:
            formatted_alert = {
                "alert_id": alert.alert_id,
                "rule_id": alert.rule_id,
                "title": alert.title,
                "description": alert.description,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "source_type": alert.source_type,
                "created_at": alert.created_at.isoformat(),
                "updated_at": alert.updated_at.isoformat(),
                "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                "escalation_count": alert.escalation_count
            }
            
            # Add resolution time if resolved
            if alert.resolved_at:
                resolution_time = (alert.resolved_at - alert.created_at).total_seconds() / 60
                formatted_alert["resolution_time_minutes"] = round(resolution_time, 2)
            
            formatted_alerts.append(formatted_alert)
        
        # Sort by creation time (newest first)
        formatted_alerts.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "status": "success",
            "time_range": {
                "hours": hours,
                "start": cutoff_time.isoformat(),
                "end": current_time.isoformat()
            },
            "filters_applied": {
                "status": status,
                "severity": severity
            },
            "alert_count": len(formatted_alerts),
            "alerts": formatted_alerts
        }
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Alert history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve alert history")


@router.post("/test", summary="Test Alert System")
async def test_alert_system(
    alert_type: str = Body("test", description="Type of test alert to generate"),
    severity: str = Body("warning", description="Severity of test alert")
):
    """
    Generate a test alert to verify the alerting system
    
    Args:
        alert_type: Type of test alert
        severity: Alert severity level
    
    Returns:
        Test alert generation confirmation
    """
    
    try:
        # Generate test alert
        test_alert_data = {
            "level": severity,
            "component": "alert_system_test",
            "metric_name": "test_metric",
            "current_value": 100.0,
            "threshold_value": 80.0,
            "description": f"Test alert of type '{alert_type}' with severity '{severity}'",
            "metadata": {
                "test_alert": True,
                "alert_type": alert_type,
                "generated_at": datetime.now().isoformat(),
                "api_endpoint": "/api/v1/alerts/test"
            },
            "timestamp": datetime.now()
        }
        
        # Process test alert through the system
        await alert_manager._process_alert("performance", test_alert_data)
        
        return {
            "status": "success",
            "message": "Test alert generated successfully",
            "test_alert": {
                "alert_type": alert_type,
                "severity": severity,
                "generated_at": datetime.now().isoformat(),
                "description": test_alert_data["description"]
            }
        }
        
    except Exception as e:
        app_logger.error(f"Test alert error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate test alert")