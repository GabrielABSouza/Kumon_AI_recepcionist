"""
Business KPIs Dashboard API
Phase 3 - Day 7: Real-time business metrics and monitoring
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio

from app.monitoring.business_kpis import kpi_tracker, BusinessKPIModel, KPIMetric, KPICategory, AlertLevel
from app.api.v1.auth import require_assistant_scope
from app.core.logger import app_logger as logger

router = APIRouter()


@router.get("/kpis", response_model=BusinessKPIModel)
async def get_business_kpis(
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> BusinessKPIModel:
    """
    Get current business KPIs dashboard
    
    Returns real-time business metrics including:
    - Appointment metrics
    - Financial indicators
    - Quality scores
    - Operational health
    - Compliance status
    """
    try:
        # Initialize KPI tracker if needed
        if not kpi_tracker.db_pool:
            await kpi_tracker.initialize()
        
        # Get current KPIs
        kpis = await kpi_tracker.get_current_kpis()
        
        # Log dashboard access
        logger.info(f"Dashboard accessed by {user.get('client_id', 'unknown')}")
        
        return kpis
        
    except Exception as e:
        logger.error(f"Failed to get business KPIs: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve business metrics"
        )


@router.get("/kpis/historical")
async def get_historical_kpis(
    days: int = Query(7, ge=1, le=30),
    category: Optional[KPICategory] = Query(None),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get historical KPI data for trend analysis
    
    Parameters:
    - days: Number of days to look back (1-30)
    - category: Filter by KPI category (optional)
    """
    try:
        # Initialize KPI tracker if needed
        if not kpi_tracker.db_pool:
            await kpi_tracker.initialize()
        
        # Get historical data
        historical_data = await kpi_tracker.get_historical_kpis(days=days)
        
        # Filter by category if specified
        if category:
            filtered_data = {}
            for metric_name, data_points in historical_data.items():
                if data_points and data_points[0].get('category') == category.value:
                    filtered_data[metric_name] = data_points
            historical_data = filtered_data
        
        return {
            "success": True,
            "data": historical_data,
            "period_days": days,
            "category_filter": category.value if category else None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get historical KPIs: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve historical metrics"
        )


