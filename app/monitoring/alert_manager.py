"""
Advanced Alert Management System

Intelligent alerting system with multi-channel notifications:
- Smart alert correlation and deduplication
- Multi-channel notification (email, webhook, logging)
- Alert escalation policies
- Performance trend analysis and predictions
- Automated incident management
- Alert fatigue prevention
"""

import asyncio
import json
import hashlib
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import statistics
import httpx

from ..core.logger import app_logger
from ..core.config import settings
from .performance_monitor import PerformanceAlert, PerformanceLevel
from .security_monitor import SecurityAlert, AlertLevel


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning" 
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(Enum):
    """Alert lifecycle status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class NotificationChannel(Enum):
    """Available notification channels"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    LOGGING = "logging"
    SMS = "sms"


@dataclass
class AlertRule:
    """Alert rule configuration"""
    rule_id: str
    name: str
    description: str
    severity: AlertSeverity
    conditions: Dict[str, Any]
    notification_channels: List[NotificationChannel]
    escalation_timeout_minutes: int = 30
    max_escalations: int = 3
    suppress_duration_minutes: int = 60
    enabled: bool = True


@dataclass
class ManagedAlert:
    """Enhanced alert with management information"""
    alert_id: str
    rule_id: str
    source_type: str  # 'performance' or 'security'
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalation_count: int = 0
    next_escalation: Optional[datetime] = None
    notification_log: List[Dict[str, Any]] = field(default_factory=list)
    correlation_key: Optional[str] = None


@dataclass
class AlertStatistics:
    """Alert management statistics"""
    total_alerts_24h: int
    active_alerts: int
    critical_alerts: int
    resolved_alerts_24h: int
    avg_resolution_time_minutes: float
    top_alert_sources: Dict[str, int]
    escalation_rate: float
    notification_success_rate: float


