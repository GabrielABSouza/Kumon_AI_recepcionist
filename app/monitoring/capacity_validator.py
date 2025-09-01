"""
Automated Capacity Validation System

Provides scheduled and automated capacity validation for the Kumon Assistant:
- Regular load testing schedules 
- Performance baseline validation
- Capacity planning and trend analysis
- Automated threshold monitoring
- Performance regression detection
- Capacity alerts and notifications
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import statistics

from ..core.logger import app_logger
from ..core.config import settings
from .load_tester import load_tester, LoadTestSummary
from .performance_monitor import performance_monitor
from .alert_manager import alert_manager


class ValidationTrigger(Enum):
    """Capacity validation triggers"""
    SCHEDULED = "scheduled"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    MANUAL = "manual"
    DEPLOYMENT = "deployment"
    THRESHOLD_BREACH = "threshold_breach"


class ValidationSeverity(Enum):
    """Validation result severity"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class CapacityBaseline:
    """Performance capacity baseline"""
    timestamp: datetime
    concurrent_users: int
    requests_per_second: float
    avg_response_time_ms: float
    p95_response_time_ms: float
    error_rate_percent: float
    performance_score: float
    system_resources: Dict[str, float]
    validation_trigger: ValidationTrigger


@dataclass
class CapacityAlert:
    """Capacity validation alert"""
    timestamp: datetime
    severity: ValidationSeverity
    alert_type: str
    description: str
    current_values: Dict[str, float]
    baseline_values: Dict[str, float]
    threshold_breaches: List[str]
    recommendations: List[str]
    auto_resolved: bool = False


@dataclass
class ValidationResult:
    """Capacity validation result"""
    validation_id: str
    timestamp: datetime
    trigger: ValidationTrigger
    test_summary: LoadTestSummary
    baseline_comparison: Dict[str, Any]
    performance_trend: Dict[str, List[float]]
    capacity_status: str
    alerts_generated: List[CapacityAlert]
    recommendations: List[str]
    next_validation: datetime


