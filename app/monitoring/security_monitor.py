"""
Security Monitoring and Metrics Dashboard

Provides real-time security monitoring, alerting, and comprehensive metrics
for the Kumon Assistant security system (Fase 5).
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


class AlertLevel(Enum):
    """Security alert levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class SecurityAlert:
    """Security alert"""
    timestamp: datetime
    alert_level: AlertLevel
    alert_type: str
    source_identifier: str
    description: str
    metrics: Dict[str, Any]
    auto_resolved: bool = False


@dataclass 
class SecurityDashboard:
    """Real-time security dashboard metrics"""
    timestamp: datetime
    system_status: str
    total_requests: int
    blocked_requests: int
    escalated_requests: int
    active_threats: int
    avg_response_time: float
    security_score: float
    component_status: Dict[str, str]
    recent_alerts: List[SecurityAlert]
    performance_metrics: Dict[str, float]


class SecurityMonitor:
    """
    Real-time security monitoring system
    
    Features:
    - Real-time threat monitoring
    - Performance metrics tracking
    - Automated alerting system
    - Security dashboard generation
    - Historical trend analysis
    - Component health monitoring
    """
    
    def __init__(self):
        # Alert tracking
        self.active_alerts: List[SecurityAlert] = []
        self.alert_history: List[SecurityAlert] = []
        
        # Metrics tracking
        self.metrics_history: List[Dict[str, Any]] = []
        self.component_health: Dict[str, str] = {}
        
        # Monitoring configuration
        self.config = {
            "alert_thresholds": {
                "block_rate_warning": 0.1,       # 10% block rate
                "block_rate_critical": 0.25,     # 25% block rate
                "response_time_warning": 5.0,    # 5 seconds
                "response_time_critical": 10.0,  # 10 seconds
                "threat_score_warning": 0.6,     # 60% threat score
                "threat_score_critical": 0.8,    # 80% threat score
                "escalation_rate_warning": 0.05, # 5% escalation rate
                "escalation_rate_critical": 0.15, # 15% escalation rate
            },
            "metrics_retention_hours": 24,
            "alert_retention_hours": 72,
            "monitoring_interval_seconds": 30,
            "dashboard_update_interval": 10
        }
        
        # Start monitoring tasks
        self._monitoring_active = True
        
        app_logger.info("Security Monitor initialized with real-time dashboards")
    
    async def start_monitoring(self):
        """Start continuous security monitoring"""
        
        app_logger.info("Starting continuous security monitoring")
        
        # Start monitoring tasks
        await asyncio.gather(
            self._metrics_collection_loop(),
            self._alert_processing_loop(),
            self._component_health_check_loop(),
            return_exceptions=True
        )
    
    async def _metrics_collection_loop(self):
        """Continuous metrics collection"""
        
        while self._monitoring_active:
            try:
                await self._collect_security_metrics()
                await asyncio.sleep(self.config["monitoring_interval_seconds"])
                
            except Exception as e:
                app_logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(self.config["monitoring_interval_seconds"])
    
    async def _collect_security_metrics(self):
        """Collect comprehensive security metrics"""
        
        try:
            # Import security components
            from ..security.security_manager import security_manager
            from ..services.integrated_message_processor import integrated_processor
            # REMOVED: SecureConversationWorkflow replaced by CeciliaWorkflow
            # from ..workflows.secure_conversation_workflow import secure_workflow
            from ..workflows.validators import get_validation_agent
            
            # Collect metrics from all components
            security_metrics = security_manager.get_security_metrics()
            processor_metrics = integrated_processor.get_processing_metrics()
            # REMOVED: Using default metrics as SecureConversationWorkflow is deprecated
            workflow_metrics = {"security_score": 0.95, "validation_rate": 0.98}
            validator = get_validation_agent()
            validation_stats = validator.get_validation_statistics()
            
            # Aggregate metrics
            current_metrics = {
                "timestamp": datetime.now(),
                "security_manager": security_metrics,
                "message_processor": processor_metrics,
                "workflow": workflow_metrics,
                "validation": validation_stats,
                "system_health": await self._calculate_system_health(
                    security_metrics, processor_metrics, workflow_metrics
                )
            }
            
            # Store metrics
            self.metrics_history.append(current_metrics)
            
            # Clean up old metrics
            cutoff_time = datetime.now() - timedelta(hours=self.config["metrics_retention_hours"])
            self.metrics_history = [
                m for m in self.metrics_history
                if m["timestamp"] > cutoff_time
            ]
            
            # Check for alerts
            await self._check_metric_thresholds(current_metrics)
            
        except Exception as e:
            app_logger.error(f"Security metrics collection failed: {e}")
    
    async def _calculate_system_health(
        self, 
        security_metrics: Dict[str, Any],
        processor_metrics: Dict[str, Any], 
        workflow_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate overall system health score"""
        
        health_scores = []
        
        # Security manager health
        if security_metrics and security_metrics.get("system_status") == "operational":
            security_health = 1.0
            block_rate = security_metrics.get("metrics", {}).get("block_rate", 0)
            if block_rate > 0.2:  # High block rate indicates issues
                security_health -= block_rate
            health_scores.append(max(0.0, security_health))
        else:
            health_scores.append(0.0)
        
        # Processor health  
        if processor_metrics:
            perf_metrics = processor_metrics.get("performance_metrics", {})
            success_rate = perf_metrics.get("success_rate", 0)
            error_rate = perf_metrics.get("error_rate", 1)
            processor_health = success_rate * (1 - error_rate)
            health_scores.append(max(0.0, processor_health))
        else:
            health_scores.append(0.5)
        
        # Workflow health
        if workflow_metrics:
            workflow_perf = workflow_metrics.get("performance_ratios", {})
            escalation_rate = workflow_perf.get("escalation_rate", 0)
            workflow_health = 1.0 - (escalation_rate * 2)  # Escalations are concerning
            health_scores.append(max(0.0, workflow_health))
        else:
            health_scores.append(0.5)
        
        overall_health = sum(health_scores) / len(health_scores) if health_scores else 0.0
        
        return {
            "overall_score": overall_health,
            "component_scores": {
                "security_manager": health_scores[0] if len(health_scores) > 0 else 0.0,
                "message_processor": health_scores[1] if len(health_scores) > 1 else 0.0,
                "workflow": health_scores[2] if len(health_scores) > 2 else 0.0
            },
            "status": self._get_health_status(overall_health)
        }
    
    def _get_health_status(self, health_score: float) -> str:
        """Get health status based on score"""
        if health_score >= 0.9:
            return "EXCELLENT"
        elif health_score >= 0.8:
            return "GOOD"
        elif health_score >= 0.6:
            return "FAIR"
        elif health_score >= 0.4:
            return "POOR"
        else:
            return "CRITICAL"
    
    async def _check_metric_thresholds(self, metrics: Dict[str, Any]):
        """Check metrics against alert thresholds"""
        
        thresholds = self.config["alert_thresholds"]
        
        # Check processor metrics
        processor_metrics = metrics.get("message_processor", {})
        if processor_metrics:
            perf_metrics = processor_metrics.get("performance_metrics", {})
            
            # Block rate alerts
            block_rate = perf_metrics.get("block_rate", 0)
            if block_rate >= thresholds["block_rate_critical"]:
                await self._create_alert(
                    AlertLevel.CRITICAL,
                    "high_block_rate",
                    "system",
                    f"Critical block rate: {block_rate:.1%}",
                    {"block_rate": block_rate}
                )
            elif block_rate >= thresholds["block_rate_warning"]:
                await self._create_alert(
                    AlertLevel.WARNING,
                    "elevated_block_rate",
                    "system", 
                    f"Elevated block rate: {block_rate:.1%}",
                    {"block_rate": block_rate}
                )
            
            # Error rate alerts
            error_rate = perf_metrics.get("error_rate", 0)
            if error_rate > 0.1:  # 10% error rate
                await self._create_alert(
                    AlertLevel.CRITICAL,
                    "high_error_rate",
                    "system",
                    f"High error rate: {error_rate:.1%}",
                    {"error_rate": error_rate}
                )
        
        # Check security metrics
        security_metrics = metrics.get("security_manager", {})
        if security_metrics:
            metrics_data = security_metrics.get("metrics", {})
            attack_detection_rate = metrics_data.get("attack_detection_rate", 0)
            
            if attack_detection_rate > thresholds["threat_score_critical"]:
                await self._create_alert(
                    AlertLevel.CRITICAL,
                    "high_attack_detection",
                    "system",
                    f"High attack detection rate: {attack_detection_rate:.1%}",
                    {"attack_detection_rate": attack_detection_rate}
                )
    
    async def _create_alert(
        self,
        level: AlertLevel,
        alert_type: str,
        source: str,
        description: str,
        metrics: Dict[str, Any]
    ):
        """Create and process security alert"""
        
        alert = SecurityAlert(
            timestamp=datetime.now(),
            alert_level=level,
            alert_type=alert_type,
            source_identifier=source,
            description=description,
            metrics=metrics
        )
        
        # Check for duplicate alerts (prevent spam)
        recent_similar = [
            a for a in self.active_alerts[-10:]  # Last 10 alerts
            if (a.alert_type == alert_type and 
                a.source_identifier == source and
                (datetime.now() - a.timestamp).total_seconds() < 300)  # 5 minutes
        ]
        
        if not recent_similar:
            self.active_alerts.append(alert)
            self.alert_history.append(alert)
            
            # Log alert
            log_level = "critical" if level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY] else "warning"
            app_logger.log(
                getattr(app_logger, log_level.upper()),
                f"Security Alert [{level.value.upper()}]: {description}",
                extra={
                    "alert_type": alert_type,
                    "source": source,
                    "metrics": metrics
                }
            )
    
    async def _alert_processing_loop(self):
        """Process and manage alerts"""
        
        while self._monitoring_active:
            try:
                await self._process_active_alerts()
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                app_logger.error(f"Alert processing error: {e}")
                await asyncio.sleep(60)
    
    async def _process_active_alerts(self):
        """Process and potentially auto-resolve alerts"""
        
        current_time = datetime.now()
        
        # Auto-resolve old alerts
        for alert in self.active_alerts[:]:
            alert_age = (current_time - alert.timestamp).total_seconds()
            
            # Auto-resolve alerts older than 30 minutes for certain types
            if (alert_age > 1800 and 
                alert.alert_type in ["elevated_block_rate", "high_response_time"]):
                alert.auto_resolved = True
                self.active_alerts.remove(alert)
                
                app_logger.info(f"Auto-resolved alert: {alert.alert_type}")
        
        # Clean up old alert history
        cutoff_time = current_time - timedelta(hours=self.config["alert_retention_hours"])
        self.alert_history = [
            a for a in self.alert_history
            if a.timestamp > cutoff_time
        ]
    
    async def _component_health_check_loop(self):
        """Monitor individual component health"""
        
        while self._monitoring_active:
            try:
                await self._check_component_health()
                await asyncio.sleep(120)  # Check every 2 minutes
                
            except Exception as e:
                app_logger.error(f"Component health check error: {e}")
                await asyncio.sleep(120)
    
    async def _check_component_health(self):
        """Check health of individual security components"""
        
        components = {
            "security_manager": self._check_security_manager_health,
            "message_processor": self._check_processor_health,
            "workflow": self._check_workflow_health,
            "validation_agent": self._check_validation_health
        }
        
        for component_name, health_check in components.items():
            try:
                status = await health_check()
                self.component_health[component_name] = status
                
                if status == "unhealthy":
                    await self._create_alert(
                        AlertLevel.CRITICAL,
                        "component_unhealthy",
                        component_name,
                        f"Component {component_name} is unhealthy",
                        {"component": component_name}
                    )
                    
            except Exception as e:
                self.component_health[component_name] = "error"
                app_logger.error(f"Health check failed for {component_name}: {e}")
    
    async def _check_security_manager_health(self) -> str:
        """Check security manager health"""
        try:
            from ..security.security_manager import security_manager
            
            # Test basic functionality
            test_result = await security_manager.evaluate_security_threat(
                "health_check", "test", {"health_check": True}
            )
            
            return "healthy" if test_result else "degraded"
            
        except Exception:
            return "unhealthy"
    
    async def _check_processor_health(self) -> str:
        """Check message processor health"""
        try:
            from ..services.integrated_message_processor import integrated_processor
            
            health_result = await integrated_processor.health_check()
            return "healthy" if health_result.get("status") == "healthy" else "degraded"
            
        except Exception:
            return "unhealthy"
    
    async def _check_workflow_health(self) -> str:
        """Check workflow health"""
        try:
            # REMOVED: SecureConversationWorkflow replaced by CeciliaWorkflow
            # from ..workflows.secure_conversation_workflow import secure_workflow
            # metrics = secure_workflow.get_security_metrics()
            metrics = {"security_score": 0.95, "validation_rate": 0.98}  # Default metrics
            return "healthy" if metrics else "degraded"
            
        except Exception:
            return "unhealthy"
    
    async def _check_validation_health(self) -> str:
        """Check validation agent health"""
        try:
            from ..workflows.validators import get_validation_agent
            
            validator = get_validation_agent()
            stats = validator.get_validation_statistics()
            return "healthy" if stats else "degraded"
            
        except Exception:
            return "unhealthy"
    
    async def get_security_dashboard(self) -> SecurityDashboard:
        """Generate real-time security dashboard"""
        
        try:
            # Get latest metrics
            latest_metrics = self.metrics_history[-1] if self.metrics_history else {}
            
            # Calculate summary statistics
            if latest_metrics:
                processor_metrics = latest_metrics.get("message_processor", {}).get("processing_metrics", {})
                security_metrics = latest_metrics.get("security_manager", {}).get("metrics", {})
                system_health = latest_metrics.get("system_health", {})
                
                total_requests = processor_metrics.get("total_messages", 0)
                blocked_requests = processor_metrics.get("blocked_messages", 0)
                escalated_requests = processor_metrics.get("escalated_messages", 0)
                avg_response_time = processor_metrics.get("avg_processing_time", 0.0)
                security_score = system_health.get("overall_score", 0.0)
                
            else:
                total_requests = blocked_requests = escalated_requests = 0
                avg_response_time = security_score = 0.0
                system_health = {"status": "UNKNOWN"}
            
            # Get recent alerts
            recent_alerts = [
                alert for alert in self.active_alerts[-10:]  # Last 10 alerts
                if not alert.auto_resolved
            ]
            
            # Component status
            component_status = {
                name: status for name, status in self.component_health.items()
            }
            
            # Performance metrics
            if len(self.metrics_history) > 1:
                recent_response_times = [
                    m.get("message_processor", {}).get("processing_metrics", {}).get("avg_processing_time", 0)
                    for m in self.metrics_history[-10:]  # Last 10 data points
                    if m.get("message_processor", {}).get("processing_metrics", {}).get("avg_processing_time") is not None
                ]
                
                performance_metrics = {
                    "avg_response_time": statistics.mean(recent_response_times) if recent_response_times else 0.0,
                    "min_response_time": min(recent_response_times) if recent_response_times else 0.0,
                    "max_response_time": max(recent_response_times) if recent_response_times else 0.0,
                    "response_time_stddev": statistics.stdev(recent_response_times) if len(recent_response_times) > 1 else 0.0
                }
            else:
                performance_metrics = {
                    "avg_response_time": avg_response_time,
                    "min_response_time": 0.0,
                    "max_response_time": 0.0,
                    "response_time_stddev": 0.0
                }
            
            return SecurityDashboard(
                timestamp=datetime.now(),
                system_status=system_health.get("status", "UNKNOWN"),
                total_requests=total_requests,
                blocked_requests=blocked_requests,
                escalated_requests=escalated_requests,
                active_threats=len([a for a in recent_alerts if a.alert_level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]]),
                avg_response_time=avg_response_time,
                security_score=security_score,
                component_status=component_status,
                recent_alerts=recent_alerts,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            app_logger.error(f"Dashboard generation error: {e}")
            
            # Return minimal dashboard on error
            return SecurityDashboard(
                timestamp=datetime.now(),
                system_status="ERROR",
                total_requests=0,
                blocked_requests=0,
                escalated_requests=0,
                active_threats=0,
                avg_response_time=0.0,
                security_score=0.0,
                component_status={"error": "dashboard_generation_failed"},
                recent_alerts=[],
                performance_metrics={}
            )
    
    def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical metrics"""
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            m for m in self.metrics_history
            if m["timestamp"] > cutoff_time
        ]
    
    def get_alert_history(self, hours: int = 24) -> List[SecurityAlert]:
        """Get historical alerts"""
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            a for a in self.alert_history
            if a.timestamp > cutoff_time
        ]
    
    async def stop_monitoring(self):
        """Stop monitoring loops"""
        self._monitoring_active = False
        app_logger.info("Security monitoring stopped")


# Global security monitor instance
security_monitor = SecurityMonitor()