"""
Compatibility Layer for Import Migration - Cecília V2

Provides backward compatibility for old import paths while migrating to canonical V2 structure.
Emits deprecation warnings to track usage and guide migration.

CANONICAL PATHS (V2):
- app.core.router.response_planner → ResponsePlanner
- app.core.router.smart_router_adapter → SmartRouterAdapter  
- app.core.router.delivery_io → DeliveryIO
- app.prompts.manager → PromptManager
- app.workflows.contracts → MessageEnvelope, DeliveryResult, IntentResult

Usage:
    # OLD (deprecated):
    from app.services.response_planner import ResponsePlanner
    
    # NEW (canonical):  
    from app.core.router.response_planner import ResponsePlanner
    
    # MIGRATION (temporary):
    from app.core.compat_imports import ResponsePlanner  # with warning
"""

import warnings
import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

def _warn_deprecated_import(old_path: str, new_path: str, symbol: str = None) -> None:
    """Emit deprecation warning for old import path"""
    symbol_info = f" (symbol: {symbol})" if symbol else ""
    warning_msg = f"DEPRECATED IMPORT: '{old_path}'{symbol_info}. Use '{new_path}' instead."
    
    # Emit both warning and log
    warnings.warn(warning_msg, DeprecationWarning, stacklevel=3)
    logger.warning(f"COMPAT_IMPORT_USED: {old_path} → {new_path}")

def _warn_once(cache_key: str, old_path: str, new_path: str, symbol: str = None):
    """Emit warning only once per import path"""
    if not hasattr(_warn_once, '_warned'):
        _warn_once._warned = set()
    
    if cache_key not in _warn_once._warned:
        _warn_deprecated_import(old_path, new_path, symbol)
        _warn_once._warned.add(cache_key)


# ========== RESPONSE PLANNER COMPATIBILITY ==========

# Canonical: app.core.router.response_planner
try:
    from app.core.router.response_planner import (
        ResponsePlanner as _ResponsePlanner,
        response_planner_node as _response_planner_node,
        plan_response as _plan_response,
        render_template as _render_template,
        resolve_channel as _resolve_channel
    )
    
    # Compat exports with warnings
    def ResponsePlanner(*args, **kwargs):
        _warn_once("ResponsePlanner", "app.services.response_planner.ResponsePlanner", 
                  "app.core.router.response_planner.ResponsePlanner", "ResponsePlanner")
        return _ResponsePlanner(*args, **kwargs)
    
    def response_planner_node(state):
        _warn_once("response_planner_node", "app.services.response_planner.response_planner_node",
                  "app.core.router.response_planner.response_planner_node", "response_planner_node")
        return _response_planner_node(state)
        
    def plan_response(state, routing_decision=None):
        _warn_once("plan_response", "app.services.response_planner.plan_response",
                  "app.core.router.response_planner.plan_response", "plan_response")
        return _plan_response(state, routing_decision)
    
    def render_template(template_name, state):
        _warn_once("render_template", "app.services.response_planner.render_template",
                  "app.core.router.response_planner.render_template", "render_template")
        return _render_template(template_name, state)
        
    def resolve_channel(state):
        _warn_once("resolve_channel", "app.services.response_planner.resolve_channel",
                  "app.core.router.response_planner.resolve_channel", "resolve_channel")
        return _resolve_channel(state)

except ImportError as e:
    logger.error(f"Failed to import ResponsePlanner canonical module: {e}")
    ResponsePlanner = None
    response_planner_node = None
    plan_response = None


# ========== SMART ROUTER COMPATIBILITY ==========

