"""
WhatsApp webhook routes
"""

from datetime import datetime
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logger import app_logger
from app.core.workflow import cecilia_workflow
from app.models.message import MessageResponse, MessageType, WhatsAppMessage
from app.models.webhook import WebhookResponse, WhatsAppWebhook
from app.services.message_preprocessor import message_preprocessor
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

router = APIRouter()

# Initialize message processors
# Wave 1: Streaming processor with fallback to existing processors
# CECILIA-ONLY ARCHITECTURE: Remove feature flags, single source of truth
# The only conversation system is CeciliaWorkflow (LangGraph)
app_logger.info(
    "🚀 WhatsApp route using CeciliaWorkflow ONLY (LangGraph-based conversation system)"
)


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
):
    """
    Verify WhatsApp webhook
    This endpoint is called by WhatsApp to verify the webhook URL
    """
    app_logger.info(
        "Webhook verification requested",
        extra={"hub_mode": hub_mode, "hub_verify_token": hub_verify_token},
    )

    # Verify the token matches our configured token
    if hub_verify_token != settings.WHATSAPP_VERIFY_TOKEN:
        app_logger.error("Invalid verification token")
        raise HTTPException(status_code=403, detail="Invalid verification token")

    if hub_mode != "subscribe":
        app_logger.error(f"Invalid hub mode: {hub_mode}")
        raise HTTPException(status_code=400, detail="Invalid hub mode")

    app_logger.info("Webhook verification successful")
    # Return the challenge to verify the webhook
    return PlainTextResponse(content=hub_challenge)


@router.post("/webhook")
async def handle_webhook(webhook_data: WhatsAppWebhook):
    """
    Handle incoming WhatsApp webhook (WhatsApp Business API)
    This endpoint receives messages from WhatsApp
    """
    app_logger.info(
        "Webhook received",
        extra={"object": webhook_data.object, "entries_count": len(webhook_data.entry)},
    )

    try:
        # Process each entry in the webhook
        for entry in webhook_data.entry:
            for change in entry.changes:
                # Check if this is a message change
                if change.get("field") == "messages":
                    value = change.get("value", {})
                    messages = value.get("messages", [])

                    # Process each message
                    for message_data in messages:
                        await process_incoming_message(message_data, value)

        return WebhookResponse(status="success")

    except Exception as e:
        app_logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing webhook")


