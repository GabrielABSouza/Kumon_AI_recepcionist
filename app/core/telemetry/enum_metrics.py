"""
Enum State Type Violation Telemetry

Tracks and reports violations of the Enum-only state policy:
- state_stage_not_enum: current_stage is not ConversationStage enum
- state_step_not_enum: current_step is not ConversationStep enum
"""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from collections import defaultdict, Counter
import threading
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class StateTypeViolation:
    """State type violation event"""
    session_id: str
    violation_type: str  # "state_stage_not_enum" | "state_step_not_enum"
    field_name: str      # "current_stage" | "current_step"
    actual_type: str     # str(type(value))
    actual_value: str    # str(value)
    module_name: str     # __name__ of the reporting module
    timestamp: str       # ISO timestamp
    stack_hint: Optional[str] = None  # Optional stack trace hint


class EnumMetrics:
    """Thread-safe enum violation metrics collector"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._violations: Dict[str, int] = Counter()
        self._violation_events: list[StateTypeViolation] = []
        self._max_events = 100  # Keep last 100 violations
    
    def record_violation(
        self, 
        session_id: str,
        violation_type: str,
        field_name: str,
        actual_value: Any,
        module_name: str,
        stack_hint: Optional[str] = None
    ) -> None:
        """Record a state type violation"""
        with self._lock:
            # Increment counter
            self._violations[violation_type] += 1
            
            # Create violation event
            violation = StateTypeViolation(
                session_id=session_id,
                violation_type=violation_type,
                field_name=field_name,
                actual_type=str(type(actual_value)),
                actual_value=str(actual_value),
                module_name=module_name,
                timestamp=datetime.now(timezone.utc).isoformat(),
                stack_hint=stack_hint
            )
            
            # Add to events list (keep last N)
            self._violation_events.append(violation)
            if len(self._violation_events) > self._max_events:
                self._violation_events.pop(0)
            
            # Log violation as JSON for structured logging
            logger.warning(
                f"STATE_TYPE_VIOLATION: {violation_type}",
                extra={
                    "event_type": "state_type_violation",
                    "violation_data": asdict(violation)
                }
            )
    
    def get_violation_counts(self) -> Dict[str, int]:
        """Get current violation counts"""
        with self._lock:
            return dict(self._violations)
    
    def get_recent_violations(self, limit: int = 10) -> list[StateTypeViolation]:
        """Get recent violations"""
        with self._lock:
            return self._violation_events[-limit:]
    
    def reset_metrics(self) -> Dict[str, int]:
        """Reset all metrics and return final counts"""
        with self._lock:
            final_counts = dict(self._violations)
            self._violations.clear()
            self._violation_events.clear()
            return final_counts
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        with self._lock:
            return {
                "violation_counts": dict(self._violations),
                "total_violations": sum(self._violations.values()),
                "recent_violations_count": len(self._violation_events),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }


# Global metrics instance
enum_metrics = EnumMetrics()


def record_stage_not_enum(
    session_id: str, 
    actual_value: Any, 
    module_name: str,
    stack_hint: Optional[str] = None
) -> None:
    """Record current_stage not being ConversationStage enum"""
    enum_metrics.record_violation(
        session_id=session_id,
        violation_type="state_stage_not_enum",
        field_name="current_stage",
        actual_value=actual_value,
        module_name=module_name,
        stack_hint=stack_hint
    )


def record_step_not_enum(
    session_id: str,
    actual_value: Any,
    module_name: str,
    stack_hint: Optional[str] = None
) -> None:
    """Record current_step not being ConversationStep enum"""
    enum_metrics.record_violation(
        session_id=session_id,
        violation_type="state_step_not_enum",
        field_name="current_step",
        actual_value=actual_value,
        module_name=module_name,
        stack_hint=stack_hint
    )


def get_metrics_for_dashboard() -> Dict[str, Any]:
    """Get metrics formatted for dashboard/monitoring"""
    return enum_metrics.get_metrics_summary()


def export_violations_jsonl(filepath: str) -> int:
    """Export recent violations to JSONL file for analysis"""
    violations = enum_metrics.get_recent_violations(limit=100)
    
    with open(filepath, 'w') as f:
        for violation in violations:
            f.write(json.dumps(asdict(violation)) + '\n')
    
    logger.info(f"Exported {len(violations)} violations to {filepath}")
    return len(violations)


def validate_zero_violations() -> bool:
    """Validate that no violations occurred (for testing)"""
    counts = enum_metrics.get_violation_counts()
    total = sum(counts.values())
    
    if total > 0:
        logger.error(f"STATE_TYPE_VIOLATIONS detected: {counts}")
        return False
    
    logger.info("✅ Zero state type violations detected")
    return True