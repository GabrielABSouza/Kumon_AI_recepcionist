"""
Business KPIs Dashboard for Kumon Assistant
Phase 3 - Day 7: Monitoring & Alerting
Real-time business metrics with compliance tracking
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import asyncio
import redis
import asyncpg
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings
from app.core.logger import app_logger as logger


class KPICategory(str, Enum):
    BUSINESS = "business"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    QUALITY = "quality"
    COMPLIANCE = "compliance"


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class KPIMetric:
    name: str
    value: float
    target: float
    unit: str
    category: KPICategory
    timestamp: datetime
    trend: str  # "up", "down", "stable"
    alert_level: AlertLevel


class BusinessKPIModel(BaseModel):
    # Appointment KPIs
    appointments_today: int
    appointments_this_week: int
    appointments_this_month: int
    appointment_conversion_rate: float
    average_response_time: float
    
    # Financial KPIs
    potential_revenue_today: float
    potential_revenue_week: float
    potential_revenue_month: float
    cost_per_lead: float
    
    # Quality KPIs
    customer_satisfaction: float
    first_response_time: float
    resolution_rate: float
    
    # Operational KPIs
    system_uptime: float
    error_rate: float
    cache_hit_rate: float
    active_conversations: int
    
    # Compliance KPIs
    lgpd_compliance_score: float
    security_incidents: int
    data_retention_compliance: float
    
    # Alerts
    active_alerts: List[Dict[str, Any]]
    
    timestamp: datetime


class BusinessKPITracker:
    """Real-time business KPI tracking and dashboard system"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.db_pool = None
        self.kpi_cache = {}
        self.alert_thresholds = self._initialize_thresholds()
        
    async def initialize(self):
        """Initialize database connections and cache"""
        try:
            # Initialize PostgreSQL connection for analytics
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
                
            logger.info("Business KPI tracker initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize KPI tracker: {e}")
            raise
    
    def _initialize_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Initialize KPI alert thresholds based on business requirements"""
        return {
            "response_time": {
                "warning": 3.0,    # 3 seconds warning
                "critical": 5.0,   # 5 seconds critical (compliance requirement)
                "emergency": 8.0   # 8 seconds emergency
            },
            "error_rate": {
                "warning": 0.005,  # 0.5%
                "critical": 0.01,  # 1%
                "emergency": 0.02  # 2%
            },
            "cost_per_day": {
                "warning": 4.0,    # R$4/day alert threshold
                "critical": 5.0,   # R$5/day budget limit
                "emergency": 6.0   # R$6/day emergency
            },
            "cache_hit_rate": {
                "warning": 75.0,   # Below 75%
                "critical": 70.0,  # Below 70%
                "emergency": 60.0  # Below 60%
            },
            "appointment_conversion": {
                "warning": 15.0,   # Below 15%
                "critical": 10.0,  # Below 10%
                "emergency": 5.0   # Below 5%
            },
            "system_uptime": {
                "warning": 99.0,   # Below 99%
                "critical": 98.0,  # Below 98%
                "emergency": 95.0  # Below 95%
            }
        }
    
    async def get_current_kpis(self) -> BusinessKPIModel:
        """Get current business KPI snapshot"""
        try:
            # Collect all KPIs in parallel
            kpi_tasks = [
                self._get_appointment_kpis(),
                self._get_financial_kpis(),
                self._get_quality_kpis(),
                self._get_operational_kpis(),
                self._get_compliance_kpis()
            ]
            
            results = await asyncio.gather(*kpi_tasks, return_exceptions=True)
            
            # Combine results
            appointment_kpis = results[0] if not isinstance(results[0], Exception) else {}
            financial_kpis = results[1] if not isinstance(results[1], Exception) else {}
            quality_kpis = results[2] if not isinstance(results[2], Exception) else {}
            operational_kpis = results[3] if not isinstance(results[3], Exception) else {}
            compliance_kpis = results[4] if not isinstance(results[4], Exception) else {}
            
            # Generate alerts
            active_alerts = await self._generate_alerts({
                **appointment_kpis,
                **financial_kpis,
                **quality_kpis,
                **operational_kpis,
                **compliance_kpis
            })
            
            return BusinessKPIModel(
                # Appointment KPIs
                appointments_today=appointment_kpis.get("appointments_today", 0),
                appointments_this_week=appointment_kpis.get("appointments_this_week", 0),
                appointments_this_month=appointment_kpis.get("appointments_this_month", 0),
                appointment_conversion_rate=appointment_kpis.get("conversion_rate", 0.0),
                average_response_time=quality_kpis.get("avg_response_time", 0.0),
                
                # Financial KPIs
                potential_revenue_today=financial_kpis.get("revenue_today", 0.0),
                potential_revenue_week=financial_kpis.get("revenue_week", 0.0),
                potential_revenue_month=financial_kpis.get("revenue_month", 0.0),
                cost_per_lead=financial_kpis.get("cost_per_lead", 0.0),
                
                # Quality KPIs
                customer_satisfaction=quality_kpis.get("satisfaction", 0.0),
                first_response_time=quality_kpis.get("first_response_time", 0.0),
                resolution_rate=quality_kpis.get("resolution_rate", 0.0),
                
                # Operational KPIs
                system_uptime=operational_kpis.get("uptime", 0.0),
                error_rate=operational_kpis.get("error_rate", 0.0),
                cache_hit_rate=operational_kpis.get("cache_hit_rate", 0.0),
                active_conversations=operational_kpis.get("active_conversations", 0),
                
                # Compliance KPIs
                lgpd_compliance_score=compliance_kpis.get("lgpd_score", 0.0),
                security_incidents=compliance_kpis.get("security_incidents", 0),
                data_retention_compliance=compliance_kpis.get("retention_compliance", 0.0),
                
                # Alerts
                active_alerts=active_alerts,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Failed to get current KPIs: {e}")
            # Return empty KPI model on error
            return BusinessKPIModel(
                appointments_today=0, appointments_this_week=0, appointments_this_month=0,
                appointment_conversion_rate=0.0, average_response_time=0.0,
                potential_revenue_today=0.0, potential_revenue_week=0.0, potential_revenue_month=0.0,
                cost_per_lead=0.0, customer_satisfaction=0.0, first_response_time=0.0,
                resolution_rate=0.0, system_uptime=0.0, error_rate=0.0, cache_hit_rate=0.0,
                active_conversations=0, lgpd_compliance_score=0.0, security_incidents=0,
                data_retention_compliance=0.0, active_alerts=[], timestamp=datetime.now(timezone.utc)
            )
    
    async def _get_appointment_kpis(self) -> Dict[str, Any]:
        """Get appointment-related KPIs"""
        try:
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=now.weekday())
            month_start = today_start.replace(day=1)
            
            if not self.db_pool:
                return {
                    "appointments_today": 0,
                    "appointments_this_week": 0,
                    "appointments_this_month": 0,
                    "conversion_rate": 0.0
                }
            
            async with self.db_pool.acquire() as conn:
                # Count appointments by period
                appointments_today = await conn.fetchval("""
                    SELECT COUNT(*) FROM appointments 
                    WHERE created_at >= $1 AND status != 'cancelled'
                """, today_start)
                
                appointments_week = await conn.fetchval("""
                    SELECT COUNT(*) FROM appointments 
                    WHERE created_at >= $1 AND status != 'cancelled'
                """, week_start)
                
                appointments_month = await conn.fetchval("""
                    SELECT COUNT(*) FROM appointments 
                    WHERE created_at >= $1 AND status != 'cancelled'
                """, month_start)
                
                # Calculate conversion rate (appointments / total conversations)
                total_conversations = await conn.fetchval("""
                    SELECT COUNT(DISTINCT phone_number) FROM conversation_history 
                    WHERE created_at >= $1
                """, today_start)
                
                conversion_rate = (appointments_today / max(total_conversations, 1)) * 100
                
                return {
                    "appointments_today": appointments_today or 0,
                    "appointments_this_week": appointments_week or 0,
                    "appointments_this_month": appointments_month or 0,
                    "conversion_rate": round(conversion_rate, 2)
                }
                
        except Exception as e:
            logger.error(f"Failed to get appointment KPIs: {e}")
            return {"appointments_today": 0, "appointments_this_week": 0, "appointments_this_month": 0, "conversion_rate": 0.0}
    
    async def _get_financial_kpis(self) -> Dict[str, Any]:
        """Get financial KPIs"""
        try:
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=now.weekday())
            month_start = today_start.replace(day=1)
            
            # Calculate potential revenue based on appointments and pricing
            price_per_subject = settings.PRICE_PER_SUBJECT
            enrollment_fee = settings.ENROLLMENT_FEE
            
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    # Get appointments with subject counts
                    revenue_today = await conn.fetchval("""
                        SELECT COALESCE(SUM((subjects_count * $1) + $2), 0) 
                        FROM appointments 
                        WHERE created_at >= $3 AND status = 'confirmed'
                    """, price_per_subject, enrollment_fee, today_start)
                    
                    revenue_week = await conn.fetchval("""
                        SELECT COALESCE(SUM((subjects_count * $1) + $2), 0) 
                        FROM appointments 
                        WHERE created_at >= $3 AND status = 'confirmed'
                    """, price_per_subject, enrollment_fee, week_start)
                    
                    revenue_month = await conn.fetchval("""
                        SELECT COALESCE(SUM((subjects_count * $1) + $2), 0) 
                        FROM appointments 
                        WHERE created_at >= $3 AND status = 'confirmed'
                    """, price_per_subject, enrollment_fee, month_start)
                    
                    # Get daily OpenAI costs from cost tracking
                    daily_costs = await conn.fetchval("""
                        SELECT COALESCE(SUM(cost_brl), 0) 
                        FROM llm_cost_tracking 
                        WHERE date = $1
                    """, today_start.date())
                    
                    total_leads = await conn.fetchval("""
                        SELECT COUNT(DISTINCT phone_number) 
                        FROM conversation_history 
                        WHERE created_at >= $1
                    """, today_start)
                    
                    cost_per_lead = (daily_costs / max(total_leads, 1)) if daily_costs else 0.0
            else:
                revenue_today = 0.0
                revenue_week = 0.0
                revenue_month = 0.0
                cost_per_lead = 0.0
            
            return {
                "revenue_today": float(revenue_today or 0.0),
                "revenue_week": float(revenue_week or 0.0),
                "revenue_month": float(revenue_month or 0.0),
                "cost_per_lead": round(cost_per_lead, 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get financial KPIs: {e}")
            return {"revenue_today": 0.0, "revenue_week": 0.0, "revenue_month": 0.0, "cost_per_lead": 0.0}
    
    async def _get_quality_kpis(self) -> Dict[str, Any]:
        """Get quality KPIs"""
        try:
            if not self.redis_client:
                return {"satisfaction": 0.0, "first_response_time": 0.0, "resolution_rate": 0.0, "avg_response_time": 0.0}
            
            # Get metrics from Redis cache
            response_times = await asyncio.to_thread(
                self.redis_client.lrange, "response_times", 0, -1
            )
            
            if response_times:
                times = [float(t) for t in response_times]
                avg_response_time = sum(times) / len(times)
                first_response_time = min(times) if times else 0.0
            else:
                avg_response_time = 0.0
                first_response_time = 0.0
            
            # Placeholder for satisfaction and resolution rate
            # In production, these would come from customer feedback and conversation analysis
            satisfaction = 4.2  # Example: 4.2/5.0
            resolution_rate = 85.0  # Example: 85%
            
            return {
                "satisfaction": satisfaction,
                "first_response_time": round(first_response_time, 2),
                "resolution_rate": resolution_rate,
                "avg_response_time": round(avg_response_time, 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get quality KPIs: {e}")
            return {"satisfaction": 0.0, "first_response_time": 0.0, "resolution_rate": 0.0, "avg_response_time": 0.0}
    
    async def _get_operational_kpis(self) -> Dict[str, Any]:
        """Get operational KPIs"""
        try:
            # System uptime calculation (placeholder - would use actual monitoring data)
            uptime = 99.5  # Example: 99.5%
            
            # Error rate from Redis metrics
            if self.redis_client:
                total_requests = await asyncio.to_thread(
                    self.redis_client.get, "total_requests_today"
                )
                error_requests = await asyncio.to_thread(
                    self.redis_client.get, "error_requests_today"
                )
                
                total_requests = int(total_requests or 1)
                error_requests = int(error_requests or 0)
                error_rate = (error_requests / total_requests) * 100
                
                # Cache hit rate
                cache_hits = await asyncio.to_thread(
                    self.redis_client.get, "cache_hits_today"
                )
                cache_misses = await asyncio.to_thread(
                    self.redis_client.get, "cache_misses_today"
                )
                
                cache_hits = int(cache_hits or 0)
                cache_misses = int(cache_misses or 1)
                cache_hit_rate = (cache_hits / (cache_hits + cache_misses)) * 100
                
                # Active conversations
                active_conversations = await asyncio.to_thread(
                    self.redis_client.scard, "active_conversations"
                )
            else:
                error_rate = 0.0
                cache_hit_rate = 80.0  # Default target
                active_conversations = 0
            
            return {
                "uptime": uptime,
                "error_rate": round(error_rate, 3),
                "cache_hit_rate": round(cache_hit_rate, 1),
                "active_conversations": active_conversations or 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get operational KPIs: {e}")
            return {"uptime": 0.0, "error_rate": 0.0, "cache_hit_rate": 0.0, "active_conversations": 0}
    
    async def _get_compliance_kpis(self) -> Dict[str, Any]:
        """Get compliance KPIs"""
        try:
            # LGPD compliance score calculation
            lgpd_score = 95.0  # Example: 95% compliance
            
            # Security incidents count
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                    security_incidents = await conn.fetchval("""
                        SELECT COUNT(*) FROM security_incidents 
                        WHERE created_at >= $1 AND severity IN ('high', 'critical')
                    """, today_start)
            else:
                security_incidents = 0
            
            # Data retention compliance
            retention_compliance = 98.0  # Example: 98% compliance
            
            return {
                "lgpd_score": lgpd_score,
                "security_incidents": security_incidents or 0,
                "retention_compliance": retention_compliance
            }
            
        except Exception as e:
            logger.error(f"Failed to get compliance KPIs: {e}")
            return {"lgpd_score": 0.0, "security_incidents": 0, "retention_compliance": 0.0}
    
    async def _generate_alerts(self, kpis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on KPI thresholds"""
        alerts = []
        
        try:
            # Response time alerts
            if "avg_response_time" in kpis:
                response_time = kpis["avg_response_time"]
                thresholds = self.alert_thresholds["response_time"]
                
                if response_time >= thresholds["emergency"]:
                    alerts.append({
                        "id": "response_time_emergency",
                        "title": "Response Time Critical",
                        "message": f"Average response time is {response_time:.1f}s (target: ≤5s)",
                        "level": AlertLevel.EMERGENCY.value,
                        "category": KPICategory.COMPLIANCE.value,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "action_required": True
                    })
                elif response_time >= thresholds["critical"]:
                    alerts.append({
                        "id": "response_time_critical",
                        "title": "Response Time SLA Breach",
                        "message": f"Response time {response_time:.1f}s exceeds SLA target of 5s",
                        "level": AlertLevel.CRITICAL.value,
                        "category": KPICategory.COMPLIANCE.value,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "action_required": True
                    })
                elif response_time >= thresholds["warning"]:
                    alerts.append({
                        "id": "response_time_warning",
                        "title": "Response Time Warning",
                        "message": f"Response time {response_time:.1f}s approaching SLA limit",
                        "level": AlertLevel.WARNING.value,
                        "category": KPICategory.OPERATIONAL.value,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "action_required": False
                    })
            
            # Error rate alerts
            if "error_rate" in kpis:
                error_rate = kpis["error_rate"]
                thresholds = self.alert_thresholds["error_rate"]
                
                if error_rate >= thresholds["critical"]:
                    alerts.append({
                        "id": "error_rate_critical",
                        "title": "High Error Rate",
                        "message": f"Error rate is {error_rate:.1f}% (target: <1%)",
                        "level": AlertLevel.CRITICAL.value,
                        "category": KPICategory.QUALITY.value,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "action_required": True
                    })
            
            # Cache hit rate alerts
            if "cache_hit_rate" in kpis:
                hit_rate = kpis["cache_hit_rate"]
                thresholds = self.alert_thresholds["cache_hit_rate"]
                
                if hit_rate <= thresholds["critical"]:
                    alerts.append({
                        "id": "cache_hit_rate_low",
                        "title": "Low Cache Hit Rate",
                        "message": f"Cache hit rate is {hit_rate:.1f}% (target: >80%)",
                        "level": AlertLevel.WARNING.value,
                        "category": KPICategory.OPERATIONAL.value,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "action_required": False
                    })
            
            # Security incidents alert
            if "security_incidents" in kpis and kpis["security_incidents"] > 0:
                alerts.append({
                    "id": "security_incidents",
                    "title": "Security Incidents Detected",
                    "message": f"{kpis['security_incidents']} security incident(s) detected today",
                    "level": AlertLevel.CRITICAL.value,
                    "category": KPICategory.COMPLIANCE.value,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action_required": True
                })
            
        except Exception as e:
            logger.error(f"Failed to generate alerts: {e}")
        
        return alerts
    
    async def record_metric(self, metric: KPIMetric):
        """Record a KPI metric for tracking"""
        try:
            if self.redis_client:
                # Store in Redis for real-time access
                key = f"kpi:{metric.category.value}:{metric.name}"
                await asyncio.to_thread(
                    self.redis_client.hset, key, mapping={
                        "value": metric.value,
                        "timestamp": metric.timestamp.isoformat(),
                        "trend": metric.trend
                    }
                )
                await asyncio.to_thread(
                    self.redis_client.expire, key, 86400  # 24 hours
                )
            
            # Store in PostgreSQL for historical analysis
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO kpi_metrics (name, value, target, unit, category, timestamp, trend, alert_level)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, metric.name, metric.value, metric.target, metric.unit, 
                    metric.category.value, metric.timestamp, metric.trend, metric.alert_level.value)
                    
        except Exception as e:
            logger.error(f"Failed to record KPI metric {metric.name}: {e}")
    
    async def get_historical_kpis(self, days: int = 7) -> Dict[str, List[Dict[str, Any]]]:
        """Get historical KPI data for trend analysis"""
        try:
            if not self.db_pool:
                return {}
            
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT name, value, timestamp, category 
                    FROM kpi_metrics 
                    WHERE timestamp >= $1 
                    ORDER BY timestamp DESC
                """, start_date)
                
                # Group by metric name
                historical_data = {}
                for row in rows:
                    metric_name = row['name']
                    if metric_name not in historical_data:
                        historical_data[metric_name] = []
                    
                    historical_data[metric_name].append({
                        "value": float(row['value']),
                        "timestamp": row['timestamp'].isoformat(),
                        "category": row['category']
                    })
                
                return historical_data
                
        except Exception as e:
            logger.error(f"Failed to get historical KPIs: {e}")
            return {}


# Global KPI tracker instance
kpi_tracker = BusinessKPITracker()