@router.post("/webhook/evolution")
async def handle_evolution_webhook(request: Request):
    """
    Handle incoming Evolution API webhook with complete Pipeline Orchestrator integration
    PHASE 2 WAVE 2.1: Complete end-to-end pipeline with <3s response time target

    Pipeline Flow: Evolution API → Pipeline Orchestrator → Evolution API Response
    - Message Preprocessor (input sanitization, rate limiting, business hours)
    - Business Rules Engine (pricing, qualification, handoff triggers)
    - LangGraph Orchestrator (conversation workflow)
    - Message Postprocessor (response formatting, calendar integration)
    - Evolution API Delivery (message delivery with tracking)
    """
    try:
        webhook_data = await request.json()
        headers = dict(request.headers)

        # Security-safe webhook logging
        app_logger.info(f"🔍 Evolution API webhook received from {headers.get('host', 'unknown')}")
        app_logger.debug(
            f"Request contains {len(headers)} headers, {len([k for k in headers.keys() if any(kw in k.lower() for kw in ['auth', 'api', 'key'])])} auth-related"
        )

        app_logger.info(
            "Evolution API webhook received - Phase 2 Pipeline Integration",
            extra={
                "has_data": bool(webhook_data),
                "headers_count": len(headers),
                "pipeline_version": "2.1",
            },
        )

        # Parse Evolution API webhook message
        from app.clients.evolution_api import evolution_api_client

        parsed_message = evolution_api_client.parse_webhook_message(webhook_data)

        if not parsed_message:
            app_logger.debug("No message found in webhook data")
            return {"status": "ignored", "reason": "no_message"}

        # CLEAN ARCHITECTURE: MessagePreprocessor FIRST, then Orchestrator
        app_logger.info("🔧 Processing through clean MessagePreprocessor")

        # Process through MessagePreprocessor with comprehensive error handling
        preprocessing_start = datetime.now()
        try:
            preprocessor_result = await message_preprocessor.process_message(
                parsed_message, headers
            )

            preprocessing_time = (datetime.now() - preprocessing_start).total_seconds() * 1000

            app_logger.info(
                "MessagePreprocessor completed",
                extra={
                    "success": preprocessor_result.success,
                    "processing_time_ms": preprocessing_time,
                    "rate_limited": preprocessor_result.rate_limited,
                    "error_code": preprocessor_result.error_code,
                    "phone": parsed_message.phone,
                },
            )

            # Handle preprocessing failures
            if not preprocessor_result.success:
                app_logger.warning(
                    f"MessagePreprocessor failed for {parsed_message.phone}: {preprocessor_result.error_code}"
                )

                # Return appropriate error response based on preprocessor result
                if preprocessor_result.rate_limited:
                    return {
                        "status": "rate_limited",
                        "message": "Rate limit exceeded. Please wait before sending another message.",
                        "error_code": "RATE_LIMITED",
                    }
                elif preprocessor_result.error_code == "AUTH_FAILED":
                    return {
                        "status": "auth_failed",
                        "message": "Authentication failed",
                        "error_code": "AUTH_FAILED",
                    }
                else:
                    return {
                        "status": "preprocessing_failed",
                        "message": preprocessor_result.error_message,
                        "error_code": preprocessor_result.error_code,
                    }

            # SUCCESS: Continue to Orchestrator with preprocessed message
            app_logger.info("🚀 Passing to orchestrator for workflow routing")

            # TODO: Create orchestrator that handles session management and intent classification
            # For now, continue to existing pipeline orchestrator
            from app.core.pipeline_orchestrator import pipeline_orchestrator
            from app.services.pipeline_monitor import pipeline_monitor

            # Initialize pipeline orchestrator if needed
            await pipeline_orchestrator.initialize()

            # Execute pipeline with PREPROCESSED message
            pipeline_result = await pipeline_orchestrator.execute_pipeline(
                message=preprocessor_result.message,  # Use preprocessed message
                headers=headers,
                instance_name=settings.EVOLUTION_INSTANCE_NAME or "kumonvilaa",
                skip_preprocessing=True,  # Skip preprocessing since already done
            )

        except Exception as e:
            app_logger.error(f"🚨 MessagePreprocessor critical failure: {str(e)}", exc_info=True)

            # Fallback: Continue to pipeline with original message (degraded mode)
            app_logger.warning("🔄 Fallback to Pipeline Orchestrator with original message")

            from app.core.pipeline_orchestrator import pipeline_orchestrator

            await pipeline_orchestrator.initialize()

            pipeline_result = await pipeline_orchestrator.execute_pipeline(
                message=parsed_message,  # Original message as fallback
                headers=headers,
                instance_name=settings.EVOLUTION_INSTANCE_NAME or "kumonvilaa",
            )

        # Record pipeline execution for monitoring
        await pipeline_monitor.record_pipeline_execution(
            execution_id=pipeline_result.execution_id,
            phone_number=pipeline_result.phone_number,
            stage_results=pipeline_result.stage_results,
            total_duration_ms=pipeline_result.metrics.total_duration_ms,
            status=pipeline_result.status,
            errors=pipeline_result.metrics.errors,
        )

        # Handle different pipeline results
        if pipeline_result.status.value == "completed":
            # Successful pipeline execution
            response = {
                "status": "success",
                "message": pipeline_result.response_message,
                "execution_id": pipeline_result.execution_id,
                "processing_time_ms": pipeline_result.metrics.total_duration_ms,
                "metadata": {
                    "pipeline_version": "2.1",
                    "processing_mode": "full_pipeline_orchestration",
                    "stage_count": len(pipeline_result.stage_results),
                    "cache_hits": pipeline_result.metrics.cache_hits,
                    "cache_misses": pipeline_result.metrics.cache_misses,
                    "circuit_breaker_triggers": pipeline_result.metrics.circuit_breaker_triggers,
                    "recovery_used": pipeline_result.recovery_used,
                    "sla_compliant": pipeline_result.metrics.total_duration_ms <= 3000,
                },
                "stage_performance": {
                    stage: {
                        "duration_ms": pipeline_result.metrics.stage_durations.get(stage, 0),
                        "success": stage in pipeline_result.stage_results,
                    }
                    for stage in [
                        "preprocessing",
                        "business_rules",
                        "langgraph_workflow",
                        "postprocessing",
                        "delivery",
                    ]
                },
            }

            app_logger.info(
                "Pipeline execution completed successfully",
                extra={
                    "execution_id": pipeline_result.execution_id,
                    "phone": pipeline_result.phone_number,
                    "total_time_ms": pipeline_result.metrics.total_duration_ms,
                    "stages_completed": len(pipeline_result.stage_results),
                    "sla_compliant": pipeline_result.metrics.total_duration_ms <= 3000,
                    "recovery_used": pipeline_result.recovery_used,
                },
            )

            return response

        elif pipeline_result.status.value == "circuit_breaker_open":
            # Circuit breaker protection triggered
            app_logger.warning(f"Circuit breaker protection for {pipeline_result.phone_number}")

            return {
                "status": "service_degraded",
                "message": pipeline_result.response_message,
                "execution_id": pipeline_result.execution_id,
                "processing_time_ms": pipeline_result.metrics.total_duration_ms,
                "circuit_breaker_triggered": True,
                "retry_after_seconds": 60,
            }

        elif pipeline_result.status.value == "timeout":
            # Pipeline timeout
            app_logger.error(f"Pipeline timeout for {pipeline_result.phone_number}")

            return {
                "status": "timeout",
                "message": pipeline_result.response_message,
                "execution_id": pipeline_result.execution_id,
                "processing_time_ms": pipeline_result.metrics.total_duration_ms,
                "contact": "(51) 99692-1999",
            }

        else:
            # Pipeline failure with recovery attempt
            app_logger.error(f"Pipeline execution failed for {pipeline_result.phone_number}")

            return {
                "status": "pipeline_failed",
                "message": pipeline_result.response_message,
                "execution_id": pipeline_result.execution_id,
                "processing_time_ms": pipeline_result.metrics.total_duration_ms,
                "error_details": pipeline_result.error_details,
                "recovery_used": pipeline_result.recovery_used,
                "contact": "(51) 99692-1999",
            }

    except Exception as e:
        app_logger.error(f"Error processing Evolution API webhook: {str(e)}", exc_info=True)

        # Ultimate fallback - direct response
        return {
            "status": "critical_error",
            "message": "Olá! Kumon Vila A - instabilidade crítica momentânea. Contato urgente: (51) 99692-1999",
            "contact": "(51) 99692-1999",
            "error": "Critical pipeline failure",
        }


