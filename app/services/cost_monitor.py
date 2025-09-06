"""
LLM Cost Monitor & Budget Enforcement Service
Real-time cost tracking with daily budget enforcement (R$ 5.00/day target)
"""

import asyncio
import time
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

from ..core.config import settings
from ..core.logger import app_logger
from ..services.enhanced_cache_service import enhanced_cache_service


class AlertLevel(Enum):
    """Cost alert severity levels"""
    INFO = "info"
    WARNING = "warning"  # 80% of budget
    CRITICAL = "critical"  # 90% of budget
    EMERGENCY = "emergency"  # 100% of budget


@dataclass
class CostEntry:
    """Individual cost tracking entry"""
    timestamp: float
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_brl: float
    request_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = field(default_factory=dict)


@dataclass
class DailyBudget:
    """Daily budget configuration and tracking"""
    date: str  # YYYY-MM-DD format
    budget_brl: float
    spent_brl: float = 0.0
    request_count: int = 0
    provider_costs: Dict[str, float] = field(default_factory=dict)
    alert_level: AlertLevel = AlertLevel.INFO
    entries: List[CostEntry] = field(default_factory=list)
    
    @property
    def remaining_budget(self) -> float:
        """Remaining budget in BRL"""
        return max(0, self.budget_brl - self.spent_brl)
    
    @property
    def usage_percentage(self) -> float:
        """Budget usage percentage"""
        return (self.spent_brl / self.budget_brl * 100) if self.budget_brl > 0 else 0
    
    @property
    def is_over_budget(self) -> bool:
        """Check if over budget"""
        return self.spent_brl >= self.budget_brl


