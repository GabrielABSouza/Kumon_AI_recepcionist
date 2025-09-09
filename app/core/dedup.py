"""
Minimal Turn Controller with in-memory deduplication.
No Redis, no persistence - just simple message_id tracking with TTL.
"""
import time
from typing import Dict


class TurnController:
    """Simple in-memory turn controller with TTL."""

    def __init__(self, ttl_seconds: int = 60):
        self._turns: Dict[str, Dict] = {}
        self._ttl = ttl_seconds

    def _cleanup_expired(self):
        """Remove expired turns from memory."""
        now = time.time()
        expired = [
            mid
            for mid, data in self._turns.items()
            if now - data.get("started_at", 0) > self._ttl
        ]
        for mid in expired:
            self._turns.pop(mid, None)

    def start_turn(self, message_id: str) -> bool:
        """
        Start a new turn if not already started.
        Returns True if turn started, False if already exists or already processed.
        """
        self._cleanup_expired()

        # Block if message already exists (either processing or already replied)
        if message_id in self._turns:
            return False

        self._turns[message_id] = {"replied": False, "started_at": time.time()}
        return True

    def has_replied(self, message_id: str) -> bool:
        """Check if we already replied to this message."""
        return self._turns.get(message_id, {}).get("replied", False)

    def mark_replied(self, message_id: str):
        """Mark that we sent a reply for this message."""
        if message_id in self._turns:
            self._turns[message_id]["replied"] = True

    def end_turn(self, message_id: str):
        """
        End turn but keep the record for deduplication.
        The record will be cleaned up by TTL, not immediately removed.
        """
        # Don't remove the record - let TTL handle cleanup
        # This ensures duplicate messages are blocked even after processing
        if message_id in self._turns:
            # Mark processing as complete but keep record for deduplication
            self._turns[message_id]["ended_at"] = time.time()


# Global instance for simplicity
turn_controller = TurnController(ttl_seconds=60)