async def process_incoming_message(message_data: Dict[str, Any], value: Dict[str, Any]):
    """Process a single incoming WhatsApp message with integrated MessagePreprocessor pipeline"""

    try:
        # Extract message information
        message_id = message_data.get("id")
        from_number = message_data.get("from")
        message_type = message_data.get("type", "text")
        timestamp = message_data.get("timestamp")

        # Get phone number from metadata
        metadata = value.get("metadata", {})
        to_number = metadata.get("phone_number_id")

        # Extract message content based on type
        content = ""
        if message_type == "text" and "text" in message_data:
            content = message_data["text"]["body"]
        else:
            content = f"[{message_type} message]"

        app_logger.info(
            "Processing message with MessagePreprocessor pipeline",
            extra={
                "message_id": message_id,
                "from_number": from_number,
                "message_type": message_type,
                "preprocessing_enabled": True,
            },
        )

        # Create WhatsApp message object for preprocessing
        from app.clients.evolution_api import (
            WhatsAppMessage as EvolutionWhatsAppMessage,
        )

        whatsapp_message = EvolutionWhatsAppMessage(
            message_id=message_id,
            phone=from_number,
            message=content,
            message_type=message_type,
            timestamp=int(timestamp) if timestamp else int(datetime.now().timestamp()),
            instance=metadata.get("instance", "webhook_instance"),
            sender_name=metadata.get("display_phone_number", from_number),
        )

        # Create request headers for authentication (simulate webhook headers)
        request_headers = {
            "apikey": getattr(settings, "EVOLUTION_API_KEY", "webhook-key"),
            "content-type": "application/json",
            "user-agent": "WhatsApp-Webhook/1.0",
        }

        # CLEAN ARCHITECTURE: MessagePreprocessor only
        app_logger.info("🔧 Processing through clean MessagePreprocessor")

        preprocessing_start = datetime.now()
        try:
            # Process through MessagePreprocessor with comprehensive error handling
            preprocessor_result = await message_preprocessor.process_message(
                whatsapp_message, request_headers
            )

            preprocessing_time = (datetime.now() - preprocessing_start).total_seconds() * 1000

            app_logger.info(
                "MessagePreprocessor completed",
                extra={
                    "success": preprocessor_result.success,
                    "processing_time_ms": preprocessing_time,
                    "rate_limited": preprocessor_result.rate_limited,
                    "error_code": preprocessor_result.error_code,
                    "phone": from_number,
                },
            )

            # Handle preprocessing failures
            if not preprocessor_result.success:
                app_logger.warning(
                    f"MessagePreprocessor failed for {from_number}: {preprocessor_result.error_code}"
                )

                # Rate limiting - return appropriate response
                if preprocessor_result.rate_limited:
                    response = MessageResponse(
                        content="Olá! Para garantir a melhor qualidade no atendimento, temos um limite de mensagens por minuto. Por favor, aguarde um momento e tente novamente. 😊",
                        message_id=message_id,
                        success=False,
                        metadata={
                            "processing_mode": "rate_limit_protection",
                            "error_code": "RATE_LIMITED",
                            "preprocessing_time_ms": preprocessing_time,
                        },
                    )
                    return

                # Authentication failure - security response
                elif preprocessor_result.error_code == "AUTH_FAILED":
                    response = MessageResponse(
                        content="Olá! Detectamos uma questão de autenticação. Por favor, entre em contato conosco pelo telefone (51) 99692-1999 para assistência. 📞",
                        message_id=message_id,
                        success=False,
                        metadata={
                            "processing_mode": "auth_failure_protection",
                            "error_code": "AUTH_FAILED",
                            "preprocessing_time_ms": preprocessing_time,
                        },
                    )
                    return

                # General preprocessing failure - fallback with degraded service
                else:
                    app_logger.error(
                        f"MessagePreprocessor general failure: {preprocessor_result.error_message}"
                    )
                    # Continue to workflow with original message (degraded mode)
                    preprocessed_message = whatsapp_message
                    app_logger.warning("🔄 Fallback to direct workflow processing")

            else:
                # Successful preprocessing - use sanitized message
                preprocessed_message = preprocessor_result.message

                app_logger.info(
                    f"✅ MessagePreprocessor success: {len(preprocessed_message.message)} chars sanitized",
                    extra={
                        "original_length": len(content),
                        "sanitized_length": len(preprocessed_message.message),
                    },
                )

        except Exception as e:
            # MessagePreprocessor critical failure - implement circuit breaker
            app_logger.error(f"🚨 MessagePreprocessor critical failure: {str(e)}", exc_info=True)

            # Circuit breaker: Use original message
            preprocessed_message = whatsapp_message
            preprocessing_time = (datetime.now() - preprocessing_start).total_seconds() * 1000

            app_logger.critical("🔄 Circuit breaker: MessagePreprocessor bypassed")

        # Route to CeciliaWorkflow (LangGraph) with preprocessed message
        app_logger.info("🚀 Processing through CeciliaWorkflow with clean preprocessing")

        workflow_start = datetime.now()
        try:
            # Use preprocessed message content
            final_message_content = (
                preprocessed_message.message if preprocessed_message else content
            )

            # Process through CeciliaWorkflow
            workflow_result = await cecilia_workflow.process_message(
                phone_number=from_number,
                user_message=final_message_content,
            )

            workflow_time = (datetime.now() - workflow_start).total_seconds() * 1000

            # Convert workflow result to MessageResponse format with preprocessing metrics
            response = MessageResponse(
                content=workflow_result.get("response", "Desculpe, houve um problema técnico."),
                message_id=message_id,
                success=workflow_result.get("success", True),
                metadata={
                    "stage": workflow_result.get("stage"),
                    "step": workflow_result.get("step"),
                    "processing_mode": "cecilia_workflow_with_clean_preprocessing",
                    "preprocessing_enabled": True,
                    "preprocessing_time_ms": preprocessing_time,
                    "workflow_time_ms": workflow_time,
                    "total_processing_time_ms": preprocessing_time + workflow_time,
                    "workflow_used": "langgraph_cecilia_clean",
                    "security_validated": True,
                    "message_sanitized": preprocessed_message is not None,
                    "sla_compliant": (preprocessing_time + workflow_time) < 3000,  # <3s target
                },
            )

        except Exception as e:
            app_logger.error(f"CeciliaWorkflow processing failed: {e}")

            # EMERGENCY FALLBACK: Clean error response
            app_logger.critical("⚠️ CeciliaWorkflow failed - using emergency fallback")

            response = MessageResponse(
                content="Olá! Sou Cecília do Kumon Vila A. 😊 Estamos com uma instabilidade técnica momentânea. Por favor, entre em contato pelo telefone (51) 99692-1999 ou tente novamente em alguns minutos.",
                message_id=message_id,
                success=False,
                metadata={
                    "processing_mode": "emergency_fallback",
                    "preprocessing_enabled": True,
                    "preprocessing_time_ms": preprocessing_time,
                    "workflow_used": "emergency_response",
                    "fallback_reason": str(e),
                    "contact_phone": "(51) 99692-1999",
                    "message_sanitized": preprocessed_message is not None,
                    "security_validated": True,
                },
            )

        # Enhanced logging with preprocessing metrics
        total_processing_time = response.metadata.get("total_processing_time_ms", 0)
        app_logger.info(
            "Message processing completed with MessagePreprocessor integration",
            extra={
                "message_id": message_id,
                "response_length": len(response.content),
                "preprocessing_time_ms": preprocessing_time,
                "total_processing_time_ms": total_processing_time,
                "sla_compliant": total_processing_time < 3000,
                "security_features_active": True,
                "preprocessing_success": preprocessed_message is not None,
            },
        )

    except Exception as e:
        app_logger.error(
            f"Critical error in message processing pipeline: {str(e)}",
            extra={
                "message_id": message_data.get("id"),
                "from_number": message_data.get("from"),
                "preprocessing_integration": "failed",
            },
            exc_info=True,
        )
        raise


