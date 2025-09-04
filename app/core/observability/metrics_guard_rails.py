"""
Observability and Metrics Guard-Rails System

Implements comprehensive monitoring and alerting for critical system components
as specified in the user requirements.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"  
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class MetricAlert:
    """Represents a metric threshold alert"""
    metric_name: str
    threshold: float
    current_value: float
    severity: AlertSeverity
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "threshold": self.threshold,
            "current_value": self.current_value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context
        }


class MetricsGuardRails:
    """
    Guard-rails system for monitoring critical metrics and generating alerts
    """
    
    def __init__(self):
        self.alerts_raised = 0
        self.metrics_tracked = {}
        
        # Define critical thresholds
        self.thresholds = {
            # Outbox and delivery metrics
            "outbox_empty_rate": {"warning": 0.1, "critical": 0.2},  # >10% empty outbox = warning
            "delivery_failure_rate": {"warning": 0.05, "critical": 0.1},  # >5% failure = warning
            "instance_resolution_failure_rate": {"warning": 0.02, "critical": 0.05},  # >2% = warning
            
            # Template safety metrics  
            "template_fallback_rate": {"warning": 0.05, "critical": 0.15},  # >5% fallback = warning
            "config_template_leaks": {"warning": 0.0, "critical": 0.0},  # ANY leak = critical
            "mustache_token_leaks": {"warning": 0.0, "critical": 0.0},  # ANY leak = critical
            
            # Performance metrics
            "avg_response_time_ms": {"warning": 2000, "critical": 5000},  # >2s = warning  
            "memory_usage_mb": {"warning": 512, "critical": 1024},  # >512MB = warning
            
            # Business continuity
            "conversation_success_rate": {"warning": 0.95, "critical": 0.90},  # <95% success = warning
            "emergency_fallback_rate": {"warning": 0.01, "critical": 0.05},  # >1% emergency = warning
        }
    
    def track_metric(self, metric_name: str, value: float, context: Optional[Dict[str, Any]] = None):
        """Track a metric value and check against thresholds"""
        self.metrics_tracked[metric_name] = {
            "value": value,
            "timestamp": datetime.now(timezone.utc),
            "context": context or {}
        }
        
        # Check thresholds
        self._check_thresholds(metric_name, value, context or {})
    
    def _check_thresholds(self, metric_name: str, value: float, context: Dict[str, Any]):
        """Check metric against defined thresholds and raise alerts"""
        if metric_name not in self.thresholds:
            return
            
        thresholds = self.thresholds[metric_name]
        
        # Check critical threshold
        if "critical" in thresholds:
            if (metric_name.endswith("_rate") and value >= thresholds["critical"]) or \
               (metric_name.endswith("_ms") or metric_name.endswith("_mb")) and value >= thresholds["critical"]:
                self._raise_alert(metric_name, value, thresholds["critical"], 
                                AlertSeverity.CRITICAL, context)
        
        # Check warning threshold  
        if "warning" in thresholds:
            if (metric_name.endswith("_rate") and value >= thresholds["warning"]) or \
               (metric_name.endswith("_ms") or metric_name.endswith("_mb")) and value >= thresholds["warning"]:
                self._raise_alert(metric_name, value, thresholds["warning"], 
                                AlertSeverity.WARNING, context)
    
    def _raise_alert(self, metric_name: str, value: float, threshold: float, 
                    severity: AlertSeverity, context: Dict[str, Any]):
        """Raise an alert for a threshold breach"""
        alert = MetricAlert(
            metric_name=metric_name,
            threshold=threshold,
            current_value=value,
            severity=severity,
            timestamp=datetime.now(timezone.utc),
            context=context
        )
        
        self.alerts_raised += 1
        
        # Log alert based on severity
        if severity == AlertSeverity.CRITICAL:
            logger.critical(f"CRITICAL ALERT: {metric_name}={value} exceeds threshold={threshold}", 
                          extra={"alert": alert.to_dict(), "guard_rail_triggered": True})
        elif severity == AlertSeverity.WARNING:
            logger.warning(f"WARNING ALERT: {metric_name}={value} exceeds threshold={threshold}",
                         extra={"alert": alert.to_dict(), "guard_rail_triggered": True})
        
        # Emit structured log for monitoring systems
        logger.info("guard_rail_alert_triggered", extra={
            "event_type": "guard_rail_alert",
            "metric_name": metric_name,
            "threshold": threshold,
            "current_value": value,
            "severity": severity.value,
            "context": context,
            "alert_id": f"{metric_name}_{self.alerts_raised}"
        })
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        return {
            "tracked_metrics": self.metrics_tracked,
            "alerts_raised_total": self.alerts_raised,
            "thresholds_configured": len(self.thresholds),
            "last_update": datetime.now(timezone.utc).isoformat()
        }


# Global instance
metrics_guard_rails = MetricsGuardRails()


# Convenience functions for common metrics

def track_outbox_metrics(outbox_before: int, outbox_after: int, delivery_success_count: int, 
                        delivery_failure_count: int, context: Optional[Dict[str, Any]] = None):
    """Track outbox and delivery related metrics"""
    
    # Outbox empty rate
    if outbox_before == 0:
        metrics_guard_rails.track_metric("outbox_empty_detected", 1.0, context)
    
    # Delivery metrics
    total_deliveries = delivery_success_count + delivery_failure_count
    if total_deliveries > 0:
        failure_rate = delivery_failure_count / total_deliveries
        metrics_guard_rails.track_metric("delivery_failure_rate", failure_rate, context)


def track_instance_resolution(resolution_success: bool, instance: Optional[str] = None, 
                            context: Optional[Dict[str, Any]] = None):
    """Track instance resolution success/failure"""
    if not resolution_success:
        metrics_guard_rails.track_metric("instance_resolution_failure", 1.0, context)
    
    # Track instance usage
    enhanced_context = (context or {}).copy()
    enhanced_context["resolved_instance"] = instance or "failed"
    
    logger.info("instance_resolution_tracked", extra={
        "success": resolution_success,
        "instance": instance,
        "context": enhanced_context
    })


def track_template_safety(config_blocked: bool, fallback_used: bool, tokens_stripped: bool,
                         template_key: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
    """Track template safety metrics"""
    enhanced_context = (context or {}).copy()
    enhanced_context["template_key"] = template_key or "unknown"
    
    if config_blocked:
        metrics_guard_rails.track_metric("config_template_blocked", 1.0, enhanced_context)
        
    if fallback_used:
        metrics_guard_rails.track_metric("template_fallback_used", 1.0, enhanced_context)
        
    if tokens_stripped:
        metrics_guard_rails.track_metric("dangerous_tokens_stripped", 1.0, enhanced_context)
        
    # Log comprehensive template safety event
    logger.info("template_safety_tracked", extra={
        "config_blocked": config_blocked,
        "fallback_used": fallback_used, 
        "tokens_stripped": tokens_stripped,
        "template_key": template_key,
        "context": enhanced_context,
        "safety_system": "v2"
    })


def track_performance_metrics(response_time_ms: float, memory_usage_mb: float, 
                            context: Optional[Dict[str, Any]] = None):
    """Track system performance metrics"""
    metrics_guard_rails.track_metric("avg_response_time_ms", response_time_ms, context)
    metrics_guard_rails.track_metric("memory_usage_mb", memory_usage_mb, context)


def track_conversation_health(success: bool, stage_reached: str, emergency_fallback_used: bool,
                             context: Optional[Dict[str, Any]] = None):
    """Track overall conversation health metrics"""
    enhanced_context = (context or {}).copy()
    enhanced_context["stage_reached"] = stage_reached
    
    if not success:
        metrics_guard_rails.track_metric("conversation_failure", 1.0, enhanced_context)
        
    if emergency_fallback_used:
        metrics_guard_rails.track_metric("emergency_fallback_used", 1.0, enhanced_context)
        
    # Log conversation outcome
    logger.info("conversation_health_tracked", extra={
        "conversation_success": success,
        "stage_reached": stage_reached,
        "emergency_fallback_used": emergency_fallback_used,
        "context": enhanced_context
    })


# Integration points for existing code

def log_outbox_handoff(planner_count_before: int, planner_count_after: int,
                      delivery_count_before: int, delivery_sent: int, delivery_failed: int,
                      phone_number: str, instance: Optional[str] = None):
    """
    Comprehensive logging for outbox handoff with guard-rails
    
    This should be called at the end of each message processing cycle
    """
    context = {
        "phone_number": phone_number,
        "instance": instance or "unknown",
        "pipeline": "planner_to_delivery"
    }
    
    # Track metrics
    track_outbox_metrics(
        outbox_before=delivery_count_before,
        outbox_after=0,  # Assuming successful delivery clears outbox
        delivery_success_count=delivery_sent,
        delivery_failure_count=delivery_failed,
        context=context
    )
    
    track_instance_resolution(
        resolution_success=(instance is not None and instance != ""),
        instance=instance,
        context=context
    )
    
    # Structured logging for monitoring systems
    logger.info("outbox_handoff_complete", extra={
        "event_type": "outbox_handoff", 
        "planner_outbox_before": planner_count_before,
        "planner_outbox_after": planner_count_after,
        "delivery_outbox_before": delivery_count_before,
        "delivery_sent_count": delivery_sent,
        "delivery_failed_count": delivery_failed,
        "instance_resolved": instance or "failed",
        "phone_number": phone_number,
        "handoff_success": delivery_sent > 0
    })


# Export public interface
__all__ = [
    'MetricsGuardRails',
    'MetricAlert', 
    'AlertSeverity',
    'metrics_guard_rails',
    'track_outbox_metrics',
    'track_instance_resolution',
    'track_template_safety',
    'track_performance_metrics',
    'track_conversation_health',
    'log_outbox_handoff'
]