class CapacityValidator:
    """
    Automated capacity validation and monitoring system
    
    Features:
    - Scheduled capacity validation tests
    - Performance baseline tracking and comparison
    - Automated threshold monitoring
    - Capacity trend analysis and forecasting
    - Integration with alerting system
    - Performance regression detection
    """
    
    def __init__(self):
        # Validation configuration
        self.config = {
            # Validation schedules
            "daily_validation_hour": 2,  # 2 AM daily validation
            "weekly_stress_test_day": 0,  # Monday (0=Monday, 6=Sunday)
            "monthly_full_test_day": 1,   # 1st of month
            
            # Validation thresholds
            "performance_degradation_threshold": 0.15,  # 15% performance drop
            "response_time_increase_threshold": 1.5,    # 1.5x response time increase
            "error_rate_increase_threshold": 0.02,      # 2% error rate increase
            "capacity_reduction_threshold": 0.20,       # 20% capacity reduction
            
            # Test configurations
            "baseline_test_users": 25,
            "capacity_test_users": 75,
            "stress_test_max_users": 150,
            "endurance_test_duration": 1800,  # 30 minutes
            
            # Baseline management
            "baseline_retention_days": 30,
            "baseline_update_frequency_days": 7,
            "performance_trend_window_days": 14,
            
            # Alerting
            "enable_capacity_alerts": True,
            "alert_cooldown_minutes": 60,
            "critical_alert_escalation": True
        }
        
        # Validation state
        self.validation_active = True
        self.baselines: List[CapacityBaseline] = []
        self.validation_history: List[ValidationResult] = []
        self.active_alerts: List[CapacityAlert] = []
        self.alert_history: List[CapacityAlert] = []
        
        # Validation schedules
        self.next_scheduled_validation = self._calculate_next_validation()
        self.last_validation_time = None
        
        app_logger.info("Capacity Validator initialized with automated scheduling")
    
    async def start_capacity_validation(self):
        """Start automated capacity validation system"""
        
        app_logger.info("Starting automated capacity validation system")
        
        # Start validation tasks
        await asyncio.gather(
            self._validation_scheduler_loop(),
            self._performance_monitoring_loop(),
            self._baseline_maintenance_loop(),
            self._alert_processing_loop(),
            return_exceptions=True
        )
    
    async def _validation_scheduler_loop(self):
        """Main validation scheduler loop"""
        
        while self.validation_active:
            try:
                current_time = datetime.now()
                
                # Check if scheduled validation is due
                if current_time >= self.next_scheduled_validation:
                    await self._execute_scheduled_validation()
                    self.next_scheduled_validation = self._calculate_next_validation()
                
                # Sleep for 5 minutes before next check
                await asyncio.sleep(300)
                
            except Exception as e:
                app_logger.error(f"Validation scheduler error: {e}")
                await asyncio.sleep(300)
    
    async def _execute_scheduled_validation(self):
        """Execute scheduled capacity validation"""
        
        try:
            current_time = datetime.now()
            app_logger.info("Executing scheduled capacity validation")
            
            # Determine validation type based on schedule
            validation_type = self._determine_validation_type(current_time)
            
            # Execute appropriate validation
            if validation_type == "daily_baseline":
                result = await self._run_baseline_validation()
            elif validation_type == "weekly_stress":
                result = await self._run_stress_validation()
            elif validation_type == "monthly_full":
                result = await self._run_comprehensive_validation()
            else:
                result = await self._run_baseline_validation()
            
            # Process validation results
            await self._process_validation_result(result)
            
            self.last_validation_time = current_time
            app_logger.info(f"Scheduled validation completed: {validation_type}")
            
        except Exception as e:
            app_logger.error(f"Scheduled validation failed: {e}")
    
    def _determine_validation_type(self, current_time: datetime) -> str:
        """Determine what type of validation to run"""
        
        # Monthly full test (1st of month)
        if current_time.day == self.config["monthly_full_test_day"]:
            return "monthly_full"
        
        # Weekly stress test (Monday)
        elif current_time.weekday() == self.config["weekly_stress_test_day"]:
            return "weekly_stress"
        
        # Daily baseline test
        else:
            return "daily_baseline"
    
    async def _run_baseline_validation(self) -> ValidationResult:
        """Run baseline capacity validation test"""
        
        app_logger.info("Running baseline capacity validation")
        
        test_name = f"baseline_validation_{int(datetime.now().timestamp())}"
        
        # Run baseline load test
        summary = await load_tester.run_load_test(
            test_name=test_name,
            concurrent_users=self.config["baseline_test_users"],
            test_duration_seconds=300,  # 5 minutes
            ramp_up_duration_seconds=60
        )
        
        # Create validation result
        result = await self._create_validation_result(
            validation_id=test_name,
            trigger=ValidationTrigger.SCHEDULED,
            test_summary=summary
        )
        
        return result
    
    async def _run_stress_validation(self) -> ValidationResult:
        """Run stress capacity validation test"""
        
        app_logger.info("Running stress capacity validation")
        
        test_name = f"stress_validation_{int(datetime.now().timestamp())}"
        
        # Run stress test with gradual load increase
        summaries = await load_tester.run_stress_test(
            test_name=test_name,
            max_users=self.config["stress_test_max_users"],
            step_size=25,
            step_duration_seconds=120
        )
        
        # Use the best performing result
        best_summary = max(summaries, key=lambda x: x.performance_score) if summaries else None
        
        if best_summary:
            result = await self._create_validation_result(
                validation_id=test_name,
                trigger=ValidationTrigger.SCHEDULED,
                test_summary=best_summary
            )
        else:
            raise Exception("Stress validation failed to produce results")
        
        return result
    
    async def _run_comprehensive_validation(self) -> ValidationResult:
        """Run comprehensive capacity validation"""
        
        app_logger.info("Running comprehensive capacity validation")
        
        test_name = f"comprehensive_validation_{int(datetime.now().timestamp())}"
        
        # Run capacity test
        summary = await load_tester.run_load_test(
            test_name=test_name,
            concurrent_users=self.config["capacity_test_users"],
            test_duration_seconds=self.config["endurance_test_duration"],
            ramp_up_duration_seconds=300  # 5 minutes ramp-up
        )
        
        # Create validation result
        result = await self._create_validation_result(
            validation_id=test_name,
            trigger=ValidationTrigger.SCHEDULED,
            test_summary=summary
        )
        
        return result
    
    async def _create_validation_result(
        self,
        validation_id: str,
        trigger: ValidationTrigger,
        test_summary: LoadTestSummary
    ) -> ValidationResult:
        """Create validation result with analysis"""
        
        # Get current system performance data
        dashboard = await performance_monitor.get_performance_dashboard()
        
        # Compare with baseline
        baseline_comparison = await self._compare_with_baseline(test_summary)
        
        # Calculate performance trends
        performance_trend = self._calculate_performance_trends()
        
        # Determine capacity status
        capacity_status = self._determine_capacity_status(test_summary, baseline_comparison)
        
        # Generate alerts if needed
        alerts_generated = await self._generate_capacity_alerts(
            test_summary, baseline_comparison, capacity_status
        )
        
        # Generate recommendations
        recommendations = self._generate_capacity_recommendations(
            test_summary, baseline_comparison, capacity_status
        )
        
        # Calculate next validation time
        next_validation = self._calculate_next_validation()
        
        result = ValidationResult(
            validation_id=validation_id,
            timestamp=datetime.now(),
            trigger=trigger,
            test_summary=test_summary,
            baseline_comparison=baseline_comparison,
            performance_trend=performance_trend,
            capacity_status=capacity_status,
            alerts_generated=alerts_generated,
            recommendations=recommendations,
            next_validation=next_validation
        )
        
        return result
    
    async def _compare_with_baseline(self, current_test: LoadTestSummary) -> Dict[str, Any]:
        """Compare current test results with baseline"""
        
        if not self.baselines:
            return {"status": "no_baseline", "message": "No baseline available for comparison"}
        
        # Get most recent baseline
        latest_baseline = max(self.baselines, key=lambda x: x.timestamp)
        
        # Calculate performance differences
        comparison = {
            "baseline_timestamp": latest_baseline.timestamp.isoformat(),
            "baseline_users": latest_baseline.concurrent_users,
            "current_users": current_test.total_requests // (current_test.total_duration_seconds / 60),  # Approximate
            
            "response_time_change": {
                "baseline_ms": latest_baseline.avg_response_time_ms,
                "current_ms": current_test.avg_response_time_ms,
                "change_percent": ((current_test.avg_response_time_ms - latest_baseline.avg_response_time_ms) / 
                                 latest_baseline.avg_response_time_ms) * 100 if latest_baseline.avg_response_time_ms > 0 else 0
            },
            
            "error_rate_change": {
                "baseline_percent": latest_baseline.error_rate_percent,
                "current_percent": current_test.error_rate_percent,
                "change_percent": current_test.error_rate_percent - latest_baseline.error_rate_percent
            },
            
            "performance_score_change": {
                "baseline_score": latest_baseline.performance_score,
                "current_score": current_test.performance_score,
                "change_percent": ((current_test.performance_score - latest_baseline.performance_score) / 
                                 latest_baseline.performance_score) * 100 if latest_baseline.performance_score > 0 else 0
            },
            
            "throughput_change": {
                "baseline_rps": latest_baseline.requests_per_second,
                "current_rps": current_test.requests_per_second,
                "change_percent": ((current_test.requests_per_second - latest_baseline.requests_per_second) / 
                                 latest_baseline.requests_per_second) * 100 if latest_baseline.requests_per_second > 0 else 0
            }
        }
        
        # Determine overall status
        response_time_degraded = comparison["response_time_change"]["change_percent"] > (self.config["response_time_increase_threshold"] * 100 - 100)
        error_rate_increased = comparison["error_rate_change"]["change_percent"] > (self.config["error_rate_increase_threshold"] * 100)
        performance_degraded = comparison["performance_score_change"]["change_percent"] < -(self.config["performance_degradation_threshold"] * 100)
        
        if performance_degraded or response_time_degraded or error_rate_increased:
            comparison["status"] = "degraded"
        elif comparison["performance_score_change"]["change_percent"] > 10:
            comparison["status"] = "improved"
        else:
            comparison["status"] = "stable"
        
        return comparison
    
    def _calculate_performance_trends(self) -> Dict[str, List[float]]:
        """Calculate performance trends from validation history"""
        
        if len(self.validation_history) < 2:
            return {}
        
        # Get recent validation results
        cutoff_time = datetime.now() - timedelta(days=self.config["performance_trend_window_days"])
        recent_validations = [
            v for v in self.validation_history
            if v.timestamp > cutoff_time
        ]
        
        if len(recent_validations) < 2:
            return {}
        
        trends = {
            "response_times": [v.test_summary.avg_response_time_ms for v in recent_validations],
            "error_rates": [v.test_summary.error_rate_percent for v in recent_validations],
            "performance_scores": [v.test_summary.performance_score for v in recent_validations],
            "throughput": [v.test_summary.requests_per_second for v in recent_validations],
            "timestamps": [v.timestamp.isoformat() for v in recent_validations]
        }
        
        return trends
    
    def _determine_capacity_status(
        self, 
        test_summary: LoadTestSummary, 
        baseline_comparison: Dict[str, Any]
    ) -> str:
        """Determine overall capacity status"""
        
        # Base status on performance score
        if test_summary.performance_score >= 90:
            base_status = "excellent"
        elif test_summary.performance_score >= 80:
            base_status = "good"
        elif test_summary.performance_score >= 60:
            base_status = "fair"
        elif test_summary.performance_score >= 40:
            base_status = "poor"
        else:
            base_status = "critical"
        
        # Adjust based on baseline comparison
        if baseline_comparison.get("status") == "degraded":
            if base_status in ["excellent", "good"]:
                base_status = "fair"
            elif base_status == "fair":
                base_status = "poor"
        elif baseline_comparison.get("status") == "improved":
            if base_status == "fair":
                base_status = "good"
            elif base_status == "poor":
                base_status = "fair"
        
        return base_status
    
    async def _generate_capacity_alerts(
        self, 
        test_summary: LoadTestSummary,
        baseline_comparison: Dict[str, Any],
        capacity_status: str
    ) -> List[CapacityAlert]:
        """Generate capacity alerts based on validation results"""
        
        alerts = []
        
        # Performance degradation alert
        if baseline_comparison.get("status") == "degraded":
            performance_change = baseline_comparison.get("performance_score_change", {}).get("change_percent", 0)
            
            if performance_change < -25:  # >25% degradation
                severity = ValidationSeverity.CRITICAL
            elif performance_change < -15:  # >15% degradation
                severity = ValidationSeverity.WARNING
            else:
                severity = ValidationSeverity.INFO
            
            alerts.append(CapacityAlert(
                timestamp=datetime.now(),
                severity=severity,
                alert_type="performance_degradation",
                description=f"Performance degraded by {abs(performance_change):.1f}% compared to baseline",
                current_values={
                    "performance_score": test_summary.performance_score,
                    "response_time_ms": test_summary.avg_response_time_ms,
                    "error_rate_percent": test_summary.error_rate_percent
                },
                baseline_values={
                    "performance_score": baseline_comparison.get("performance_score_change", {}).get("baseline_score", 0),
                    "response_time_ms": baseline_comparison.get("response_time_change", {}).get("baseline_ms", 0),
                    "error_rate_percent": baseline_comparison.get("error_rate_change", {}).get("baseline_percent", 0)
                },
                threshold_breaches=["performance_degradation_threshold"],
                recommendations=["Review recent changes", "Check system resources", "Consider scaling"]
            ))
        
        # High error rate alert
        if test_summary.error_rate_percent > 5.0:  # >5% error rate
            severity = ValidationSeverity.CRITICAL if test_summary.error_rate_percent > 10 else ValidationSeverity.WARNING
            
            alerts.append(CapacityAlert(
                timestamp=datetime.now(),
                severity=severity,
                alert_type="high_error_rate",
                description=f"High error rate detected: {test_summary.error_rate_percent:.1f}%",
                current_values={"error_rate_percent": test_summary.error_rate_percent},
                baseline_values={},
                threshold_breaches=["error_rate_threshold"],
                recommendations=["Investigate error causes", "Review application logs", "Check service health"]
            ))
        
        # Low performance score alert
        if test_summary.performance_score < 60:
            severity = ValidationSeverity.CRITICAL if test_summary.performance_score < 40 else ValidationSeverity.WARNING
            
            alerts.append(CapacityAlert(
                timestamp=datetime.now(),
                severity=severity,
                alert_type="low_performance_score",
                description=f"Low performance score: {test_summary.performance_score:.1f}",
                current_values={"performance_score": test_summary.performance_score},
                baseline_values={},
                threshold_breaches=["performance_score_threshold"],
                recommendations=["Optimize application performance", "Review bottlenecks", "Consider infrastructure scaling"]
            ))
        
        # Send alerts to alert manager
        for alert in alerts:
            if self.config["enable_capacity_alerts"]:
                await self._send_alert_to_manager(alert)
        
        return alerts
    
    def _generate_capacity_recommendations(
        self,
        test_summary: LoadTestSummary,
        baseline_comparison: Dict[str, Any],
        capacity_status: str
    ) -> List[str]:
        """Generate capacity planning recommendations"""
        
        recommendations = []
        
        # Performance-based recommendations
        if test_summary.performance_score < 70:
            recommendations.append("Consider performance optimization or infrastructure scaling")
        
        if test_summary.avg_response_time_ms > 2000:
            recommendations.append("Investigate and optimize slow response times")
        
        if test_summary.error_rate_percent > 2:
            recommendations.append("Address application errors and stability issues")
        
        # Baseline comparison recommendations
        if baseline_comparison.get("status") == "degraded":
            recommendations.append("Performance has degraded - review recent deployments and changes")
            
            response_change = baseline_comparison.get("response_time_change", {}).get("change_percent", 0)
            if response_change > 50:  # >50% response time increase
                recommendations.append("Significant response time increase detected - immediate investigation required")
        
        # Capacity status recommendations
        if capacity_status in ["poor", "critical"]:
            recommendations.append("System is operating below acceptable performance levels")
            recommendations.append("Immediate performance tuning or scaling required")
        elif capacity_status == "fair":
            recommendations.append("System performance is marginal - consider proactive optimization")
        
        # Trend-based recommendations
        trends = self._calculate_performance_trends()
        if trends and len(trends.get("performance_scores", [])) >= 3:
            recent_scores = trends["performance_scores"][-3:]
            if all(recent_scores[i] <= recent_scores[i-1] for i in range(1, len(recent_scores))):
                recommendations.append("Declining performance trend detected - proactive intervention recommended")
        
        return recommendations
    
    async def _send_alert_to_manager(self, alert: CapacityAlert):
        """Send capacity alert to alert manager"""
        
        try:
            # Convert to alert manager format
            alert_data = {
                "alert_type": f"capacity_{alert.alert_type}",
                "severity": alert.severity.value,
                "title": f"Capacity Alert: {alert.alert_type.replace('_', ' ').title()}",
                "description": alert.description,
                "metadata": {
                    "current_values": alert.current_values,
                    "baseline_values": alert.baseline_values,
                    "threshold_breaches": alert.threshold_breaches,
                    "recommendations": alert.recommendations
                }
            }
            
            # Send to alert manager
            await alert_manager.process_alert(alert_data)
            
        except Exception as e:
            app_logger.error(f"Failed to send capacity alert: {e}")
    
    async def _performance_monitoring_loop(self):
        """Monitor for performance degradation triggers"""
        
        while self.validation_active:
            try:
                # Check if performance has degraded enough to trigger validation
                should_trigger = await self._check_performance_degradation()
                
                if should_trigger and self._can_trigger_validation():
                    app_logger.info("Performance degradation detected - triggering validation")
                    result = await self._run_baseline_validation()
                    result.trigger = ValidationTrigger.PERFORMANCE_DEGRADATION
                    await self._process_validation_result(result)
                
                # Sleep for 10 minutes
                await asyncio.sleep(600)
                
            except Exception as e:
                app_logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(600)
    
    async def _check_performance_degradation(self) -> bool:
        """Check if current performance indicates degradation"""
        
        try:
            dashboard = await performance_monitor.get_performance_dashboard()
            
            # Check performance indicators
            if dashboard.overall_performance_score < 0.6:  # Below 60%
                return True
            
            # Check API response times
            if dashboard.api_metrics.avg_response_time_ms > 3000:  # Above 3 seconds
                return True
            
            # Check error rates
            if dashboard.api_metrics.error_rate_percent > 5.0:  # Above 5%
                return True
            
            return False
            
        except Exception as e:
            app_logger.error(f"Performance degradation check failed: {e}")
            return False
    
    def _can_trigger_validation(self) -> bool:
        """Check if validation can be triggered (cooldown, etc.)"""
        
        if not self.last_validation_time:
            return True
        
        # Check cooldown period (minimum 1 hour between triggered validations)
        time_since_last = datetime.now() - self.last_validation_time
        return time_since_last.total_seconds() >= 3600
    
    async def _baseline_maintenance_loop(self):
        """Maintain performance baselines"""
        
        while self.validation_active:
            try:
                await self._update_baselines()
                await self._cleanup_old_data()
                
                # Sleep for 1 hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                app_logger.error(f"Baseline maintenance error: {e}")
                await asyncio.sleep(3600)
    
    async def _update_baselines(self):
        """Update performance baselines from recent validation data"""
        
        if not self.validation_history:
            return
        
        # Check if baseline update is due
        if self.baselines:
            latest_baseline = max(self.baselines, key=lambda x: x.timestamp)
            days_since_update = (datetime.now() - latest_baseline.timestamp).days
            
            if days_since_update < self.config["baseline_update_frequency_days"]:
                return
        
        # Find good baseline candidates from recent validations
        cutoff_time = datetime.now() - timedelta(days=7)  # Last week
        recent_validations = [
            v for v in self.validation_history
            if (v.timestamp > cutoff_time and 
                v.test_summary.performance_score >= 80 and  # Good performance
                v.test_summary.error_rate_percent <= 2.0)   # Low error rate
        ]
        
        if not recent_validations:
            return
        
        # Use the best recent validation as new baseline
        best_validation = max(recent_validations, key=lambda v: v.test_summary.performance_score)
        
        # Create new baseline
        new_baseline = CapacityBaseline(
            timestamp=datetime.now(),
            concurrent_users=self.config["baseline_test_users"],  # Standard baseline
            requests_per_second=best_validation.test_summary.requests_per_second,
            avg_response_time_ms=best_validation.test_summary.avg_response_time_ms,
            p95_response_time_ms=best_validation.test_summary.p95_response_time_ms,
            error_rate_percent=best_validation.test_summary.error_rate_percent,
            performance_score=best_validation.test_summary.performance_score,
            system_resources={},  # Would be populated with actual system metrics
            validation_trigger=best_validation.trigger
        )
        
        self.baselines.append(new_baseline)
        app_logger.info(f"Updated performance baseline: {new_baseline.performance_score:.1f} score")
    
    async def _cleanup_old_data(self):
        """Clean up old validation data"""
        
        current_time = datetime.now()
        
        # Clean up old baselines
        baseline_cutoff = current_time - timedelta(days=self.config["baseline_retention_days"])
        self.baselines = [b for b in self.baselines if b.timestamp > baseline_cutoff]
        
        # Clean up old validation history (keep last 100 validations or 30 days)
        validation_cutoff = current_time - timedelta(days=30)
        self.validation_history = [
            v for v in self.validation_history[-100:]  # Keep last 100
            if v.timestamp > validation_cutoff
        ]
        
        # Clean up old alerts
        alert_cutoff = current_time - timedelta(days=7)
        self.alert_history = [a for a in self.alert_history if a.timestamp > alert_cutoff]
    
    async def _alert_processing_loop(self):
        """Process and manage capacity alerts"""
        
        while self.validation_active:
            try:
                await self._process_capacity_alerts()
                await asyncio.sleep(self.config["alert_cooldown_minutes"] * 60)
                
            except Exception as e:
                app_logger.error(f"Alert processing error: {e}")
                await asyncio.sleep(self.config["alert_cooldown_minutes"] * 60)
    
    async def _process_capacity_alerts(self):
        """Process and potentially auto-resolve alerts"""
        
        current_time = datetime.now()
        
        # Auto-resolve old alerts
        for alert in self.active_alerts[:]:
            alert_age = (current_time - alert.timestamp).total_seconds()
            
            # Auto-resolve info and warning alerts after 4 hours
            if (alert_age > 14400 and 
                alert.severity in [ValidationSeverity.INFO, ValidationSeverity.WARNING]):
                alert.auto_resolved = True
                self.active_alerts.remove(alert)
                self.alert_history.append(alert)
                
                app_logger.info(f"Auto-resolved capacity alert: {alert.alert_type}")
    
    async def _process_validation_result(self, result: ValidationResult):
        """Process and store validation result"""
        
        # Store validation result
        self.validation_history.append(result)
        
        # Add alerts to active alerts
        self.active_alerts.extend(result.alerts_generated)
        
        # Log validation result
        app_logger.info(
            f"Capacity validation completed: {result.capacity_status} "
            f"(score: {result.test_summary.performance_score:.1f}, "
            f"response: {result.test_summary.avg_response_time_ms:.1f}ms, "
            f"errors: {result.test_summary.error_rate_percent:.1f}%)"
        )
        
        # Log any critical alerts
        critical_alerts = [a for a in result.alerts_generated if a.severity == ValidationSeverity.CRITICAL]
        if critical_alerts:
            app_logger.warning(f"Critical capacity alerts generated: {len(critical_alerts)}")
    
    def _calculate_next_validation(self) -> datetime:
        """Calculate next scheduled validation time"""
        
        now = datetime.now()
        
        # Next daily validation at configured hour
        next_validation = now.replace(
            hour=self.config["daily_validation_hour"],
            minute=0,
            second=0,
            microsecond=0
        )
        
        # If time has passed today, schedule for tomorrow
        if next_validation <= now:
            next_validation += timedelta(days=1)
        
        return next_validation
    
    async def run_manual_validation(
        self,
        test_type: str = "baseline",
        concurrent_users: Optional[int] = None
    ) -> ValidationResult:
        """Run manual capacity validation"""
        
        app_logger.info(f"Running manual capacity validation: {test_type}")
        
        if test_type == "stress":
            result = await self._run_stress_validation()
        elif test_type == "comprehensive":
            result = await self._run_comprehensive_validation()
        else:  # baseline
            result = await self._run_baseline_validation()
        
        result.trigger = ValidationTrigger.MANUAL
        await self._process_validation_result(result)
        
        return result
    
    def get_capacity_status(self) -> Dict[str, Any]:
        """Get current capacity validation status"""
        
        return {
            "validation_active": self.validation_active,
            "next_scheduled_validation": self.next_scheduled_validation.isoformat(),
            "last_validation": self.last_validation_time.isoformat() if self.last_validation_time else None,
            "total_validations": len(self.validation_history),
            "active_alerts": len(self.active_alerts),
            "critical_alerts": len([a for a in self.active_alerts if a.severity == ValidationSeverity.CRITICAL]),
            "baselines_count": len(self.baselines),
            "latest_baseline": self.baselines[-1].timestamp.isoformat() if self.baselines else None,
            "config": self.config
        }
    
    def get_validation_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get capacity validation history"""
        
        cutoff_time = datetime.now() - timedelta(days=days)
        recent_validations = [
            v for v in self.validation_history
            if v.timestamp > cutoff_time
        ]
        
        return [
            {
                "validation_id": v.validation_id,
                "timestamp": v.timestamp.isoformat(),
                "trigger": v.trigger.value,
                "capacity_status": v.capacity_status,
                "performance_score": v.test_summary.performance_score,
                "avg_response_time_ms": v.test_summary.avg_response_time_ms,
                "error_rate_percent": v.test_summary.error_rate_percent,
                "alerts_count": len(v.alerts_generated),
                "recommendations_count": len(v.recommendations)
            }
            for v in recent_validations
        ]
    
    async def stop_capacity_validation(self):
        """Stop capacity validation system"""
        self.validation_active = False
        app_logger.info("Capacity validation system stopped")


# Global capacity validator instance
capacity_validator = CapacityValidator()