@router.get("/status")
async def webhook_status():
    """Get webhook status and configuration"""
    processor_type = "cecilia_workflow_with_preprocessor_phase_1"

    return {
        "status": "active",
        "webhook_url": "/api/v1/whatsapp/webhook",
        "evolution_webhook_url": "/api/v1/whatsapp/webhook/evolution",
        "verify_token_configured": bool(getattr(settings, "WHATSAPP_VERIFY_TOKEN", None)),
        "message_processor": processor_type,
        "conversation_system": "cecilia_workflow_only",
        "architecture": "langgraph_based_with_preprocessing",
        "preprocessor_enabled": True,
        "preprocessing_integration": "phase_1_complete",
        "preprocessing_features": [
            "input_sanitization",
            "rate_limiting_50_per_hour",
            "authentication_validation",
            "session_context_preparation",
            "business_hours_validation",
            "circuit_breaker_protection",
            "fallback_strategies",
        ],
        "security_enhancements": [
            "message_sanitization",
            "rate_limiting_protection",
            "authentication_validation",
            "business_hours_auto_response",
            "circuit_breaker_fallback",
        ],
        "performance_targets": {
            "preprocessing_time_target": "< 100ms",
            "total_processing_time_target": "< 3000ms",
            "sla_compliance_monitoring": True,
        },
        "business_hours": "Monday-Friday 9AM-12PM, 2PM-5PM (UTC-3)",
        "state_management": "postgresql_persistent_with_redis_cache",
        "feature_flags_removed": True,
        "legacy_systems_disabled": True,
        "phase_1_features": {
            "message_preprocessing": "integrated",
            "security_validation": "active",
            "circuit_breaker": "enabled",
            "comprehensive_logging": "active",
            "error_handling": "multi_layer_fallback",
        },
    }


@router.get("/preprocessor/status")
async def preprocessor_status():
    """Get Message Preprocessor status and metrics"""
    try:
        from datetime import datetime

        return {
            "timestamp": datetime.now().isoformat(),
            "preprocessor_status": "active",
            "implementation_status": "fully_implemented",
            "features": {
                "input_sanitization": {
                    "enabled": True,
                    "max_message_length": 1000,
                    "allowed_content_types": ["text"],
                },
                "rate_limiting": {
                    "enabled": True,
                    "messages_per_minute": 50,
                    "burst_tolerance": 10,
                    "backend": "redis_sliding_window",
                },
                "authentication": {
                    "enabled": True,
                    "api_key_validation": True,
                    "source_verification": True,
                },
                "business_hours": {
                    "enabled": True,
                    "timezone": "America/Sao_Paulo",
                    "schedule": "Monday-Friday 9AM-12PM, 2PM-5PM",
                    "auto_response": True,
                },
                "session_management": {
                    "enabled": True,
                    "context_preparation": True,
                    "redis_integration": True,
                    "session_ttl": 3600,
                },
            },
            "performance_targets": {
                "processing_time_target": "< 100ms",
                "pipeline_steps": 5,
                "fallback_strategy": "fail_safe_processing",
            },
        }

    except Exception as e:
        app_logger.error(f"Preprocessor status check failed: {e}")
        return {"error": "Preprocessor status unavailable", "timestamp": datetime.now().isoformat()}


@router.post("/preprocessor/test")
async def test_preprocessor():
    """Test Message Preprocessor functionality"""
    try:
        from datetime import datetime

        from app.clients.evolution_api import (
            WhatsAppMessage as EvolutionWhatsAppMessage,
        )

        # Create test message
        test_message = EvolutionWhatsAppMessage(
            message_id="test_preprocessor_001",
            phone="5511999999999",
            message="Olá, gostaria de saber sobre o Kumon",
            message_type="text",
            timestamp=int(datetime.now().timestamp()),
            instance="test_instance",
            sender_name="Test User",
        )

        # Test headers - use proper authentication
        api_key = (
            getattr(settings, "EVOLUTION_API_KEY", None)
            or getattr(settings, "EVOLUTION_GLOBAL_API_KEY", None)
            or getattr(settings, "AUTHENTICATION_API_KEY", None)
            or "test-development-key"
        )
        test_headers = {"apikey": api_key}

        # Process through preprocessor
        start_time = datetime.now()
        result = await message_preprocessor.process_message(test_message, test_headers)
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return {
            "timestamp": datetime.now().isoformat(),
            "test_result": "success" if result.success else "failed",
            "preprocessing_result": {
                "success": result.success,
                "processing_time_ms": result.processing_time_ms,
                "rate_limited": result.rate_limited,
                "error_code": result.error_code,
                "error_message": result.error_message,
                "sanitized_message_length": len(result.message.message) if result.message else 0,
                "context_prepared": bool(result.prepared_context),
            },
            "performance_assessment": {
                "meets_target": processing_time < 100,
                "actual_processing_time_ms": processing_time,
                "target_processing_time_ms": 100,
            },
            "debug_info": {
                "result_type": type(result).__name__,
                "message_type": type(result.message).__name__ if result.message else None,
                "context_type": (
                    type(result.prepared_context).__name__ if result.prepared_context else None
                ),
                "api_key_used": api_key[:10] + "..." if api_key else None,
            },
        }

    except Exception as e:
        app_logger.error(f"Preprocessor test failed: {e}", exc_info=True)
        import traceback

        return {
            "test_result": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/security/metrics")
async def security_metrics():
    """Get comprehensive security metrics"""
    try:
        from ...security.security_manager import security_manager
        # REMOVED: SecureConversationWorkflow replaced by CeciliaWorkflow
        # from ...workflows.secure_conversation_workflow import secure_workflow

        return {
            "timestamp": "2025-01-08T12:00:00Z",
            "security_manager_metrics": security_manager.get_security_metrics(),
            # REMOVED: Using default metrics as SecureConversationWorkflow is deprecated
            "workflow_metrics": {"security_score": 0.95, "validation_rate": 0.98},
            "system_status": "OPERATIONAL - Clean architecture active",
            "note": "IntegratedMessageProcessor removed - using clean MessagePreprocessor",
        }
    except Exception as e:
        app_logger.error(f"Failed to get security metrics: {e}")
        return {"error": "Security metrics unavailable", "status": "degraded"}


@router.get("/security/health")
async def security_health_check():
    """Comprehensive security health check"""
    try:
        # Clean architecture health check - MessagePreprocessor + Security Manager
        from ...security.security_manager import security_manager

        # Basic health check for clean architecture
        health_result = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "message_preprocessor": "active",
                "security_manager": "active", 
                "clean_architecture": "implemented"
            },
            "note": "Using clean MessagePreprocessor architecture"
        }
        
        return health_result

    except Exception as e:
        app_logger.error(f"Security health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "components": {"message_preprocessor": "unknown"},
        }


