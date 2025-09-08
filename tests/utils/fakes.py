"""
Fake implementations for testing without external dependencies.
"""
import asyncio
import time
from typing import Any, Dict, List, Optional


class FakeRedis:
    """Simple in-memory Redis fake for testing."""

    def __init__(self):
        self.store: Dict[str, Any] = {}
        self.ttl: Dict[str, float] = {}

    def _expired(self, key: str) -> bool:
        """Check if key has expired."""
        exp = self.ttl.get(key)
        return exp is not None and time.time() > exp

    def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if self._expired(key):
            self.delete(key)
            return None
        val = self.store.get(key)
        return str(val) if val is not None else None

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set key-value with optional expiry."""
        self.store[key] = value
        if ex:
            self.ttl[key] = time.time() + ex
        return True

    def incr(self, key: str) -> int:
        """Increment counter."""
        v = int(self.get(key) or 0) + 1
        self.set(key, v)
        return v

    def decr(self, key: str) -> int:
        """Decrement counter."""
        v = int(self.get(key) or 0) - 1
        self.set(key, v)
        return v

    def expire(self, key: str, seconds: int) -> bool:
        """Set expiry for key."""
        if key in self.store:
            self.ttl[key] = time.time() + seconds
            return True
        return False

    def lpush(self, key: str, value: Any) -> int:
        """Push to list."""
        arr = self.store.setdefault(key, [])
        arr.insert(0, value)
        return len(arr)

    def rpush(self, key: str, value: Any) -> int:
        """Push to end of list."""
        arr = self.store.setdefault(key, [])
        arr.append(value)
        return len(arr)

    def lrange(self, key: str, start: int, end: int) -> List[Any]:
        """Get list range."""
        arr = self.store.get(key, [])
        if end == -1:
            return arr[start:]
        else:
            end = end + 1  # Redis end is inclusive
            return arr[start:end]

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        return key in self.store and not self._expired(key)

    def delete(self, key: str) -> bool:
        """Delete key."""
        existed = key in self.store
        self.store.pop(key, None)
        self.ttl.pop(key, None)
        return existed


class CallRecorder:
    """Utility to record function calls for testing."""

    def __init__(self, delay: float = 0.0, return_value: Any = True):
        self.calls: List[Dict[str, Any]] = []
        self.delay = delay
        self.return_value = return_value

    async def __call__(self, *args, **kwargs):
        """Record call and optionally delay."""
        self.calls.append({"args": args, "kwargs": kwargs, "timestamp": time.time()})
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.return_value

    def reset(self):
        """Clear recorded calls."""
        self.calls = []

    @property
    def call_count(self) -> int:
        """Number of recorded calls."""
        return len(self.calls)

    def was_called_with(self, *args, **kwargs) -> bool:
        """Check if called with specific arguments."""
        for call in self.calls:
            if call["args"] == args and call["kwargs"] == kwargs:
                return True
        return False
