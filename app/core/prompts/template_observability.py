"""
Template System Observability and Telemetry

Provides comprehensive observability for the template system including metrics,
logging, and performance monitoring for production debugging and optimization.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

from ...core.logger import app_logger


class TemplateOperation(Enum):
    """Types of template operations for tracking"""
    LOAD = "load"
    RENDER = "render"
    VALIDATE = "validate"
    SAFETY_CHECK = "safety_check"
    VARIABLE_FILTER = "variable_filter"
    FALLBACK = "fallback"


class TemplateMetricType(Enum):
    """Types of template metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class TemplateEvent:
    """Template system event for observability"""
    timestamp: datetime
    operation: TemplateOperation
    template_key: Optional[str]
    stage: Optional[str]
    success: bool
    duration_ms: Optional[float]
    metadata: Dict[str, Any]


@dataclass
class TemplateMetrics:
    """Template system metrics snapshot"""
    timestamp: datetime
    
    # Load metrics
    templates_loaded_total: int = 0
    template_load_failures: int = 0
    template_cache_hits: int = 0
    template_cache_misses: int = 0
    
    # Rendering metrics
    templates_rendered_total: int = 0
    template_render_failures: int = 0
    variables_resolved_total: int = 0
    conditionals_processed_total: int = 0
    mustache_converted_total: int = 0
    
    # Safety metrics
    safety_checks_total: int = 0
    safety_blocks_total: int = 0
    fallbacks_used_total: int = 0
    configuration_templates_blocked: int = 0
    
    # Variable policy metrics
    variables_blocked_total: int = 0
    policy_violations_total: int = 0
    
    # Performance metrics
    avg_load_time_ms: float = 0.0
    avg_render_time_ms: float = 0.0
    avg_safety_check_time_ms: float = 0.0
    
    # Quality metrics
    linting_errors_total: int = 0
    linting_warnings_total: int = 0