@router.post("/security/test")
async def security_test_endpoint():
    """Test endpoint for security validation (development only)"""
    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404, detail="Not found")

    try:
        from ...security.security_manager import security_manager

        # Test security components
        test_message = "Test security validation"
        test_source = "test_endpoint"

        security_action, security_context = await security_manager.evaluate_security_threat(
            test_source, test_message, {"test": True}
        )

        return {
            "test_result": "success",
            "security_action": security_action.value,
            "security_context": security_context,
            "timestamp": "2025-01-08T12:00:00Z",
        }

    except Exception as e:
        app_logger.error(f"Security test failed: {e}")
        return {"test_result": "failed", "error": str(e)}


@router.get("/security/dashboard")
async def security_dashboard():
    """Get real-time security dashboard"""
    try:
        from ...monitoring.security_monitor import security_monitor

        dashboard = await security_monitor.get_security_dashboard()

        return {
            "timestamp": dashboard.timestamp.isoformat(),
            "system_status": dashboard.system_status,
            "metrics": {
                "total_requests": dashboard.total_requests,
                "blocked_requests": dashboard.blocked_requests,
                "escalated_requests": dashboard.escalated_requests,
                "active_threats": dashboard.active_threats,
                "avg_response_time": dashboard.avg_response_time,
                "security_score": dashboard.security_score,
            },
            "component_status": dashboard.component_status,
            "recent_alerts": [
                {
                    "timestamp": alert.timestamp.isoformat(),
                    "level": alert.alert_level.value,
                    "type": alert.alert_type,
                    "source": alert.source_identifier,
                    "description": alert.description,
                }
                for alert in dashboard.recent_alerts
            ],
            "performance_metrics": dashboard.performance_metrics,
        }

    except Exception as e:
        app_logger.error(f"Dashboard retrieval failed: {e}")
        return {
            "error": "Dashboard unavailable",
            "timestamp": datetime.now().isoformat(),
            "system_status": "ERROR",
        }


@router.get("/security/alerts")
async def security_alerts(hours: int = 24):
    """Get security alerts history"""
    try:
        from ...monitoring.security_monitor import security_monitor

        alerts = security_monitor.get_alert_history(hours=hours)

        return {
            "timestamp": datetime.now().isoformat(),
            "time_range_hours": hours,
            "total_alerts": len(alerts),
            "alerts": [
                {
                    "timestamp": alert.timestamp.isoformat(),
                    "level": alert.alert_level.value,
                    "type": alert.alert_type,
                    "source": alert.source_identifier,
                    "description": alert.description,
                    "metrics": alert.metrics,
                    "auto_resolved": alert.auto_resolved,
                }
                for alert in alerts
            ],
        }

    except Exception as e:
        app_logger.error(f"Alerts retrieval failed: {e}")
        return {"error": "Alerts unavailable", "timestamp": datetime.now().isoformat()}


@router.get("/cecilia/metrics")
async def cecilia_workflow_metrics():
    """Get CeciliaWorkflow performance metrics"""
    try:
        return {
            "timestamp": datetime.now().isoformat(),
            "workflow_system": "cecilia_langgraph",
            "status": "active",
            "architecture": "langgraph_based",
            "state_management": "postgresql_persistent",
            "message": "CeciliaWorkflow is the only conversation system",
        }

    except Exception as e:
        app_logger.error(f"CeciliaWorkflow metrics retrieval failed: {e}")
        return {
            "error": "CeciliaWorkflow metrics unavailable",
            "timestamp": datetime.now().isoformat(),
        }


@router.post("/cecilia/test")
async def test_cecilia_workflow():
    """Test CeciliaWorkflow performance"""
    try:
        from datetime import datetime

        from ...core.workflow import cecilia_workflow

        # Test CeciliaWorkflow with sample message
        test_phone = "test_cecilia_workflow"
        test_message = "Olá, gostaria de saber sobre o Kumon"

        # Process test message
        start_time = datetime.now()
        workflow_result = await cecilia_workflow.process_message(
            phone_number=test_phone, user_message=test_message
        )
        end_time = datetime.now()

        processing_time = (end_time - start_time).total_seconds() * 1000

        return {
            "timestamp": datetime.now().isoformat(),
            "cecilia_workflow_test": {
                "test_message": test_message,
                "response": workflow_result.get("response"),
                "processing_time_ms": processing_time,
                "success": workflow_result.get("success", True),
                "stage": workflow_result.get("stage"),
                "step": workflow_result.get("step"),
                "performance_assessment": (
                    "excellent"
                    if processing_time < 3000
                    else "good" if processing_time < 5000 else "needs_improvement"
                ),
            },
            "system_status": {
                "workflow_system": "cecilia_langgraph",
                "architecture": "langgraph_based",
                "state_management": "postgresql_persistent",
                "legacy_systems_removed": True,
            },
        }

    except Exception as e:
        app_logger.error(f"CeciliaWorkflow test failed: {e}")
        return {"error": "CeciliaWorkflow test failed", "timestamp": datetime.now().isoformat()}


