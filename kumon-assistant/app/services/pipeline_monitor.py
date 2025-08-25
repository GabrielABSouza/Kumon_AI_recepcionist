"""
Pipeline Performance Monitor - Real-time pipeline monitoring and bottleneck identification
Implements comprehensive monitoring with alerting and performance optimization suggestions

Performance Targets:
- Pipeline monitoring: <50ms overhead
- Alert generation: <100ms
- Performance analysis: <200ms
- SLA tracking: <3s response time compliance >95%
"""

import asyncio
import json
import statistics
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..core.config import settings
from ..core.logger import app_logger
from ..core.pipeline_orchestrator import PipelineStage, PipelineStatus
from ..services.enhanced_cache_service import CacheLayer, enhanced_cache_service


class AlertLevel(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """Performance metric types"""

    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    CACHE_HIT_RATE = "cache_hit_rate"
    CIRCUIT_BREAKER = "circuit_breaker"
    SLA_COMPLIANCE = "sla_compliance"


@dataclass
class PerformanceAlert:
    """Performance alert data structure"""

    alert_id: str
    level: AlertLevel
    metric_type: MetricType
    message: str
    current_value: float
    threshold_value: float
    phone_number: Optional[str] = None
    stage: Optional[str] = None
    timestamp: Optional[datetime] = None
    resolved: bool = False

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class StageMetrics:
    """Pipeline stage performance metrics"""

    stage: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    error_rate: float = 0.0
    circuit_breaker_triggers: int = 0
    recent_durations: Optional[deque] = None

    def __post_init__(self):
        if self.recent_durations is None:
            self.recent_durations = deque(maxlen=100)  # Keep last 100 measurements


@dataclass
class PipelineHealthReport:
    """Comprehensive pipeline health report"""

    timestamp: datetime
    overall_health_score: float
    sla_compliance_rate: float
    avg_response_time_ms: float
    error_rate: float
    throughput_per_minute: float
    cache_hit_rate: float
    stage_metrics: Dict[str, StageMetrics]
    bottlenecks: List[Dict[str, Any]]
    active_alerts: List[PerformanceAlert]
    recommendations: List[str]


class BottleneckAnalyzer:
    """Analyzes pipeline performance to identify bottlenecks"""

    def __init__(self):
        self.analysis_cache_ttl = 60  # 1 minute

    async def analyze_bottlenecks(
        self, stage_metrics: Dict[str, StageMetrics], target_total_time_ms: float = 3000
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Analyze pipeline stages to identify bottlenecks and generate recommendations

        Args:
            stage_metrics: Performance metrics for each pipeline stage
            target_total_time_ms: Target total pipeline execution time

        Returns:
            Tuple of (bottlenecks_list, recommendations_list)
        """
        bottlenecks: List[str] = []
        recommendations: List[str] = []

        try:
            # Calculate total average time
            total_avg_time = sum(
                metrics.avg_duration_ms
                for metrics in stage_metrics.values()
                if metrics.total_executions > 0
            )

            if total_avg_time == 0:
                return bottlenecks, recommendations

            # Identify bottlenecks (stages taking >20% of total time or >500ms)
            for stage_name, metrics in stage_metrics.items():
                if metrics.total_executions == 0:
                    continue

                time_percentage = (metrics.avg_duration_ms / total_avg_time) * 100
                is_bottleneck = time_percentage > 20 or metrics.avg_duration_ms > 500

                if is_bottleneck:
                    bottleneck_severity = "critical" if metrics.avg_duration_ms > 1000 else "high"

                    bottlenecks.append(
                        {
                            "stage": stage_name,
                            "avg_duration_ms": metrics.avg_duration_ms,
                            "time_percentage": time_percentage,
                            "error_rate": metrics.error_rate,
                            "severity": bottleneck_severity,
                            "p95_duration_ms": metrics.p95_duration_ms,
                            "circuit_breaker_triggers": metrics.circuit_breaker_triggers,
                        }
                    )

                    # Generate stage-specific recommendations
                    stage_recommendations = self._generate_stage_recommendations(
                        stage_name, metrics
                    )
                    recommendations.extend(stage_recommendations)

            # Generate system-wide recommendations
            system_recommendations = self._generate_system_recommendations(
                stage_metrics, total_avg_time, target_total_time_ms
            )
            recommendations.extend(system_recommendations)

            app_logger.info(f"Bottleneck analysis completed: {len(bottlenecks)} bottlenecks found")
            return bottlenecks, recommendations

        except Exception as e:
            app_logger.error(f"Bottleneck analysis error: {e}")
            return [], []

    def _generate_stage_recommendations(self, stage_name: str, metrics: StageMetrics) -> List[str]:
        """Generate recommendations for specific pipeline stage"""
        recommendations = []

        if stage_name == "preprocessing":
            if metrics.avg_duration_ms > 200:
                recommendations.append(
                    "Optimize preprocessing: Consider caching sanitization patterns "
                    "and implementing parallel validation checks"
                )
            if metrics.error_rate > 5:
                recommendations.append(
                    "Preprocessing error rate high: Review input validation logic "
                    "and add better error handling for edge cases"
                )

        elif stage_name == "business_rules":
            if metrics.avg_duration_ms > 150:
                recommendations.append(
                    "Business rules taking too long: Implement rule result caching "
                    "and optimize qualification data extraction patterns"
                )

        elif stage_name == "langgraph_workflow":
            if metrics.avg_duration_ms > 2000:
                recommendations.append(
                    "LangGraph workflow is primary bottleneck: Consider prompt "
                    "optimization, response caching, and model fine-tuning"
                )
            if metrics.circuit_breaker_triggers > 0:
                recommendations.append(
                    "LangGraph circuit breaker triggering: Investigate model "
                    "timeout issues and implement better fallback mechanisms"
                )

        elif stage_name == "postprocessing":
            if metrics.avg_duration_ms > 300:
                recommendations.append(
                    "Postprocessing bottleneck: Optimize template rendering "
                    "and calendar integration with better caching strategies"
                )

        elif stage_name == "delivery":
            if metrics.error_rate > 10:
                recommendations.append(
                    "High delivery error rate: Review Evolution API connectivity "
                    "and implement more robust retry mechanisms"
                )

        return recommendations

    def _generate_system_recommendations(
        self, stage_metrics: Dict[str, StageMetrics], total_avg_time: float, target_time: float
    ) -> List[str]:
        """Generate system-wide performance recommendations"""
        recommendations = []

        # Check if total time exceeds SLA
        if total_avg_time > target_time:
            excess_time = total_avg_time - target_time
            recommendations.append(
                f"Pipeline exceeding SLA by {excess_time:.0f}ms: Prioritize "
                f"optimization of slowest stages and implement parallel processing"
            )

        # Check overall error rates
        total_errors = sum(metrics.failed_executions for metrics in stage_metrics.values())
        total_executions = sum(metrics.total_executions for metrics in stage_metrics.values())

        if total_executions > 0:
            overall_error_rate = (total_errors / total_executions) * 100
            if overall_error_rate > 1:
                recommendations.append(
                    f"Overall error rate {overall_error_rate:.1f}% exceeds target 1%: "
                    f"Implement comprehensive error recovery and circuit breaker tuning"
                )

        # Check for cache optimization opportunities
        cache_enabled_stages = ["preprocessing", "business_rules", "postprocessing"]
        for stage_name in cache_enabled_stages:
            if stage_name in stage_metrics:
                metrics = stage_metrics[stage_name]
                if metrics.avg_duration_ms > 100:
                    recommendations.append(
                        f"Consider aggressive caching for {stage_name} stage "
                        f"to reduce {metrics.avg_duration_ms:.0f}ms average duration"
                    )

        return recommendations


class PipelineMonitor:
    """
    Real-time pipeline performance monitor with alerting and bottleneck identification

    Features:
    - Real-time performance tracking
    - SLA compliance monitoring (<3s response time)
    - Bottleneck identification and recommendations
    - Alert generation and management
    - Performance trend analysis
    - Auto-scaling recommendations
    """

    def __init__(self):
        # Performance tracking
        self.stage_metrics: Dict[str, StageMetrics] = {}
        self.alert_history: List[PerformanceAlert] = []
        self.active_alerts: Dict[str, PerformanceAlert] = {}

        # Monitoring configuration
        self.monitoring_config = {
            "sla_target_ms": 3000,
            "error_rate_threshold": 1.0,  # 1%
            "cache_hit_rate_threshold": 80.0,  # 80%
            "circuit_breaker_threshold": 3,
            "alert_cooldown_seconds": 300,  # 5 minutes
            "metrics_retention_hours": 24,
        }

        # Performance thresholds per stage
        self.stage_thresholds = {
            "preprocessing": {"max_duration_ms": 200, "error_rate": 2.0},
            "business_rules": {"max_duration_ms": 150, "error_rate": 1.0},
            "langgraph_workflow": {"max_duration_ms": 2000, "error_rate": 5.0},
            "postprocessing": {"max_duration_ms": 300, "error_rate": 2.0},
            "delivery": {"max_duration_ms": 500, "error_rate": 10.0},
        }

        # Initialize bottleneck analyzer
        self.bottleneck_analyzer = BottleneckAnalyzer()

        # Metrics collection
        self.metrics_collection_enabled = True
        self.last_health_check = datetime.now()

        app_logger.info(
            "Pipeline Monitor initialized successfully",
            extra={
                "sla_target_ms": self.monitoring_config["sla_target_ms"],
                "error_rate_threshold": self.monitoring_config["error_rate_threshold"],
                "monitoring_enabled": True,
            },
        )

    async def record_pipeline_execution(
        self,
        execution_id: str,
        phone_number: str,
        stage_results: Dict[str, Dict[str, Any]],
        total_duration_ms: float,
        status: PipelineStatus,
        errors: Optional[List[str]] = None,
    ):
        """
        Record pipeline execution metrics and trigger alerts if needed

        Args:
            execution_id: Pipeline execution ID
            phone_number: Phone number being processed
            stage_results: Results from each pipeline stage
            total_duration_ms: Total pipeline execution time
            status: Final pipeline status
            errors: List of errors encountered
        """
        if not self.metrics_collection_enabled:
            return

        try:
            # Update stage metrics
            for stage_name, stage_result in stage_results.items():
                await self._update_stage_metrics(
                    stage_name, stage_result, status == PipelineStatus.COMPLETED
                )

            # Check for SLA violation
            if total_duration_ms > self.monitoring_config["sla_target_ms"]:
                await self._generate_alert(
                    AlertLevel.WARNING,
                    MetricType.SLA_COMPLIANCE,
                    f"SLA violation: {total_duration_ms:.0f}ms > {self.monitoring_config['sla_target_ms']}ms",
                    total_duration_ms,
                    self.monitoring_config["sla_target_ms"],
                    phone_number=phone_number,
                )

            # Check for high error rates
            if errors and len(errors) > 0:
                await self._generate_alert(
                    AlertLevel.ERROR,
                    MetricType.ERROR_RATE,
                    f"Pipeline execution failed with {len(errors)} errors",
                    len(errors),
                    0,
                    phone_number=phone_number,
                )

            # Perform periodic bottleneck analysis
            if self._should_perform_analysis():
                await self._perform_bottleneck_analysis()

            app_logger.debug(f"Recorded pipeline execution metrics for {execution_id}")

        except Exception as e:
            app_logger.error(f"Error recording pipeline metrics: {e}")

    async def _update_stage_metrics(
        self, stage_name: str, stage_result: Dict[str, Any], success: bool
    ):
        """Update metrics for a specific pipeline stage"""
        if stage_name not in self.stage_metrics:
            self.stage_metrics[stage_name] = StageMetrics(stage=stage_name)

        metrics = self.stage_metrics[stage_name]

        # Update execution counts
        metrics.total_executions += 1
        if success:
            metrics.successful_executions += 1
        else:
            metrics.failed_executions += 1

        # Update duration metrics
        duration_ms = stage_result.get("processing_time_ms", 0) or stage_result.get(
            "duration_ms", 0
        )
        if duration_ms > 0:
            metrics.recent_durations.append(duration_ms)

            # Update min/max
            metrics.min_duration_ms = min(metrics.min_duration_ms, duration_ms)
            metrics.max_duration_ms = max(metrics.max_duration_ms, duration_ms)

            # Calculate rolling average
            if len(metrics.recent_durations) > 0:
                metrics.avg_duration_ms = statistics.mean(metrics.recent_durations)

                # Calculate percentiles
                sorted_durations = sorted(metrics.recent_durations)
                if len(sorted_durations) >= 20:  # Only calculate percentiles with sufficient data
                    metrics.p95_duration_ms = sorted_durations[int(len(sorted_durations) * 0.95)]
                    metrics.p99_duration_ms = sorted_durations[int(len(sorted_durations) * 0.99)]

        # Update error rate
        metrics.error_rate = (metrics.failed_executions / metrics.total_executions) * 100

        # Update circuit breaker triggers
        if stage_result.get("circuit_breaker_open", False):
            metrics.circuit_breaker_triggers += 1

        # Check stage-specific thresholds
        await self._check_stage_thresholds(stage_name, metrics)

    async def _check_stage_thresholds(self, stage_name: str, metrics: StageMetrics):
        """Check if stage metrics exceed thresholds and generate alerts"""
        if stage_name not in self.stage_thresholds:
            return

        thresholds = self.stage_thresholds[stage_name]

        # Check duration threshold
        if metrics.avg_duration_ms > thresholds["max_duration_ms"]:
            await self._generate_alert(
                AlertLevel.WARNING,
                MetricType.RESPONSE_TIME,
                f"Stage {stage_name} average duration {metrics.avg_duration_ms:.0f}ms exceeds threshold {thresholds['max_duration_ms']}ms",
                metrics.avg_duration_ms,
                thresholds["max_duration_ms"],
                stage=stage_name,
            )

        # Check error rate threshold
        if metrics.error_rate > thresholds["error_rate"]:
            await self._generate_alert(
                AlertLevel.ERROR,
                MetricType.ERROR_RATE,
                f"Stage {stage_name} error rate {metrics.error_rate:.1f}% exceeds threshold {thresholds['error_rate']}%",
                metrics.error_rate,
                thresholds["error_rate"],
                stage=stage_name,
            )

        # Check circuit breaker triggers
        if metrics.circuit_breaker_triggers > self.monitoring_config["circuit_breaker_threshold"]:
            await self._generate_alert(
                AlertLevel.CRITICAL,
                MetricType.CIRCUIT_BREAKER,
                f"Stage {stage_name} circuit breaker triggered {metrics.circuit_breaker_triggers} times",
                metrics.circuit_breaker_triggers,
                self.monitoring_config["circuit_breaker_threshold"],
                stage=stage_name,
            )

    async def _generate_alert(
        self,
        level: AlertLevel,
        metric_type: MetricType,
        message: str,
        current_value: float,
        threshold_value: float,
        phone_number: Optional[str] = None,
        stage: Optional[str] = None,
    ):
        """Generate and store performance alert"""
        try:
            # Create alert ID
            alert_key = f"{metric_type.value}:{stage or 'system'}:{phone_number or 'all'}"

            # Check cooldown period to avoid alert spam
            if alert_key in self.active_alerts:
                last_alert_time = self.active_alerts[alert_key].timestamp
                if (datetime.now() - last_alert_time).total_seconds() < self.monitoring_config[
                    "alert_cooldown_seconds"
                ]:
                    return  # Skip alert due to cooldown

            # Create new alert
            alert = PerformanceAlert(
                alert_id=f"{alert_key}:{int(time.time())}",
                level=level,
                metric_type=metric_type,
                message=message,
                current_value=current_value,
                threshold_value=threshold_value,
                phone_number=phone_number,
                stage=stage,
            )

            # Store alert
            self.active_alerts[alert_key] = alert
            self.alert_history.append(alert)

            # Log alert
            app_logger.warning(
                f"Performance Alert [{level.value.upper()}]: {message}",
                extra={
                    "alert_id": alert.alert_id,
                    "metric_type": metric_type.value,
                    "current_value": current_value,
                    "threshold_value": threshold_value,
                    "phone_number": phone_number,
                    "stage": stage,
                },
            )

            # Cache alert for external access
            await enhanced_cache_service.set(
                f"alert:{alert.alert_id}",
                json.dumps(asdict(alert), default=str),
                CacheLayer.L2,
                ttl=3600,
            )

        except Exception as e:
            app_logger.error(f"Error generating alert: {e}")

    def _should_perform_analysis(self) -> bool:
        """Determine if bottleneck analysis should be performed"""
        # Perform analysis every 5 minutes or after 100 executions
        time_since_last = (datetime.now() - self.last_health_check).total_seconds()

        total_executions = sum(metrics.total_executions for metrics in self.stage_metrics.values())

        return time_since_last > 300 or total_executions % 100 == 0

    async def _perform_bottleneck_analysis(self):
        """Perform comprehensive bottleneck analysis"""
        try:
            app_logger.info("Performing bottleneck analysis")

            bottlenecks, recommendations = await self.bottleneck_analyzer.analyze_bottlenecks(
                self.stage_metrics, self.monitoring_config["sla_target_ms"]
            )

            # Generate alerts for critical bottlenecks
            for bottleneck in bottlenecks:
                if bottleneck["severity"] == "critical":
                    await self._generate_alert(
                        AlertLevel.CRITICAL,
                        MetricType.RESPONSE_TIME,
                        f"Critical bottleneck in {bottleneck['stage']}: {bottleneck['avg_duration_ms']:.0f}ms average",
                        bottleneck["avg_duration_ms"],
                        500,  # Critical threshold
                        stage=bottleneck["stage"],
                    )

            # Cache analysis results
            analysis_result = {
                "timestamp": datetime.now().isoformat(),
                "bottlenecks": bottlenecks,
                "recommendations": recommendations,
            }

            await enhanced_cache_service.set(
                "bottleneck_analysis",
                json.dumps(analysis_result),
                CacheLayer.L2,
                ttl=300,  # 5 minutes
            )

            self.last_health_check = datetime.now()

            app_logger.info(
                f"Bottleneck analysis completed: {len(bottlenecks)} bottlenecks, {len(recommendations)} recommendations"
            )

        except Exception as e:
            app_logger.error(f"Bottleneck analysis error: {e}")

    async def get_pipeline_health_report(self) -> PipelineHealthReport:
        """Generate comprehensive pipeline health report"""
        try:
            # Calculate overall metrics
            total_executions = sum(
                metrics.total_executions for metrics in self.stage_metrics.values()
            )
            total_successful = sum(
                metrics.successful_executions for metrics in self.stage_metrics.values()
            )
            total_avg_time = sum(
                metrics.avg_duration_ms
                for metrics in self.stage_metrics.values()
                if metrics.total_executions > 0
            )

            # Calculate rates
            success_rate = (total_successful / max(1, total_executions)) * 100
            error_rate = ((total_executions - total_successful) / max(1, total_executions)) * 100
            sla_compliance_rate = success_rate  # Simplified for now

            # Calculate health score (weighted combination of metrics)
            health_score = (
                (success_rate * 0.4)
                + (
                    min(
                        100,
                        (self.monitoring_config["sla_target_ms"] / max(1, total_avg_time)) * 100,
                    )
                    * 0.3
                )
                + (min(100, self.monitoring_config["cache_hit_rate_threshold"]) * 0.2)
                + (max(0, 100 - len(self.active_alerts) * 10) * 0.1)
            )

            # Get bottleneck analysis
            bottlenecks, recommendations = await self.bottleneck_analyzer.analyze_bottlenecks(
                self.stage_metrics
            )

            # Get active alerts
            active_alerts = list(self.active_alerts.values())

            return PipelineHealthReport(
                timestamp=datetime.now(),
                overall_health_score=round(health_score, 1),
                sla_compliance_rate=round(sla_compliance_rate, 1),
                avg_response_time_ms=round(total_avg_time, 1),
                error_rate=round(error_rate, 2),
                throughput_per_minute=0.0,  # Would need time-window calculation
                cache_hit_rate=0.0,  # Would need integration with cache service
                stage_metrics=self.stage_metrics.copy(),
                bottlenecks=bottlenecks,
                active_alerts=active_alerts,
                recommendations=recommendations,
            )

        except Exception as e:
            app_logger.error(f"Error generating health report: {e}")
            return PipelineHealthReport(
                timestamp=datetime.now(),
                overall_health_score=0.0,
                sla_compliance_rate=0.0,
                avg_response_time_ms=0.0,
                error_rate=100.0,
                throughput_per_minute=0.0,
                cache_hit_rate=0.0,
                stage_metrics={},
                bottlenecks=[],
                active_alerts=[],
                recommendations=["Health report generation failed - check monitor logs"],
            )

    async def get_stage_metrics(self, stage_name: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for specific stage or all stages"""
        if stage_name:
            if stage_name in self.stage_metrics:
                metrics = self.stage_metrics[stage_name]
                return {
                    "stage": stage_name,
                    "total_executions": metrics.total_executions,
                    "successful_executions": metrics.successful_executions,
                    "failed_executions": metrics.failed_executions,
                    "success_rate": round(
                        (metrics.successful_executions / max(1, metrics.total_executions)) * 100, 2
                    ),
                    "error_rate": round(metrics.error_rate, 2),
                    "avg_duration_ms": round(metrics.avg_duration_ms, 1),
                    "min_duration_ms": (
                        metrics.min_duration_ms if metrics.min_duration_ms != float("inf") else 0
                    ),
                    "max_duration_ms": metrics.max_duration_ms,
                    "p95_duration_ms": round(metrics.p95_duration_ms, 1),
                    "p99_duration_ms": round(metrics.p99_duration_ms, 1),
                    "circuit_breaker_triggers": metrics.circuit_breaker_triggers,
                    "recent_samples": len(metrics.recent_durations),
                }
            else:
                return {"error": f"Stage {stage_name} not found"}
        else:
            # Return all stage metrics
            all_metrics = {}
            for stage_name, metrics in self.stage_metrics.items():
                all_metrics[stage_name] = {
                    "total_executions": metrics.total_executions,
                    "success_rate": round(
                        (metrics.successful_executions / max(1, metrics.total_executions)) * 100, 2
                    ),
                    "error_rate": round(metrics.error_rate, 2),
                    "avg_duration_ms": round(metrics.avg_duration_ms, 1),
                    "p95_duration_ms": round(metrics.p95_duration_ms, 1),
                    "circuit_breaker_triggers": metrics.circuit_breaker_triggers,
                }
            return all_metrics

    async def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[Dict[str, Any]]:
        """Get active alerts, optionally filtered by level"""
        alerts = []

        for alert in self.active_alerts.values():
            if level is None or alert.level == level:
                alerts.append(
                    {
                        "alert_id": alert.alert_id,
                        "level": alert.level.value,
                        "metric_type": alert.metric_type.value,
                        "message": alert.message,
                        "current_value": alert.current_value,
                        "threshold_value": alert.threshold_value,
                        "phone_number": alert.phone_number,
                        "stage": alert.stage,
                        "timestamp": alert.timestamp.isoformat(),
                        "resolved": alert.resolved,
                    }
                )

        return alerts

    async def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved"""
        try:
            # Find alert in active alerts
            for key, alert in self.active_alerts.items():
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    del self.active_alerts[key]

                    # Update cache
                    await enhanced_cache_service.set(
                        f"alert:{alert_id}",
                        json.dumps(asdict(alert), default=str),
                        CacheLayer.L2,
                        ttl=3600,
                    )

                    app_logger.info(f"Alert {alert_id} resolved")
                    return True

            return False

        except Exception as e:
            app_logger.error(f"Error resolving alert {alert_id}: {e}")
            return False

    async def clear_all_alerts(self) -> int:
        """Clear all active alerts (admin function)"""
        try:
            count = len(self.active_alerts)

            for alert in self.active_alerts.values():
                alert.resolved = True

            self.active_alerts.clear()

            app_logger.info(f"Cleared {count} active alerts")
            return count

        except Exception as e:
            app_logger.error(f"Error clearing alerts: {e}")
            return 0

    async def reset_metrics(self) -> bool:
        """Reset all performance metrics (admin function)"""
        try:
            self.stage_metrics.clear()
            self.alert_history.clear()
            self.active_alerts.clear()
            self.last_health_check = datetime.now()

            app_logger.info("All performance metrics reset")
            return True

        except Exception as e:
            app_logger.error(f"Error resetting metrics: {e}")
            return False


# Global pipeline monitor instance
pipeline_monitor = PipelineMonitor()
