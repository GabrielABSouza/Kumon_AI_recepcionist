"""
Core Contracts Package for Kumon Assistant

This package provides all contract definitions for communication between
components, including delivery, outbox, and intent classification contracts.
"""

# Import and re-export from delivery_contracts for backward compatibility
from .delivery_contracts import (
    DeliveryPayload,
    DeliveryResult,
    IntentResult,
    build_intent_result
)

# Import and re-export from outbox for the new outbox system
from .outbox import (
    OutboxItem,
    enqueue_to_outbox,
    rehydrate_outbox_if_needed,
    ensure_outbox
)

# Make all symbols available at package level for backward compatibility
__all__ = [
    # Delivery contracts
    "DeliveryPayload",
    "DeliveryResult", 
    "IntentResult",
    "build_intent_result",
    
    # Outbox contracts
    "OutboxItem",
    "enqueue_to_outbox",
    "rehydrate_outbox_if_needed",
    "ensure_outbox"
]