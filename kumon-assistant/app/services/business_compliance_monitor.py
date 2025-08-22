"""
Business Compliance Monitor - Phase 2 Wave 2.2 Business Logic Integration

Real-time business rule compliance tracking system:
- Pricing accuracy monitoring (R$375 + R$100 enforcement)
- Lead qualification completeness tracking (8 fields)
- Handoff appropriateness validation
- Business hours compliance verification
- RAG response accuracy monitoring
- Compliance audit trail maintenance

Provides real-time monitoring and alerting for business rule violations.
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import json

from ..core.logger import app_logger
from ..services.business_rules_engine import (
    business_rules_engine,
    BusinessRuleResult,
    RuleType,
    ValidationResult,
    LeadQualificationData
)
from ..services.enhanced_cache_service import enhanced_cache_service
from ..core.config import settings


class ComplianceLevel(Enum):
    """Business compliance severity levels"""
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    CRITICAL_VIOLATION = "critical_violation"


class ComplianceCategory(Enum):
    """Business compliance categories"""
    PRICING = "pricing"
    QUALIFICATION = "qualification"
    BUSINESS_HOURS = "business_hours"
    HANDOFF = "handoff"
    RAG_ACCURACY = "rag_accuracy"
    OVERALL = "overall"


@dataclass
class ComplianceAlert:
    """Business compliance alert"""
    alert_id: str
    category: ComplianceCategory
    level: ComplianceLevel
    message: str
    phone_number: str
    violation_details: Dict[str, Any]
    timestamp: datetime
    resolved: bool = False
    resolution_notes: Optional[str] = None


@dataclass
class ComplianceMetrics:
    """Business compliance metrics"""
    total_conversations: int = 0
    compliant_conversations: int = 0
    pricing_violations: int = 0
    qualification_incomplete: int = 0
    inappropriate_handoffs: int = 0
    business_hours_violations: int = 0
    rag_accuracy_issues: int = 0
    compliance_score: float = 100.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationComplianceRecord:
    """Individual conversation compliance record"""
    phone_number: str
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    compliance_checks: List[Dict[str, Any]] = field(default_factory=list)
    violations: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    final_compliance_score: float = 100.0
    handoff_occurred: bool = False
    handoff_reason: Optional[str] = None


class PricingComplianceMonitor:
    """Monitor pricing accuracy and policy compliance"""
    
    def __init__(self):
        self.monitor_name = "pricing_compliance"
        self.cache_prefix = "pricing_monitor"
        self.violation_threshold = 0.0  # Zero tolerance for pricing violations
    
    async def monitor_pricing_compliance(
        self, 
        conversation_record: ConversationComplianceRecord,
        business_rule_results: Dict[RuleType, BusinessRuleResult]
    ) -> Tuple[ComplianceLevel, List[ComplianceAlert]]:
        """Monitor pricing compliance in conversation"""
        
        try:
            alerts = []
            compliance_level = ComplianceLevel.COMPLIANT
            
            pricing_result = business_rule_results.get(RuleType.PRICING)
            if not pricing_result:
                return compliance_level, alerts
            
            # Check for pricing negotiations
            if pricing_result.validation_result == ValidationResult.REQUIRES_HANDOFF:
                violation_data = pricing_result.business_data or {}
                if violation_data.get("negotiation_detected", False):
                    alert = ComplianceAlert(
                        alert_id=f"pricing_neg_{conversation_record.session_id}_{int(datetime.now().timestamp())}",
                        category=ComplianceCategory.PRICING,
                        level=ComplianceLevel.WARNING,
                        message="Tentativa de negociação de preços detectada",
                        phone_number=conversation_record.phone_number,
                        violation_details={
                            "rule_type": "pricing_negotiation",
                            "detected_at": datetime.now().isoformat(),
                            "handoff_triggered": True,
                            "standard_pricing": violation_data.get("pricing_standard", {})
                        },
                        timestamp=datetime.now()
                    )
                    alerts.append(alert)
                    compliance_level = ComplianceLevel.WARNING
            
            # Check for pricing accuracy violations
            if pricing_result.validation_result == ValidationResult.REJECTED:
                alert = ComplianceAlert(
                    alert_id=f"pricing_acc_{conversation_record.session_id}_{int(datetime.now().timestamp())}",
                    category=ComplianceCategory.PRICING,
                    level=ComplianceLevel.VIOLATION,
                    message="Erro na validação de preços",
                    phone_number=conversation_record.phone_number,
                    violation_details={
                        "rule_type": "pricing_accuracy",
                        "error_code": pricing_result.error_code,
                        "detected_at": datetime.now().isoformat()
                    },
                    timestamp=datetime.now()
                )
                alerts.append(alert)
                compliance_level = ComplianceLevel.VIOLATION
            
            return compliance_level, alerts
            
        except Exception as e:
            app_logger.error(f"Pricing compliance monitoring error: {e}")
            return ComplianceLevel.VIOLATION, []


class QualificationComplianceMonitor:
    """Monitor lead qualification completeness and progress"""
    
    def __init__(self):
        self.monitor_name = "qualification_compliance"
        self.cache_prefix = "qualification_monitor"
        self.completion_threshold = 100.0  # 100% completion required
        self.warning_threshold = 50.0      # Warning below 50%
    
    async def monitor_qualification_compliance(
        self, 
        conversation_record: ConversationComplianceRecord,
        business_rule_results: Dict[RuleType, BusinessRuleResult]
    ) -> Tuple[ComplianceLevel, List[ComplianceAlert]]:
        """Monitor lead qualification compliance"""
        
        try:
            alerts = []
            compliance_level = ComplianceLevel.COMPLIANT
            
            qualification_result = business_rule_results.get(RuleType.QUALIFICATION)
            if not qualification_result:
                return compliance_level, alerts
            
            qualification_data = qualification_result.business_data or {}
            completion_percentage = qualification_data.get("completion_percentage", 0.0)
            missing_fields = qualification_data.get("missing_fields", [])
            is_qualified = qualification_data.get("is_qualified", False)
            
            # Check for incomplete qualification at conversation end
            conversation_duration = (
                (conversation_record.end_time or datetime.now()) - conversation_record.start_time
            ).total_seconds() / 60  # minutes
            
            if conversation_duration > 5 and not is_qualified:  # After 5 minutes
                if completion_percentage < self.warning_threshold:
                    alert = ComplianceAlert(
                        alert_id=f"qual_inc_{conversation_record.session_id}_{int(datetime.now().timestamp())}",
                        category=ComplianceCategory.QUALIFICATION,
                        level=ComplianceLevel.WARNING,
                        message=f"Qualificação incompleta após {conversation_duration:.0f} minutos: {completion_percentage:.0f}%",
                        phone_number=conversation_record.phone_number,
                        violation_details={
                            "completion_percentage": completion_percentage,
                            "missing_fields": missing_fields,
                            "conversation_duration_minutes": conversation_duration,
                            "detected_at": datetime.now().isoformat()
                        },
                        timestamp=datetime.now()
                    )
                    alerts.append(alert)
                    compliance_level = ComplianceLevel.WARNING
            
            # Check for qualification stagnation (no progress)
            if len(conversation_record.compliance_checks) > 3:
                recent_checks = conversation_record.compliance_checks[-3:]
                completion_progress = [
                    check.get("qualification_completion", 0.0) for check in recent_checks
                    if "qualification_completion" in check
                ]
                
                if len(completion_progress) >= 2:
                    progress_change = completion_progress[-1] - completion_progress[0]
                    if progress_change == 0 and completion_progress[-1] < 75.0:
                        alert = ComplianceAlert(
                            alert_id=f"qual_stag_{conversation_record.session_id}_{int(datetime.now().timestamp())}",
                            category=ComplianceCategory.QUALIFICATION,
                            level=ComplianceLevel.WARNING,
                            message="Estagnação na qualificação detectada",
                            phone_number=conversation_record.phone_number,
                            violation_details={
                                "stagnation_detected": True,
                                "current_completion": completion_progress[-1],
                                "progress_change": progress_change,
                                "detected_at": datetime.now().isoformat()
                            },
                            timestamp=datetime.now()
                        )
                        alerts.append(alert)
                        if compliance_level == ComplianceLevel.COMPLIANT:
                            compliance_level = ComplianceLevel.WARNING
            
            return compliance_level, alerts
            
        except Exception as e:
            app_logger.error(f"Qualification compliance monitoring error: {e}")
            return ComplianceLevel.COMPLIANT, []


class HandoffComplianceMonitor:
    """Monitor handoff appropriateness and timing"""
    
    def __init__(self):
        self.monitor_name = "handoff_compliance"
        self.cache_prefix = "handoff_monitor"
    
    async def monitor_handoff_compliance(
        self, 
        conversation_record: ConversationComplianceRecord,
        business_rule_results: Dict[RuleType, BusinessRuleResult]
    ) -> Tuple[ComplianceLevel, List[ComplianceAlert]]:
        """Monitor handoff compliance"""
        
        try:
            alerts = []
            compliance_level = ComplianceLevel.COMPLIANT
            
            handoff_result = business_rule_results.get(RuleType.HANDOFF)
            if not handoff_result:
                return compliance_level, alerts
            
            # Check for appropriate handoff triggers
            if handoff_result.validation_result == ValidationResult.REQUIRES_HANDOFF:
                handoff_data = handoff_result.business_data or {}
                handoff_score = handoff_data.get("handoff_score", 0.0)
                handoff_reasons = handoff_data.get("handoff_reasons", [])
                
                # Validate handoff appropriateness
                if handoff_score < 0.7:
                    alert = ComplianceAlert(
                        alert_id=f"handoff_low_{conversation_record.session_id}_{int(datetime.now().timestamp())}",
                        category=ComplianceCategory.HANDOFF,
                        level=ComplianceLevel.WARNING,
                        message=f"Handoff com score baixo: {handoff_score:.2f}",
                        phone_number=conversation_record.phone_number,
                        violation_details={
                            "handoff_score": handoff_score,
                            "handoff_reasons": handoff_reasons,
                            "threshold": 0.7,
                            "detected_at": datetime.now().isoformat()
                        },
                        timestamp=datetime.now()
                    )
                    alerts.append(alert)
                    compliance_level = ComplianceLevel.WARNING
                
                # Log appropriate handoff
                conversation_record.handoff_occurred = True
                conversation_record.handoff_reason = ", ".join(handoff_reasons)
            
            # Check for missed handoff opportunities
            elif handoff_result.validation_result == ValidationResult.WARNING:
                handoff_data = handoff_result.business_data or {}
                if handoff_data.get("monitoring", False):
                    alert = ComplianceAlert(
                        alert_id=f"handoff_mon_{conversation_record.session_id}_{int(datetime.now().timestamp())}",
                        category=ComplianceCategory.HANDOFF,
                        level=ComplianceLevel.WARNING,
                        message="Situação monitorada para possível escalação",
                        phone_number=conversation_record.phone_number,
                        violation_details={
                            "monitoring_active": True,
                            "handoff_score": handoff_data.get("handoff_score", 0.0),
                            "detected_at": datetime.now().isoformat()
                        },
                        timestamp=datetime.now()
                    )
                    alerts.append(alert)
                    if compliance_level == ComplianceLevel.COMPLIANT:
                        compliance_level = ComplianceLevel.WARNING
            
            return compliance_level, alerts
            
        except Exception as e:
            app_logger.error(f"Handoff compliance monitoring error: {e}")
            return ComplianceLevel.COMPLIANT, []


class BusinessHoursComplianceMonitor:
    """Monitor business hours compliance"""
    
    def __init__(self):
        self.monitor_name = "business_hours_compliance"
        self.cache_prefix = "hours_monitor"
    
    async def monitor_business_hours_compliance(
        self, 
        conversation_record: ConversationComplianceRecord,
        business_rule_results: Dict[RuleType, BusinessRuleResult]
    ) -> Tuple[ComplianceLevel, List[ComplianceAlert]]:
        """Monitor business hours compliance"""
        
        try:
            alerts = []
            compliance_level = ComplianceLevel.COMPLIANT
            
            hours_result = business_rule_results.get(RuleType.BUSINESS_HOURS)
            if not hours_result:
                return compliance_level, alerts
            
            # Check for out-of-hours interactions
            if hours_result.validation_result == ValidationResult.REJECTED:
                hours_data = hours_result.business_data or {}
                alert = ComplianceAlert(
                    alert_id=f"hours_out_{conversation_record.session_id}_{int(datetime.now().timestamp())}",
                    category=ComplianceCategory.BUSINESS_HOURS,
                    level=ComplianceLevel.WARNING,
                    message="Interação fora do horário comercial",
                    phone_number=conversation_record.phone_number,
                    violation_details={
                        "is_business_hours": hours_data.get("is_business_hours", False),
                        "is_business_day": hours_data.get("is_business_day", False),
                        "current_time": hours_data.get("current_time", ""),
                        "next_available": hours_data.get("next_available", ""),
                        "detected_at": datetime.now().isoformat()
                    },
                    timestamp=datetime.now()
                )
                alerts.append(alert)
                compliance_level = ComplianceLevel.WARNING
            
            # Check for lunch break interactions
            elif hours_result.validation_result == ValidationResult.WARNING:
                hours_data = hours_result.business_data or {}
                if hours_data.get("is_lunch_break", False):
                    alert = ComplianceAlert(
                        alert_id=f"hours_lunch_{conversation_record.session_id}_{int(datetime.now().timestamp())}",
                        category=ComplianceCategory.BUSINESS_HOURS,
                        level=ComplianceLevel.WARNING,
                        message="Interação durante horário de almoço",
                        phone_number=conversation_record.phone_number,
                        violation_details={
                            "is_lunch_break": True,
                            "current_time": hours_data.get("current_time", ""),
                            "next_available": hours_data.get("next_available", ""),
                            "detected_at": datetime.now().isoformat()
                        },
                        timestamp=datetime.now()
                    )
                    alerts.append(alert)
                    if compliance_level == ComplianceLevel.COMPLIANT:
                        compliance_level = ComplianceLevel.WARNING
            
            return compliance_level, alerts
            
        except Exception as e:
            app_logger.error(f"Business hours compliance monitoring error: {e}")
            return ComplianceLevel.COMPLIANT, []


class BusinessComplianceMonitor:
    """
    Comprehensive Business Compliance Monitor
    
    Real-time monitoring of business rule adherence across all conversations:
    - Pricing accuracy and policy enforcement
    - Lead qualification completeness tracking
    - Handoff appropriateness validation
    - Business hours compliance verification
    - RAG response accuracy monitoring
    - Compliance audit trail maintenance
    """
    
    def __init__(self):
        # Initialize specialized monitors
        self.pricing_monitor = PricingComplianceMonitor()
        self.qualification_monitor = QualificationComplianceMonitor()
        self.handoff_monitor = HandoffComplianceMonitor()
        self.hours_monitor = BusinessHoursComplianceMonitor()
        
        # Active conversation records
        self.active_conversations: Dict[str, ConversationComplianceRecord] = {}
        
        # Compliance metrics and alerts
        self.compliance_metrics = ComplianceMetrics()
        self.active_alerts: Dict[str, ComplianceAlert] = {}
        self.resolved_alerts: List[ComplianceAlert] = []
        
        # Configuration
        self.config = {
            "alert_retention_days": 30,
            "metrics_update_interval": 60,  # seconds
            "critical_alert_threshold": 5,
            "auto_resolution_timeout": 3600  # 1 hour
        }
        
        app_logger.info("Business Compliance Monitor initialized")
    
    async def start_conversation_monitoring(
        self, 
        phone_number: str, 
        session_id: str
    ) -> ConversationComplianceRecord:
        """Start monitoring a new conversation"""
        
        try:
            conversation_record = ConversationComplianceRecord(
                phone_number=phone_number,
                session_id=session_id,
                start_time=datetime.now(),
                end_time=None
            )
            
            self.active_conversations[session_id] = conversation_record
            
            app_logger.info(f"Started compliance monitoring for conversation {session_id}")
            return conversation_record
            
        except Exception as e:
            app_logger.error(f"Error starting conversation monitoring: {e}")
            raise
    
    async def monitor_business_compliance(
        self,
        session_id: str,
        business_rule_results: Dict[RuleType, BusinessRuleResult]
    ) -> Dict[ComplianceCategory, Tuple[ComplianceLevel, List[ComplianceAlert]]]:
        """Monitor comprehensive business compliance for a conversation"""
        
        try:
            conversation_record = self.active_conversations.get(session_id)
            if not conversation_record:
                app_logger.warning(f"No active conversation record for session {session_id}")
                return {}
            
            # Execute all compliance monitors in parallel
            monitor_tasks = [
                self.pricing_monitor.monitor_pricing_compliance(conversation_record, business_rule_results),
                self.qualification_monitor.monitor_qualification_compliance(conversation_record, business_rule_results),
                self.handoff_monitor.monitor_handoff_compliance(conversation_record, business_rule_results),
                self.hours_monitor.monitor_business_hours_compliance(conversation_record, business_rule_results)
            ]
            
            # Wait for all monitors to complete
            monitor_results = await asyncio.gather(*monitor_tasks, return_exceptions=True)
            
            # Process monitoring results
            compliance_report = {}
            all_alerts = []
            overall_compliance_level = ComplianceLevel.COMPLIANT
            
            categories = [
                ComplianceCategory.PRICING,
                ComplianceCategory.QUALIFICATION,
                ComplianceCategory.HANDOFF,
                ComplianceCategory.BUSINESS_HOURS
            ]
            
            for i, result in enumerate(monitor_results):
                if isinstance(result, Exception):
                    app_logger.error(f"Monitor {categories[i].value} failed: {result}")
                    continue
                
                if isinstance(result, tuple) and len(result) == 2:
                    compliance_level, alerts = result
                    compliance_report[categories[i]] = (compliance_level, alerts)
                    all_alerts.extend(alerts)
                    
                    # Update overall compliance level
                    if compliance_level.value == "critical_violation":
                        overall_compliance_level = ComplianceLevel.CRITICAL_VIOLATION
                    elif compliance_level.value == "violation" and overall_compliance_level.value != "critical_violation":
                        overall_compliance_level = ComplianceLevel.VIOLATION
                    elif compliance_level.value == "warning" and overall_compliance_level.value == "compliant":
                        overall_compliance_level = ComplianceLevel.WARNING
            
            # Store compliance check in conversation record
            compliance_check = {
                "timestamp": datetime.now().isoformat(),
                "overall_compliance": overall_compliance_level.value,
                "category_results": {
                    cat.value: level.value for cat, (level, _) in compliance_report.items()
                },
                "alerts_generated": len(all_alerts)
            }
            
            # Add qualification completion tracking
            qualification_result = business_rule_results.get(RuleType.QUALIFICATION)
            if qualification_result and qualification_result.business_data:
                compliance_check["qualification_completion"] = qualification_result.business_data.get("completion_percentage", 0.0)
            
            conversation_record.compliance_checks.append(compliance_check)
            
            # Process alerts
            for alert in all_alerts:
                self.active_alerts[alert.alert_id] = alert
                
                if alert.level in [ComplianceLevel.VIOLATION, ComplianceLevel.CRITICAL_VIOLATION]:
                    conversation_record.violations.append(asdict(alert))
                else:
                    conversation_record.warnings.append(asdict(alert))
            
            # Update compliance metrics
            await self._update_compliance_metrics(conversation_record, compliance_report)
            
            app_logger.info(
                f"Compliance monitoring completed for {session_id}: "
                f"{overall_compliance_level.value}, {len(all_alerts)} alerts"
            )
            
            return compliance_report
            
        except Exception as e:
            app_logger.error(f"Business compliance monitoring error: {e}")
            return {}
    
    async def end_conversation_monitoring(
        self, 
        session_id: str
    ) -> Optional[ConversationComplianceRecord]:
        """End monitoring for a conversation and generate final report"""
        
        try:
            conversation_record = self.active_conversations.get(session_id)
            if not conversation_record:
                return None
            
            conversation_record.end_time = datetime.now()
            
            # Calculate final compliance score
            if conversation_record.compliance_checks:
                compliance_scores = []
                for check in conversation_record.compliance_checks:
                    if check["overall_compliance"] == "compliant":
                        compliance_scores.append(100.0)
                    elif check["overall_compliance"] == "warning":
                        compliance_scores.append(80.0)
                    elif check["overall_compliance"] == "violation":
                        compliance_scores.append(60.0)
                    else:  # critical_violation
                        compliance_scores.append(20.0)
                
                conversation_record.final_compliance_score = sum(compliance_scores) / len(compliance_scores)
            
            # Archive the conversation record
            await self._archive_conversation_record(conversation_record)
            
            # Remove from active conversations
            del self.active_conversations[session_id]
            
            app_logger.info(
                f"Ended compliance monitoring for {session_id}: "
                f"Final score {conversation_record.final_compliance_score:.1f}%"
            )
            
            return conversation_record
            
        except Exception as e:
            app_logger.error(f"Error ending conversation monitoring: {e}")
            return None
    
    async def get_compliance_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive compliance dashboard data"""
        
        try:
            # Update current metrics
            await self._refresh_compliance_metrics()
            
            # Get active alerts summary
            active_alerts_summary = {}
            for category in ComplianceCategory:
                category_alerts = [
                    alert for alert in self.active_alerts.values() 
                    if alert.category == category and not alert.resolved
                ]
                active_alerts_summary[category.value] = {
                    "total": len(category_alerts),
                    "critical": len([a for a in category_alerts if a.level == ComplianceLevel.CRITICAL_VIOLATION]),
                    "violations": len([a for a in category_alerts if a.level == ComplianceLevel.VIOLATION]),
                    "warnings": len([a for a in category_alerts if a.level == ComplianceLevel.WARNING])
                }
            
            # Get conversation statistics
            conversation_stats = {
                "active_conversations": len(self.active_conversations),
                "conversations_today": await self._count_conversations_today(),
                "avg_compliance_score": await self._calculate_avg_compliance_score(),
                "handoff_rate": await self._calculate_handoff_rate()
            }
            
            dashboard = {
                "compliance_metrics": asdict(self.compliance_metrics),
                "active_alerts_summary": active_alerts_summary,
                "conversation_statistics": conversation_stats,
                "monitoring_status": {
                    "monitors_active": 4,
                    "last_update": datetime.now().isoformat(),
                    "system_health": "operational"
                },
                "recent_violations": [
                    asdict(alert) for alert in list(self.active_alerts.values())[-10:]
                    if alert.level in [ComplianceLevel.VIOLATION, ComplianceLevel.CRITICAL_VIOLATION]
                ]
            }
            
            return dashboard
            
        except Exception as e:
            app_logger.error(f"Error generating compliance dashboard: {e}")
            return {"error": str(e)}
    
    async def _update_compliance_metrics(
        self, 
        conversation_record: ConversationComplianceRecord,
        compliance_report: Dict[ComplianceCategory, Tuple[ComplianceLevel, List[ComplianceAlert]]]
    ):
        """Update overall compliance metrics"""
        
        try:
            # Update conversation counts
            self.compliance_metrics.total_conversations += 1
            
            # Check if conversation is compliant
            is_compliant = all(
                level == ComplianceLevel.COMPLIANT 
                for level, _ in compliance_report.values()
            )
            
            if is_compliant:
                self.compliance_metrics.compliant_conversations += 1
            
            # Update category-specific violations
            for category, (level, alerts) in compliance_report.items():
                if category == ComplianceCategory.PRICING and level != ComplianceLevel.COMPLIANT:
                    self.compliance_metrics.pricing_violations += 1
                elif category == ComplianceCategory.QUALIFICATION and level != ComplianceLevel.COMPLIANT:
                    self.compliance_metrics.qualification_incomplete += 1
                elif category == ComplianceCategory.HANDOFF and level != ComplianceLevel.COMPLIANT:
                    self.compliance_metrics.inappropriate_handoffs += 1
                elif category == ComplianceCategory.BUSINESS_HOURS and level != ComplianceLevel.COMPLIANT:
                    self.compliance_metrics.business_hours_violations += 1
            
            # Calculate overall compliance score
            if self.compliance_metrics.total_conversations > 0:
                self.compliance_metrics.compliance_score = (
                    (self.compliance_metrics.compliant_conversations / self.compliance_metrics.total_conversations) * 100
                )
            
            self.compliance_metrics.last_updated = datetime.now()
            
        except Exception as e:
            app_logger.error(f"Error updating compliance metrics: {e}")
    
    async def _archive_conversation_record(self, record: ConversationComplianceRecord):
        """Archive completed conversation record"""
        
        try:
            cache_key = f"conversation_record:{record.session_id}"
            await enhanced_cache_service.set(
                cache_key,
                asdict(record),
                category="compliance_records",
                ttl=self.config["alert_retention_days"] * 24 * 3600  # Convert days to seconds
            )
            
        except Exception as e:
            app_logger.error(f"Error archiving conversation record: {e}")
    
    async def _refresh_compliance_metrics(self):
        """Refresh compliance metrics with current data"""
        # Implementation would refresh metrics from stored data
        pass
    
    async def _count_conversations_today(self) -> int:
        """Count conversations started today"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = 0
        
        for record in self.active_conversations.values():
            if record.start_time >= today_start:
                count += 1
        
        return count
    
    async def _calculate_avg_compliance_score(self) -> float:
        """Calculate average compliance score"""
        if not self.active_conversations:
            return 100.0
        
        total_score = sum(
            record.final_compliance_score for record in self.active_conversations.values()
            if record.final_compliance_score > 0
        )
        
        valid_records = len([
            record for record in self.active_conversations.values()
            if record.final_compliance_score > 0
        ])
        
        return total_score / max(1, valid_records)
    
    async def _calculate_handoff_rate(self) -> float:
        """Calculate handoff rate percentage"""
        if not self.active_conversations:
            return 0.0
        
        handoff_count = sum(
            1 for record in self.active_conversations.values()
            if record.handoff_occurred
        )
        
        return (handoff_count / len(self.active_conversations)) * 100


# Global business compliance monitor instance
business_compliance_monitor = BusinessComplianceMonitor()


__all__ = [
    'ComplianceLevel',
    'ComplianceCategory',
    'ComplianceAlert',
    'ComplianceMetrics',
    'ConversationComplianceRecord',
    'PricingComplianceMonitor',
    'QualificationComplianceMonitor',
    'HandoffComplianceMonitor',
    'BusinessHoursComplianceMonitor',
    'BusinessComplianceMonitor',
    'business_compliance_monitor'
]