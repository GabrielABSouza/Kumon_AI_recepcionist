"""
Quality Metrics Dashboard
Real-time quality monitoring and metrics collection for the Kumon Assistant
"""

import asyncio
import json
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

from app.core.logger import app_logger
from app.monitoring.security_monitor import security_monitor
from app.core.config import settings


class MetricType(Enum):
    """Types of quality metrics"""
    SECURITY = "security"
    PERFORMANCE = "performance" 
    RELIABILITY = "reliability"
    BUSINESS = "business"
    QUALITY = "quality"


@dataclass
class QualityMetric:
    """Individual quality metric"""
    name: str
    value: float
    threshold: float
    status: str  # "good", "warning", "critical"
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass
class QualityReport:
    """Comprehensive quality report"""
    timestamp: datetime
    overall_score: float
    category_scores: Dict[str, float]
    metrics: List[QualityMetric]
    trends: Dict[str, List[float]]
    alerts: List[str]
    recommendations: List[str]


class QualityMetricsDashboard:
    """
    Quality Metrics Dashboard
    
    Provides comprehensive quality monitoring including:
    - Real-time quality scoring
    - Trend analysis and alerting
    - Performance benchmarking
    - Quality gate validation
    - Automated reporting
    """
    
    def __init__(self):
        self.metrics_history: List[QualityReport] = []
        self.alert_thresholds = {
            # Security metrics
            "security_score": 0.95,
            "threat_detection_rate": 0.95,
            "false_positive_rate": 0.05,
            
            # Performance metrics
            "avg_response_time": 3.0,
            "p95_response_time": 5.0,
            "memory_usage_mb": 500,
            "error_rate": 0.001,
            
            # Reliability metrics
            "uptime_percentage": 0.999,
            "success_rate": 0.98,
            "failover_time": 30.0,
            
            # Business metrics
            "intent_accuracy": 0.90,
            "conversation_completion": 0.85,
            "customer_satisfaction": 4.5,
            "booking_conversion": 0.60,
            
            # Quality metrics
            "test_coverage": 0.80,
            "code_quality_score": 0.80,
            "documentation_coverage": 0.75
        }
        
        self.trend_analysis_window = 24  # hours
        self.reporting_interval = 3600  # 1 hour
        
        app_logger.info("Quality Metrics Dashboard initialized")
    
    async def collect_comprehensive_metrics(self) -> QualityReport:
        """Collect comprehensive quality metrics from all systems"""
        
        timestamp = datetime.now()
        
        # Collect metrics from various sources
        security_metrics = await self._collect_security_metrics()
        performance_metrics = await self._collect_performance_metrics()
        reliability_metrics = await self._collect_reliability_metrics()
        business_metrics = await self._collect_business_metrics()
        quality_metrics = await self._collect_quality_metrics()
        
        # Combine all metrics
        all_metrics = (
            security_metrics + performance_metrics + 
            reliability_metrics + business_metrics + quality_metrics
        )
        
        # Calculate category scores
        category_scores = {
            "security": self._calculate_category_score(security_metrics),
            "performance": self._calculate_category_score(performance_metrics),
            "reliability": self._calculate_category_score(reliability_metrics),
            "business": self._calculate_category_score(business_metrics),
            "quality": self._calculate_category_score(quality_metrics)
        }
        
        # Calculate overall score
        overall_score = sum(category_scores.values()) / len(category_scores)
        
        # Generate trends
        trends = self._calculate_trends(all_metrics)
        
        # Generate alerts and recommendations
        alerts = self._generate_alerts(all_metrics)
        recommendations = self._generate_recommendations(all_metrics, category_scores)
        
        # Create quality report
        report = QualityReport(
            timestamp=timestamp,
            overall_score=overall_score,
            category_scores=category_scores,
            metrics=all_metrics,
            trends=trends,
            alerts=alerts,
            recommendations=recommendations
        )
        
        # Store in history
        self.metrics_history.append(report)
        
        # Clean up old metrics (keep last 7 days)
        cutoff_time = timestamp - timedelta(days=7)
        self.metrics_history = [
            r for r in self.metrics_history
            if r.timestamp > cutoff_time
        ]
        
        return report
    
    async def _collect_security_metrics(self) -> List[QualityMetric]:
        """Collect security-related quality metrics"""
        
        try:
            # Get security dashboard data
            dashboard = await security_monitor.get_security_dashboard()
            
            metrics = []
            
            # Security score metric
            metrics.append(QualityMetric(
                name="security_score",
                value=dashboard.security_score,
                threshold=self.alert_thresholds["security_score"],
                status=self._get_metric_status(
                    dashboard.security_score, 
                    self.alert_thresholds["security_score"]
                ),
                timestamp=datetime.now(),
                metadata={"source": "security_monitor"}
            ))
            
            # Threat detection rate
            if dashboard.total_requests > 0:
                threat_detection_rate = dashboard.blocked_requests / dashboard.total_requests
                metrics.append(QualityMetric(
                    name="threat_detection_rate",
                    value=threat_detection_rate,
                    threshold=self.alert_thresholds["threat_detection_rate"],
                    status=self._get_metric_status(
                        threat_detection_rate,
                        self.alert_thresholds["threat_detection_rate"]
                    ),
                    timestamp=datetime.now(),
                    metadata={"blocked": dashboard.blocked_requests, "total": dashboard.total_requests}
                ))
            
            # Active threats metric
            metrics.append(QualityMetric(
                name="active_threats",
                value=dashboard.active_threats,
                threshold=5,  # More than 5 active threats is concerning
                status="critical" if dashboard.active_threats > 5 else "good",
                timestamp=datetime.now(),
                metadata={"count": dashboard.active_threats}
            ))
            
            return metrics
            
        except Exception as e:
            app_logger.error(f"Failed to collect security metrics: {e}")
            return []
    
    async def _collect_performance_metrics(self) -> List[QualityMetric]:
        """Collect performance-related quality metrics"""
        
        try:
            # Get performance metrics from security monitor
            dashboard = await security_monitor.get_security_dashboard()
            
            metrics = []
            
            # Average response time
            metrics.append(QualityMetric(
                name="avg_response_time",
                value=dashboard.avg_response_time,
                threshold=self.alert_thresholds["avg_response_time"],
                status=self._get_metric_status(
                    dashboard.avg_response_time,
                    self.alert_thresholds["avg_response_time"],
                    lower_is_better=True
                ),
                timestamp=datetime.now(),
                metadata={"unit": "seconds"}
            ))
            
            # Memory usage (requires psutil)
            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                
                metrics.append(QualityMetric(
                    name="memory_usage_mb",
                    value=memory_mb,
                    threshold=self.alert_thresholds["memory_usage_mb"],
                    status=self._get_metric_status(
                        memory_mb,
                        self.alert_thresholds["memory_usage_mb"],
                        lower_is_better=True
                    ),
                    timestamp=datetime.now(),
                    metadata={"unit": "MB"}
                ))
            except ImportError:
                app_logger.warning("psutil not available for memory metrics")
            
            return metrics
            
        except Exception as e:
            app_logger.error(f"Failed to collect performance metrics: {e}")
            return []
    
    async def _collect_reliability_metrics(self) -> List[QualityMetric]:
        """Collect reliability-related quality metrics"""
        
        try:
            metrics = []
            
            # System uptime calculation (simplified)
            dashboard = await security_monitor.get_security_dashboard()
            
            # Calculate uptime based on system status
            uptime_score = 1.0 if dashboard.system_status in ["EXCELLENT", "GOOD"] else 0.8
            
            metrics.append(QualityMetric(
                name="system_uptime",
                value=uptime_score,
                threshold=self.alert_thresholds["uptime_percentage"],
                status=self._get_metric_status(
                    uptime_score,
                    self.alert_thresholds["uptime_percentage"]
                ),
                timestamp=datetime.now(),
                metadata={"system_status": dashboard.system_status}
            ))
            
            # Component health analysis
            healthy_components = sum(1 for status in dashboard.component_status.values() 
                                   if status == "healthy")
            total_components = len(dashboard.component_status)
            
            if total_components > 0:
                component_health_ratio = healthy_components / total_components
                
                metrics.append(QualityMetric(
                    name="component_health_ratio",
                    value=component_health_ratio,
                    threshold=0.90,  # 90% of components should be healthy
                    status=self._get_metric_status(component_health_ratio, 0.90),
                    timestamp=datetime.now(),
                    metadata={
                        "healthy": healthy_components,
                        "total": total_components,
                        "status_details": dashboard.component_status
                    }
                ))
            
            return metrics
            
        except Exception as e:
            app_logger.error(f"Failed to collect reliability metrics: {e}")
            return []
    
    async def _collect_business_metrics(self) -> List[QualityMetric]:
        """Collect business-related quality metrics"""
        
        try:
            metrics = []
            
            # Simulated business metrics (would come from actual business logic)
            # In real implementation, these would come from conversation analytics
            
            # Intent classification accuracy (simulated)
            intent_accuracy = 0.92  # Would be calculated from actual conversation data
            metrics.append(QualityMetric(
                name="intent_accuracy",
                value=intent_accuracy,
                threshold=self.alert_thresholds["intent_accuracy"],
                status=self._get_metric_status(intent_accuracy, self.alert_thresholds["intent_accuracy"]),
                timestamp=datetime.now(),
                metadata={"method": "simulated", "note": "Replace with real analytics"}
            ))
            
            # Conversation completion rate (simulated)
            completion_rate = 0.88
            metrics.append(QualityMetric(
                name="conversation_completion_rate",
                value=completion_rate,
                threshold=self.alert_thresholds["conversation_completion"],
                status=self._get_metric_status(completion_rate, self.alert_thresholds["conversation_completion"]),
                timestamp=datetime.now(),
                metadata={"method": "simulated"}
            ))
            
            # Customer satisfaction (simulated)
            satisfaction_score = 4.6
            metrics.append(QualityMetric(
                name="customer_satisfaction",
                value=satisfaction_score,
                threshold=self.alert_thresholds["customer_satisfaction"],
                status=self._get_metric_status(satisfaction_score, self.alert_thresholds["customer_satisfaction"]),
                timestamp=datetime.now(),
                metadata={"scale": "1-5", "method": "simulated"}
            ))
            
            return metrics
            
        except Exception as e:
            app_logger.error(f"Failed to collect business metrics: {e}")
            return []
    
    async def _collect_quality_metrics(self) -> List[QualityMetric]:
        """Collect code/system quality metrics"""
        
        try:
            metrics = []
            
            # Test coverage (would be calculated from test runner)
            # For now, simulated based on project structure
            test_coverage = 0.82  # Would come from pytest coverage report
            
            metrics.append(QualityMetric(
                name="test_coverage",
                value=test_coverage,
                threshold=self.alert_thresholds["test_coverage"],
                status=self._get_metric_status(test_coverage, self.alert_thresholds["test_coverage"]),
                timestamp=datetime.now(),
                metadata={"unit": "percentage", "method": "simulated"}
            ))
            
            # Code quality score (would come from linting/static analysis)
            code_quality = 0.85
            metrics.append(QualityMetric(
                name="code_quality_score",
                value=code_quality,
                threshold=self.alert_thresholds["code_quality_score"],
                status=self._get_metric_status(code_quality, self.alert_thresholds["code_quality_score"]),
                timestamp=datetime.now(),
                metadata={"method": "simulated", "note": "Implement with pylint/flake8"}
            ))
            
            return metrics
            
        except Exception as e:
            app_logger.error(f"Failed to collect quality metrics: {e}")
            return []
    
    def _calculate_category_score(self, metrics: List[QualityMetric]) -> float:
        """Calculate average score for a category of metrics"""
        
        if not metrics:
            return 0.0
        
        # Convert metrics to normalized scores (0-1)
        scores = []
        for metric in metrics:
            if metric.status == "good":
                scores.append(1.0)
            elif metric.status == "warning":
                scores.append(0.7)
            else:  # critical
                scores.append(0.3)
        
        return sum(scores) / len(scores)
    
    def _get_metric_status(self, value: float, threshold: float, lower_is_better: bool = False) -> str:
        """Determine metric status based on value and threshold"""
        
        if lower_is_better:
            if value <= threshold:
                return "good"
            elif value <= threshold * 1.5:
                return "warning"
            else:
                return "critical"
        else:
            if value >= threshold:
                return "good"
            elif value >= threshold * 0.8:
                return "warning"
            else:
                return "critical"
    
    def _calculate_trends(self, metrics: List[QualityMetric]) -> Dict[str, List[float]]:
        """Calculate trends for key metrics"""
        
        trends = {}
        
        # Get historical data for trend calculation
        if len(self.metrics_history) > 1:
            for metric in metrics:
                metric_name = metric.name
                historical_values = []
                
                # Get last 10 values for this metric
                for report in self.metrics_history[-10:]:
                    for historical_metric in report.metrics:
                        if historical_metric.name == metric_name:
                            historical_values.append(historical_metric.value)
                            break
                
                if len(historical_values) > 1:
                    trends[metric_name] = historical_values
        
        return trends
    
    def _generate_alerts(self, metrics: List[QualityMetric]) -> List[str]:
        """Generate alerts based on metric status"""
        
        alerts = []
        
        critical_metrics = [m for m in metrics if m.status == "critical"]
        warning_metrics = [m for m in metrics if m.status == "warning"]
        
        for metric in critical_metrics:
            alerts.append(f"CRITICAL: {metric.name} is {metric.value:.3f} (threshold: {metric.threshold})")
        
        for metric in warning_metrics:
            alerts.append(f"WARNING: {metric.name} is {metric.value:.3f} (threshold: {metric.threshold})")
        
        return alerts
    
    def _generate_recommendations(
        self, 
        metrics: List[QualityMetric], 
        category_scores: Dict[str, float]
    ) -> List[str]:
        """Generate improvement recommendations based on metrics"""
        
        recommendations = []
        
        # Category-based recommendations
        if category_scores["security"] < 0.8:
            recommendations.append("Review security configurations and update threat detection rules")
        
        if category_scores["performance"] < 0.8:
            recommendations.append("Investigate performance bottlenecks and optimize response times")
        
        if category_scores["reliability"] < 0.8:
            recommendations.append("Check system components and improve error handling")
        
        if category_scores["business"] < 0.8:
            recommendations.append("Review conversation flows and improve intent classification")
        
        # Specific metric recommendations
        critical_metrics = [m for m in metrics if m.status == "critical"]
        
        for metric in critical_metrics:
            if metric.name == "avg_response_time":
                recommendations.append("Optimize database queries and implement caching")
            elif metric.name == "memory_usage_mb":
                recommendations.append("Investigate memory leaks and optimize data structures")
            elif metric.name == "security_score":
                recommendations.append("Update security policies and review threat detection accuracy")
        
        return recommendations
    
    async def generate_html_report(self, output_path: str = "quality_report.html") -> str:
        """Generate HTML quality report"""
        
        if not self.metrics_history:
            await self.collect_comprehensive_metrics()
        
        latest_report = self.metrics_history[-1]
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Kumon Assistant - Quality Metrics Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #2196F3; color: white; padding: 20px; border-radius: 5px; }}
                .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }}
                .metric-card {{ border: 1px solid #ddd; border-radius: 5px; padding: 15px; }}
                .metric-good {{ border-left: 5px solid #4CAF50; }}
                .metric-warning {{ border-left: 5px solid #FF9800; }}
                .metric-critical {{ border-left: 5px solid #F44336; }}
                .score {{ font-size: 2em; font-weight: bold; }}
                .alerts {{ background: #ffebee; border: 1px solid #ffcdd2; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .recommendations {{ background: #e8f5e8; border: 1px solid #c8e6c9; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Quality Metrics Dashboard</h1>
                <p>Generated: {latest_report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Overall Quality Score: <span class="score">{latest_report.overall_score:.2f}</span></p>
            </div>
            
            <h2>Category Scores</h2>
            <div class="metric-grid">
        """
        
        # Add category scores
        for category, score in latest_report.category_scores.items():
            status_class = "good" if score >= 0.8 else "warning" if score >= 0.6 else "critical"
            html_content += f"""
                <div class="metric-card metric-{status_class}">
                    <h3>{category.capitalize()}</h3>
                    <div class="score">{score:.2f}</div>
                </div>
            """
        
        html_content += """
            </div>
            
            <h2>Detailed Metrics</h2>
            <div class="metric-grid">
        """
        
        # Add detailed metrics
        for metric in latest_report.metrics:
            html_content += f"""
                <div class="metric-card metric-{metric.status}">
                    <h4>{metric.name.replace('_', ' ').title()}</h4>
                    <p><strong>Value:</strong> {metric.value:.3f}</p>
                    <p><strong>Threshold:</strong> {metric.threshold}</p>
                    <p><strong>Status:</strong> {metric.status.upper()}</p>
                </div>
            """
        
        # Add alerts
        if latest_report.alerts:
            html_content += f"""
            </div>
            
            <div class="alerts">
                <h2>Alerts</h2>
                <ul>
            """
            for alert in latest_report.alerts:
                html_content += f"<li>{alert}</li>"
            
            html_content += "</ul></div>"
        
        # Add recommendations
        if latest_report.recommendations:
            html_content += f"""
            <div class="recommendations">
                <h2>Recommendations</h2>
                <ul>
            """
            for rec in latest_report.recommendations:
                html_content += f"<li>{rec}</li>"
            
            html_content += "</ul></div>"
        
        html_content += """
        </body>
        </html>
        """
        
        # Save to file
        Path(output_path).write_text(html_content, encoding='utf-8')
        
        return output_path
    
    async def export_metrics_json(self, output_path: str = "quality_metrics.json") -> str:
        """Export metrics to JSON format"""
        
        if not self.metrics_history:
            await self.collect_comprehensive_metrics()
        
        # Convert to JSON-serializable format
        export_data = []
        for report in self.metrics_history[-10:]:  # Last 10 reports
            report_data = asdict(report)
            # Convert datetime to string
            report_data["timestamp"] = report.timestamp.isoformat()
            for metric in report_data["metrics"]:
                metric["timestamp"] = metric["timestamp"].isoformat() if isinstance(metric["timestamp"], datetime) else metric["timestamp"]
            
            export_data.append(report_data)
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    async def start_continuous_monitoring(self, interval: int = 3600):
        """Start continuous quality monitoring"""
        
        app_logger.info(f"Starting continuous quality monitoring (interval: {interval}s)")
        
        while True:
            try:
                # Collect metrics
                report = await self.collect_comprehensive_metrics()
                
                # Log quality status
                app_logger.info(
                    f"Quality Report - Overall: {report.overall_score:.2f}, "
                    f"Security: {report.category_scores['security']:.2f}, "
                    f"Performance: {report.category_scores['performance']:.2f}, "
                    f"Alerts: {len(report.alerts)}"
                )
                
                # Generate reports if there are critical issues
                if report.overall_score < 0.7 or any("CRITICAL" in alert for alert in report.alerts):
                    await self.generate_html_report("critical_quality_report.html")
                    app_logger.warning("Critical quality issues detected - report generated")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                app_logger.error(f"Quality monitoring error: {e}")
                await asyncio.sleep(60)  # Short retry interval on error


# Global dashboard instance
quality_dashboard = QualityMetricsDashboard()


if __name__ == "__main__":
    # CLI interface for manual report generation
    import argparse
    
    parser = argparse.ArgumentParser(description="Quality Metrics Dashboard")
    parser.add_argument("--generate-report", action="store_true", help="Generate HTML report")
    parser.add_argument("--export-json", action="store_true", help="Export metrics to JSON")
    parser.add_argument("--monitor", action="store_true", help="Start continuous monitoring")
    parser.add_argument("--interval", type=int, default=3600, help="Monitoring interval in seconds")
    
    args = parser.parse_args()
    
    async def main():
        if args.generate_report:
            report_path = await quality_dashboard.generate_html_report()
            print(f"Quality report generated: {report_path}")
        
        if args.export_json:
            json_path = await quality_dashboard.export_metrics_json()
            print(f"Metrics exported: {json_path}")
        
        if args.monitor:
            await quality_dashboard.start_continuous_monitoring(args.interval)
    
    asyncio.run(main())