@router.get("/alerts")
async def get_active_alerts(
    level: Optional[AlertLevel] = Query(None),
    category: Optional[KPICategory] = Query(None),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get active alerts
    
    Parameters:
    - level: Filter by alert level (optional)
    - category: Filter by category (optional)
    """
    try:
        # Initialize KPI tracker if needed
        if not kpi_tracker.db_pool:
            await kpi_tracker.initialize()
        
        # Get current KPIs to access alerts
        kpis = await kpi_tracker.get_current_kpis()
        alerts = kpis.active_alerts
        
        # Apply filters
        if level:
            alerts = [alert for alert in alerts if alert.get('level') == level.value]
        
        if category:
            alerts = [alert for alert in alerts if alert.get('category') == category.value]
        
        # Sort by priority and timestamp
        priority_order = {'emergency': 0, 'critical': 1, 'warning': 2, 'info': 3}
        alerts.sort(key=lambda x: (
            priority_order.get(x.get('level', 'info'), 3),
            x.get('timestamp', '')
        ))
        
        return {
            "success": True,
            "alerts": alerts,
            "total_count": len(alerts),
            "critical_count": len([a for a in alerts if a.get('level') in ['critical', 'emergency']]),
            "filters": {
                "level": level.value if level else None,
                "category": category.value if category else None
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve alerts"
        )


@router.get("/summary")
async def get_dashboard_summary(
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get dashboard summary with key metrics
    
    Returns condensed view of most important KPIs
    """
    try:
        # Initialize KPI tracker if needed
        if not kpi_tracker.db_pool:
            await kpi_tracker.initialize()
        
        # Get current KPIs
        kpis = await kpi_tracker.get_current_kpis()
        
        # Calculate summary metrics
        summary = {
            "business_health": {
                "appointments_today": kpis.appointments_today,
                "conversion_rate": kpis.appointment_conversion_rate,
                "potential_revenue_today": kpis.potential_revenue_today,
                "status": "healthy" if kpis.appointment_conversion_rate > 10 else "needs_attention"
            },
            "system_health": {
                "uptime": kpis.system_uptime,
                "response_time": kpis.average_response_time,
                "error_rate": kpis.error_rate,
                "status": "healthy" if kpis.average_response_time <= 5.0 and kpis.error_rate < 0.01 else "degraded"
            },
            "compliance_status": {
                "sla_compliance": "compliant" if kpis.average_response_time <= 5.0 else "breach",
                "lgpd_score": kpis.lgpd_compliance_score,
                "security_incidents": kpis.security_incidents,
                "status": "compliant" if kpis.lgpd_compliance_score >= 90 and kpis.security_incidents == 0 else "requires_attention"
            },
            "alerts_summary": {
                "total_alerts": len(kpis.active_alerts),
                "critical_alerts": len([a for a in kpis.active_alerts if a.get('level') in ['critical', 'emergency']]),
                "status": "normal" if len([a for a in kpis.active_alerts if a.get('level') in ['critical', 'emergency']]) == 0 else "attention_required"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "summary": summary,
            "data_freshness": "real-time"
        }
        
    except Exception as e:
        logger.error(f"Failed to get dashboard summary: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate dashboard summary"
        )


@router.get("/metrics/{metric_name}")
async def get_metric_details(
    metric_name: str,
    days: int = Query(7, ge=1, le=30),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific metric
    
    Parameters:
    - metric_name: Name of the metric to analyze
    - days: Number of days for historical analysis
    """
    try:
        # Initialize KPI tracker if needed
        if not kpi_tracker.db_pool:
            await kpi_tracker.initialize()
        
        # Get historical data for the specific metric
        historical_data = await kpi_tracker.get_historical_kpis(days=days)
        metric_data = historical_data.get(metric_name, [])
        
        if not metric_data:
            raise HTTPException(
                status_code=404,
                detail=f"Metric '{metric_name}' not found"
            )
        
        # Calculate statistics
        values = [point['value'] for point in metric_data]
        if values:
            avg_value = sum(values) / len(values)
            min_value = min(values)
            max_value = max(values)
            
            # Calculate trend
            if len(values) >= 2:
                recent_avg = sum(values[:len(values)//2]) / (len(values)//2)
                older_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
                trend = "increasing" if recent_avg > older_avg else "decreasing" if recent_avg < older_avg else "stable"
            else:
                trend = "insufficient_data"
        else:
            avg_value = min_value = max_value = 0
            trend = "no_data"
        
        return {
            "success": True,
            "metric_name": metric_name,
            "current_value": values[0] if values else 0,
            "statistics": {
                "average": round(avg_value, 2),
                "minimum": min_value,
                "maximum": max_value,
                "trend": trend,
                "data_points": len(values)
            },
            "historical_data": metric_data[:50],  # Limit to 50 most recent points
            "analysis_period_days": days,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metric details for {metric_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze metric '{metric_name}'"
        )


@router.post("/metrics/record")
async def record_custom_metric(
    metric_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, str]:
    """
    Record a custom KPI metric
    
    Allows manual recording of business metrics
    """
    try:
        # Validate required fields
        required_fields = ['name', 'value', 'category']
        for field in required_fields:
            if field not in metric_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field: {field}"
                )
        
        # Create KPI metric
        metric = KPIMetric(
            name=metric_data['name'],
            value=float(metric_data['value']),
            target=float(metric_data.get('target', 0)),
            unit=metric_data.get('unit', ''),
            category=KPICategory(metric_data['category']),
            timestamp=datetime.utcnow(),
            trend=metric_data.get('trend', 'stable'),
            alert_level=AlertLevel(metric_data.get('alert_level', 'info'))
        )
        
        # Initialize KPI tracker if needed
        if not kpi_tracker.db_pool:
            await kpi_tracker.initialize()
        
        # Record the metric
        await kpi_tracker.record_metric(metric)
        
        logger.info(f"Custom metric recorded: {metric.name} = {metric.value} by {user.get('client_id', 'unknown')}")
        
        return {
            "success": True,
            "message": f"Metric '{metric.name}' recorded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record custom metric: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to record metric"
        )


@router.get("/export")
async def export_dashboard_data(
    format: str = Query("json", regex="^(json|csv)$"),
    days: int = Query(7, ge=1, le=30),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Export dashboard data for external analysis
    
    Parameters:
    - format: Export format (json or csv)
    - days: Number of days to include
    """
    try:
        # Initialize KPI tracker if needed
        if not kpi_tracker.db_pool:
            await kpi_tracker.initialize()
        
        # Get current and historical data
        current_kpis = await kpi_tracker.get_current_kpis()
        historical_data = await kpi_tracker.get_historical_kpis(days=days)
        
        export_data = {
            "export_info": {
                "timestamp": datetime.utcnow().isoformat(),
                "period_days": days,
                "format": format,
                "exported_by": user.get('client_id', 'unknown')
            },
            "current_snapshot": current_kpis.dict(),
            "historical_metrics": historical_data,
            "summary_statistics": {
                "total_metrics": len(historical_data),
                "data_points": sum(len(points) for points in historical_data.values()),
                "alert_count": len(current_kpis.active_alerts)
            }
        }
        
        # Log export activity
        logger.info(f"Dashboard data exported ({format}) by {user.get('client_id', 'unknown')}")
        
        if format == "json":
            return export_data
        else:
            # For CSV format, return instructions for client-side processing
            return {
                "success": True,
                "message": "CSV export data prepared",
                "data": export_data,
                "csv_instructions": "Process the historical_metrics data on client side for CSV conversion"
            }
        
    except Exception as e:
        logger.error(f"Failed to export dashboard data: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to export dashboard data"
        )