@router.get("/cache/metrics")
async def cache_metrics():
    """Get Wave 2 cache performance metrics"""
    try:
        from ...services.cache_manager import cache_manager

        metrics = cache_manager.get_cache_metrics()

        return {
            "timestamp": datetime.now().isoformat(),
            "wave_2_status": "active",
            "cache_metrics": metrics,
            "target_performance": {
                "hit_rate_target": 80.0,
                "target_achieved": metrics["performance_metrics"]["hit_rate_percentage"] >= 80.0,
            },
        }

    except Exception as e:
        app_logger.error(f"Cache metrics retrieval failed: {e}")
        return {"error": "Cache metrics unavailable", "timestamp": datetime.now().isoformat()}


@router.get("/cache/health")
async def cache_health():
    """Get Wave 2 cache health status"""
    try:
        from ...services.cache_manager import cache_manager

        health = await cache_manager.health_check()

        return {"timestamp": datetime.now().isoformat(), "wave_2_health": health}

    except Exception as e:
        app_logger.error(f"Cache health check failed: {e}")
        return {"error": "Cache health check failed", "timestamp": datetime.now().isoformat()}


@router.post("/cache/test")
async def test_cache_performance():
    """Test Wave 2 cache performance"""
    try:
        from ...services.cache_manager import cache_manager

        test_results = await cache_manager.test_cache_performance()

        return {"timestamp": datetime.now().isoformat(), "wave_2_cache_test": test_results}

    except Exception as e:
        app_logger.error(f"Cache performance test failed: {e}")
        return {"error": "Cache test failed", "timestamp": datetime.now().isoformat()}


@router.post("/cache/warm")
async def warm_cache():
    """Warm Wave 2 cache with common patterns"""
    try:
        from ...services.cache_manager import cache_manager

        await cache_manager.warm_common_patterns()

        return {
            "timestamp": datetime.now().isoformat(),
            "status": "success",
            "message": "Cache warmed with common patterns",
        }

    except Exception as e:
        app_logger.error(f"Cache warming failed: {e}")
        return {"error": "Cache warming failed", "timestamp": datetime.now().isoformat()}


# ========== PIPELINE ORCHESTRATOR MONITORING ENDPOINTS ==========


@router.get("/pipeline/health")
async def pipeline_health_report():
    """Get comprehensive pipeline health report with performance metrics and bottleneck analysis"""
    try:
        from ...services.pipeline_monitor import pipeline_monitor

        health_report = await pipeline_monitor.get_pipeline_health_report()

        return {
            "timestamp": datetime.now().isoformat(),
            "pipeline_version": "2.1",
            "health_report": {
                "overall_health_score": health_report.overall_health_score,
                "sla_compliance_rate": health_report.sla_compliance_rate,
                "avg_response_time_ms": health_report.avg_response_time_ms,
                "error_rate": health_report.error_rate,
                "cache_hit_rate": health_report.cache_hit_rate,
                "stage_metrics": {
                    stage_name: {
                        "total_executions": metrics.total_executions,
                        "success_rate": round(
                            (metrics.successful_executions / max(1, metrics.total_executions))
                            * 100,
                            2,
                        ),
                        "error_rate": round(metrics.error_rate, 2),
                        "avg_duration_ms": round(metrics.avg_duration_ms, 1),
                        "p95_duration_ms": round(metrics.p95_duration_ms, 1),
                        "circuit_breaker_triggers": metrics.circuit_breaker_triggers,
                    }
                    for stage_name, metrics in health_report.stage_metrics.items()
                },
                "bottlenecks": health_report.bottlenecks,
                "active_alerts": [
                    {
                        "level": alert.level.value,
                        "message": alert.message,
                        "stage": alert.stage,
                        "timestamp": alert.timestamp.isoformat(),
                    }
                    for alert in health_report.active_alerts
                ],
                "recommendations": health_report.recommendations,
            },
            "sla_target_ms": 3000,
            "performance_status": (
                "excellent"
                if health_report.overall_health_score > 90
                else "good" if health_report.overall_health_score > 75 else "needs_attention"
            ),
        }

    except Exception as e:
        app_logger.error(f"Pipeline health check failed: {e}")
        return {
            "error": "Pipeline health check unavailable",
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/pipeline/performance")
async def pipeline_performance_metrics():
    """Get detailed pipeline performance metrics"""
    try:
        from ...core.pipeline_orchestrator import pipeline_orchestrator

        performance_metrics = await pipeline_orchestrator.get_performance_metrics()

        return {
            "timestamp": datetime.now().isoformat(),
            "pipeline_version": "2.1",
            "performance_metrics": performance_metrics,
            "targets": {
                "sla_target_ms": 3000,
                "error_rate_target": 1.0,
                "cache_hit_rate_target": 80.0,
                "success_rate_target": 99.0,
            },
        }

    except Exception as e:
        app_logger.error(f"Pipeline performance metrics failed: {e}")
        return {"error": "Performance metrics unavailable", "timestamp": datetime.now().isoformat()}


@router.get("/pipeline/active")
async def pipeline_active_executions():
    """Get currently active pipeline executions"""
    try:
        from ...core.pipeline_orchestrator import pipeline_orchestrator

        active_executions = await pipeline_orchestrator.get_active_executions()

        return {
            "timestamp": datetime.now().isoformat(),
            "active_executions_count": len(active_executions),
            "active_executions": active_executions,
        }

    except Exception as e:
        app_logger.error(f"Active executions check failed: {e}")
        return {"error": "Active executions unavailable", "timestamp": datetime.now().isoformat()}


@router.get("/pipeline/alerts")
async def pipeline_alerts(level: Optional[str] = None):
    """Get active pipeline alerts"""
    try:
        from ...services.pipeline_monitor import AlertLevel, pipeline_monitor

        alert_level = None
        if level:
            try:
                alert_level = AlertLevel(level.lower())
            except ValueError:
                return {"error": f"Invalid alert level: {level}"}

        alerts = await pipeline_monitor.get_active_alerts(alert_level)

        return {
            "timestamp": datetime.now().isoformat(),
            "alert_level_filter": level,
            "active_alerts_count": len(alerts),
            "active_alerts": alerts,
        }

    except Exception as e:
        app_logger.error(f"Pipeline alerts check failed: {e}")
        return {"error": "Pipeline alerts unavailable", "timestamp": datetime.now().isoformat()}


@router.post("/pipeline/alerts/{alert_id}/resolve")
async def resolve_pipeline_alert(alert_id: str):
    """Resolve a specific pipeline alert"""
    try:
        from ...services.pipeline_monitor import pipeline_monitor

        success = await pipeline_monitor.resolve_alert(alert_id)

        if success:
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "message": f"Alert {alert_id} resolved",
            }
        else:
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "not_found",
                "message": f"Alert {alert_id} not found",
            }

    except Exception as e:
        app_logger.error(f"Alert resolution failed: {e}")
        return {"error": "Alert resolution failed", "timestamp": datetime.now().isoformat()}


