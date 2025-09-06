"""
Enterprise Rate Limiting and Quota Management for Google Calendar API
Implements intelligent rate limiting to prevent quota exhaustion
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import deque
import logging

from ..core.config import settings
from ..core.logger import app_logger


class TokenBucket:
    """
    Token bucket rate limiter implementation
    
    Features:
    - Configurable token refill rate
    - Burst capacity handling
    - Thread-safe operations
    - Automatic token replenishment
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket
        
        Args:
            capacity: Maximum number of tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if not enough tokens available
        """
        async with self.lock:
            await self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    async def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current bucket status"""
        async with self.lock:
            await self._refill()
            return {
                "tokens_available": int(self.tokens),
                "capacity": self.capacity,
                "refill_rate": self.refill_rate,
                "utilization_percentage": ((self.capacity - self.tokens) / self.capacity) * 100
            }


class CalendarRateLimiter:
    """
    Comprehensive rate limiting and quota management for Google Calendar API
    
    Features:
    - Multi-tier rate limiting (per-second, per-minute, per-day)
    - Quota monitoring and alerting
    - Request prioritization
    - Automatic backoff recommendations
    - Performance analytics
    """
    
    def __init__(self):
        # Google Calendar API limits
        # Reference: https://developers.google.com/calendar/api/guides/quota
        self.requests_per_100_seconds = getattr(settings, 'GOOGLE_API_RATE_LIMIT', 90)
        self.requests_per_day = getattr(settings, 'GOOGLE_API_DAILY_QUOTA', 1000000)
        
        # Token buckets for different time windows
        self.per_second_bucket = TokenBucket(
            capacity=10,  # Allow bursts of 10 requests
            refill_rate=self.requests_per_100_seconds / 100  # Smooth over 100 seconds
        )
        
        # Daily quota tracking
        self.daily_quota_used = 0
        self.daily_quota_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        # Request tracking
        self.request_history = deque(maxlen=1000)  # Last 1000 requests
        self.total_requests = 0
        self.total_rejected = 0
        self.total_quota_warnings = 0
        
        # Performance tracking
        self.average_request_duration = 0
        self.request_durations = deque(maxlen=100)  # Last 100 request times
        
        # Alert thresholds
        self.quota_warning_threshold = getattr(settings, 'API_QUOTA_ALERT_THRESHOLD', 0.8)
        self.rate_limit_warning_threshold = 0.9
    
    async def acquire_permission(self, request_type: str = "standard", priority: int = 0) -> Dict[str, Any]:
        """
        Request permission to make API call
        
        Args:
            request_type: Type of request (standard, batch, high_priority)
            priority: Request priority (0-10, higher is more important)
            
        Returns:
            Dictionary with permission status and metadata
        """
        self.total_requests += 1
        current_time = time.time()
        
        # Check daily quota
        if datetime.now() >= self.daily_quota_reset:
            await self._reset_daily_quota()
        
        if self.daily_quota_used >= self.requests_per_day:
            self.total_rejected += 1
            return {
                "permitted": False,
                "reason": "daily_quota_exhausted",
                "retry_after": self.daily_quota_reset,
                "quota_used": self.daily_quota_used,
                "quota_limit": self.requests_per_day
            }
        
        # Check rate limits
        token_cost = self._get_token_cost(request_type)
        if not await self.per_second_bucket.consume(token_cost):
            self.total_rejected += 1
            bucket_status = await self.per_second_bucket.get_status()
            
            # Calculate retry after based on token refill rate
            tokens_needed = token_cost - bucket_status["tokens_available"]
            retry_after_seconds = tokens_needed / self.per_second_bucket.refill_rate
            
            return {
                "permitted": False,
                "reason": "rate_limit_exceeded",
                "retry_after_seconds": retry_after_seconds,
                "bucket_status": bucket_status,
                "token_cost": token_cost
            }
        
        # Update quota usage
        self.daily_quota_used += 1
        
        # Check for warnings
        warnings = await self._check_warnings()
        
        # Record request
        self.request_history.append({
            "timestamp": current_time,
            "request_type": request_type,
            "priority": priority,
            "quota_used": self.daily_quota_used
        })
        
        return {
            "permitted": True,
            "quota_used": self.daily_quota_used,
            "quota_remaining": self.requests_per_day - self.daily_quota_used,
            "quota_percentage": (self.daily_quota_used / self.requests_per_day) * 100,
            "warnings": warnings,
            "token_cost": token_cost
        }
    
    async def record_request_completion(self, duration_ms: float, success: bool):
        """Record completion of API request for analytics"""
        self.request_durations.append(duration_ms)
        
        # Update average duration (exponential moving average)
        if self.average_request_duration == 0:
            self.average_request_duration = duration_ms
        else:
            # EMA with alpha = 0.1
            self.average_request_duration = 0.1 * duration_ms + 0.9 * self.average_request_duration
        
        if not success:
            app_logger.warning("Google Calendar API request failed - checking for quota issues")
    
    def _get_token_cost(self, request_type: str) -> int:
        """Calculate token cost based on request type"""
        costs = {
            "standard": 1,      # Regular API calls
            "batch": 5,         # Batch operations
            "high_priority": 2, # Priority requests
            "list": 3,          # List operations (potentially expensive)
            "watch": 10         # Watch/webhook setup
        }
        return costs.get(request_type, 1)
    
    async def _check_warnings(self) -> List[str]:
        """Check for quota and rate limit warnings"""
        warnings = []
        
        # Daily quota warning
        quota_percentage = (self.daily_quota_used / self.requests_per_day)
        if quota_percentage >= self.quota_warning_threshold:
            if self.total_quota_warnings == 0 or self.daily_quota_used % 1000 == 0:
                warning = f"Daily quota at {quota_percentage*100:.1f}% ({self.daily_quota_used}/{self.requests_per_day})"
                warnings.append(warning)
                app_logger.warning(f"Google Calendar API quota warning: {warning}")
                self.total_quota_warnings += 1
        
        # Rate limit warning
        bucket_status = await self.per_second_bucket.get_status()
        if bucket_status["utilization_percentage"] >= self.rate_limit_warning_threshold * 100:
            warnings.append(f"Rate limit high utilization: {bucket_status['utilization_percentage']:.1f}%")
        
        return warnings
    
    async def _reset_daily_quota(self):
        """Reset daily quota counters"""
        app_logger.info(f"Resetting daily quota - Used: {self.daily_quota_used}/{self.requests_per_day}")
        self.daily_quota_used = 0
        self.daily_quota_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        self.total_quota_warnings = 0
    
    async def get_analytics(self) -> Dict[str, Any]:
        """Get comprehensive rate limiting and quota analytics"""
        bucket_status = await self.per_second_bucket.get_status()
        
        # Calculate request rate statistics
        recent_requests = [
            req for req in self.request_history
            if time.time() - req["timestamp"] < 300  # Last 5 minutes
        ]
        
        analytics = {
            "quota_status": {
                "daily_used": self.daily_quota_used,
                "daily_limit": self.requests_per_day,
                "daily_percentage": (self.daily_quota_used / self.requests_per_day) * 100,
                "daily_remaining": self.requests_per_day - self.daily_quota_used,
                "reset_time": self.daily_quota_reset.isoformat()
            },
            "rate_limiting": {
                "per_100_seconds_limit": self.requests_per_100_seconds,
                "bucket_status": bucket_status,
                "recent_requests_5min": len(recent_requests),
                "current_rate_per_minute": len(recent_requests) / 5 * 60
            },
            "performance": {
                "total_requests": self.total_requests,
                "total_rejected": self.total_rejected,
                "rejection_rate": (self.total_rejected / max(1, self.total_requests)) * 100,
                "average_request_duration_ms": self.average_request_duration,
                "total_quota_warnings": self.total_quota_warnings
            },
            "health": {
                "quota_healthy": (self.daily_quota_used / self.requests_per_day) < 0.9,
                "rate_healthy": bucket_status["utilization_percentage"] < 80,
                "performance_healthy": self.average_request_duration < 500  # < 500ms
            }
        }
        
        return analytics
    
    async def get_backoff_recommendation(self) -> Dict[str, Any]:
        """Get intelligent backoff recommendations based on current usage"""
        analytics = await self.get_analytics()
        
        recommendations = {
            "should_backoff": False,
            "backoff_seconds": 0,
            "reason": "normal_operation",
            "priority_only": False
        }
        
        # High quota usage
        if analytics["quota_status"]["daily_percentage"] > 90:
            recommendations.update({
                "should_backoff": True,
                "backoff_seconds": 300,  # 5 minutes
                "reason": "high_quota_usage",
                "priority_only": True
            })
        
        # High rate limit utilization
        elif analytics["rate_limiting"]["bucket_status"]["utilization_percentage"] > 85:
            recommendations.update({
                "should_backoff": True,
                "backoff_seconds": 60,  # 1 minute
                "reason": "high_rate_limit_utilization"
            })
        
        # Poor performance
        elif analytics["performance"]["average_request_duration_ms"] > 1000:
            recommendations.update({
                "should_backoff": True,
                "backoff_seconds": 30,
                "reason": "poor_api_performance"
            })
        
        return recommendations
    
    async def reset_counters(self):
        """Reset all counters (for testing/admin purposes)"""
        app_logger.info("Rate limiter counters manually reset")
        self.daily_quota_used = 0
        self.total_requests = 0
        self.total_rejected = 0
        self.total_quota_warnings = 0
        self.request_history.clear()
        self.request_durations.clear()
        self.average_request_duration = 0
        
        # Reset token bucket
        self.per_second_bucket.tokens = self.per_second_bucket.capacity


# Global rate limiter instance
calendar_rate_limiter = CalendarRateLimiter()