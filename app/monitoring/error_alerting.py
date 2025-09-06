"""
Error Alerting and Escalation System
Phase 3 - Day 7: Comprehensive error monitoring with escalation
"""
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum
import asyncio
import redis
import asyncpg
import json
import hashlib
from collections import defaultdict, Counter

from app.core.config import settings
from app.core.logger import app_logger as logger


class ErrorSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class EscalationLevel(str, Enum):
    NONE = "none"
    LEVEL_1 = "level_1"  # Team notification
    LEVEL_2 = "level_2"  # Management notification
    LEVEL_3 = "level_3"  # Executive notification


@dataclass
class ErrorEvent:
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    component: str
    error_type: str
    message: str
    stack_trace: Optional[str]
    request_id: Optional[str]
    user_context: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]


@dataclass
class ErrorAlert:
    alert_id: str
    error_pattern: str
    first_occurrence: datetime
    last_occurrence: datetime
    occurrence_count: int
    severity: ErrorSeverity
    status: AlertStatus
    escalation_level: EscalationLevel
    affected_components: Set[str]
    error_rate_per_hour: float
    estimated_impact: str
    resolution_suggestions: List[str]


class ErrorAlertingSystem:
    """Comprehensive error alerting and escalation system"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.db_pool = None
        
        # Error aggregation windows
        self.active_errors = defaultdict(list)  # Error pattern -> [ErrorEvent]
        self.error_counters = defaultdict(int)  # Error pattern -> count
        self.alert_cache = {}  # alert_id -> ErrorAlert
        
        # Escalation thresholds
        self.escalation_thresholds = {
            ErrorSeverity.CRITICAL: {
                "count_threshold": 5,
                "time_window_minutes": 15,
                "escalation_delay_minutes": 30
            },
            ErrorSeverity.HIGH: {
                "count_threshold": 10,
                "time_window_minutes": 30,
                "escalation_delay_minutes": 60
            },
            ErrorSeverity.MEDIUM: {
                "count_threshold": 20,
                "time_window_minutes": 60,
                "escalation_delay_minutes": 120
            }
        }
        
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
            
            # Create error tracking tables
            if self.db_pool:
                await self._create_error_tables()
            
            logger.info("Error alerting system initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize error alerting system: {e}")
            raise
    
    async def _create_error_tables(self):
        """Create error tracking tables if not exist"""
        try:
            async with self.db_pool.acquire() as conn:
                # Error events table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS error_events (
                        id SERIAL PRIMARY KEY,
                        error_id VARCHAR(255) NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        severity VARCHAR(20) NOT NULL,
                        component VARCHAR(100) NOT NULL,
                        error_type VARCHAR(100) NOT NULL,
                        message TEXT NOT NULL,
                        stack_trace TEXT,
                        request_id VARCHAR(255),
                        user_context JSONB,
                        metadata JSONB,
                        INDEX (timestamp, severity),
                        INDEX (error_id),
                        INDEX (component, error_type)
                    )
                """)
                
                # Error alerts table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS error_alerts (
                        id SERIAL PRIMARY KEY,
                        alert_id VARCHAR(255) UNIQUE NOT NULL,
                        error_pattern VARCHAR(255) NOT NULL,
                        first_occurrence TIMESTAMP WITH TIME ZONE NOT NULL,
                        last_occurrence TIMESTAMP WITH TIME ZONE NOT NULL,
                        occurrence_count INTEGER DEFAULT 1,
                        severity VARCHAR(20) NOT NULL,
                        status VARCHAR(20) DEFAULT 'active',
                        escalation_level VARCHAR(20) DEFAULT 'none',
                        affected_components TEXT[],
                        error_rate_per_hour DECIMAL(10, 2) DEFAULT 0,
                        estimated_impact TEXT,
                        resolution_suggestions TEXT[],
                        acknowledged_by VARCHAR(255),
                        acknowledged_at TIMESTAMP WITH TIME ZONE,
                        resolved_at TIMESTAMP WITH TIME ZONE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        INDEX (status, severity),
                        INDEX (error_pattern),
                        INDEX (created_at)
                    )
                """)
                
                # Escalation logs table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS escalation_logs (
                        id SERIAL PRIMARY KEY,
                        alert_id VARCHAR(255) NOT NULL,
                        escalation_level VARCHAR(20) NOT NULL,
                        escalated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        escalated_to TEXT[],
                        notification_method VARCHAR(50),
                        notification_status VARCHAR(20),
                        response_time_minutes INTEGER,
                        INDEX (alert_id),
                        INDEX (escalated_at)
                    )
                """)
                
        except Exception as e:
            logger.error(f"Failed to create error tables: {e}")
            raise
    
    async def record_error(self, error: ErrorEvent) -> Optional[ErrorAlert]:
        """
        Record error event and return alert if threshold exceeded
        """
        try:
            # Store error event
            await self._store_error_event(error)
            
            # Generate error pattern for grouping similar errors
            error_pattern = self._generate_error_pattern(error)
            
            # Update error counters
            self.active_errors[error_pattern].append(error)
            self.error_counters[error_pattern] += 1
            
            # Check if alert should be generated
            alert = await self._check_alert_threshold(error_pattern, error)
            
            # Update real-time metrics
            await self._update_error_metrics(error)
            
            return alert
            
        except Exception as e:
            logger.error(f"Failed to record error: {e}")
            return None
    
    def _generate_error_pattern(self, error: ErrorEvent) -> str:
        """Generate error pattern for grouping similar errors"""
        # Create a pattern based on component, error type, and message fingerprint
        message_hash = hashlib.md5(error.message.encode()).hexdigest()[:8]
        return f"{error.component}::{error.error_type}::{message_hash}"
    
    async def _store_error_event(self, error: ErrorEvent):
        """Store error event in database"""
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO error_events 
                        (error_id, timestamp, severity, component, error_type, message, 
                         stack_trace, request_id, user_context, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """, error.error_id, error.timestamp, error.severity.value, error.component,
                    error.error_type, error.message, error.stack_trace, error.request_id,
                    json.dumps(error.user_context) if error.user_context else None,
                    json.dumps(error.metadata))
            
            # Update Redis counters
            if self.redis_client:
                today = datetime.now(timezone.utc).date().isoformat()
                
                # Update daily error counts
                await asyncio.to_thread(
                    self.redis_client.incr, f"errors:total:{today}"
                )
                await asyncio.to_thread(
                    self.redis_client.incr, f"errors:{error.severity.value}:{today}"
                )
                await asyncio.to_thread(
                    self.redis_client.incr, f"errors:component:{error.component}:{today}"
                )
                
                # Set expiration
                for key in [f"errors:total:{today}", f"errors:{error.severity.value}:{today}", f"errors:component:{error.component}:{today}"]:
                    await asyncio.to_thread(
                        self.redis_client.expire, key, 86400 * 7  # 7 days
                    )
                
        except Exception as e:
            logger.error(f"Failed to store error event: {e}")
    
    async def _check_alert_threshold(self, error_pattern: str, latest_error: ErrorEvent) -> Optional[ErrorAlert]:
        """Check if error pattern exceeds alert threshold"""
        try:
            now = datetime.now(timezone.utc)
            recent_errors = self.active_errors[error_pattern]
            
            # Get threshold config
            threshold_config = self.escalation_thresholds.get(latest_error.severity)
            if not threshold_config:
                return None
            
            # Filter recent errors within time window
            time_window = timedelta(minutes=threshold_config["time_window_minutes"])
            recent_errors = [
                err for err in recent_errors 
                if now - err.timestamp <= time_window
            ]
            
            # Check if threshold exceeded
            if len(recent_errors) >= threshold_config["count_threshold"]:
                # Check if alert already exists
                alert_id = f"{error_pattern}::{latest_error.severity.value}"
                
                if alert_id in self.alert_cache:
                    # Update existing alert
                    alert = self.alert_cache[alert_id]
                    alert.last_occurrence = now
                    alert.occurrence_count += 1
                    alert.error_rate_per_hour = len(recent_errors) * (60 / threshold_config["time_window_minutes"])
                    
                    # Check for escalation
                    await self._check_escalation(alert, threshold_config)
                    
                else:
                    # Create new alert
                    alert = ErrorAlert(
                        alert_id=alert_id,
                        error_pattern=error_pattern,
                        first_occurrence=recent_errors[0].timestamp,
                        last_occurrence=now,
                        occurrence_count=len(recent_errors),
                        severity=latest_error.severity,
                        status=AlertStatus.ACTIVE,
                        escalation_level=EscalationLevel.NONE,
                        affected_components={err.component for err in recent_errors},
                        error_rate_per_hour=len(recent_errors) * (60 / threshold_config["time_window_minutes"]),
                        estimated_impact=self._estimate_impact(recent_errors),
                        resolution_suggestions=self._generate_resolution_suggestions(latest_error)
                    )
                    
                    self.alert_cache[alert_id] = alert
                
                # Store/update alert in database
                await self._store_alert(alert)
                
                return alert
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to check alert threshold: {e}")
            return None
    
    def _estimate_impact(self, errors: List[ErrorEvent]) -> str:
        """Estimate impact based on error characteristics"""
        unique_requests = len(set(err.request_id for err in errors if err.request_id))
        unique_components = len(set(err.component for err in errors))
        
        if unique_components > 3:
            return "system_wide"
        elif unique_requests > 10:
            return "high_user_impact"
        elif unique_requests > 3:
            return "moderate_user_impact"
        else:
            return "low_user_impact"
    
    def _generate_resolution_suggestions(self, error: ErrorEvent) -> List[str]:
        """Generate resolution suggestions based on error type"""
        suggestions = []
        
        error_type = error.error_type.lower()
        component = error.component.lower()
        message = error.message.lower()
        
        # Database-related errors
        if "database" in component or "connection" in message:
            suggestions.extend([
                "Check database connection pool settings",
                "Verify database server status",
                "Review database query performance",
                "Check for deadlocks or long-running transactions"
            ])
        
        # API-related errors
        if "api" in component or "timeout" in message:
            suggestions.extend([
                "Check external API service status",
                "Review API timeout configurations",
                "Verify network connectivity",
                "Consider implementing circuit breaker pattern"
            ])
        
        # Memory-related errors
        if "memory" in message or "outofmemory" in error_type:
            suggestions.extend([
                "Check memory usage and limits",
                "Review memory leak possibilities",
                "Consider scaling up resources",
                "Optimize memory-intensive operations"
            ])
        
        # Rate limiting errors
        if "rate limit" in message or "429" in message:
            suggestions.extend([
                "Review rate limiting configuration",
                "Check for unusual traffic patterns",
                "Consider implementing request queuing",
                "Verify API key quotas"
            ])
        
        # Authentication errors
        if "auth" in message or "unauthorized" in message:
            suggestions.extend([
                "Check API key validity",
                "Verify authentication configuration",
                "Review token expiration settings",
                "Check user permissions"
            ])
        
        # Default suggestions
        if not suggestions:
            suggestions.extend([
                "Review application logs for additional context",
                "Check system resources (CPU, memory, disk)",
                "Verify external service dependencies",
                "Consider temporary traffic reduction"
            ])
        
        return suggestions[:5]  # Limit to 5 suggestions
    
    async def _check_escalation(self, alert: ErrorAlert, threshold_config: Dict[str, Any]):
        """Check if alert should be escalated"""
        try:
            now = datetime.now(timezone.utc)
            escalation_delay = timedelta(minutes=threshold_config["escalation_delay_minutes"])
            
            # Check if escalation delay has passed
            if now - alert.first_occurrence >= escalation_delay and alert.escalation_level == EscalationLevel.NONE:
                if alert.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.EMERGENCY]:
                    alert.escalation_level = EscalationLevel.LEVEL_3
                elif alert.severity == ErrorSeverity.HIGH:
                    alert.escalation_level = EscalationLevel.LEVEL_2
                else:
                    alert.escalation_level = EscalationLevel.LEVEL_1
                
                alert.status = AlertStatus.ESCALATED
                
                # Log escalation
                await self._log_escalation(alert)
                
        except Exception as e:
            logger.error(f"Failed to check escalation: {e}")
    
    async def _store_alert(self, alert: ErrorAlert):
        """Store or update alert in database"""
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO error_alerts 
                        (alert_id, error_pattern, first_occurrence, last_occurrence, 
                         occurrence_count, severity, status, escalation_level, 
                         affected_components, error_rate_per_hour, estimated_impact, 
                         resolution_suggestions, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
                        ON CONFLICT (alert_id) DO UPDATE SET
                            last_occurrence = $4,
                            occurrence_count = $5,
                            status = $7,
                            escalation_level = $8,
                            error_rate_per_hour = $10,
                            updated_at = NOW()
                    """, alert.alert_id, alert.error_pattern, alert.first_occurrence,
                    alert.last_occurrence, alert.occurrence_count, alert.severity.value,
                    alert.status.value, alert.escalation_level.value,
                    list(alert.affected_components), alert.error_rate_per_hour,
                    alert.estimated_impact, alert.resolution_suggestions)
            
            # Log alert based on severity
            if alert.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.EMERGENCY]:
                logger.error(f"CRITICAL ALERT: {alert.error_pattern} - {alert.occurrence_count} occurrences")
            elif alert.severity == ErrorSeverity.HIGH:
                logger.warning(f"HIGH ALERT: {alert.error_pattern} - {alert.occurrence_count} occurrences")
            else:
                logger.info(f"ALERT: {alert.error_pattern} - {alert.occurrence_count} occurrences")
                
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")
    
    async def _log_escalation(self, alert: ErrorAlert):
        """Log escalation event"""
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO escalation_logs 
                        (alert_id, escalation_level, escalated_to, notification_method, notification_status)
                        VALUES ($1, $2, $3, $4, $5)
                    """, alert.alert_id, alert.escalation_level.value,
                    self._get_escalation_recipients(alert.escalation_level),
                    "system_log", "logged")
            
            logger.error(f"ESCALATION: Alert {alert.alert_id} escalated to {alert.escalation_level.value}")
            
        except Exception as e:
            logger.error(f"Failed to log escalation: {e}")
    
    def _get_escalation_recipients(self, level: EscalationLevel) -> List[str]:
        """Get escalation recipients based on level"""
        recipients = {
            EscalationLevel.LEVEL_1: ["team@kumon.com"],
            EscalationLevel.LEVEL_2: ["management@kumon.com", "team@kumon.com"],
            EscalationLevel.LEVEL_3: ["executives@kumon.com", "management@kumon.com", "team@kumon.com"]
        }
        return recipients.get(level, [])
    
    async def _update_error_metrics(self, error: ErrorEvent):
        """Update real-time error metrics"""
        try:
            if self.redis_client:
                now = datetime.now(timezone.utc)
                
                # Update real-time error metrics
                metrics = {
                    "last_error_timestamp": now.isoformat(),
                    "last_error_severity": error.severity.value,
                    "last_error_component": error.component,
                    "total_errors_today": await asyncio.to_thread(
                        self.redis_client.get, f"errors:total:{now.date().isoformat()}"
                    ) or 0
                }
                
                await asyncio.to_thread(
                    self.redis_client.hset, "errors:realtime", mapping=metrics
                )
                await asyncio.to_thread(
                    self.redis_client.expire, "errors:realtime", 3600  # 1 hour
                )
                
        except Exception as e:
            logger.error(f"Failed to update error metrics: {e}")
    
    async def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive error summary"""
        try:
            if not self.db_pool:
                return {}
            
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            async with self.db_pool.acquire() as conn:
                # Error statistics
                error_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_errors,
                        COUNT(DISTINCT component) as affected_components,
                        COUNT(DISTINCT error_type) as unique_error_types,
                        COUNT(*) FILTER (WHERE severity = 'critical') as critical_errors,
                        COUNT(*) FILTER (WHERE severity = 'high') as high_errors,
                        COUNT(*) FILTER (WHERE severity = 'medium') as medium_errors,
                        COUNT(*) FILTER (WHERE severity = 'low') as low_errors
                    FROM error_events
                    WHERE timestamp >= $1 AND timestamp <= $2
                """, start_time, end_time)
                
                # Top error patterns
                error_patterns = await conn.fetch("""
                    SELECT 
                        component, error_type, COUNT(*) as count,
                        severity, MAX(timestamp) as last_occurrence
                    FROM error_events
                    WHERE timestamp >= $1 AND timestamp <= $2
                    GROUP BY component, error_type, severity
                    ORDER BY count DESC
                    LIMIT 10
                """, start_time, end_time)
                
                # Active alerts
                active_alerts = await conn.fetch("""
                    SELECT alert_id, error_pattern, severity, status, 
                           escalation_level, occurrence_count, error_rate_per_hour,
                           estimated_impact, first_occurrence, last_occurrence
                    FROM error_alerts
                    WHERE status IN ('active', 'escalated')
                    ORDER BY severity DESC, occurrence_count DESC
                """)
                
                # Hourly error breakdown
                hourly_errors = await conn.fetch("""
                    SELECT 
                        DATE_TRUNC('hour', timestamp) as hour,
                        COUNT(*) as error_count,
                        COUNT(*) FILTER (WHERE severity IN ('critical', 'high')) as critical_count
                    FROM error_events
                    WHERE timestamp >= $1 AND timestamp <= $2
                    GROUP BY DATE_TRUNC('hour', timestamp)
                    ORDER BY hour
                """, start_time, end_time)
            
            # Get real-time metrics
            realtime_metrics = {}
            if self.redis_client:
                metrics_data = await asyncio.to_thread(
                    self.redis_client.hgetall, "errors:realtime"
                )
                realtime_metrics = {k.decode(): v.decode() for k, v in metrics_data.items()} if metrics_data else {}
            
            return {
                "summary": {
                    "analysis_period_hours": hours,
                    "total_errors": error_stats["total_errors"] or 0,
                    "affected_components": error_stats["affected_components"] or 0,
                    "unique_error_types": error_stats["unique_error_types"] or 0,
                    "error_breakdown": {
                        "critical": error_stats["critical_errors"] or 0,
                        "high": error_stats["high_errors"] or 0,
                        "medium": error_stats["medium_errors"] or 0,
                        "low": error_stats["low_errors"] or 0
                    },
                    "error_rate_per_hour": (error_stats["total_errors"] or 0) / max(hours, 1)
                },
                "top_error_patterns": [
                    {
                        "component": row["component"],
                        "error_type": row["error_type"],
                        "count": row["count"],
                        "severity": row["severity"],
                        "last_occurrence": row["last_occurrence"].isoformat()
                    } for row in error_patterns
                ],
                "active_alerts": [
                    {
                        "alert_id": row["alert_id"],
                        "error_pattern": row["error_pattern"],
                        "severity": row["severity"],
                        "status": row["status"],
                        "escalation_level": row["escalation_level"],
                        "occurrence_count": row["occurrence_count"],
                        "error_rate_per_hour": float(row["error_rate_per_hour"]),
                        "estimated_impact": row["estimated_impact"],
                        "first_occurrence": row["first_occurrence"].isoformat(),
                        "last_occurrence": row["last_occurrence"].isoformat()
                    } for row in active_alerts
                ],
                "hourly_breakdown": [
                    {
                        "hour": row["hour"].isoformat(),
                        "error_count": row["error_count"],
                        "critical_count": row["critical_count"]
                    } for row in hourly_errors
                ],
                "realtime_metrics": realtime_metrics,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get error summary: {e}")
            return {}
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an active alert"""
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    result = await conn.execute("""
                        UPDATE error_alerts 
                        SET status = 'acknowledged', 
                            acknowledged_by = $1, 
                            acknowledged_at = NOW(),
                            updated_at = NOW()
                        WHERE alert_id = $2 AND status IN ('active', 'escalated')
                    """, acknowledged_by, alert_id)
                    
                    if result == "UPDATE 1":
                        # Update cache
                        if alert_id in self.alert_cache:
                            self.alert_cache[alert_id].status = AlertStatus.ACKNOWLEDGED
                        
                        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            return False
    
    async def resolve_alert(self, alert_id: str, resolved_by: str) -> bool:
        """Resolve an alert"""
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    result = await conn.execute("""
                        UPDATE error_alerts 
                        SET status = 'resolved', 
                            resolved_at = NOW(),
                            updated_at = NOW()
                        WHERE alert_id = $1 AND status IN ('active', 'acknowledged', 'escalated')
                    """, alert_id)
                    
                    if result == "UPDATE 1":
                        # Update cache
                        if alert_id in self.alert_cache:
                            self.alert_cache[alert_id].status = AlertStatus.RESOLVED
                        
                        logger.info(f"Alert {alert_id} resolved by {resolved_by}")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to resolve alert {alert_id}: {e}")
            return False


# Global error alerting system instance
error_alerting = ErrorAlertingSystem()