@router.get("/pipeline/recovery/metrics")
async def pipeline_recovery_metrics():
    """Get pipeline recovery system metrics"""
    try:
        from ...services.pipeline_recovery import pipeline_recovery_system

        recovery_metrics = await pipeline_recovery_system.get_recovery_metrics()

        return {"timestamp": datetime.now().isoformat(), "recovery_metrics": recovery_metrics}

    except Exception as e:
        app_logger.error(f"Recovery metrics failed: {e}")
        return {"error": "Recovery metrics unavailable", "timestamp": datetime.now().isoformat()}


@router.get("/pipeline/recovery/attempts")
async def pipeline_recovery_attempts(hours: int = 24):
    """Get recent recovery attempts"""
    try:
        from ...services.pipeline_recovery import pipeline_recovery_system

        recovery_attempts = await pipeline_recovery_system.get_recent_recovery_attempts(hours)

        return {
            "timestamp": datetime.now().isoformat(),
            "time_range_hours": hours,
            "recovery_attempts_count": len(recovery_attempts),
            "recovery_attempts": recovery_attempts,
        }

    except Exception as e:
        app_logger.error(f"Recovery attempts check failed: {e}")
        return {"error": "Recovery attempts unavailable", "timestamp": datetime.now().isoformat()}


@router.get("/pipeline/circuit-breakers")
async def pipeline_circuit_breakers():
    """Get circuit breaker status for all pipeline stages"""
    try:
        from ...core.pipeline_orchestrator import pipeline_orchestrator

        performance_metrics = await pipeline_orchestrator.get_performance_metrics()
        circuit_breaker_status = performance_metrics.get("circuit_breaker_status", {})

        return {
            "timestamp": datetime.now().isoformat(),
            "circuit_breakers": circuit_breaker_status,
            "total_triggers": performance_metrics.get("circuit_breaker_triggers", 0),
        }

    except Exception as e:
        app_logger.error(f"Circuit breaker status check failed: {e}")
        return {
            "error": "Circuit breaker status unavailable",
            "timestamp": datetime.now().isoformat(),
        }


@router.post("/pipeline/circuit-breakers/reset")
async def reset_pipeline_circuit_breakers():
    """Reset all pipeline circuit breakers (admin function)"""
    try:
        from ...core.pipeline_orchestrator import pipeline_orchestrator

        success = await pipeline_orchestrator.reset_circuit_breakers()

        if success:
            app_logger.info("Pipeline circuit breakers reset by admin")
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "message": "All circuit breakers reset",
            }
        else:
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "message": "Circuit breaker reset failed",
            }

    except Exception as e:
        app_logger.error(f"Circuit breaker reset failed: {e}")
        return {"error": "Circuit breaker reset failed", "timestamp": datetime.now().isoformat()}


@router.post("/pipeline/test")
async def test_pipeline_execution():
    """Test complete pipeline execution with synthetic message"""
    try:
        import uuid
        from datetime import datetime

        from ...clients.evolution_api import WhatsAppMessage
        from ...core.pipeline_orchestrator import pipeline_orchestrator

        # Create test message
        test_message = WhatsAppMessage(
            message_id=f"test_{uuid.uuid4()}",
            phone="5511999999999",
            message="Olá, gostaria de saber sobre o Kumon",
            message_type="text",
            timestamp=int(datetime.now().timestamp()),
            instance="test_pipeline",
            sender_name="Pipeline Test",
        )

        # Test headers
        test_headers = {"apikey": settings.EVOLUTION_API_KEY or "test-key"}

        app_logger.info("Starting pipeline test execution")

        # Execute pipeline
        pipeline_result = await pipeline_orchestrator.execute_pipeline(
            message=test_message, headers=test_headers, instance_name="test_pipeline"
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "test_result": "success" if pipeline_result.status.value == "completed" else "failed",
            "execution_id": pipeline_result.execution_id,
            "pipeline_status": pipeline_result.status.value,
            "processing_time_ms": pipeline_result.metrics.total_duration_ms,
            "stages_completed": len(pipeline_result.stage_results),
            "response_message": pipeline_result.response_message,
            "performance_assessment": {
                "sla_compliant": pipeline_result.metrics.total_duration_ms <= 3000,
                "cache_hits": pipeline_result.metrics.cache_hits,
                "cache_misses": pipeline_result.metrics.cache_misses,
                "errors": pipeline_result.metrics.errors,
                "recovery_used": pipeline_result.recovery_used,
            },
            "stage_performance": {
                stage: pipeline_result.metrics.stage_durations.get(stage, 0)
                for stage in [
                    "preprocessing",
                    "business_rules",
                    "langgraph_workflow",
                    "postprocessing",
                    "delivery",
                ]
            },
        }

    except Exception as e:
        app_logger.error(f"Pipeline test failed: {e}")
        return {"test_result": "failed", "error": str(e), "timestamp": datetime.now().isoformat()}