# Canonical: app.core.router.smart_router_adapter
try:
    from app.core.router.smart_router_adapter import (
        SmartRouterAdapter as _SmartRouterAdapter,
        smart_router_adapter as _smart_router_adapter,
        CoreRoutingDecision as _CoreRoutingDecision,
        routing_mode_from_decision as _routing_mode_from_decision,
        normalize_rd_obj as _normalize_rd_obj
    )
    
    # Compat exports with warnings
    def SmartRouterAdapter(*args, **kwargs):
        _warn_once("SmartRouterAdapter", "app.services.smart_router_adapter.SmartRouterAdapter",
                  "app.core.router.smart_router_adapter.SmartRouterAdapter", "SmartRouterAdapter")
        return _SmartRouterAdapter(*args, **kwargs)
    
    smart_router_adapter = _smart_router_adapter
    CoreRoutingDecision = _CoreRoutingDecision
    routing_mode_from_decision = _routing_mode_from_decision
    normalize_rd_obj = _normalize_rd_obj

except ImportError as e:
    logger.error(f"Failed to import SmartRouterAdapter canonical module: {e}")
    SmartRouterAdapter = None
    smart_router_adapter = None


# ========== DELIVERY SERVICE COMPATIBILITY ==========

# Canonical: app.core.router.delivery_io (V2)  
try:
    from app.core.router.delivery_io import (
        delivery_node as _delivery_node,
        emit_to_channel as _emit_to_channel
    )
    
    # Compat exports with warnings
    def delivery_node(state, **kwargs):
        _warn_once("delivery_node", "app.core.services.delivery_service.DeliveryService",
                  "app.core.router.delivery_io.delivery_node", "delivery_node")
        return _delivery_node(state, **kwargs)
        
    def emit_to_channel(msg):
        _warn_once("emit_to_channel", "app.core.services.delivery_service.emit_to_channel",
                  "app.core.router.delivery_io.emit_to_channel", "emit_to_channel")
        return _emit_to_channel(msg)
    
    # Legacy class-style interface (if needed)
    class DeliveryService:
        def __init__(self):
            _warn_once("DeliveryService_class", "app.core.services.delivery_service.DeliveryService",
                      "app.core.router.delivery_io.delivery_node", "DeliveryService")
            
        @staticmethod
        def deliver(state, **kwargs):
            return delivery_node(state, **kwargs)

except ImportError as e:
    logger.error(f"Failed to import DeliveryIO canonical module: {e}")
    delivery_node = None
    DeliveryService = None


# ========== PROMPT MANAGER COMPATIBILITY ==========

# Canonical: app.prompts.manager
try:
    from app.prompts.manager import (
        prompt_manager as _prompt_manager,
        PromptManager as _PromptManager
    )
    
    # These are already canonical, so just re-export
    prompt_manager = _prompt_manager
    PromptManager = _PromptManager
    
except ImportError as e:
    logger.error(f"Failed to import PromptManager canonical module: {e}")
    prompt_manager = None
    PromptManager = None


# ========== CONTRACTS COMPATIBILITY ==========

# Canonical: app.workflows.contracts
try:
    from app.workflows.contracts import (
        MessageEnvelope as _MessageEnvelope,
        DeliveryResult as _DeliveryResult,
        IntentResult as _IntentResult,
        RoutingDecision as _RoutingDecision,
        normalize_outbox_messages as _normalize_outbox_messages,
        ensure_outbox as _ensure_outbox
    )
    
    # These are already canonical, so just re-export
    MessageEnvelope = _MessageEnvelope
    DeliveryResult = _DeliveryResult
    IntentResult = _IntentResult
    RoutingDecision = _RoutingDecision
    normalize_outbox_messages = _normalize_outbox_messages
    ensure_outbox = _ensure_outbox
    
except ImportError as e:
    logger.error(f"Failed to import Contracts canonical module: {e}")
    MessageEnvelope = None
    DeliveryResult = None
    IntentResult = None


# ========== FEATURE FLAGS COMPATIBILITY ==========

