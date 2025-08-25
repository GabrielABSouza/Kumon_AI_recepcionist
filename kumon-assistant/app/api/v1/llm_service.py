"""
LLM Service API Endpoints
Health monitoring and cost management endpoints for Production LLM Service
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional
from datetime import datetime
import re

from ...core.logger import app_logger
from ...services.production_llm_service import production_llm_service
from ...services.cost_monitor import cost_monitor
from ...services.langgraph_llm_adapter import kumon_llm_service
from ...services.business_metrics_service import business_metrics_service


router = APIRouter(prefix="/llm", tags=["LLM Service"])


@router.get("/health")
async def get_llm_health() -> Dict[str, Any]:
    """
    Get comprehensive health status of LLM service
    
    Returns:
        - Service initialization status
        - Provider availability and performance
        - Cost monitoring status  
        - Circuit breaker status
        - Performance metrics
    """
    try:
        # Initialize service if needed
        if not production_llm_service.is_initialized:
            await production_llm_service.initialize()
        
        health_status = await production_llm_service.get_health_status()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": health_status,
            "endpoints": {
                "health": "/api/v1/llm/health",
                "cost": "/api/v1/llm/cost",
                "metrics": "/api/v1/llm/metrics",
                "test": "/api/v1/llm/test"
            }
        }
        
    except Exception as e:
        app_logger.error(f"LLM health check error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"LLM service health check failed: {str(e)}"
        )


@router.get("/cost")
async def get_cost_status() -> Dict[str, Any]:
    """
    Get current cost monitoring status
    
    Returns:
        - Daily budget and spending
        - Weekly summary
        - Alert level and thresholds
        - Provider cost breakdown
    """
    try:
        # Get daily and weekly summaries
        daily_summary = await cost_monitor.get_daily_summary()
        weekly_summary = await cost_monitor.get_weekly_summary()
        
        return {
            "status": "active",
            "timestamp": datetime.utcnow().isoformat(),
            "daily": daily_summary,
            "weekly": weekly_summary,
            "budget_enforcement": {
                "enabled": True,
                "daily_budget_brl": cost_monitor.daily_budget_brl,
                "alert_thresholds": {
                    "warning": "80%",
                    "critical": "90%", 
                    "emergency": "100%"
                }
            }
        }
        
    except Exception as e:
        app_logger.error(f"Cost status error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cost monitoring error: {str(e)}"
        )


@router.get("/metrics")
async def get_performance_metrics() -> Dict[str, Any]:
    """
    Get performance metrics from all providers
    
    Returns:
        - Provider performance statistics
        - Response time metrics
        - Success rates and error patterns
        - Token usage statistics
    """
    try:
        if not production_llm_service.is_initialized:
            await production_llm_service.initialize()
        
        all_metrics = production_llm_service.router.get_all_metrics()
        
        # Add service-level metrics
        service_metrics = {
            "circuit_breakers": {
                provider: {
                    "failure_count": production_llm_service.circuit_breaker_counts.get(provider, 0),
                    "is_open": production_llm_service._is_circuit_breaker_open(provider),
                }
                for provider in production_llm_service.router.providers.keys()
            },
            "routing": {
                "default_provider": production_llm_service.router.default_provider,
                "available_providers": list(production_llm_service.router.providers.keys()),
                "routing_rules_count": len(production_llm_service.router.routing_rules)
            }
        }
        
        return {
            "status": "active",
            "timestamp": datetime.utcnow().isoformat(),
            "providers": all_metrics,
            "service": service_metrics
        }
        
    except Exception as e:
        app_logger.error(f"Metrics retrieval error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Metrics retrieval failed: {str(e)}"
        )


class TestMessage(BaseModel):
    """Validated test message model"""
    message: str = Field(
        default="Olá! Este é um teste do serviço LLM.",
        min_length=1,
        max_length=500,
        description="Test message content"
    )
    provider: Optional[str] = Field(
        default=None,
        pattern=r"^(openai|anthropic)$",
        description="Specific provider to test"
    )
    
    @validator('message')
    def validate_message_content(cls, v):
        # Remove potentially dangerous content
        if re.search(r'[<>"\'\/\\]', v):
            raise ValueError("Message contains invalid characters")
        return v.strip()

@router.post("/test")
async def test_llm_service(test_data: TestMessage) -> Dict[str, Any]:
    """
    Test LLM service functionality
    
    Args:
        message: Test message to send
        provider: Specific provider to test (optional)
    
    Returns:
        - Test results including response time
        - Provider used and performance
        - Cost estimate for the test
    """
    try:
        if not production_llm_service.is_initialized:
            await production_llm_service.initialize()
        
        start_time = datetime.utcnow()
        
        # Generate test response with validated input
        response = await kumon_llm_service.generate_business_response(
            user_input=test_data.message,
            conversation_context={"messages": []},
            workflow_stage="general"
        )
        
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        # Track response time for SLA monitoring
        from ...services.business_metrics_service import track_response_time
        await track_response_time(duration_ms, {
            "provider": production_llm_service.router.default_provider,
            "endpoint": "test",
            "message_length": len(test_data.message)
        })
        
        return {
            "status": "success",
            "test_message": test_data.message,
            "response": response,
            "performance": {
                "response_time_ms": duration_ms,
                "target_met": duration_ms < 200,  # Updated to 200ms SLA target
                "sla_threshold_ms": 200
            },
            "provider_used": production_llm_service.router.default_provider,
            "timestamp": start_time.isoformat()
        }
        
    except Exception as e:
        app_logger.error(f"LLM service test error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"LLM service test failed: {str(e)}"
        )


@router.post("/test-provider/{provider_name}")
async def test_specific_provider(
    provider_name: str,
    test_data: TestMessage = TestMessage(message="Teste de conexão específica do provedor.")
) -> Dict[str, Any]:
    """
    Test specific provider functionality
    
    Args:
        provider_name: Provider to test (openai, anthropic, twilio)
        message: Test message
    
    Returns:
        - Provider-specific test results
        - Connection status and performance
        - Cost estimate
    """
    try:
        if not production_llm_service.is_initialized:
            await production_llm_service.initialize()
        
        if provider_name not in production_llm_service.router.providers:
            raise HTTPException(
                status_code=404,
                detail=f"Provider '{provider_name}' not found. Available: {list(production_llm_service.router.providers.keys())}"
            )
        
        provider = production_llm_service.router.providers[provider_name]
        
        # Test connection if available
        if hasattr(provider, 'test_connection'):
            test_result = await provider.test_connection()
            
            return {
                "status": "completed",
                "provider": provider_name,
                "test_result": test_result,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "unavailable",
                "provider": provider_name,
                "message": "Provider does not support connection testing",
                "timestamp": datetime.utcnow().isoformat()
            }
        
    except Exception as e:
        app_logger.error(f"Provider test error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Provider test failed: {str(e)}"
        )


@router.get("/cost/history/{days}")
async def get_cost_history(days: int = 7) -> Dict[str, Any]:
    """
    Get cost history for specified number of days
    
    Args:
        days: Number of days to retrieve (max 30)
    
    Returns:
        - Daily cost breakdown
        - Usage patterns
        - Provider cost distribution
    """
    try:
        if days > 30:
            days = 30
        
        # This would typically query historical data
        # For now, return weekly summary as base
        weekly_summary = await cost_monitor.get_weekly_summary()
        
        return {
            "status": "success",
            "days_requested": days,
            "data_available": 7,  # Currently only have 7 days
            "summary": weekly_summary,
            "note": "Historical data beyond 7 days not yet implemented",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        app_logger.error(f"Cost history error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cost history retrieval failed: {str(e)}"
        )


@router.get("/business-metrics")
async def get_business_metrics() -> Dict[str, Any]:
    """
    Get business metrics and conversion funnel data
    
    Returns:
        - Conversion funnel statistics
        - SLA compliance status
        - Business health indicators
        - Performance trends
    """
    try:
        # Initialize business metrics service if needed
        if not business_metrics_service.is_initialized:
            await business_metrics_service.initialize()
        
        # Get conversion summary
        conversion_summary = await business_metrics_service.get_conversion_summary()
        
        # Get SLA status
        sla_status = await business_metrics_service.get_sla_status()
        
        # Get business metrics
        metrics = await business_metrics_service.get_business_metrics(24)
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "conversion_funnel": conversion_summary,
            "sla_compliance": sla_status,
            "business_health": {
                "daily_qualified_leads": metrics.daily_qualified_leads,
                "weekly_appointments": metrics.weekly_appointments,
                "cost_per_qualified_lead": f"R$ {metrics.cost_per_qualified_lead:.2f}",
                "revenue_potential": f"R$ {metrics.revenue_potential:.2f}"
            },
            "kpis": {
                "overall_conversion_rate": f"{metrics.overall_conversion_rate:.1f}%",
                "avg_response_time_ms": metrics.avg_response_time_ms,
                "system_availability": f"{metrics.system_availability_pct:.1f}%",
                "error_rate": f"{metrics.error_rate_pct:.2f}%"
            }
        }
        
    except Exception as e:
        app_logger.error(f"Business metrics error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Business metrics retrieval failed: {str(e)}"
        )


@router.post("/track-conversion")
async def track_conversion_event(
    phone_number: str,
    stage: str,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Track conversion funnel event
    
    Args:
        phone_number: User phone number (last 4 digits for privacy)
        stage: Conversion stage (lead, qualified, scheduled, confirmed, completed)
        session_id: Optional session identifier
        metadata: Optional event metadata
    
    Returns:
        - Tracking confirmation
        - Updated conversion metrics
    """
    try:
        from ...services.business_metrics_service import ConversionStage
        
        # Validate stage
        try:
            conversion_stage = ConversionStage(stage.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid conversion stage: {stage}. Valid stages: {[s.value for s in ConversionStage]}"
            )
        
        # Initialize business metrics service if needed
        if not business_metrics_service.is_initialized:
            await business_metrics_service.initialize()
        
        # Track the conversion event
        success = await business_metrics_service.track_conversion_event(
            phone_number=phone_number,
            stage=conversion_stage,
            session_id=session_id,
            metadata=metadata or {}
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to track conversion event"
            )
        
        # Get updated metrics
        conversion_summary = await business_metrics_service.get_conversion_summary()
        
        return {
            "status": "tracked",
            "timestamp": datetime.utcnow().isoformat(),
            "tracked_event": {
                "stage": stage,
                "phone_number": f"***{phone_number[-4:]}" if len(phone_number) > 4 else "****",
                "session_id": session_id
            },
            "updated_metrics": conversion_summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Conversion tracking error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Conversion tracking failed: {str(e)}"
        )


