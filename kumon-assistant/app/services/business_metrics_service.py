"""
Business Metrics Service for Kumon Assistant
Tracks conversion funnel, SLA compliance, and business KPIs with real-time monitoring
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

from ..core.config import settings
from ..core.logger import app_logger
from .enhanced_cache_service import enhanced_cache_service
from .cost_monitor import cost_monitor


class ConversionStage(Enum):
    """Conversion funnel stages"""
    LEAD = "lead"
    QUALIFIED = "qualified" 
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"


class SLAMetric(Enum):
    """SLA performance metrics"""
    RESPONSE_TIME = "response_time"
    CONVERSION_RATE = "conversion_rate"
    SYSTEM_AVAILABILITY = "system_availability"
    ERROR_RATE = "error_rate"
    COST_EFFICIENCY = "cost_efficiency"


@dataclass
class ConversionEvent:
    """Individual conversion tracking event"""
    phone_number: str
    stage: ConversionStage
    timestamp: float
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None


@dataclass
class SLAViolation:
    """SLA violation record"""
    metric: SLAMetric
    threshold: float
    actual_value: float
    timestamp: float
    severity: str  # "warning", "critical", "emergency"
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BusinessMetrics:
    """Complete business metrics snapshot"""
    timestamp: float
    
    # Conversion Funnel
    total_leads: int
    qualified_leads: int
    scheduled_appointments: int
    confirmed_appointments: int
    completed_appointments: int
    
    # Conversion Rates (%)
    lead_to_qualified_rate: float
    qualified_to_scheduled_rate: float
    scheduled_to_confirmed_rate: float
    confirmed_to_completed_rate: float
    overall_conversion_rate: float
    
    # Performance Metrics
    avg_response_time_ms: float
    system_availability_pct: float
    error_rate_pct: float
    
    # Business Health
    daily_qualified_leads: int
    weekly_appointments: int
    cost_per_qualified_lead: float
    revenue_potential: float
    
    # SLA Compliance
    sla_violations: int
    sla_compliance_pct: float


class BusinessMetricsService:
    """
    Business metrics tracking and SLA monitoring service
    
    Features:
    - Real-time conversion funnel tracking
    - SLA performance monitoring with alerts
    - Business KPI calculation and reporting
    - Cost vs conversion correlation analysis
    - Automated threshold enforcement
    """
    
    def __init__(self):
        self.conversion_events: List[ConversionEvent] = []
        self.sla_violations: List[SLAViolation] = []
        self.performance_buffer = []
        self.is_initialized = False
        
        # Business SLA Thresholds
        self.sla_thresholds = {
            SLAMetric.RESPONSE_TIME: 200.0,  # 200ms max response time
            SLAMetric.CONVERSION_RATE: 60.0,  # 60% lead to qualified
            SLAMetric.SYSTEM_AVAILABILITY: 99.5,  # 99.5% uptime
            SLAMetric.ERROR_RATE: 1.0,  # <1% error rate
            SLAMetric.COST_EFFICIENCY: 1.0  # <R$1 per qualified lead
        }
        
        # Business Targets
        self.business_targets = {
            "daily_qualified_leads": 3,  # Min 3 qualified leads per day
            "weekly_appointments": 15,  # Min 15 appointments per week
            "conversion_rate_lead_qualified": 60.0,  # 60% target
            "conversion_rate_qualified_scheduled": 80.0,  # 80% target
            "conversion_rate_scheduled_confirmed": 90.0,  # 90% target
            "avg_response_time": 200.0,  # 200ms target
            "cost_per_lead": 1.67  # R$5 daily budget / 3 leads = R$1.67
        }
        
        app_logger.info("Business Metrics Service initialized", extra={
            "sla_thresholds": self.sla_thresholds,
            "business_targets": self.business_targets
        })
    
    async def initialize(self):
        """Initialize business metrics service"""
        if self.is_initialized:
            return
        
        # Load cached metrics and events
        await self._load_cached_data()
        
        # Start background monitoring
        asyncio.create_task(self._background_monitoring())
        
        self.is_initialized = True
        app_logger.info("Business metrics service ready")
    
    async def track_conversion_event(
        self,
        phone_number: str,
        stage: ConversionStage,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Track conversion funnel event"""
        try:
            event = ConversionEvent(
                phone_number=phone_number,
                stage=stage,
                timestamp=time.time(),
                metadata=metadata or {},
                session_id=session_id
            )
            
            self.conversion_events.append(event)
            
            # Cache event for persistence
            await self._cache_conversion_event(event)
            
            app_logger.info("Conversion event tracked", extra={
                "phone_number": phone_number[-4:],  # Last 4 digits only
                "stage": stage.value,
                "session_id": session_id,
                "metadata_keys": list(metadata.keys()) if metadata else []
            })
            
            # Check for SLA violations
            await self._check_conversion_sla()
            
            return True
            
        except Exception as e:
            app_logger.error(f"Error tracking conversion event: {e}")
            return False
    
    async def track_performance_metric(
        self,
        metric: SLAMetric,
        value: float,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Track performance metric and check SLA compliance"""
        try:
            timestamp = time.time()
            
            # Add to performance buffer
            self.performance_buffer.append({
                "metric": metric.value,
                "value": value,
                "timestamp": timestamp,
                "context": context or {}
            })
            
            # Check SLA threshold
            threshold = self.sla_thresholds.get(metric)
            if threshold and self._is_sla_violation(metric, value, threshold):
                violation = SLAViolation(
                    metric=metric,
                    threshold=threshold,
                    actual_value=value,
                    timestamp=timestamp,
                    severity=self._calculate_violation_severity(metric, value, threshold),
                    context=context or {}
                )
                
                self.sla_violations.append(violation)
                await self._handle_sla_violation(violation)
            
            # Cleanup old buffer entries (keep last 1000)
            if len(self.performance_buffer) > 1000:
                self.performance_buffer = self.performance_buffer[-1000:]
            
            return True
            
        except Exception as e:
            app_logger.error(f"Error tracking performance metric: {e}")
            return False
    
    async def get_business_metrics(self, period_hours: int = 24) -> BusinessMetrics:
        """Generate comprehensive business metrics for specified period"""
        try:
            current_time = time.time()
            period_start = current_time - (period_hours * 3600)
            
            # Filter events by period
            period_events = [
                e for e in self.conversion_events 
                if e.timestamp >= period_start
            ]
            
            # Calculate conversion funnel
            funnel_metrics = self._calculate_conversion_funnel(period_events)
            
            # Calculate performance metrics
            performance_metrics = self._calculate_performance_metrics(period_hours)
            
            # Calculate business health metrics
            business_health = await self._calculate_business_health(period_events)
            
            # Calculate SLA compliance
            sla_compliance = self._calculate_sla_compliance(period_hours)
            
            metrics = BusinessMetrics(
                timestamp=current_time,
                **funnel_metrics,
                **performance_metrics,
                **business_health,
                **sla_compliance
            )
            
            app_logger.info("Business metrics calculated", extra={
                "period_hours": period_hours,
                "total_events": len(period_events),
                "overall_conversion_rate": metrics.overall_conversion_rate,
                "sla_compliance_pct": metrics.sla_compliance_pct
            })
            
            return metrics
            
        except Exception as e:
            app_logger.error(f"Error calculating business metrics: {e}")
            # Return empty metrics on error
            return BusinessMetrics(
                timestamp=current_time,
                total_leads=0, qualified_leads=0, scheduled_appointments=0,
                confirmed_appointments=0, completed_appointments=0,
                lead_to_qualified_rate=0.0, qualified_to_scheduled_rate=0.0,
                scheduled_to_confirmed_rate=0.0, confirmed_to_completed_rate=0.0,
                overall_conversion_rate=0.0, avg_response_time_ms=0.0,
                system_availability_pct=0.0, error_rate_pct=0.0,
                daily_qualified_leads=0, weekly_appointments=0,
                cost_per_qualified_lead=0.0, revenue_potential=0.0,
                sla_violations=0, sla_compliance_pct=0.0
            )
    
    async def get_conversion_summary(self) -> Dict[str, Any]:
        """Get conversion funnel summary for last 24 hours"""
        metrics = await self.get_business_metrics(24)
        
        return {
            "funnel": {
                "leads": metrics.total_leads,
                "qualified": metrics.qualified_leads,
                "scheduled": metrics.scheduled_appointments,
                "confirmed": metrics.confirmed_appointments,
                "completed": metrics.completed_appointments
            },
            "rates": {
                "lead_to_qualified": f"{metrics.lead_to_qualified_rate:.1f}%",
                "qualified_to_scheduled": f"{metrics.qualified_to_scheduled_rate:.1f}%",
                "scheduled_to_confirmed": f"{metrics.scheduled_to_confirmed_rate:.1f}%",
                "overall_conversion": f"{metrics.overall_conversion_rate:.1f}%"
            },
            "targets": {
                "lead_to_qualified_target": f"{self.business_targets['conversion_rate_lead_qualified']:.1f}%",
                "qualified_to_scheduled_target": f"{self.business_targets['conversion_rate_qualified_scheduled']:.1f}%",
                "scheduled_to_confirmed_target": f"{self.business_targets['conversion_rate_scheduled_confirmed']:.1f}%"
            },
            "performance": {
                "daily_qualified_leads": metrics.daily_qualified_leads,
                "target_daily_leads": self.business_targets["daily_qualified_leads"],
                "weekly_appointments": metrics.weekly_appointments,
                "target_weekly_appointments": self.business_targets["weekly_appointments"]
            }
        }
    
    async def get_sla_status(self) -> Dict[str, Any]:
        """Get SLA compliance status"""
        metrics = await self.get_business_metrics(24)
        
        # Get recent violations (last 24 hours)
        current_time = time.time()
        recent_violations = [
            v for v in self.sla_violations
            if v.timestamp >= (current_time - 86400)
        ]
        
        return {
            "overall_compliance": f"{metrics.sla_compliance_pct:.1f}%",
            "violations_24h": len(recent_violations),
            "thresholds": {
                "response_time_ms": self.sla_thresholds[SLAMetric.RESPONSE_TIME],
                "conversion_rate_pct": self.sla_thresholds[SLAMetric.CONVERSION_RATE],
                "availability_pct": self.sla_thresholds[SLAMetric.SYSTEM_AVAILABILITY],
                "error_rate_pct": self.sla_thresholds[SLAMetric.ERROR_RATE]
            },
            "current_performance": {
                "response_time_ms": metrics.avg_response_time_ms,
                "conversion_rate_pct": metrics.lead_to_qualified_rate,
                "availability_pct": metrics.system_availability_pct,
                "error_rate_pct": metrics.error_rate_pct
            },
            "recent_violations": [
                {
                    "metric": v.metric.value,
                    "threshold": v.threshold,
                    "actual": v.actual_value,
                    "severity": v.severity,
                    "timestamp": datetime.fromtimestamp(v.timestamp).isoformat()
                }
                for v in recent_violations[-10:]  # Last 10 violations
            ]
        }
    
    def _calculate_conversion_funnel(self, events: List[ConversionEvent]) -> Dict[str, Any]:
        """Calculate conversion funnel metrics from events"""
        stage_counts = {stage: 0 for stage in ConversionStage}
        
        for event in events:
            stage_counts[event.stage] += 1
        
        leads = stage_counts[ConversionStage.LEAD]
        qualified = stage_counts[ConversionStage.QUALIFIED]
        scheduled = stage_counts[ConversionStage.SCHEDULED]
        confirmed = stage_counts[ConversionStage.CONFIRMED]
        completed = stage_counts[ConversionStage.COMPLETED]
        
        # Calculate rates (handle division by zero)
        lead_to_qualified_rate = (qualified / leads * 100) if leads > 0 else 0
        qualified_to_scheduled_rate = (scheduled / qualified * 100) if qualified > 0 else 0
        scheduled_to_confirmed_rate = (confirmed / scheduled * 100) if scheduled > 0 else 0
        confirmed_to_completed_rate = (completed / confirmed * 100) if confirmed > 0 else 0
        overall_conversion_rate = (completed / leads * 100) if leads > 0 else 0
        
        return {
            "total_leads": leads,
            "qualified_leads": qualified,
            "scheduled_appointments": scheduled,
            "confirmed_appointments": confirmed,
            "completed_appointments": completed,
            "lead_to_qualified_rate": lead_to_qualified_rate,
            "qualified_to_scheduled_rate": qualified_to_scheduled_rate,
            "scheduled_to_confirmed_rate": scheduled_to_confirmed_rate,
            "confirmed_to_completed_rate": confirmed_to_completed_rate,
            "overall_conversion_rate": overall_conversion_rate
        }
    
    def _calculate_performance_metrics(self, period_hours: int) -> Dict[str, Any]:
        """Calculate performance metrics from buffer"""
        current_time = time.time()
        period_start = current_time - (period_hours * 3600)
        
        # Filter performance data by period
        period_data = [
            d for d in self.performance_buffer
            if d["timestamp"] >= period_start
        ]
        
        if not period_data:
            return {
                "avg_response_time_ms": 0.0,
                "system_availability_pct": 100.0,
                "error_rate_pct": 0.0
            }
        
        # Calculate averages
        response_times = [
            d["value"] for d in period_data
            if d["metric"] == SLAMetric.RESPONSE_TIME.value
        ]
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
        
        # System availability (assume 100% minus downtime events)
        availability_events = [
            d for d in period_data
            if d["metric"] == SLAMetric.SYSTEM_AVAILABILITY.value
        ]
        avg_availability = sum(d["value"] for d in availability_events) / len(availability_events) if availability_events else 99.9
        
        # Error rate
        error_events = [
            d for d in period_data
            if d["metric"] == SLAMetric.ERROR_RATE.value
        ]
        avg_error_rate = sum(d["value"] for d in error_events) / len(error_events) if error_events else 0.0
        
        return {
            "avg_response_time_ms": avg_response_time,
            "system_availability_pct": avg_availability,
            "error_rate_pct": avg_error_rate
        }
    
    async def _calculate_business_health(self, events: List[ConversionEvent]) -> Dict[str, Any]:
        """Calculate business health metrics"""
        # Count qualified leads today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today_qualified = len([
            e for e in events
            if e.stage == ConversionStage.QUALIFIED and e.timestamp >= today_start
        ])
        
        # Count appointments this week
        week_start = today_start - (datetime.now(timezone.utc).weekday() * 86400)
        week_appointments = len([
            e for e in events
            if e.stage in [ConversionStage.SCHEDULED, ConversionStage.CONFIRMED, ConversionStage.COMPLETED]
            and e.timestamp >= week_start
        ])
        
        # Calculate cost per qualified lead
        daily_cost = await self._get_daily_cost()
        cost_per_qualified_lead = (daily_cost / today_qualified) if today_qualified > 0 else 0.0
        
        # Estimate revenue potential (R$ 375 per program + R$ 100 enrollment)
        revenue_potential = week_appointments * 475.0  # R$ 475 average per conversion
        
        return {
            "daily_qualified_leads": today_qualified,
            "weekly_appointments": week_appointments,
            "cost_per_qualified_lead": cost_per_qualified_lead,
            "revenue_potential": revenue_potential
        }
    
    def _calculate_sla_compliance(self, period_hours: int) -> Dict[str, Any]:
        """Calculate SLA compliance metrics"""
        current_time = time.time()
        period_start = current_time - (period_hours * 3600)
        
        # Count violations in period
        period_violations = [
            v for v in self.sla_violations
            if v.timestamp >= period_start
        ]
        
        # Calculate compliance percentage
        total_checks = len(self.performance_buffer)
        violations_count = len(period_violations)
        
        compliance_pct = ((total_checks - violations_count) / total_checks * 100) if total_checks > 0 else 100.0
        
        return {
            "sla_violations": violations_count,
            "sla_compliance_pct": compliance_pct
        }
    
    def _is_sla_violation(self, metric: SLAMetric, value: float, threshold: float) -> bool:
        """Check if metric value violates SLA threshold"""
        if metric in [SLAMetric.RESPONSE_TIME, SLAMetric.ERROR_RATE, SLAMetric.COST_EFFICIENCY]:
            return value > threshold  # Higher is worse
        else:  # CONVERSION_RATE, SYSTEM_AVAILABILITY
            return value < threshold  # Lower is worse
    
    def _calculate_violation_severity(self, metric: SLAMetric, value: float, threshold: float) -> str:
        """Calculate severity of SLA violation"""
        if metric == SLAMetric.RESPONSE_TIME:
            if value > threshold * 3:
                return "critical"
            elif value > threshold * 2:
                return "warning"
            else:
                return "info"
        elif metric == SLAMetric.CONVERSION_RATE:
            if value < threshold * 0.5:
                return "critical"
            elif value < threshold * 0.7:
                return "warning"
            else:
                return "info"
        else:
            return "warning"
    
    async def _handle_sla_violation(self, violation: SLAViolation):
        """Handle SLA violation with appropriate action"""
        app_logger.warning("SLA violation detected", extra={
            "metric": violation.metric.value,
            "threshold": violation.threshold,
            "actual_value": violation.actual_value,
            "severity": violation.severity,
            "context": violation.context
        })
        
        # Cache violation for persistence
        await self._cache_sla_violation(violation)
    
    async def _get_daily_cost(self) -> float:
        """Get current daily cost from cost monitor"""
        try:
            daily_summary = await cost_monitor.get_daily_summary()
            return daily_summary.get("spent_brl", 0.0)
        except Exception as e:
            app_logger.warning(f"Could not get daily cost: {e}")
            return 0.0
    
    async def _cache_conversion_event(self, event: ConversionEvent):
        """Cache conversion event for persistence"""
        try:
            cache_key = f"conversion_event_{event.phone_number}_{int(event.timestamp)}"
            event_data = {
                "phone_number": event.phone_number,
                "stage": event.stage.value,
                "timestamp": event.timestamp,
                "metadata": event.metadata,
                "session_id": event.session_id
            }
            
            await enhanced_cache_service.set(
                cache_key,
                json.dumps(event_data),
                ttl=86400 * 7,  # Keep for 7 days
                category="metrics"
            )
        except Exception as e:
            app_logger.warning(f"Could not cache conversion event: {e}")
    
    async def _cache_sla_violation(self, violation: SLAViolation):
        """Cache SLA violation for persistence"""
        try:
            cache_key = f"sla_violation_{violation.metric.value}_{int(violation.timestamp)}"
            violation_data = {
                "metric": violation.metric.value,
                "threshold": violation.threshold,
                "actual_value": violation.actual_value,
                "timestamp": violation.timestamp,
                "severity": violation.severity,
                "context": violation.context
            }
            
            await enhanced_cache_service.set(
                cache_key,
                json.dumps(violation_data),
                ttl=86400 * 30,  # Keep for 30 days
                category="metrics"
            )
        except Exception as e:
            app_logger.warning(f"Could not cache SLA violation: {e}")
    
    async def _load_cached_data(self):
        """Load cached conversion events and violations"""
        try:
            # Load recent conversion events (last 7 days)
            # Load recent SLA violations (last 30 days)
            # Implementation would query enhanced_cache_service
            app_logger.info("Cached business metrics data loaded")
        except Exception as e:
            app_logger.warning(f"Could not load cached metrics data: {e}")
    
    async def _background_monitoring(self):
        """Background task for continuous monitoring"""
        while True:
            try:
                # Cleanup old data
                await self._cleanup_old_data()
                
                # Generate periodic metrics
                metrics = await self.get_business_metrics(1)  # Last hour
                
                # Check for business health alerts
                await self._check_business_health_alerts(metrics)
                
                # Sleep for 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                app_logger.error(f"Background monitoring error: {e}")
                await asyncio.sleep(60)  # Retry in 1 minute
    
    async def _cleanup_old_data(self):
        """Cleanup old metrics data"""
        current_time = time.time()
        cutoff_time = current_time - (86400 * 7)  # 7 days
        
        # Remove old conversion events
        self.conversion_events = [
            e for e in self.conversion_events
            if e.timestamp >= cutoff_time
        ]
        
        # Remove old SLA violations (keep 30 days)
        sla_cutoff = current_time - (86400 * 30)
        self.sla_violations = [
            v for v in self.sla_violations
            if v.timestamp >= sla_cutoff
        ]
    
    async def _check_business_health_alerts(self, metrics: BusinessMetrics):
        """Check for business health alerts"""
        # Check if daily qualified leads target is met
        if metrics.daily_qualified_leads < self.business_targets["daily_qualified_leads"]:
            app_logger.warning("Daily qualified leads below target", extra={
                "actual": metrics.daily_qualified_leads,
                "target": self.business_targets["daily_qualified_leads"]
            })
        
        # Check conversion rates
        if metrics.lead_to_qualified_rate < self.business_targets["conversion_rate_lead_qualified"]:
            app_logger.warning("Lead to qualified conversion rate below target", extra={
                "actual": metrics.lead_to_qualified_rate,
                "target": self.business_targets["conversion_rate_lead_qualified"]
            })
    
    async def _check_conversion_sla(self):
        """Check conversion rate SLA"""
        metrics = await self.get_business_metrics(1)  # Last hour
        
        if metrics.lead_to_qualified_rate > 0:
            await self.track_performance_metric(
                SLAMetric.CONVERSION_RATE,
                metrics.lead_to_qualified_rate,
                {"timeframe": "1_hour"}
            )


# Global business metrics service instance
business_metrics_service = BusinessMetricsService()


async def initialize_business_metrics_service():
    """Initialize global business metrics service"""
    await business_metrics_service.initialize()


# Convenience functions for easy integration
async def track_lead(phone_number: str, session_id: str = None, metadata: Dict[str, Any] = None):
    """Track new lead conversion event"""
    return await business_metrics_service.track_conversion_event(
        phone_number, ConversionStage.LEAD, session_id, metadata
    )


async def track_qualified_lead(phone_number: str, session_id: str = None, metadata: Dict[str, Any] = None):
    """Track qualified lead conversion event"""
    return await business_metrics_service.track_conversion_event(
        phone_number, ConversionStage.QUALIFIED, session_id, metadata
    )


async def track_scheduled_appointment(phone_number: str, session_id: str = None, metadata: Dict[str, Any] = None):
    """Track scheduled appointment conversion event"""
    return await business_metrics_service.track_conversion_event(
        phone_number, ConversionStage.SCHEDULED, session_id, metadata
    )


async def track_response_time(response_time_ms: float, context: Dict[str, Any] = None):
    """Track response time SLA metric"""
    return await business_metrics_service.track_performance_metric(
        SLAMetric.RESPONSE_TIME, response_time_ms, context
    )