class TemplateObservability:
    """
    Template system observability and telemetry collector
    """
    
    def __init__(self):
        self.events: List[TemplateEvent] = []
        self.metrics = TemplateMetrics(timestamp=datetime.now())
        self.operation_timers: Dict[str, float] = {}
        self.custom_counters: Dict[str, int] = {}
        
        # Configuration
        self.max_events = 10000  # Keep last N events in memory
        self.metrics_window_minutes = 60  # Rolling window for metrics
    
    def start_operation(self, operation_id: str) -> str:
        """Start timing an operation"""
        self.operation_timers[operation_id] = time.time()
        return operation_id
    
    def end_operation(self, operation_id: str) -> float:
        """End timing an operation and return duration"""
        start_time = self.operation_timers.get(operation_id)
        if start_time:
            duration = (time.time() - start_time) * 1000  # Convert to ms
            del self.operation_timers[operation_id]
            return duration
        return 0.0
    
    def record_event(self, operation: TemplateOperation, template_key: Optional[str] = None,
                    stage: Optional[str] = None, success: bool = True,
                    duration_ms: Optional[float] = None, **metadata) -> None:
        """Record a template system event"""
        
        event = TemplateEvent(
            timestamp=datetime.now(),
            operation=operation,
            template_key=template_key,
            stage=stage,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata
        )
        
        self.events.append(event)
        
        # Trim events if we exceed maximum
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        # Update metrics based on event
        self._update_metrics_from_event(event)
        
        # Log event for structured logging
        self._log_event(event)
    
    def record_template_load(self, template_key: str, success: bool, duration_ms: float,
                           cache_hit: bool = False, **metadata) -> None:
        """Record template load event"""
        
        # Update load metrics
        self.metrics.templates_loaded_total += 1
        if not success:
            self.metrics.template_load_failures += 1
        
        if cache_hit:
            self.metrics.template_cache_hits += 1
        else:
            self.metrics.template_cache_misses += 1
        
        # Update average load time
        self._update_average('avg_load_time_ms', duration_ms, self.metrics.templates_loaded_total)
        
        self.record_event(
            TemplateOperation.LOAD,
            template_key=template_key,
            success=success,
            duration_ms=duration_ms,
            cache_hit=cache_hit,
            **metadata
        )
    
    def record_template_render(self, template_key: str, stage: Optional[str], success: bool,
                             duration_ms: float, variables_resolved: int = 0,
                             conditionals_processed: int = 0, mustache_converted: int = 0,
                             **metadata) -> None:
        """Record template rendering event"""
        
        # Update render metrics
        self.metrics.templates_rendered_total += 1
        if not success:
            self.metrics.template_render_failures += 1
        
        self.metrics.variables_resolved_total += variables_resolved
        self.metrics.conditionals_processed_total += conditionals_processed
        self.metrics.mustache_converted_total += mustache_converted
        
        # Update average render time
        self._update_average('avg_render_time_ms', duration_ms, self.metrics.templates_rendered_total)
        
        self.record_event(
            TemplateOperation.RENDER,
            template_key=template_key,
            stage=stage,
            success=success,
            duration_ms=duration_ms,
            variables_resolved=variables_resolved,
            conditionals_processed=conditionals_processed,
            mustache_converted=mustache_converted,
            **metadata
        )
    
    def record_safety_check(self, template_key: Optional[str], success: bool, duration_ms: float,
                          blocked: bool = False, fallback_used: bool = False,
                          reason: Optional[str] = None, **metadata) -> None:
        """Record safety check event"""
        
        # Update safety metrics
        self.metrics.safety_checks_total += 1
        if blocked:
            self.metrics.safety_blocks_total += 1
        
        if fallback_used:
            self.metrics.fallbacks_used_total += 1
        
        if reason == 'configuration_template_blocked':
            self.metrics.configuration_templates_blocked += 1
        
        # Update average safety check time
        self._update_average('avg_safety_check_time_ms', duration_ms, self.metrics.safety_checks_total)
        
        self.record_event(
            TemplateOperation.SAFETY_CHECK,
            template_key=template_key,
            success=success,
            duration_ms=duration_ms,
            blocked=blocked,
            fallback_used=fallback_used,
            reason=reason,
            **metadata
        )
    
    def record_variable_filtering(self, stage: str, variables_total: int, variables_blocked: int,
                                policy_violations: int = 0, **metadata) -> None:
        """Record variable filtering event"""
        
        # Update variable policy metrics
        self.metrics.variables_blocked_total += variables_blocked
        self.metrics.policy_violations_total += policy_violations
        
        self.record_event(
            TemplateOperation.VARIABLE_FILTER,
            stage=stage,
            success=True,
            variables_total=variables_total,
            variables_blocked=variables_blocked,
            policy_violations=policy_violations,
            **metadata
        )
    
    def record_fallback_usage(self, original_key: str, fallback_key: str, reason: str,
                            stage: Optional[str] = None, **metadata) -> None:
        """Record fallback template usage"""
        
        self.metrics.fallbacks_used_total += 1
        
        self.record_event(
            TemplateOperation.FALLBACK,
            template_key=original_key,
            stage=stage,
            success=True,
            fallback_key=fallback_key,
            reason=reason,
            **metadata
        )
    
    def increment_counter(self, counter_name: str, value: int = 1) -> None:
        """Increment a custom counter"""
        self.custom_counters[counter_name] = self.custom_counters.get(counter_name, 0) + value
    
    def get_current_metrics(self) -> TemplateMetrics:
        """Get current metrics snapshot"""
        # Update timestamp
        self.metrics.timestamp = datetime.now()
        return self.metrics
    
    def get_events_in_window(self, minutes: int = 60) -> List[TemplateEvent]:
        """Get events within a time window"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [event for event in self.events if event.timestamp >= cutoff_time]
    
    def get_error_events(self, minutes: int = 60) -> List[TemplateEvent]:
        """Get error events within a time window"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [event for event in self.events 
               if event.timestamp >= cutoff_time and not event.success]
    
    def get_performance_summary(self, minutes: int = 60) -> Dict[str, Any]:
        """Get performance summary for a time window"""
        events = self.get_events_in_window(minutes)
        
        if not events:
            return {'message': 'No events in time window'}
        
        # Group by operation
        by_operation = {}
        for event in events:
            op = event.operation.value
            if op not in by_operation:
                by_operation[op] = []
            if event.duration_ms is not None:
                by_operation[op].append(event.duration_ms)
        
        # Calculate statistics
        performance = {}
        for operation, durations in by_operation.items():
            if durations:
                performance[operation] = {
                    'count': len(durations),
                    'avg_duration_ms': sum(durations) / len(durations),
                    'min_duration_ms': min(durations),
                    'max_duration_ms': max(durations),
                    'p95_duration_ms': self._percentile(durations, 95)
                }
        
        return {
            'time_window_minutes': minutes,
            'total_events': len(events),
            'performance_by_operation': performance,
            'error_rate': len([e for e in events if not e.success]) / len(events) * 100
        }
    
    def get_template_usage_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """Get template usage statistics"""
        events = self.get_events_in_window(minutes)
        
        # Count by template key
        template_usage = {}
        for event in events:
            if event.template_key:
                key = event.template_key
                if key not in template_usage:
                    template_usage[key] = {'total': 0, 'errors': 0}
                template_usage[key]['total'] += 1
                if not event.success:
                    template_usage[key]['errors'] += 1
        
        # Sort by usage
        sorted_templates = sorted(template_usage.items(), 
                                key=lambda x: x[1]['total'], reverse=True)
        
        return {
            'time_window_minutes': minutes,
            'unique_templates_used': len(template_usage),
            'most_used_templates': dict(sorted_templates[:10]),
            'templates_with_errors': {k: v for k, v in template_usage.items() if v['errors'] > 0}
        }
    
    def log_metrics_summary(self) -> None:
        """Log current metrics summary for observability"""
        metrics = self.get_current_metrics()
        
        app_logger.info("Template System Metrics Summary",
                       extra={
                           'templates_loaded_total': metrics.templates_loaded_total,
                           'templates_rendered_total': metrics.templates_rendered_total,
                           'safety_blocks_total': metrics.safety_blocks_total,
                           'fallbacks_used_total': metrics.fallbacks_used_total,
                           'variables_blocked_total': metrics.variables_blocked_total,
                           'avg_load_time_ms': metrics.avg_load_time_ms,
                           'avg_render_time_ms': metrics.avg_render_time_ms,
                           'custom_counters': self.custom_counters
                       })
    
    def _update_metrics_from_event(self, event: TemplateEvent) -> None:
        """Update metrics based on recorded event"""
        # This is handled by specific record_* methods
        # This method can be extended for additional metric calculations
        pass
    
    def _update_average(self, metric_name: str, new_value: float, count: int) -> None:
        """Update a running average metric"""
        current_avg = getattr(self.metrics, metric_name, 0.0)
        new_avg = ((current_avg * (count - 1)) + new_value) / count
        setattr(self.metrics, metric_name, new_avg)
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values"""
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def _log_event(self, event: TemplateEvent) -> None:
        """Log event for structured logging"""
        log_data = {
            'event_type': 'template_operation',
            'operation': event.operation.value,
            'template_key': event.template_key,
            'stage': event.stage,
            'success': event.success,
            'duration_ms': event.duration_ms,
            **event.metadata
        }
        
        if event.success:
            app_logger.debug(f"Template {event.operation.value}", extra=log_data)
        else:
            app_logger.warning(f"Template {event.operation.value} failed", extra=log_data)
    
    def reset_metrics(self) -> None:
        """Reset all metrics and events"""
        self.events.clear()
        self.metrics = TemplateMetrics(timestamp=datetime.now())
        self.operation_timers.clear()
        self.custom_counters.clear()
    
    def export_metrics(self, format: str = 'json') -> Dict[str, Any]:
        """Export metrics in specified format"""
        data = {
            'metrics': asdict(self.get_current_metrics()),
            'custom_counters': self.custom_counters,
            'performance_summary': self.get_performance_summary(),
            'template_usage': self.get_template_usage_stats()
        }
        
        if format.lower() == 'json':
            return data
        else:
            raise ValueError(f"Unsupported export format: {format}")


# Global observability instance
template_observability = TemplateObservability()


# Convenience functions for common operations
def record_template_load(template_key: str, success: bool, duration_ms: float, **metadata):
    """Convenience function for recording template loads"""
    template_observability.record_template_load(template_key, success, duration_ms, **metadata)


def record_template_render(template_key: str, stage: str, success: bool, duration_ms: float, **metadata):
    """Convenience function for recording template renders"""
    template_observability.record_template_render(template_key, stage, success, duration_ms, **metadata)


def record_safety_check(template_key: str, success: bool, duration_ms: float, **metadata):
    """Convenience function for recording safety checks"""
    template_observability.record_safety_check(template_key, success, duration_ms, **metadata)


def start_operation_timer(operation_id: str) -> str:
    """Convenience function for starting operation timer"""
    return template_observability.start_operation(operation_id)


def end_operation_timer(operation_id: str) -> float:
    """Convenience function for ending operation timer"""
    return template_observability.end_operation(operation_id)


__all__ = [
    'TemplateObservability',
    'TemplateOperation',
    'TemplateEvent', 
    'TemplateMetrics',
    'template_observability',
    'record_template_load',
    'record_template_render',
    'record_safety_check',
    'start_operation_timer',
    'end_operation_timer'
]