@router.get("/sla-status")
async def get_sla_status() -> Dict[str, Any]:
    """
    Get SLA compliance and performance status
    
    Returns:
        - SLA thresholds and current performance
        - Recent violations
        - Compliance percentage
        - Performance trends
    """
    try:
        # Initialize business metrics service if needed
        if not business_metrics_service.is_initialized:
            await business_metrics_service.initialize()
        
        sla_status = await business_metrics_service.get_sla_status()
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "sla_compliance": sla_status,
            "targets": {
                "response_time_target": "< 200ms",
                "conversion_rate_target": "> 60%",
                "availability_target": "> 99.5%",
                "error_rate_target": "< 1%"
            }
        }
        
    except Exception as e:
        app_logger.error(f"SLA status error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"SLA status retrieval failed: {str(e)}"
        )


@router.post("/initialize")
async def initialize_llm_service() -> Dict[str, Any]:
    """
    Manually initialize LLM service (useful for testing)
    
    Returns:
        - Initialization status
        - Provider configuration
        - Service readiness
    """
    try:
        await production_llm_service.initialize()
        
        return {
            "status": "initialized",
            "providers": list(production_llm_service.router.providers.keys()),
            "default_provider": production_llm_service.router.default_provider,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        app_logger.error(f"LLM initialization error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"LLM service initialization failed: {str(e)}"
        )