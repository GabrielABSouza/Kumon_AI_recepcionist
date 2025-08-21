"""
Performance SLA Tracking System
Phase 3 - Day 7: Real-time response time monitoring
Compliance: ≤5s response time SLA tracking and alerting
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum
import asyncio
import redis
import asyncpg
import json
import statistics
from collections import deque, defaultdict

from app.core.config import settings
from app.core.logger import app_logger as logger


class SLAStatus(str, Enum):
    COMPLIANT = "compliant"
    WARNING = "warning"
    BREACH = "breach"
    CRITICAL = "critical"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class ResponseTimeMetric:
    endpoint: str
    method: str
    response_time_ms: float
    status_code: int
    timestamp: datetime
    user_agent: Optional[str] = None
    request_id: Optional[str] = None


@dataclass
class SLAAlert:
    severity: AlertSeverity
    message: str
    current_avg_ms: float
    sla_threshold_ms: float
    breach_duration_minutes: int
    affected_endpoints: List[str]
    timestamp: datetime
    action_required: bool


@dataclass
class SLAMetrics:
    current_avg_response_time: float
    sla_compliance_percentage: float
    total_requests: int
    sla_breaches: int
    fastest_response: float
    slowest_response: float
    p95_response_time: float
    p99_response_time: float
    status: SLAStatus
    timestamp: datetime


class PerformanceSLATracker:
    """Real-time performance SLA tracking and monitoring"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.db_pool = None
        self.sla_threshold_ms = settings.RESPONSE_TIME_TARGET * 1000  # Convert to milliseconds
        self.warning_threshold_ms = settings.RESPONSE_TIME_WARNING * 1000
        
        # In-memory cache for fast calculations
        self.recent_response_times = deque(maxlen=1000)  # Last 1000 requests
        self.endpoint_metrics = defaultdict(lambda: deque(maxlen=100))  # Per endpoint
        self.current_breach_start = None
        
    async def initialize(self):
        """Initialize database connections and tables"""
        try:
            # Initialize PostgreSQL connection
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
            
            # Create performance tracking tables
            if self.db_pool:
                await self._create_performance_tables()
            
            logger.info("Performance SLA tracker initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize SLA tracker: {e}")
            raise
    
    async def _create_performance_tables(self):
        """Create performance tracking tables if not exist"""
        try:
            async with self.db_pool.acquire() as conn:
                # Response time metrics table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS response_time_metrics (
                        id SERIAL PRIMARY KEY,
                        endpoint VARCHAR(255) NOT NULL,
                        method VARCHAR(10) NOT NULL,
                        response_time_ms DECIMAL(10, 2) NOT NULL,
                        status_code INTEGER NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        user_agent TEXT,
                        request_id VARCHAR(255),
                        INDEX (timestamp, endpoint),
                        INDEX (response_time_ms),
                        INDEX (endpoint, method)
                    )
                """)
                
                # SLA breach events table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS sla_breach_events (
                        id SERIAL PRIMARY KEY,
                        breach_start TIMESTAMP WITH TIME ZONE NOT NULL,
                        breach_end TIMESTAMP WITH TIME ZONE,
                        duration_minutes INTEGER,
                        max_response_time_ms DECIMAL(10, 2) NOT NULL,
                        avg_response_time_ms DECIMAL(10, 2) NOT NULL,
                        affected_requests INTEGER DEFAULT 0,
                        affected_endpoints TEXT[],
                        severity VARCHAR(20) NOT NULL,
                        resolved BOOLEAN DEFAULT FALSE,
                        INDEX (breach_start),
                        INDEX (severity, resolved)
                    )
                """)
                
                # SLA alerts table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS sla_alerts (
                        id SERIAL PRIMARY KEY,
                        severity VARCHAR(20) NOT NULL,
                        message TEXT NOT NULL,
                        current_avg_ms DECIMAL(10, 2) NOT NULL,
                        sla_threshold_ms DECIMAL(10, 2) NOT NULL,
                        breach_duration_minutes INTEGER NOT NULL,
                        affected_endpoints TEXT[],
                        action_required BOOLEAN DEFAULT FALSE,
                        resolved BOOLEAN DEFAULT FALSE,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        INDEX (timestamp, severity),
                        INDEX (resolved)
                    )
                """)
                
        except Exception as e:
            logger.error(f"Failed to create performance tables: {e}")
            raise
    
    async def record_response_time(self, metric: ResponseTimeMetric) -> Tuple[SLAMetrics, Optional[SLAAlert]]:
        """
        Record response time and return (metrics, alert)
        
        Returns current SLA metrics and alert if threshold breached
        """
        try:
            # Store in database
            await self._store_response_time(metric)
            
            # Update in-memory cache
            self.recent_response_times.append(metric.response_time_ms)
            self.endpoint_metrics[f"{metric.method} {metric.endpoint}"].append(metric.response_time_ms)
            
            # Calculate current metrics
            current_metrics = await self._calculate_sla_metrics()
            
            # Check for SLA breaches and generate alerts
            alert = await self._check_sla_breach(current_metrics, metric)
            
            # Update real-time metrics in Redis
            await self._update_realtime_metrics(current_metrics)
            
            return current_metrics, alert
            
        except Exception as e:
            logger.error(f"Failed to record response time: {e}")
            # Return default metrics on error
            default_metrics = SLAMetrics(
                current_avg_response_time=0.0,
                sla_compliance_percentage=100.0,
                total_requests=0,
                sla_breaches=0,
                fastest_response=0.0,
                slowest_response=0.0,
                p95_response_time=0.0,
                p99_response_time=0.0,
                status=SLAStatus.COMPLIANT,
                timestamp=datetime.now(timezone.utc)
            )
            return default_metrics, None
    
    async def _store_response_time(self, metric: ResponseTimeMetric):
        """Store response time metric in database"""
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO response_time_metrics 
                        (endpoint, method, response_time_ms, status_code, timestamp, user_agent, request_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, metric.endpoint, metric.method, metric.response_time_ms, 
                    metric.status_code, metric.timestamp, metric.user_agent, metric.request_id)
            
            # Update Redis counters
            if self.redis_client:
                today = datetime.now(timezone.utc).date().isoformat()
                
                # Update daily counters
                await asyncio.to_thread(
                    self.redis_client.incr, f"requests:total:{today}"
                )
                
                if metric.response_time_ms > self.sla_threshold_ms:
                    await asyncio.to_thread(
                        self.redis_client.incr, f"requests:sla_breach:{today}"
                    )
                
                # Update recent response times (sliding window)
                await asyncio.to_thread(
                    self.redis_client.lpush, "response_times:recent", metric.response_time_ms
                )
                await asyncio.to_thread(
                    self.redis_client.ltrim, "response_times:recent", 0, 999  # Keep last 1000
                )
                
                # Set expiration
                await asyncio.to_thread(
                    self.redis_client.expire, f"requests:total:{today}", 86400 * 2
                )
                await asyncio.to_thread(
                    self.redis_client.expire, f"requests:sla_breach:{today}", 86400 * 2
                )
                
        except Exception as e:
            logger.error(f"Failed to store response time metric: {e}")
    
    async def _calculate_sla_metrics(self) -> SLAMetrics:
        """Calculate current SLA metrics"""
        try:
            if not self.recent_response_times:
                return SLAMetrics(
                    current_avg_response_time=0.0,
                    sla_compliance_percentage=100.0,
                    total_requests=0,
                    sla_breaches=0,
                    fastest_response=0.0,
                    slowest_response=0.0,
                    p95_response_time=0.0,
                    p99_response_time=0.0,
                    status=SLAStatus.COMPLIANT,
                    timestamp=datetime.now(timezone.utc)
                )
            
            response_times = list(self.recent_response_times)
            
            # Calculate basic statistics
            avg_response_time = statistics.mean(response_times)
            fastest_response = min(response_times)
            slowest_response = max(response_times)
            
            # Calculate percentiles
            sorted_times = sorted(response_times)
            p95_index = int(0.95 * len(sorted_times))
            p99_index = int(0.99 * len(sorted_times))
            p95_response_time = sorted_times[p95_index] if p95_index < len(sorted_times) else sorted_times[-1]
            p99_response_time = sorted_times[p99_index] if p99_index < len(sorted_times) else sorted_times[-1]
            
            # Calculate SLA compliance
            compliant_requests = sum(1 for rt in response_times if rt <= self.sla_threshold_ms)
            total_requests = len(response_times)
            sla_breaches = total_requests - compliant_requests
            sla_compliance_percentage = (compliant_requests / total_requests) * 100
            
            # Determine status
            if avg_response_time > self.sla_threshold_ms:
                status = SLAStatus.BREACH
            elif avg_response_time > self.warning_threshold_ms:
                status = SLAStatus.WARNING
            elif sla_compliance_percentage < 95:
                status = SLAStatus.WARNING
            else:
                status = SLAStatus.COMPLIANT
            
            return SLAMetrics(
                current_avg_response_time=round(avg_response_time, 2),
                sla_compliance_percentage=round(sla_compliance_percentage, 2),
                total_requests=total_requests,
                sla_breaches=sla_breaches,
                fastest_response=round(fastest_response, 2),
                slowest_response=round(slowest_response, 2),
                p95_response_time=round(p95_response_time, 2),
                p99_response_time=round(p99_response_time, 2),
                status=status,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate SLA metrics: {e}")
            return SLAMetrics(
                current_avg_response_time=0.0,
                sla_compliance_percentage=100.0,
                total_requests=0,
                sla_breaches=0,
                fastest_response=0.0,
                slowest_response=0.0,
                p95_response_time=0.0,
                p99_response_time=0.0,
                status=SLAStatus.COMPLIANT,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def _check_sla_breach(self, metrics: SLAMetrics, latest_metric: ResponseTimeMetric) -> Optional[SLAAlert]:
        """Check for SLA breaches and generate alerts"""
        try:
            alert = None
            now = datetime.now(timezone.utc)
            
            # Check if we're currently in breach
            if metrics.current_avg_response_time > self.sla_threshold_ms:
                # Track breach start time
                if not self.current_breach_start:
                    self.current_breach_start = now
                
                # Calculate breach duration
                breach_duration = (now - self.current_breach_start).total_seconds() / 60
                
                # Get affected endpoints
                affected_endpoints = list(self.endpoint_metrics.keys())
                
                # Determine alert severity based on duration and severity
                if breach_duration >= 15:  # 15+ minutes
                    severity = AlertSeverity.EMERGENCY
                elif breach_duration >= 5:  # 5+ minutes
                    severity = AlertSeverity.CRITICAL
                elif metrics.current_avg_response_time > self.sla_threshold_ms * 1.5:  # 50% over SLA
                    severity = AlertSeverity.CRITICAL
                else:
                    severity = AlertSeverity.WARNING
                
                alert = SLAAlert(
                    severity=severity,
                    message=f"SLA breach detected: Avg response time {metrics.current_avg_response_time:.1f}ms exceeds {self.sla_threshold_ms:.0f}ms target",
                    current_avg_ms=metrics.current_avg_response_time,
                    sla_threshold_ms=self.sla_threshold_ms,
                    breach_duration_minutes=int(breach_duration),
                    affected_endpoints=affected_endpoints,
                    timestamp=now,
                    action_required=severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]
                )
                
                # Store breach event
                await self._store_breach_event(alert)
                
            else:
                # End of breach if we were in one
                if self.current_breach_start:
                    breach_duration = (now - self.current_breach_start).total_seconds() / 60
                    logger.info(f"SLA breach resolved after {breach_duration:.1f} minutes")
                    
                    # Mark breach as resolved
                    await self._resolve_breach_event(self.current_breach_start, now)
                    self.current_breach_start = None
            
            # Check for warning conditions
            if not alert and metrics.current_avg_response_time > self.warning_threshold_ms:
                alert = SLAAlert(
                    severity=AlertSeverity.WARNING,
                    message=f"Performance warning: Avg response time {metrics.current_avg_response_time:.1f}ms approaching SLA limit",
                    current_avg_ms=metrics.current_avg_response_time,
                    sla_threshold_ms=self.sla_threshold_ms,
                    breach_duration_minutes=0,
                    affected_endpoints=list(self.endpoint_metrics.keys()),
                    timestamp=now,
                    action_required=False
                )
            
            # Store alert if generated
            if alert:
                await self._store_alert(alert)
            
            return alert
            
        except Exception as e:
            logger.error(f"Failed to check SLA breach: {e}")
            return None
    
    async def _store_breach_event(self, alert: SLAAlert):
        """Store SLA breach event"""
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO sla_breach_events 
                        (breach_start, max_response_time_ms, avg_response_time_ms, 
                         affected_endpoints, severity, resolved)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """, self.current_breach_start, alert.current_avg_ms, alert.current_avg_ms,
                    alert.affected_endpoints, alert.severity.value, False)
                    
        except Exception as e:
            logger.error(f"Failed to store breach event: {e}")
    
    async def _resolve_breach_event(self, breach_start: datetime, breach_end: datetime):
        """Mark breach event as resolved"""
        try:
            if self.db_pool:
                duration_minutes = (breach_end - breach_start).total_seconds() / 60
                
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE sla_breach_events 
                        SET breach_end = $1, duration_minutes = $2, resolved = true
                        WHERE breach_start = $3 AND resolved = false
                    """, breach_end, int(duration_minutes), breach_start)
                    
        except Exception as e:
            logger.error(f"Failed to resolve breach event: {e}")
    
    async def _store_alert(self, alert: SLAAlert):
        """Store SLA alert"""
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO sla_alerts 
                        (severity, message, current_avg_ms, sla_threshold_ms, 
                         breach_duration_minutes, affected_endpoints, action_required, timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, alert.severity.value, alert.message, alert.current_avg_ms, alert.sla_threshold_ms,
                    alert.breach_duration_minutes, alert.affected_endpoints, alert.action_required, alert.timestamp)
            
            # Log alert
            if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
                logger.error(f"SLA alert: {alert.message}")
            elif alert.severity == AlertSeverity.WARNING:
                logger.warning(f"SLA alert: {alert.message}")
            else:
                logger.info(f"SLA alert: {alert.message}")
                
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")
    
    async def _update_realtime_metrics(self, metrics: SLAMetrics):
        """Update real-time metrics in Redis"""
        try:
            if self.redis_client:
                metrics_data = {
                    "current_avg_response_time": metrics.current_avg_response_time,
                    "sla_compliance_percentage": metrics.sla_compliance_percentage,
                    "total_requests": metrics.total_requests,
                    "sla_breaches": metrics.sla_breaches,
                    "p95_response_time": metrics.p95_response_time,
                    "p99_response_time": metrics.p99_response_time,
                    "status": metrics.status.value,
                    "in_breach": self.current_breach_start is not None,
                    "last_updated": metrics.timestamp.isoformat()
                }
                
                await asyncio.to_thread(
                    self.redis_client.hset, "sla:realtime", mapping=metrics_data
                )
                await asyncio.to_thread(
                    self.redis_client.expire, "sla:realtime", 3600  # 1 hour
                )
                
        except Exception as e:
            logger.error(f"Failed to update realtime metrics: {e}")
    
    async def get_sla_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get SLA performance summary for specified hours"""
        try:
            if not self.db_pool:
                return {}
            
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            async with self.db_pool.acquire() as conn:
                # Overall statistics
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_requests,
                        AVG(response_time_ms) as avg_response_time,
                        MIN(response_time_ms) as min_response_time,
                        MAX(response_time_ms) as max_response_time,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95_response_time,
                        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99_response_time,
                        COUNT(*) FILTER (WHERE response_time_ms > $1) as sla_breaches
                    FROM response_time_metrics
                    WHERE timestamp >= $2 AND timestamp <= $3
                """, self.sla_threshold_ms, start_time, end_time)
                
                # Hourly breakdown
                hourly_stats = await conn.fetch("""
                    SELECT 
                        DATE_TRUNC('hour', timestamp) as hour,
                        COUNT(*) as requests,
                        AVG(response_time_ms) as avg_response_time,
                        COUNT(*) FILTER (WHERE response_time_ms > $1) as breaches
                    FROM response_time_metrics
                    WHERE timestamp >= $2 AND timestamp <= $3
                    GROUP BY DATE_TRUNC('hour', timestamp)
                    ORDER BY hour
                """, self.sla_threshold_ms, start_time, end_time)
                
                # Endpoint breakdown
                endpoint_stats = await conn.fetch("""
                    SELECT 
                        method || ' ' || endpoint as endpoint,
                        COUNT(*) as requests,
                        AVG(response_time_ms) as avg_response_time,
                        MAX(response_time_ms) as max_response_time,
                        COUNT(*) FILTER (WHERE response_time_ms > $1) as breaches
                    FROM response_time_metrics
                    WHERE timestamp >= $2 AND timestamp <= $3
                    GROUP BY method, endpoint
                    ORDER BY avg_response_time DESC
                """, self.sla_threshold_ms, start_time, end_time)
                
                # Recent breach events
                breach_events = await conn.fetch("""
                    SELECT breach_start, breach_end, duration_minutes, 
                           avg_response_time_ms, severity, resolved
                    FROM sla_breach_events
                    WHERE breach_start >= $1
                    ORDER BY breach_start DESC
                    LIMIT 10
                """, start_time)
                
                # Recent alerts
                recent_alerts = await conn.fetch("""
                    SELECT severity, message, current_avg_ms, 
                           breach_duration_minutes, timestamp
                    FROM sla_alerts
                    WHERE timestamp >= $1
                    ORDER BY timestamp DESC
                    LIMIT 20
                """, start_time)
            
            # Calculate SLA compliance percentage
            total_requests = stats["total_requests"] or 0
            sla_breaches = stats["sla_breaches"] or 0
            sla_compliance = ((total_requests - sla_breaches) / max(total_requests, 1)) * 100
            
            # Get real-time metrics
            realtime_metrics = {}
            if self.redis_client:
                metrics_data = await asyncio.to_thread(
                    self.redis_client.hgetall, "sla:realtime"
                )
                realtime_metrics = {k.decode(): v.decode() for k, v in metrics_data.items()} if metrics_data else {}
            
            return {
                "summary": {
                    "sla_threshold_ms": self.sla_threshold_ms,
                    "warning_threshold_ms": self.warning_threshold_ms,
                    "analysis_period_hours": hours,
                    "total_requests": total_requests,
                    "avg_response_time_ms": float(stats["avg_response_time"] or 0),
                    "min_response_time_ms": float(stats["min_response_time"] or 0),
                    "max_response_time_ms": float(stats["max_response_time"] or 0),
                    "p95_response_time_ms": float(stats["p95_response_time"] or 0),
                    "p99_response_time_ms": float(stats["p99_response_time"] or 0),
                    "sla_breaches": sla_breaches,
                    "sla_compliance_percentage": round(sla_compliance, 2),
                    "status": "compliant" if sla_compliance >= 95 else "degraded"
                },
                "hourly_breakdown": [
                    {
                        "hour": row["hour"].isoformat(),
                        "requests": row["requests"],
                        "avg_response_time_ms": float(row["avg_response_time"]),
                        "breaches": row["breaches"],
                        "compliance_percentage": round(((row["requests"] - row["breaches"]) / max(row["requests"], 1)) * 100, 1)
                    } for row in hourly_stats
                ],
                "endpoint_performance": [
                    {
                        "endpoint": row["endpoint"],
                        "requests": row["requests"],
                        "avg_response_time_ms": float(row["avg_response_time"]),
                        "max_response_time_ms": float(row["max_response_time"]),
                        "breaches": row["breaches"],
                        "compliance_percentage": round(((row["requests"] - row["breaches"]) / max(row["requests"], 1)) * 100, 1)
                    } for row in endpoint_stats
                ],
                "breach_events": [
                    {
                        "start": row["breach_start"].isoformat(),
                        "end": row["breach_end"].isoformat() if row["breach_end"] else None,
                        "duration_minutes": row["duration_minutes"],
                        "avg_response_time_ms": float(row["avg_response_time_ms"]),
                        "severity": row["severity"],
                        "resolved": row["resolved"]
                    } for row in breach_events
                ],
                "recent_alerts": [
                    {
                        "severity": row["severity"],
                        "message": row["message"],
                        "response_time_ms": float(row["current_avg_ms"]),
                        "duration_minutes": row["breach_duration_minutes"],
                        "timestamp": row["timestamp"].isoformat()
                    } for row in recent_alerts
                ],
                "realtime_metrics": realtime_metrics,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get SLA summary: {e}")
            return {}
    
    async def get_current_metrics(self) -> SLAMetrics:
        """Get current SLA metrics"""
        return await self._calculate_sla_metrics()
    
    def is_in_breach(self) -> bool:
        """Check if currently in SLA breach"""
        return self.current_breach_start is not None


# Global SLA tracker instance
sla_tracker = PerformanceSLATracker()