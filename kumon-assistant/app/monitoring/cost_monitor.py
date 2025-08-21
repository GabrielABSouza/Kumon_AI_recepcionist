"""
OpenAI Cost Monitoring System
Phase 3 - Day 7: Real-time cost tracking with R$4/day alerts
Compliance: Daily budget R$5, Alert threshold R$4
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone, date
from dataclasses import dataclass
from enum import Enum
import asyncio
import redis
import asyncpg
import json
from decimal import Decimal, ROUND_HALF_UP

from app.core.config import settings
from app.core.logger import app_logger as logger


class CostAlertLevel(str, Enum):
    INFO = "info"           # 50% of budget
    WARNING = "warning"     # 75% of budget
    CRITICAL = "critical"   # 80% of budget (R$4/day)
    EMERGENCY = "emergency" # 100% of budget (R$5/day)


@dataclass
class CostAlert:
    level: CostAlertLevel
    message: str
    current_cost: float
    budget_remaining: float
    percentage_used: float
    timestamp: datetime
    action_required: bool
    estimated_daily_total: float


@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    cost_brl: float
    timestamp: datetime
    request_id: Optional[str] = None


class OpenAICostTracker:
    """Real-time OpenAI cost tracking with budget enforcement"""
    
    # OpenAI pricing per 1k tokens (in USD, converted to BRL)
    MODEL_PRICING = {
        "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
        "text-embedding-ada-002": {"input": 0.0001, "output": 0.0}
    }
    
    # USD to BRL conversion rate (should be updated regularly)
    USD_TO_BRL = 5.0  # Approximate rate
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.db_pool = None
        self.daily_budget_brl = settings.LLM_DAILY_BUDGET_BRL
        self.alert_threshold_brl = settings.LLM_COST_ALERT_THRESHOLD_BRL
        self.circuit_breaker_active = False
        
    async def initialize(self):
        """Initialize database connections"""
        try:
            # Initialize PostgreSQL connection for cost tracking
            if settings.MEMORY_POSTGRES_URL:
                self.db_pool = await asyncpg.create_pool(
                    settings.MEMORY_POSTGRES_URL,
                    min_size=2,
                    max_size=5,
                    command_timeout=10
                )
            
            # Initialize Redis connection if not provided
            if not self.redis_client and settings.MEMORY_REDIS_URL:
                self.redis_client = redis.from_url(settings.MEMORY_REDIS_URL)
            
            # Create cost tracking table if not exists
            if self.db_pool:
                await self._create_cost_tracking_table()
            
            logger.info("OpenAI cost tracker initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize cost tracker: {e}")
            raise
    
    async def _create_cost_tracking_table(self):
        """Create cost tracking table if not exists"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS llm_cost_tracking (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL,
                        model VARCHAR(100) NOT NULL,
                        prompt_tokens INTEGER NOT NULL,
                        completion_tokens INTEGER NOT NULL,
                        total_tokens INTEGER NOT NULL,
                        cost_usd DECIMAL(10, 6) NOT NULL,
                        cost_brl DECIMAL(10, 4) NOT NULL,
                        request_id VARCHAR(255),
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        INDEX (date, model),
                        INDEX (timestamp)
                    )
                """)
                
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS cost_alerts (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL,
                        alert_level VARCHAR(20) NOT NULL,
                        message TEXT NOT NULL,
                        current_cost DECIMAL(10, 4) NOT NULL,
                        budget_remaining DECIMAL(10, 4) NOT NULL,
                        percentage_used DECIMAL(5, 2) NOT NULL,
                        estimated_daily_total DECIMAL(10, 4) NOT NULL,
                        action_taken TEXT,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        INDEX (date, alert_level),
                        INDEX (timestamp)
                    )
                """)
                
        except Exception as e:
            logger.error(f"Failed to create cost tracking tables: {e}")
            raise
    
    async def track_usage(self, usage: TokenUsage) -> Tuple[bool, Optional[CostAlert]]:
        """
        Track token usage and return (continue_allowed, alert)
        
        Returns:
        - continue_allowed: Whether to continue processing (budget check)
        - alert: Cost alert if threshold exceeded
        """
        try:
            # Calculate cost
            cost_usd = self._calculate_cost_usd(usage)
            cost_brl = cost_usd * self.USD_TO_BRL
            
            # Store usage
            await self._store_usage(usage, cost_usd, cost_brl)
            
            # Get daily total
            daily_total = await self._get_daily_total()
            
            # Check budget and generate alerts
            alert = await self._check_budget_alerts(daily_total)
            
            # Update circuit breaker
            continue_allowed = daily_total < self.daily_budget_brl
            if not continue_allowed:
                self.circuit_breaker_active = True
                logger.warning(f"Cost circuit breaker activated: daily total R${daily_total:.2f} exceeds budget R${self.daily_budget_brl:.2f}")
            
            # Update real-time metrics
            await self._update_realtime_metrics(daily_total, cost_brl)
            
            return continue_allowed, alert
            
        except Exception as e:
            logger.error(f"Failed to track usage: {e}")
            # Allow processing to continue on tracking errors
            return True, None
    
    def _calculate_cost_usd(self, usage: TokenUsage) -> float:
        """Calculate cost in USD based on token usage"""
        model_pricing = self.MODEL_PRICING.get(usage.model.lower())
        if not model_pricing:
            # Fallback to gpt-3.5-turbo pricing for unknown models
            model_pricing = self.MODEL_PRICING["gpt-3.5-turbo"]
            logger.warning(f"Unknown model {usage.model}, using gpt-3.5-turbo pricing")
        
        # Calculate cost per 1k tokens
        input_cost = (usage.prompt_tokens / 1000) * model_pricing["input"]
        output_cost = (usage.completion_tokens / 1000) * model_pricing["output"]
        
        return input_cost + output_cost
    
    async def _store_usage(self, usage: TokenUsage, cost_usd: float, cost_brl: float):
        """Store usage data in database and cache"""
        try:
            today = datetime.now(timezone.utc).date()
            
            # Store in PostgreSQL
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO llm_cost_tracking 
                        (date, model, prompt_tokens, completion_tokens, total_tokens, 
                         cost_usd, cost_brl, request_id, timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """, today, usage.model, usage.prompt_tokens, usage.completion_tokens,
                    usage.total_tokens, cost_usd, cost_brl, usage.request_id, usage.timestamp)
            
            # Update Redis cache for real-time access
            if self.redis_client:
                # Update daily total
                daily_key = f"cost:daily:{today.isoformat()}"
                await asyncio.to_thread(
                    self.redis_client.incrbyfloat, daily_key, cost_brl
                )
                await asyncio.to_thread(
                    self.redis_client.expire, daily_key, 86400 * 2  # 2 days
                )
                
                # Update hourly breakdown
                hour = usage.timestamp.hour
                hourly_key = f"cost:hourly:{today.isoformat()}:{hour:02d}"
                await asyncio.to_thread(
                    self.redis_client.incrbyfloat, hourly_key, cost_brl
                )
                await asyncio.to_thread(
                    self.redis_client.expire, hourly_key, 86400
                )
                
                # Update model-specific costs
                model_key = f"cost:model:{today.isoformat()}:{usage.model}"
                await asyncio.to_thread(
                    self.redis_client.incrbyfloat, model_key, cost_brl
                )
                await asyncio.to_thread(
                    self.redis_client.expire, model_key, 86400
                )
                
        except Exception as e:
            logger.error(f"Failed to store usage data: {e}")
    
    async def _get_daily_total(self) -> float:
        """Get current daily cost total"""
        try:
            today = datetime.now(timezone.utc).date()
            
            # Try Redis first for real-time data
            if self.redis_client:
                daily_key = f"cost:daily:{today.isoformat()}"
                cached_total = await asyncio.to_thread(
                    self.redis_client.get, daily_key
                )
                if cached_total:
                    return float(cached_total)
            
            # Fallback to database
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    total = await conn.fetchval("""
                        SELECT COALESCE(SUM(cost_brl), 0) 
                        FROM llm_cost_tracking 
                        WHERE date = $1
                    """, today)
                    return float(total or 0.0)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to get daily total: {e}")
            return 0.0
    
    async def _check_budget_alerts(self, daily_total: float) -> Optional[CostAlert]:
        """Check if budget thresholds are exceeded and generate alerts"""
        try:
            percentage_used = (daily_total / self.daily_budget_brl) * 100
            budget_remaining = self.daily_budget_brl - daily_total
            
            # Estimate daily total based on current usage and time of day
            now = datetime.now(timezone.utc)
            hours_elapsed = now.hour + now.minute / 60.0
            if hours_elapsed > 0:
                estimated_daily_total = daily_total * (24 / hours_elapsed)
            else:
                estimated_daily_total = daily_total
            
            alert = None
            
            # Check alert thresholds
            if daily_total >= self.daily_budget_brl:
                alert = CostAlert(
                    level=CostAlertLevel.EMERGENCY,
                    message=f"EMERGENCY: Daily budget exceeded! Current: R${daily_total:.2f}, Budget: R${self.daily_budget_brl:.2f}",
                    current_cost=daily_total,
                    budget_remaining=budget_remaining,
                    percentage_used=percentage_used,
                    timestamp=now,
                    action_required=True,
                    estimated_daily_total=estimated_daily_total
                )
            elif daily_total >= self.alert_threshold_brl:
                alert = CostAlert(
                    level=CostAlertLevel.CRITICAL,
                    message=f"CRITICAL: Cost alert threshold reached! Current: R${daily_total:.2f}, Threshold: R${self.alert_threshold_brl:.2f}",
                    current_cost=daily_total,
                    budget_remaining=budget_remaining,
                    percentage_used=percentage_used,
                    timestamp=now,
                    action_required=True,
                    estimated_daily_total=estimated_daily_total
                )
            elif percentage_used >= 75:
                alert = CostAlert(
                    level=CostAlertLevel.WARNING,
                    message=f"WARNING: 75% of daily budget used. Current: R${daily_total:.2f} ({percentage_used:.1f}%)",
                    current_cost=daily_total,
                    budget_remaining=budget_remaining,
                    percentage_used=percentage_used,
                    timestamp=now,
                    action_required=False,
                    estimated_daily_total=estimated_daily_total
                )
            elif percentage_used >= 50:
                alert = CostAlert(
                    level=CostAlertLevel.INFO,
                    message=f"INFO: 50% of daily budget used. Current: R${daily_total:.2f} ({percentage_used:.1f}%)",
                    current_cost=daily_total,
                    budget_remaining=budget_remaining,
                    percentage_used=percentage_used,
                    timestamp=now,
                    action_required=False,
                    estimated_daily_total=estimated_daily_total
                )
            
            # Store alert if generated
            if alert:
                await self._store_alert(alert)
            
            return alert
            
        except Exception as e:
            logger.error(f"Failed to check budget alerts: {e}")
            return None
    
    async def _store_alert(self, alert: CostAlert):
        """Store cost alert in database"""
        try:
            if self.db_pool:
                today = datetime.now(timezone.utc).date()
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO cost_alerts 
                        (date, alert_level, message, current_cost, budget_remaining, 
                         percentage_used, estimated_daily_total, timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, today, alert.level.value, alert.message, alert.current_cost,
                    alert.budget_remaining, alert.percentage_used, alert.estimated_daily_total, alert.timestamp)
            
            # Log alert
            if alert.level in [CostAlertLevel.CRITICAL, CostAlertLevel.EMERGENCY]:
                logger.error(f"Cost alert: {alert.message}")
            elif alert.level == CostAlertLevel.WARNING:
                logger.warning(f"Cost alert: {alert.message}")
            else:
                logger.info(f"Cost alert: {alert.message}")
                
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")
    
    async def _update_realtime_metrics(self, daily_total: float, last_cost: float):
        """Update real-time metrics in Redis"""
        try:
            if self.redis_client:
                now = datetime.now(timezone.utc)
                
                # Update current metrics
                metrics = {
                    "daily_total": daily_total,
                    "budget_remaining": self.daily_budget_brl - daily_total,
                    "percentage_used": (daily_total / self.daily_budget_brl) * 100,
                    "last_request_cost": last_cost,
                    "circuit_breaker_active": self.circuit_breaker_active,
                    "last_updated": now.isoformat()
                }
                
                await asyncio.to_thread(
                    self.redis_client.hset, "cost:realtime", mapping=metrics
                )
                await asyncio.to_thread(
                    self.redis_client.expire, "cost:realtime", 86400
                )
                
        except Exception as e:
            logger.error(f"Failed to update realtime metrics: {e}")
    
    async def get_cost_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get cost summary for specified number of days"""
        try:
            if not self.db_pool:
                return {}
            
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days)
            
            async with self.db_pool.acquire() as conn:
                # Daily costs
                daily_costs = await conn.fetch("""
                    SELECT date, SUM(cost_brl) as total_cost
                    FROM llm_cost_tracking
                    WHERE date >= $1 AND date <= $2
                    GROUP BY date
                    ORDER BY date DESC
                """, start_date, end_date)
                
                # Model breakdown for today
                model_breakdown = await conn.fetch("""
                    SELECT model, SUM(cost_brl) as cost, COUNT(*) as requests
                    FROM llm_cost_tracking
                    WHERE date = $1
                    GROUP BY model
                    ORDER BY cost DESC
                """, end_date)
                
                # Hourly pattern for today
                hourly_pattern = await conn.fetch("""
                    SELECT EXTRACT(HOUR FROM timestamp) as hour, SUM(cost_brl) as cost
                    FROM llm_cost_tracking
                    WHERE date = $1
                    GROUP BY EXTRACT(HOUR FROM timestamp)
                    ORDER BY hour
                """, end_date)
                
                # Recent alerts
                recent_alerts = await conn.fetch("""
                    SELECT alert_level, message, current_cost, percentage_used, timestamp
                    FROM cost_alerts
                    WHERE date >= $1
                    ORDER BY timestamp DESC
                    LIMIT 10
                """, start_date)
            
            # Get real-time metrics
            realtime_metrics = {}
            if self.redis_client:
                metrics_data = await asyncio.to_thread(
                    self.redis_client.hgetall, "cost:realtime"
                )
                realtime_metrics = {k.decode(): v.decode() for k, v in metrics_data.items()} if metrics_data else {}
            
            return {
                "summary": {
                    "daily_budget": self.daily_budget_brl,
                    "alert_threshold": self.alert_threshold_brl,
                    "current_total": float(realtime_metrics.get("daily_total", 0)),
                    "budget_remaining": float(realtime_metrics.get("budget_remaining", self.daily_budget_brl)),
                    "percentage_used": float(realtime_metrics.get("percentage_used", 0)),
                    "circuit_breaker_active": realtime_metrics.get("circuit_breaker_active", "False") == "True"
                },
                "daily_costs": [
                    {
                        "date": row["date"].isoformat(),
                        "cost": float(row["total_cost"])
                    } for row in daily_costs
                ],
                "model_breakdown": [
                    {
                        "model": row["model"],
                        "cost": float(row["cost"]),
                        "requests": row["requests"]
                    } for row in model_breakdown
                ],
                "hourly_pattern": [
                    {
                        "hour": int(row["hour"]),
                        "cost": float(row["cost"])
                    } for row in hourly_pattern
                ],
                "recent_alerts": [
                    {
                        "level": row["alert_level"],
                        "message": row["message"],
                        "cost": float(row["current_cost"]),
                        "percentage": float(row["percentage_used"]),
                        "timestamp": row["timestamp"].isoformat()
                    } for row in recent_alerts
                ],
                "realtime_metrics": realtime_metrics,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get cost summary: {e}")
            return {}
    
    async def reset_daily_circuit_breaker(self):
        """Reset circuit breaker for new day"""
        try:
            self.circuit_breaker_active = False
            
            if self.redis_client:
                await asyncio.to_thread(
                    self.redis_client.hset, "cost:realtime", "circuit_breaker_active", "False"
                )
            
            logger.info("Daily cost circuit breaker reset")
            
        except Exception as e:
            logger.error(f"Failed to reset circuit breaker: {e}")
    
    def is_budget_exceeded(self) -> bool:
        """Check if daily budget is exceeded (for circuit breaker)"""
        return self.circuit_breaker_active
    
    async def get_current_daily_cost(self) -> float:
        """Get current daily cost total"""
        return await self._get_daily_total()


# Global cost tracker instance
cost_tracker = OpenAICostTracker()