class CostMonitor:
    """
    Real-time LLM cost monitoring with budget enforcement
    
    Features:
    - Daily budget tracking (R$ 5.00 target)
    - Provider-specific cost breakdown
    - Real-time alerts at 80%, 90%, 100% thresholds
    - Request blocking when over budget
    - Persistent storage with Redis caching
    """
    
    def __init__(self, daily_budget_brl: float = 5.00):
        self.daily_budget_brl = daily_budget_brl
        self.current_budget: Optional[DailyBudget] = None
        self.alert_callbacks: List[callable] = []
        
        # Secure cache key generation
        self._cache_salt = secrets.token_hex(16)
        self.budget_cache_key = self._generate_secure_cache_key("daily_budget")
        self.history_cache_key = self._generate_secure_cache_key("history")
        
        app_logger.info("Cost monitor initialized", extra={
            "daily_budget_brl": daily_budget_brl,
            "timezone": "America/Sao_Paulo"
        })
    
    async def initialize(self):
        """Initialize cost monitor with cached data"""
        await self._load_current_budget()
        
        # Clean up old entries (keep only 7 days)
        await self._cleanup_old_entries()
        
        app_logger.info("Cost monitor ready", extra={
            "current_date": self._get_today_str(),
            "budget_brl": self.daily_budget_brl,
            "current_spent": self.current_budget.spent_brl if self.current_budget else 0
        })
    
    async def track_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_brl: float,
        request_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Track LLM usage and update budget
        
        Returns:
            Dict with tracking result and budget status
        """
        # Ensure current budget exists
        if not self.current_budget or self.current_budget.date != self._get_today_str():
            await self._create_daily_budget()
        
        # Create cost entry
        entry = CostEntry(
            timestamp=time.time(),
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_brl=cost_brl,
            request_id=request_id,
            context=context or {}
        )
        
        # Update budget
        self.current_budget.spent_brl += cost_brl
        self.current_budget.request_count += 1
        self.current_budget.entries.append(entry)
        
        # Update provider-specific costs
        if provider not in self.current_budget.provider_costs:
            self.current_budget.provider_costs[provider] = 0.0
        self.current_budget.provider_costs[provider] += cost_brl
        
        # Check alert thresholds
        previous_alert = self.current_budget.alert_level
        self.current_budget.alert_level = self._determine_alert_level()
        
        # Save updated budget
        await self._save_current_budget()
        
        # Trigger alerts if threshold crossed
        if self.current_budget.alert_level.value != previous_alert.value:
            await self._trigger_alert(self.current_budget.alert_level)
        
        # Log usage
        app_logger.info("LLM usage tracked", extra={
            "provider": provider,
            "model": model,
            "cost_brl": cost_brl,
            "daily_spent": self.current_budget.spent_brl,
            "budget_remaining": self.current_budget.remaining_budget,
            "usage_percentage": self.current_budget.usage_percentage,
            "alert_level": self.current_budget.alert_level.value,
            "request_id": request_id
        })
        
        return {
            "success": True,
            "cost_tracked": cost_brl,
            "daily_spent": self.current_budget.spent_brl,
            "remaining_budget": self.current_budget.remaining_budget,
            "usage_percentage": self.current_budget.usage_percentage,
            "alert_level": self.current_budget.alert_level.value,
            "over_budget": self.current_budget.is_over_budget
        }
    
    async def check_budget_allowance(self, estimated_cost_brl: float) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed within budget constraints
        
        Returns:
            (allowed: bool, status: dict)
        """
        # Ensure current budget exists
        if not self.current_budget or self.current_budget.date != self._get_today_str():
            await self._create_daily_budget()
        
        projected_spent = self.current_budget.spent_brl + estimated_cost_brl
        would_exceed = projected_spent > self.daily_budget_brl
        
        status = {
            "current_spent": self.current_budget.spent_brl,
            "estimated_cost": estimated_cost_brl,
            "projected_spent": projected_spent,
            "daily_budget": self.daily_budget_brl,
            "would_exceed_budget": would_exceed,
            "usage_percentage": self.current_budget.usage_percentage,
            "remaining_budget": self.current_budget.remaining_budget
        }
        
        if would_exceed:
            app_logger.warning("Budget allowance check failed", extra={
                **status,
                "action": "request_blocked"
            })
            
            return False, status
        
        return True, status
    
    def _determine_alert_level(self) -> AlertLevel:
        """Determine current alert level based on usage"""
        percentage = self.current_budget.usage_percentage
        
        if percentage >= 100:
            return AlertLevel.EMERGENCY
        elif percentage >= 90:
            return AlertLevel.CRITICAL
        elif percentage >= 80:
            return AlertLevel.WARNING
        else:
            return AlertLevel.INFO
    
    async def _trigger_alert(self, alert_level: AlertLevel):
        """Trigger alert for budget threshold"""
        alert_data = {
            "alert_level": alert_level.value,
            "date": self.current_budget.date,
            "spent_brl": self.current_budget.spent_brl,
            "budget_brl": self.daily_budget_brl,
            "usage_percentage": self.current_budget.usage_percentage,
            "remaining_budget": self.current_budget.remaining_budget,
            "request_count": self.current_budget.request_count,
            "provider_breakdown": self.current_budget.provider_costs
        }
        
        app_logger.warning(f"Budget alert triggered: {alert_level.value.upper()}", extra=alert_data)
        
        # Execute alert callbacks
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert_level, alert_data)
                else:
                    callback(alert_level, alert_data)
            except Exception as e:
                app_logger.error(f"Alert callback error: {e}")
    
    def add_alert_callback(self, callback: callable):
        """Add callback for budget alerts"""
        self.alert_callbacks.append(callback)
    
    async def get_daily_summary(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get daily cost summary"""
        target_date = date or self._get_today_str()
        
        if self.current_budget and self.current_budget.date == target_date:
            budget = self.current_budget
        else:
            budget = await self._load_budget_for_date(target_date)
        
        if not budget:
            return {
                "date": target_date,
                "budget_brl": self.daily_budget_brl,
                "spent_brl": 0.0,
                "usage_percentage": 0.0,
                "request_count": 0,
                "provider_costs": {},
                "alert_level": "info"
            }
        
        return {
            "date": budget.date,
            "budget_brl": budget.budget_brl,
            "spent_brl": budget.spent_brl,
            "remaining_budget": budget.remaining_budget,
            "usage_percentage": budget.usage_percentage,
            "request_count": budget.request_count,
            "provider_costs": budget.provider_costs,
            "alert_level": budget.alert_level.value,
            "entries_count": len(budget.entries)
        }
    
    async def get_weekly_summary(self) -> Dict[str, Any]:
        """Get weekly cost summary (last 7 days)"""
        today = datetime.now(timezone.utc)
        weekly_data = {}
        total_cost = 0.0
        total_requests = 0
        
        for i in range(7):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_summary = await self.get_daily_summary(date)
            weekly_data[date] = daily_summary
            total_cost += daily_summary["spent_brl"]
            total_requests += daily_summary["request_count"]
        
        return {
            "week_period": f"{(today - timedelta(days=6)).strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}",
            "total_cost_brl": total_cost,
            "total_requests": total_requests,
            "daily_average_cost": total_cost / 7,
            "weekly_budget": self.daily_budget_brl * 7,
            "weekly_usage_percentage": (total_cost / (self.daily_budget_brl * 7)) * 100,
            "daily_breakdown": weekly_data
        }
    
    async def _create_daily_budget(self):
        """Create new daily budget for today"""
        today = self._get_today_str()
        self.current_budget = DailyBudget(
            date=today,
            budget_brl=self.daily_budget_brl
        )
        await self._save_current_budget()
        
        app_logger.info("New daily budget created", extra={
            "date": today,
            "budget_brl": self.daily_budget_brl
        })
    
    async def _load_current_budget(self):
        """Load current day's budget from cache"""
        today = self._get_today_str()
        self.current_budget = await self._load_budget_for_date(today)
        
        if not self.current_budget:
            await self._create_daily_budget()
    
    def _generate_secure_cache_key(self, key_type: str, identifier: str = "") -> str:
        """Generate cryptographically secure cache key"""
        base_string = f"llm_cost_monitor:{key_type}:{identifier}:{self._cache_salt}"
        return hashlib.sha256(base_string.encode()).hexdigest()[:32]
    
    async def _load_budget_for_date(self, date: str) -> Optional[DailyBudget]:
        """Load budget for specific date"""
        cache_key = self._generate_secure_cache_key("daily_budget", date)
        
        try:
            cached_data = await enhanced_cache_service.get(
                cache_key,
                category="budget"
            )
            
            if cached_data:
                # Reconstruct budget from cached data
                budget_data = json.loads(cached_data)
                
                # Reconstruct entries
                entries = []
                for entry_data in budget_data.get("entries", []):
                    entry = CostEntry(**entry_data)
                    entries.append(entry)
                
                budget = DailyBudget(
                    date=budget_data["date"],
                    budget_brl=budget_data["budget_brl"],
                    spent_brl=budget_data["spent_brl"],
                    request_count=budget_data["request_count"],
                    provider_costs=budget_data.get("provider_costs", {}),
                    alert_level=AlertLevel(budget_data.get("alert_level", "info")),
                    entries=entries
                )
                
                return budget
                
        except Exception as e:
            app_logger.error(f"Error loading budget for {date}: {e}")
        
        return None
    
    async def _save_current_budget(self):
        """Save current budget to cache"""
        if not self.current_budget:
            return
        
        cache_key = self._generate_secure_cache_key("daily_budget", self.current_budget.date)
        
        try:
            # Serialize budget data
            budget_data = {
                "date": self.current_budget.date,
                "budget_brl": self.current_budget.budget_brl,
                "spent_brl": self.current_budget.spent_brl,
                "request_count": self.current_budget.request_count,
                "provider_costs": self.current_budget.provider_costs,
                "alert_level": self.current_budget.alert_level.value,
                "entries": [
                    {
                        "timestamp": entry.timestamp,
                        "provider": entry.provider,
                        "model": entry.model,
                        "input_tokens": entry.input_tokens,
                        "output_tokens": entry.output_tokens,
                        "cost_brl": entry.cost_brl,
                        "request_id": entry.request_id,
                        "context": entry.context
                    }
                    for entry in self.current_budget.entries
                ]
            }
            
            await enhanced_cache_service.set(
                cache_key,
                json.dumps(budget_data),
                ttl=86400,  # 24 hours
                category="budget"
            )
            
        except Exception as e:
            app_logger.error(f"Error saving budget: {e}")
    
    async def _cleanup_old_entries(self):
        """Clean up entries older than 7 days"""
        try:
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
            
            # This would typically involve database cleanup
            # For now, we rely on Redis TTL for automatic cleanup
            
            app_logger.info("Old entries cleanup completed", extra={
                "cutoff_date": cutoff_date
            })
            
        except Exception as e:
            app_logger.error(f"Error during cleanup: {e}")
    
    def _get_today_str(self) -> str:
        """Get today's date string in São Paulo timezone"""
        # Convert to São Paulo timezone for business context
        sp_tz = timezone(timedelta(hours=-3))  # UTC-3 (São Paulo)
        now = datetime.now(sp_tz)
        return now.strftime("%Y-%m-%d")


# Global cost monitor instance
cost_monitor = CostMonitor(daily_budget_brl=5.00)


async def initialize_cost_monitor():
    """Initialize global cost monitor"""
    await cost_monitor.initialize()


async def simple_budget_alert_callback(alert_level: AlertLevel, alert_data: Dict[str, Any]):
    """Simple alert callback that logs to system"""
    if alert_level == AlertLevel.EMERGENCY:
        app_logger.critical("BUDGET EXCEEDED - LLM requests may be blocked", extra=alert_data)
    elif alert_level == AlertLevel.CRITICAL:
        app_logger.error("Budget at 90% - immediate action required", extra=alert_data)
    elif alert_level == AlertLevel.WARNING:
        app_logger.warning("Budget at 80% - monitor usage closely", extra=alert_data)


# Register default alert callback
cost_monitor.add_alert_callback(simple_budget_alert_callback)