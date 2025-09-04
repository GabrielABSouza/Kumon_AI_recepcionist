# app/services/response_planner.py
"""
ResponsePlanner Compatibility Shim

Re-exports ResponsePlanner functionality from the canonical location
to maintain compatibility with legacy imports.

Canonical location: app/core/router/response_planner.py
"""

# Import from canonical location
from ..core.router.response_planner import (
    plan_response,
    response_planner_node,
    ResponsePlanner,
    plan
)

# Re-export for compatibility
__all__ = [
    "plan_response",
    "response_planner_node", 
    "ResponsePlanner",
    "plan"
]

# Legacy aliases for backward compatibility
response_planner = ResponsePlanner()  # Instance for legacy code that expects instance