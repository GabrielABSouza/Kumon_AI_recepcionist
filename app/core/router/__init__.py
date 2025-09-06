"""
Core Router Module

Bridge between core routing system and modular workflow components.
"""

from .smart_router_adapter import smart_router_adapter, SmartRouterAdapter, CoreRoutingDecision

__all__ = ["smart_router_adapter", "SmartRouterAdapter", "CoreRoutingDecision"]