# Canonical: app.core.feature_flags
try:
    from app.core.feature_flags import (
        feature_flags as _feature_flags,
        FeatureFlagManager as _FeatureFlagManager
    )
    
    # These are already canonical, so just re-export
    feature_flags = _feature_flags
    FeatureFlagManager = _FeatureFlagManager
    
    def get_feature_flags():
        """Canonical API for accessing feature flags"""
        return feature_flags
    
except ImportError as e:
    logger.error(f"Failed to import FeatureFlags canonical module: {e}")
    feature_flags = None
    get_feature_flags = lambda: None


# ========== TEMPLATE VARIABLES COMPATIBILITY ==========

# Canonical: app.prompts.template_variables
try:
    from app.prompts.template_variables import (
        template_variable_resolver as _template_variable_resolver,
        TemplateVariableResolver as _TemplateVariableResolver
    )
    
    # These are already canonical, so just re-export
    template_variable_resolver = _template_variable_resolver
    TemplateVariableResolver = _TemplateVariableResolver
    
except ImportError as e:
    logger.error(f"Failed to import TemplateVariables canonical module: {e}")
    template_variable_resolver = None
    TemplateVariableResolver = None


# ========== WORKFLOW COMPATIBILITY ==========

# Canonical: app.core.workflow_migration (V2)
try:
    from app.core.workflow_migration import (
        get_cecilia_workflow as _get_cecilia_workflow,
    )
    
    # Compat exports with warnings
    def get_cecilia_workflow(*args, **kwargs):
        _warn_once("get_cecilia_workflow", "app.core.workflow.get_cecilia_workflow",
                  "app.core.workflow_migration.get_cecilia_workflow", "get_cecilia_workflow")
        return _get_cecilia_workflow(*args, **kwargs)

except ImportError as e:
    logger.error(f"Failed to import WorkflowMigration canonical module: {e}")
    
    # Fallback to legacy module
    try:
        from app.core.workflow import get_cecilia_workflow as _legacy_get_cecilia_workflow
        
        def get_cecilia_workflow(*args, **kwargs):
            _warn_once("get_cecilia_workflow_legacy", "app.core.workflow.get_cecilia_workflow",
                      "app.core.workflow_migration.get_cecilia_workflow", "get_cecilia_workflow")
            return _legacy_get_cecilia_workflow(*args, **kwargs)
    
    except ImportError as e2:
        logger.error(f"Failed to import legacy workflow module: {e2}")
        get_cecilia_workflow = None


# ========== EXPORTS SUMMARY ==========

__all__ = [
    # Response Planner
    "ResponsePlanner",
    "response_planner_node", 
    "plan_response",
    "render_template",
    "resolve_channel",
    
    # Smart Router
    "SmartRouterAdapter",
    "smart_router_adapter",
    "CoreRoutingDecision",
    "routing_mode_from_decision",
    "normalize_rd_obj",
    
    # Delivery
    "delivery_node",
    "emit_to_channel", 
    "DeliveryService",
    
    # Prompt Manager
    "prompt_manager",
    "PromptManager",
    
    # Contracts
    "MessageEnvelope",
    "DeliveryResult",
    "IntentResult",
    "RoutingDecision",
    "normalize_outbox_messages",
    "ensure_outbox",
    
    # Feature Flags
    "feature_flags",
    "get_feature_flags",
    "FeatureFlagManager",
    
    # Template Variables
    "template_variable_resolver",
    "TemplateVariableResolver",
    
    # Workflow
    "get_cecilia_workflow",
]


# ========== USAGE TRACKING ==========

def get_compat_usage_stats():
    """Get statistics about deprecated import usage"""
    if hasattr(_warn_once, '_warned'):
        return {
            "deprecated_imports_used": list(_warn_once._warned),
            "total_deprecated_count": len(_warn_once._warned)
        }
    return {"deprecated_imports_used": [], "total_deprecated_count": 0}


def reset_compat_warnings():
    """Reset warning cache (for testing)"""
    if hasattr(_warn_once, '_warned'):
        _warn_once._warned.clear()