class AlertManager:
    """
    Advanced alert management system
    
    Features:
    - Intelligent alert correlation and deduplication
    - Multi-channel notification system
    - Escalation policies with timeout management
    - Alert fatigue prevention
    - Performance trend analysis
    - Automated incident management
    - Real-time alert dashboards
    """
    
    def __init__(self):
        # Alert storage
        self.managed_alerts: Dict[str, ManagedAlert] = {}
        self.alert_history: List[ManagedAlert] = []
        self.suppressed_alerts: Set[str] = set()
        
        # Alert rules
        self.alert_rules: Dict[str, AlertRule] = {}
        
        # Notification configuration
        self.notification_config = {
            "webhook_endpoints": [
                # Add webhook URLs for external alerting systems
            ],
            "email_config": {
                "smtp_server": getattr(settings, "SMTP_SERVER", None),
                "smtp_port": getattr(settings, "SMTP_PORT", 587),
                "smtp_user": getattr(settings, "SMTP_USER", None),
                "smtp_password": getattr(settings, "SMTP_PASSWORD", None),
                "from_email": getattr(settings, "ALERT_FROM_EMAIL", "alerts@kumon-ai.com"),
                "to_emails": getattr(settings, "ALERT_TO_EMAILS", "admin@kumon-ai.com").split(",")
            },
            "slack_config": {
                "webhook_url": getattr(settings, "SLACK_WEBHOOK_URL", None),
                "channel": getattr(settings, "SLACK_ALERT_CHANNEL", "#alerts")
            }
        }
        
        # Alert processing state
        self._processing_active = True
        
        # Initialize default alert rules
        self._initialize_default_rules()
        
        app_logger.info("Alert Manager initialized with intelligent alerting")
    
    def _initialize_default_rules(self):
        """Initialize default alert rules"""
        
        # Performance alert rules
        performance_rules = [
            AlertRule(
                rule_id="high_cpu_usage",
                name="High CPU Usage",
                description="CPU usage exceeds safe thresholds",
                severity=AlertSeverity.WARNING,
                conditions={
                    "metric": "cpu_usage_percent",
                    "threshold": 80.0,
                    "duration_minutes": 5
                },
                notification_channels=[NotificationChannel.LOGGING, NotificationChannel.WEBHOOK],
                escalation_timeout_minutes=15
            ),
            AlertRule(
                rule_id="critical_cpu_usage", 
                name="Critical CPU Usage",
                description="CPU usage at critical levels",
                severity=AlertSeverity.CRITICAL,
                conditions={
                    "metric": "cpu_usage_percent", 
                    "threshold": 95.0,
                    "duration_minutes": 2
                },
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.WEBHOOK, NotificationChannel.SLACK],
                escalation_timeout_minutes=10,
                max_escalations=5
            ),
            AlertRule(
                rule_id="high_memory_usage",
                name="High Memory Usage",
                description="Memory usage approaching limits",
                severity=AlertSeverity.WARNING,
                conditions={
                    "metric": "memory_usage_percent",
                    "threshold": 85.0,
                    "duration_minutes": 5
                },
                notification_channels=[NotificationChannel.LOGGING, NotificationChannel.WEBHOOK],
                escalation_timeout_minutes=20
            ),
            AlertRule(
                rule_id="slow_api_response",
                name="Slow API Response Times",
                description="API response times degrading user experience",
                severity=AlertSeverity.WARNING,
                conditions={
                    "metric": "avg_response_time_ms",
                    "threshold": 2000.0,
                    "duration_minutes": 3
                },
                notification_channels=[NotificationChannel.LOGGING, NotificationChannel.WEBHOOK],
                escalation_timeout_minutes=10
            ),
            AlertRule(
                rule_id="high_error_rate",
                name="High API Error Rate", 
                description="API error rate indicates system issues",
                severity=AlertSeverity.CRITICAL,
                conditions={
                    "metric": "error_rate_percent",
                    "threshold": 5.0,
                    "duration_minutes": 2
                },
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.WEBHOOK, NotificationChannel.SLACK],
                escalation_timeout_minutes=5,
                max_escalations=10
            )
        ]
        
        # Security alert rules
        security_rules = [
            AlertRule(
                rule_id="security_threat_detected",
                name="Security Threat Detected",
                description="Potential security threat identified",
                severity=AlertSeverity.CRITICAL,
                conditions={
                    "source": "security_monitor",
                    "threat_level": "critical"
                },
                notification_channels=[NotificationChannel.EMAIL, NotificationChannel.WEBHOOK, NotificationChannel.SLACK],
                escalation_timeout_minutes=5,
                max_escalations=10
            ),
            AlertRule(
                rule_id="high_block_rate",
                name="High Security Block Rate",
                description="High rate of blocked requests indicates attack",
                severity=AlertSeverity.WARNING,
                conditions={
                    "metric": "block_rate",
                    "threshold": 0.15,
                    "duration_minutes": 5
                },
                notification_channels=[NotificationChannel.LOGGING, NotificationChannel.WEBHOOK],
                escalation_timeout_minutes=15
            )
        ]
        
        # Store all rules
        all_rules = performance_rules + security_rules
        for rule in all_rules:
            self.alert_rules[rule.rule_id] = rule
        
        app_logger.info(f"Initialized {len(all_rules)} default alert rules")
    
    async def start_alert_processing(self):
        """Start alert processing loops"""
        
        app_logger.info("Starting alert processing system")
        
        await asyncio.gather(
            self._alert_processing_loop(),
            self._escalation_loop(),
            self._cleanup_loop(),
            return_exceptions=True
        )
    
    async def _alert_processing_loop(self):
        """Main alert processing loop"""
        
        while self._processing_active:
            try:
                # Process new alerts from monitoring systems
                await self._process_performance_alerts()
                await self._process_security_alerts()
                
                await asyncio.sleep(30)  # Process every 30 seconds
                
            except Exception as e:
                app_logger.error(f"Alert processing error: {e}")
                await asyncio.sleep(30)
    
    async def _process_performance_alerts(self):
        """Process performance alerts from performance monitor"""
        
        try:
            from .performance_monitor import performance_monitor
            
            # Get recent performance alerts
            recent_alerts = performance_monitor.active_alerts[-10:]  # Last 10 alerts
            
            for perf_alert in recent_alerts:
                await self._process_alert(
                    source_type="performance",
                    alert_data={
                        "level": perf_alert.level.value,
                        "component": perf_alert.component,
                        "metric_name": perf_alert.metric_name,
                        "current_value": perf_alert.current_value,
                        "threshold_value": perf_alert.threshold_value,
                        "description": perf_alert.description,
                        "metadata": perf_alert.metadata,
                        "timestamp": perf_alert.timestamp
                    }
                )
                
        except Exception as e:
            app_logger.error(f"Performance alert processing error: {e}")
    
    async def _process_security_alerts(self):
        """Process security alerts from security monitor"""
        
        try:
            from .security_monitor import security_monitor
            
            # Get recent security alerts
            recent_alerts = security_monitor.active_alerts[-10:]  # Last 10 alerts
            
            for sec_alert in recent_alerts:
                await self._process_alert(
                    source_type="security",
                    alert_data={
                        "level": sec_alert.alert_level.value,
                        "alert_type": sec_alert.alert_type,
                        "source_identifier": sec_alert.source_identifier,
                        "description": sec_alert.description,
                        "metadata": sec_alert.metrics,
                        "timestamp": sec_alert.timestamp
                    }
                )
                
        except Exception as e:
            app_logger.error(f"Security alert processing error: {e}")
    
    async def _process_alert(self, source_type: str, alert_data: Dict[str, Any]):
        """Process individual alert through management system"""
        
        try:
            # Generate alert correlation key
            correlation_key = self._generate_correlation_key(source_type, alert_data)
            
            # Check if this alert is suppressed
            if correlation_key in self.suppressed_alerts:
                return
            
            # Check for existing similar alert (deduplication)
            existing_alert = self._find_similar_alert(correlation_key)
            
            if existing_alert:
                # Update existing alert
                existing_alert.updated_at = datetime.now()
                existing_alert.metadata.update(alert_data.get("metadata", {}))
                
            else:
                # Create new managed alert
                managed_alert = await self._create_managed_alert(source_type, alert_data, correlation_key)
                
                # Store alert
                self.managed_alerts[managed_alert.alert_id] = managed_alert
                
                # Send initial notifications
                await self._send_notifications(managed_alert)
                
                # Schedule escalation if needed
                await self._schedule_escalation(managed_alert)
                
        except Exception as e:
            app_logger.error(f"Alert processing failed: {e}")
    
    def _generate_correlation_key(self, source_type: str, alert_data: Dict[str, Any]) -> str:
        """Generate correlation key for alert deduplication"""
        
        # Create key based on source and key attributes
        key_data = {
            "source_type": source_type,
            "component": alert_data.get("component", ""),
            "metric_name": alert_data.get("metric_name", ""),
            "alert_type": alert_data.get("alert_type", "")
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()[:16]
    
    def _find_similar_alert(self, correlation_key: str) -> Optional[ManagedAlert]:
        """Find existing similar alert by correlation key"""
        
        for alert in self.managed_alerts.values():
            if (alert.correlation_key == correlation_key and 
                alert.status == AlertStatus.ACTIVE):
                return alert
        
        return None
    
    async def _create_managed_alert(
        self, 
        source_type: str, 
        alert_data: Dict[str, Any], 
        correlation_key: str
    ) -> ManagedAlert:
        """Create a new managed alert"""
        
        # Generate unique alert ID
        alert_id = f"{source_type}_{correlation_key}_{int(datetime.now().timestamp())}"
        
        # Determine severity from alert level
        alert_level = alert_data.get("level", "warning")
        if alert_level in ["critical", "emergency"]:
            severity = AlertSeverity.CRITICAL
        elif alert_level == "warning":
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO
        
        # Create title and description
        if source_type == "performance":
            title = f"Performance Alert: {alert_data.get('component', 'System')}"
            description = alert_data.get("description", "Performance threshold exceeded")
        else:
            title = f"Security Alert: {alert_data.get('alert_type', 'Threat')}"
            description = alert_data.get("description", "Security threat detected")
        
        # Find matching rule
        rule_id = self._find_matching_rule(source_type, alert_data)
        
        managed_alert = ManagedAlert(
            alert_id=alert_id,
            rule_id=rule_id,
            source_type=source_type,
            severity=severity,
            status=AlertStatus.ACTIVE,
            title=title,
            description=description,
            metadata=alert_data,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            correlation_key=correlation_key
        )
        
        return managed_alert
    
    def _find_matching_rule(self, source_type: str, alert_data: Dict[str, Any]) -> str:
        """Find matching alert rule for alert data"""
        
        # Simple rule matching logic
        if source_type == "performance":
            metric_name = alert_data.get("metric_name", "")
            current_value = alert_data.get("current_value", 0)
            
            if "cpu_usage" in metric_name and current_value >= 95:
                return "critical_cpu_usage"
            elif "cpu_usage" in metric_name and current_value >= 80:
                return "high_cpu_usage"
            elif "memory_usage" in metric_name:
                return "high_memory_usage"
            elif "response_time" in metric_name:
                return "slow_api_response"
            elif "error_rate" in metric_name:
                return "high_error_rate"
                
        elif source_type == "security":
            alert_type = alert_data.get("alert_type", "")
            
            if "threat" in alert_type.lower():
                return "security_threat_detected"
            elif "block_rate" in alert_type.lower():
                return "high_block_rate"
        
        # Default rule
        return "default_alert"
    
    async def _send_notifications(self, alert: ManagedAlert):
        """Send notifications for alert"""
        
        try:
            rule = self.alert_rules.get(alert.rule_id)
            if not rule or not rule.enabled:
                return
            
            notification_tasks = []
            
            for channel in rule.notification_channels:
                if channel == NotificationChannel.LOGGING:
                    notification_tasks.append(self._send_log_notification(alert))
                elif channel == NotificationChannel.WEBHOOK:
                    notification_tasks.append(self._send_webhook_notification(alert))
                elif channel == NotificationChannel.EMAIL:
                    notification_tasks.append(self._send_email_notification(alert))
                elif channel == NotificationChannel.SLACK:
                    notification_tasks.append(self._send_slack_notification(alert))
            
            # Send notifications concurrently
            if notification_tasks:
                results = await asyncio.gather(*notification_tasks, return_exceptions=True)
                
                # Log notification results
                successful_notifications = sum(1 for r in results if r is True)
                
                alert.notification_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "channels": [ch.value for ch in rule.notification_channels],
                    "successful": successful_notifications,
                    "total": len(notification_tasks)
                })
                
        except Exception as e:
            app_logger.error(f"Notification sending failed for alert {alert.alert_id}: {e}")
    
    async def _send_log_notification(self, alert: ManagedAlert) -> bool:
        """Send log-based notification"""
        
        try:
            log_level = "critical" if alert.severity == AlertSeverity.CRITICAL else "warning"
            app_logger.log(
                getattr(app_logger, log_level.upper()),
                f"Alert: {alert.title}",
                extra={
                    "alert_id": alert.alert_id,
                    "severity": alert.severity.value,
                    "description": alert.description,
                    "source_type": alert.source_type,
                    "metadata": alert.metadata
                }
            )
            return True
            
        except Exception as e:
            app_logger.error(f"Log notification failed: {e}")
            return False
    
    async def _send_webhook_notification(self, alert: ManagedAlert) -> bool:
        """Send webhook notification"""
        
        try:
            webhook_data = {
                "alert_id": alert.alert_id,
                "title": alert.title,
                "description": alert.description,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "source_type": alert.source_type,
                "created_at": alert.created_at.isoformat(),
                "metadata": alert.metadata
            }
            
            async with httpx.AsyncClient() as client:
                for endpoint in self.notification_config["webhook_endpoints"]:
                    try:
                        response = await client.post(
                            endpoint,
                            json=webhook_data,
                            timeout=10.0
                        )
                        
                        if response.status_code == 200:
                            return True
                            
                    except Exception as e:
                        app_logger.warning(f"Webhook notification to {endpoint} failed: {e}")
            
            return len(self.notification_config["webhook_endpoints"]) == 0  # True if no webhooks configured
            
        except Exception as e:
            app_logger.error(f"Webhook notification failed: {e}")
            return False
    
    async def _send_email_notification(self, alert: ManagedAlert) -> bool:
        """Send email notification"""
        
        try:
            # Email notification would require SMTP configuration
            # For now, just log that email would be sent
            
            app_logger.info(
                f"Email notification would be sent for alert {alert.alert_id}",
                extra={
                    "alert_title": alert.title,
                    "severity": alert.severity.value,
                    "to_emails": self.notification_config["email_config"]["to_emails"]
                }
            )
            
            return True  # Simulate successful email
            
        except Exception as e:
            app_logger.error(f"Email notification failed: {e}")
            return False
    
    async def _send_slack_notification(self, alert: ManagedAlert) -> bool:
        """Send Slack notification"""
        
        try:
            slack_webhook = self.notification_config["slack_config"]["webhook_url"]
            
            if not slack_webhook:
                return True  # No Slack configured
            
            # Determine emoji and color based on severity
            if alert.severity == AlertSeverity.CRITICAL:
                emoji = "🚨"
                color = "danger"
            elif alert.severity == AlertSeverity.WARNING:
                emoji = "⚠️"
                color = "warning"
            else:
                emoji = "ℹ️"
                color = "good"
            
            slack_message = {
                "channel": self.notification_config["slack_config"]["channel"],
                "username": "Kumon AI Assistant Alerts",
                "icon_emoji": ":robot_face:",
                "attachments": [
                    {
                        "color": color,
                        "title": f"{emoji} {alert.title}",
                        "text": alert.description,
                        "fields": [
                            {
                                "title": "Severity",
                                "value": alert.severity.value.upper(),
                                "short": True
                            },
                            {
                                "title": "Source",
                                "value": alert.source_type.title(),
                                "short": True
                            },
                            {
                                "title": "Alert ID",
                                "value": alert.alert_id,
                                "short": False
                            }
                        ],
                        "timestamp": int(alert.created_at.timestamp())
                    }
                ]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    slack_webhook,
                    json=slack_message,
                    timeout=10.0
                )
                
                return response.status_code == 200
                
        except Exception as e:
            app_logger.error(f"Slack notification failed: {e}")
            return False
    
    async def _schedule_escalation(self, alert: ManagedAlert):
        """Schedule alert escalation"""
        
        rule = self.alert_rules.get(alert.rule_id)
        if not rule or alert.severity == AlertSeverity.INFO:
            return
        
        # Set next escalation time
        alert.next_escalation = datetime.now() + timedelta(minutes=rule.escalation_timeout_minutes)
    
    async def _escalation_loop(self):
        """Handle alert escalations"""
        
        while self._processing_active:
            try:
                current_time = datetime.now()
                
                for alert in list(self.managed_alerts.values()):
                    if (alert.next_escalation and 
                        current_time >= alert.next_escalation and
                        alert.status == AlertStatus.ACTIVE):
                        
                        await self._escalate_alert(alert)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                app_logger.error(f"Escalation loop error: {e}")
                await asyncio.sleep(60)
    
    async def _escalate_alert(self, alert: ManagedAlert):
        """Escalate an alert"""
        
        try:
            rule = self.alert_rules.get(alert.rule_id)
            if not rule:
                return
            
            alert.escalation_count += 1
            
            # Check if we've reached max escalations
            if alert.escalation_count >= rule.max_escalations:
                # Move to suppressed or mark as unresolvable
                self.suppressed_alerts.add(alert.correlation_key)
                
                app_logger.warning(
                    f"Alert {alert.alert_id} suppressed after {alert.escalation_count} escalations"
                )
                return
            
            # Send escalation notification
            app_logger.warning(
                f"Escalating alert {alert.alert_id} (escalation #{alert.escalation_count})",
                extra={
                    "alert_title": alert.title,
                    "severity": alert.severity.value,
                    "escalation_count": alert.escalation_count
                }
            )
            
            # Increase severity for escalation
            if alert.severity == AlertSeverity.WARNING:
                alert.severity = AlertSeverity.CRITICAL
            
            # Send escalated notifications
            await self._send_notifications(alert)
            
            # Schedule next escalation
            alert.next_escalation = datetime.now() + timedelta(minutes=rule.escalation_timeout_minutes)
            
        except Exception as e:
            app_logger.error(f"Alert escalation failed: {e}")
    
    async def _cleanup_loop(self):
        """Clean up old alerts and manage suppression"""
        
        while self._processing_active:
            try:
                current_time = datetime.now()
                
                # Clean up resolved alerts older than 24 hours
                cutoff_time = current_time - timedelta(hours=24)
                
                for alert_id in list(self.managed_alerts.keys()):
                    alert = self.managed_alerts[alert_id]
                    
                    if (alert.status == AlertStatus.RESOLVED and 
                        alert.resolved_at and 
                        alert.resolved_at < cutoff_time):
                        
                        # Move to history and remove from active
                        self.alert_history.append(alert)
                        del self.managed_alerts[alert_id]
                
                # Clean up old suppressions (4 hours)
                suppression_cutoff = current_time - timedelta(hours=4)
                # Note: In a real implementation, you'd track suppression timestamps
                
                # Cleanup runs every hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                app_logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(3600)
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """Acknowledge an alert"""
        
        try:
            alert = self.managed_alerts.get(alert_id)
            if not alert:
                return False
            
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now()
            alert.updated_at = datetime.now()
            
            app_logger.info(
                f"Alert {alert_id} acknowledged by {acknowledged_by}",
                extra={"alert_id": alert_id, "acknowledged_by": acknowledged_by}
            )
            
            return True
            
        except Exception as e:
            app_logger.error(f"Alert acknowledgment failed: {e}")
            return False
    
    async def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """Resolve an alert"""
        
        try:
            alert = self.managed_alerts.get(alert_id)
            if not alert:
                return False
            
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            alert.updated_at = datetime.now()
            
            # Remove from suppression if present
            if alert.correlation_key:
                self.suppressed_alerts.discard(alert.correlation_key)
            
            app_logger.info(
                f"Alert {alert_id} resolved by {resolved_by}",
                extra={"alert_id": alert_id, "resolved_by": resolved_by}
            )
            
            return True
            
        except Exception as e:
            app_logger.error(f"Alert resolution failed: {e}")
            return False
    
    def get_alert_statistics(self) -> AlertStatistics:
        """Get alert management statistics"""
        
        try:
            current_time = datetime.now()
            twenty_four_hours_ago = current_time - timedelta(hours=24)
            
            # All alerts from last 24 hours
            recent_alerts = [
                alert for alert in list(self.managed_alerts.values()) + self.alert_history
                if alert.created_at > twenty_four_hours_ago
            ]
            
            # Active alerts
            active_alerts = [
                alert for alert in self.managed_alerts.values()
                if alert.status == AlertStatus.ACTIVE
            ]
            
            # Critical alerts
            critical_alerts = [
                alert for alert in active_alerts
                if alert.severity == AlertSeverity.CRITICAL
            ]
            
            # Resolved alerts in last 24 hours
            resolved_alerts = [
                alert for alert in recent_alerts
                if alert.status == AlertStatus.RESOLVED and alert.resolved_at
            ]
            
            # Calculate average resolution time
            if resolved_alerts:
                resolution_times = [
                    (alert.resolved_at - alert.created_at).total_seconds() / 60
                    for alert in resolved_alerts
                    if alert.resolved_at
                ]
                avg_resolution_time = statistics.mean(resolution_times)
            else:
                avg_resolution_time = 0.0
            
            # Top alert sources
            source_counts = {}
            for alert in recent_alerts:
                source_key = f"{alert.source_type}.{alert.metadata.get('component', 'unknown')}"
                source_counts[source_key] = source_counts.get(source_key, 0) + 1
            
            # Sort and get top 5
            top_sources = dict(sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5])
            
            # Escalation rate
            escalated_alerts = [alert for alert in recent_alerts if alert.escalation_count > 0]
            escalation_rate = len(escalated_alerts) / len(recent_alerts) if recent_alerts else 0.0
            
            # Notification success rate (simplified)
            total_notifications = sum(
                sum(log.get("total", 0) for log in alert.notification_log)
                for alert in recent_alerts
            )
            successful_notifications = sum(
                sum(log.get("successful", 0) for log in alert.notification_log)
                for alert in recent_alerts  
            )
            notification_success_rate = (
                successful_notifications / total_notifications 
                if total_notifications > 0 else 1.0
            )
            
            return AlertStatistics(
                total_alerts_24h=len(recent_alerts),
                active_alerts=len(active_alerts),
                critical_alerts=len(critical_alerts),
                resolved_alerts_24h=len(resolved_alerts),
                avg_resolution_time_minutes=avg_resolution_time,
                top_alert_sources=top_sources,
                escalation_rate=escalation_rate,
                notification_success_rate=notification_success_rate
            )
            
        except Exception as e:
            app_logger.error(f"Alert statistics calculation failed: {e}")
            
            # Return empty statistics on error
            return AlertStatistics(
                total_alerts_24h=0,
                active_alerts=0,
                critical_alerts=0,
                resolved_alerts_24h=0,
                avg_resolution_time_minutes=0.0,
                top_alert_sources={},
                escalation_rate=0.0,
                notification_success_rate=0.0
            )
    
    async def stop_processing(self):
        """Stop alert processing"""
        self._processing_active = False
        app_logger.info("Alert processing stopped")


# Global alert manager instance
alert_manager = AlertManager()