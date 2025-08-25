"""
OpenAI Cost Monitoring API
Phase 3 - Day 7: Real-time cost tracking with alerts
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
from pydantic import BaseModel

from app.monitoring.cost_monitor import cost_tracker, TokenUsage, CostAlert, CostAlertLevel
from app.api.v1.auth import require_assistant_scope, require_admin_scope
from app.core.logger import app_logger as logger

router = APIRouter()


class TokenUsageRequest(BaseModel):
    model: str
    prompt_tokens: int
    completion_tokens: int
    request_id: Optional[str] = None


class CostSummaryResponse(BaseModel):
    daily_budget: float
    alert_threshold: float
    current_total: float
    budget_remaining: float
    percentage_used: float
    circuit_breaker_active: bool
    daily_costs: List[Dict[str, Any]]
    model_breakdown: List[Dict[str, Any]]
    hourly_pattern: List[Dict[str, Any]]
    recent_alerts: List[Dict[str, Any]]
    timestamp: datetime


@router.get("/summary", response_model=Dict[str, Any])
async def get_cost_summary(
    days: int = Query(7, ge=1, le=30),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get cost monitoring summary
    
    Returns comprehensive cost analysis including:
    - Current daily usage vs budget
    - Historical costs
    - Model breakdown
    - Alert history
    """
    try:
        # Initialize cost tracker if needed
        if not cost_tracker.db_pool:
            await cost_tracker.initialize()
        
        # Get cost summary
        summary = await cost_tracker.get_cost_summary(days=days)
        
        if not summary:
            # Return default structure if no data
            summary = {
                "summary": {
                    "daily_budget": cost_tracker.daily_budget_brl,
                    "alert_threshold": cost_tracker.alert_threshold_brl,
                    "current_total": 0.0,
                    "budget_remaining": cost_tracker.daily_budget_brl,
                    "percentage_used": 0.0,
                    "circuit_breaker_active": False
                },
                "daily_costs": [],
                "model_breakdown": [],
                "hourly_pattern": [],
                "recent_alerts": [],
                "realtime_metrics": {},
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Add compliance status
        summary["compliance_status"] = {
            "within_budget": summary["summary"]["current_total"] < cost_tracker.daily_budget_brl,
            "alert_triggered": summary["summary"]["current_total"] >= cost_tracker.alert_threshold_brl,
            "budget_exceeded": summary["summary"]["current_total"] >= cost_tracker.daily_budget_brl,
            "days_analyzed": days
        }
        
        logger.info(f"Cost summary accessed by {user.get('client_id', 'unknown')}")
        
        return {
            "success": True,
            "data": summary
        }
        
    except Exception as e:
        logger.error(f"Failed to get cost summary: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve cost summary"
        )


@router.get("/current")
async def get_current_cost(
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """Get current daily cost total and status"""
    try:
        # Initialize cost tracker if needed
        if not cost_tracker.db_pool:
            await cost_tracker.initialize()
        
        current_total = await cost_tracker.get_current_daily_cost()
        budget_remaining = cost_tracker.daily_budget_brl - current_total
        percentage_used = (current_total / cost_tracker.daily_budget_brl) * 100
        
        return {
            "success": True,
            "current_cost": round(current_total, 2),
            "daily_budget": cost_tracker.daily_budget_brl,
            "alert_threshold": cost_tracker.alert_threshold_brl,
            "budget_remaining": round(budget_remaining, 2),
            "percentage_used": round(percentage_used, 1),
            "circuit_breaker_active": cost_tracker.is_budget_exceeded(),
            "status": {
                "within_budget": current_total < cost_tracker.daily_budget_brl,
                "alert_triggered": current_total >= cost_tracker.alert_threshold_brl,
                "budget_exceeded": current_total >= cost_tracker.daily_budget_brl
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get current cost: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve current cost"
        )


@router.post("/track")
async def track_usage(
    usage_request: TokenUsageRequest,
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Track token usage and update cost monitoring
    
    This endpoint is called by LLM services to report usage
    """
    try:
        # Initialize cost tracker if needed
        if not cost_tracker.db_pool:
            await cost_tracker.initialize()
        
        # Create usage object
        usage = TokenUsage(
            prompt_tokens=usage_request.prompt_tokens,
            completion_tokens=usage_request.completion_tokens,
            total_tokens=usage_request.prompt_tokens + usage_request.completion_tokens,
            model=usage_request.model,
            cost_brl=0.0,  # Will be calculated
            timestamp=datetime.utcnow(),
            request_id=usage_request.request_id
        )
        
        # Track usage and check budget
        continue_allowed, alert = await cost_tracker.track_usage(usage)
        
        response = {
            "success": True,
            "continue_allowed": continue_allowed,
            "usage_recorded": True,
            "total_tokens": usage.total_tokens,
            "estimated_cost": 0.0  # Will be filled below
        }
        
        # Get updated current cost
        current_cost = await cost_tracker.get_current_daily_cost()
        response["current_daily_cost"] = round(current_cost, 2)
        response["budget_remaining"] = round(cost_tracker.daily_budget_brl - current_cost, 2)
        
        # Include alert information if generated
        if alert:
            response["alert"] = {
                "level": alert.level.value,
                "message": alert.message,
                "action_required": alert.action_required,
                "percentage_used": round(alert.percentage_used, 1),
                "estimated_daily_total": round(alert.estimated_daily_total, 2)
            }
        
        # Calculate estimated cost for this request
        cost_usd = cost_tracker._calculate_cost_usd(usage)
        response["estimated_cost"] = round(cost_usd * cost_tracker.USD_TO_BRL, 4)
        
        logger.info(f"Usage tracked: {usage.model} - {usage.total_tokens} tokens, Cost: R${response['estimated_cost']:.4f}")
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to track usage: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to track token usage"
        )


@router.get("/alerts")
async def get_cost_alerts(
    level: Optional[CostAlertLevel] = Query(None),
    days: int = Query(7, ge=1, le=30),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get cost alerts history
    
    Parameters:
    - level: Filter by alert level (optional)
    - days: Number of days to look back
    """
    try:
        # Initialize cost tracker if needed
        if not cost_tracker.db_pool:
            await cost_tracker.initialize()
        
        # Get cost summary which includes alerts
        summary = await cost_tracker.get_cost_summary(days=days)
        alerts = summary.get("recent_alerts", [])
        
        # Filter by level if specified
        if level:
            alerts = [alert for alert in alerts if alert.get("level") == level.value]
        
        # Sort by timestamp (most recent first)
        alerts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Add summary statistics
        alert_stats = {
            "total_alerts": len(alerts),
            "critical_alerts": len([a for a in alerts if a.get("level") in ["critical", "emergency"]]),
            "warning_alerts": len([a for a in alerts if a.get("level") == "warning"]),
            "info_alerts": len([a for a in alerts if a.get("level") == "info"])
        }
        
        return {
            "success": True,
            "alerts": alerts,
            "statistics": alert_stats,
            "filters": {
                "level": level.value if level else None,
                "days": days
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get cost alerts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve cost alerts"
        )


@router.get("/models")
async def get_model_costs(
    days: int = Query(7, ge=1, le=30),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get cost breakdown by model
    
    Returns detailed cost analysis per AI model
    """
    try:
        # Initialize cost tracker if needed
        if not cost_tracker.db_pool:
            await cost_tracker.initialize()
        
        summary = await cost_tracker.get_cost_summary(days=days)
        model_breakdown = summary.get("model_breakdown", [])
        
        # Calculate totals and percentages
        total_cost = sum(model["cost"] for model in model_breakdown)
        total_requests = sum(model["requests"] for model in model_breakdown)
        
        for model in model_breakdown:
            model["percentage_of_total"] = round((model["cost"] / max(total_cost, 0.01)) * 100, 1)
            model["avg_cost_per_request"] = round(model["cost"] / max(model["requests"], 1), 4)
        
        # Sort by cost (highest first)
        model_breakdown.sort(key=lambda x: x["cost"], reverse=True)
        
        return {
            "success": True,
            "model_costs": model_breakdown,
            "totals": {
                "total_cost": round(total_cost, 2),
                "total_requests": total_requests,
                "average_cost_per_request": round(total_cost / max(total_requests, 1), 4)
            },
            "analysis_period_days": days,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get model costs: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve model cost breakdown"
        )


@router.get("/hourly")
async def get_hourly_pattern(
    date_str: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """
    Get hourly cost pattern for a specific date
    
    Parameters:
    - date_str: Date in YYYY-MM-DD format (default: today)
    """
    try:
        # Parse date or use today
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target_date = datetime.utcnow().date()
        
        # Initialize cost tracker if needed
        if not cost_tracker.db_pool:
            await cost_tracker.initialize()
        
        summary = await cost_tracker.get_cost_summary(days=1)
        hourly_pattern = summary.get("hourly_pattern", [])
        
        # Create complete 24-hour pattern (fill missing hours with 0)
        hourly_costs = {hour: 0.0 for hour in range(24)}
        for item in hourly_pattern:
            hourly_costs[item["hour"]] = item["cost"]
        
        # Convert to list format
        complete_pattern = [
            {
                "hour": hour,
                "cost": round(cost, 4),
                "hour_label": f"{hour:02d}:00"
            }
            for hour, cost in hourly_costs.items()
        ]
        
        # Calculate statistics
        costs = [item["cost"] for item in complete_pattern]
        stats = {
            "total_cost": round(sum(costs), 2),
            "peak_hour": max(range(24), key=lambda h: hourly_costs[h]),
            "peak_cost": round(max(costs), 4),
            "average_hourly": round(sum(costs) / 24, 4),
            "hours_with_usage": len([c for c in costs if c > 0])
        }
        
        return {
            "success": True,
            "date": target_date.isoformat(),
            "hourly_pattern": complete_pattern,
            "statistics": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    except Exception as e:
        logger.error(f"Failed to get hourly pattern: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve hourly cost pattern"
        )


@router.post("/reset-circuit-breaker")
async def reset_circuit_breaker(
    user: Dict[str, Any] = Depends(require_admin_scope)
) -> Dict[str, str]:
    """
    Reset daily cost circuit breaker (admin only)
    
    This should only be used for new day resets or emergency override
    """
    try:
        await cost_tracker.reset_daily_circuit_breaker()
        
        logger.warning(f"Cost circuit breaker reset by admin: {user.get('client_id', 'unknown')}")
        
        return {
            "success": True,
            "message": "Cost circuit breaker has been reset"
        }
        
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to reset circuit breaker"
        )


@router.get("/budget")
async def get_budget_info(
    user: Dict[str, Any] = Depends(require_assistant_scope)
) -> Dict[str, Any]:
    """Get current budget configuration and status"""
    return {
        "success": True,
        "budget_config": {
            "daily_budget_brl": cost_tracker.daily_budget_brl,
            "alert_threshold_brl": cost_tracker.alert_threshold_brl,
            "currency": "BRL",
            "usd_to_brl_rate": cost_tracker.USD_TO_BRL
        },
        "thresholds": {
            "info_at_percentage": 50,
            "warning_at_percentage": 75,
            "critical_at_cost": cost_tracker.alert_threshold_brl,
            "emergency_at_cost": cost_tracker.daily_budget_brl
        },
        "model_pricing_usd": cost_tracker.MODEL_PRICING,
        "circuit_breaker": {
            "active": cost_tracker.is_budget_exceeded(),
            "description": "Blocks new requests when daily budget is exceeded"
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/export")
async def export_cost_data(
    format: str = Query("json", regex="^(json|csv)$"),
    days: int = Query(30, ge=1, le=90),
    user: Dict[str, Any] = Depends(require_admin_scope)
) -> Dict[str, Any]:
    """
    Export cost data for external analysis (admin only)
    
    Parameters:
    - format: Export format (json or csv)
    - days: Number of days to include
    """
    try:
        # Initialize cost tracker if needed
        if not cost_tracker.db_pool:
            await cost_tracker.initialize()
        
        summary = await cost_tracker.get_cost_summary(days=days)
        
        export_data = {
            "export_info": {
                "timestamp": datetime.utcnow().isoformat(),
                "period_days": days,
                "format": format,
                "exported_by": user.get('client_id', 'unknown')
            },
            "budget_config": {
                "daily_budget": cost_tracker.daily_budget_brl,
                "alert_threshold": cost_tracker.alert_threshold_brl
            },
            "cost_data": summary
        }
        
        logger.info(f"Cost data exported ({format}) by admin: {user.get('client_id', 'unknown')}")
        
        return {
            "success": True,
            "data": export_data,
            "export_format": format
        }
        
    except Exception as e:
        logger.error(f"Failed to export cost data: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to export cost data"
        )