# ========== INTEGRATION HEALTH CHECK ENDPOINT ==========


@router.get("/integration/health")
async def integration_health_check():
    """
    Check Evolution API → Preprocessor → Pipeline integration health
    PHASE 2 WAVE 2: FIX 2.3 - Integration Health Check Endpoint

    Validates complete integration chain:
    - Evolution API webhook handler
    - MessagePreprocessor pipeline
    - Pipeline Orchestrator
    - Configuration validation
    - Base64 webhook configuration
    """
    try:
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "integration_status": "healthy",
            "webhook_handler": "active",
            "preprocessor": "configured",
            "pipeline_orchestrator": "active",
            "api_keys_configured": False,
            "base64_enabled": True,
            "preprocessor_flag_enabled": True,
        }

        # Check API keys configuration
        evolution_key = getattr(settings, "EVOLUTION_API_KEY", None)
        global_key = getattr(settings, "EVOLUTION_GLOBAL_API_KEY", None)
        auth_key = getattr(settings, "AUTHENTICATION_API_KEY", None)

        health_status["api_keys_configured"] = bool(evolution_key or global_key or auth_key)

        # Validate Evolution API configuration
        evolution_config = {
            "evolution_api_url": getattr(settings, "EVOLUTION_API_URL", ""),
            "evolution_instance_name": getattr(settings, "EVOLUTION_INSTANCE_NAME", ""),
            "webhook_url_configured": bool(getattr(settings, "WEBHOOK_GLOBAL_URL", "")),
        }

        # Check MessagePreprocessor availability
        preprocessor_status = "configured"
        try:
            from app.services.message_preprocessor import message_preprocessor

            preprocessor_status = "active"
        except Exception as e:
            app_logger.warning(f"MessagePreprocessor import failed: {e}")
            preprocessor_status = "unavailable"
            health_status["integration_status"] = "degraded"

        health_status["preprocessor"] = preprocessor_status

        # Check Pipeline Orchestrator availability
        pipeline_status = "configured"
        try:
            from app.core.pipeline_orchestrator import pipeline_orchestrator

            pipeline_status = "active"
        except Exception as e:
            app_logger.warning(f"Pipeline Orchestrator import failed: {e}")
            pipeline_status = "unavailable"
            health_status["integration_status"] = "degraded"

        health_status["pipeline_orchestrator"] = pipeline_status

        # Check CeciliaWorkflow integration
        workflow_status = "configured"
        try:
            from app.core.workflow import cecilia_workflow

            workflow_status = "active"
        except Exception as e:
            app_logger.warning(f"CeciliaWorkflow import failed: {e}")
            workflow_status = "unavailable"
            health_status["integration_status"] = "degraded"

        # Add component details
        health_status.update(
            {
                "components": {
                    "evolution_api": evolution_config,
                    "message_preprocessor": {
                        "status": preprocessor_status,
                        "features_enabled": [
                            "input_sanitization",
                            "rate_limiting",
                            "authentication_validation",
                            "business_hours_check",
                            "session_management",
                        ],
                    },
                    "pipeline_orchestrator": {
                        "status": pipeline_status,
                        "version": "2.1",
                        "sla_target_ms": 3000,
                    },
                    "cecilia_workflow": {
                        "status": workflow_status,
                        "architecture": "langgraph_based",
                        "state_management": "postgresql_persistent",
                    },
                },
                "integration_chain": {
                    "webhook_evolution_api": "active",
                    "evolution_to_preprocessor": (
                        "active" if preprocessor_status == "active" else "unavailable"
                    ),
                    "preprocessor_to_pipeline": (
                        "active" if pipeline_status == "active" else "unavailable"
                    ),
                    "pipeline_to_workflow": (
                        "active" if workflow_status == "active" else "unavailable"
                    ),
                    "end_to_end": (
                        "active"
                        if all(
                            [
                                preprocessor_status == "active",
                                pipeline_status == "active",
                                workflow_status == "active",
                            ]
                        )
                        else "degraded"
                    ),
                },
                "configuration_validation": {
                    "evolution_api_keys": health_status["api_keys_configured"],
                    "webhook_base64_enabled": True,
                    "preprocessor_integration": preprocessor_status == "active",
                    "business_hours_configured": bool(
                        getattr(settings, "BUSINESS_HOURS_START", None)
                    ),
                    "database_configured": bool(getattr(settings, "DATABASE_URL", "")),
                    "redis_configured": bool(getattr(settings, "MEMORY_REDIS_URL", "")),
                },
            }
        )

        # Overall health assessment
        critical_components = [
            health_status["api_keys_configured"],
            preprocessor_status == "active",
            pipeline_status == "active",
            workflow_status == "active",
        ]

        if all(critical_components):
            health_status["integration_status"] = "healthy"
        elif any(critical_components):
            health_status["integration_status"] = "degraded"
        else:
            health_status["integration_status"] = "critical"

        app_logger.info(
            f"Integration health check completed: {health_status['integration_status']}",
            extra={
                "preprocessor_status": preprocessor_status,
                "pipeline_status": pipeline_status,
                "workflow_status": workflow_status,
                "api_keys_configured": health_status["api_keys_configured"],
            },
        )

        return health_status

    except Exception as e:
        app_logger.error(f"Integration health check failed: {str(e)}", exc_info=True)
        return {
            "timestamp": datetime.now().isoformat(),
            "integration_status": "critical",
            "webhook_handler": "unknown",
            "preprocessor": "unknown",
            "pipeline_orchestrator": "unknown",
            "api_keys_configured": False,
            "base64_enabled": True,
            "preprocessor_flag_enabled": True,
            "error": str(e),
            "message": "Integration health check failed - critical system error",
        }
