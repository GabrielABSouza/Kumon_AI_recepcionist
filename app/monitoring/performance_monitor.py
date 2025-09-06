"""
Performance Monitoring and Optimization System

Comprehensive performance monitoring for the Kumon Assistant with:
- Real-time performance metrics collection
- Database performance monitoring (Redis, PostgreSQL)
- AI/ML operation performance tracking
- API response time analysis
- Memory and resource usage monitoring
- Performance alerting and dashboard generation
"""

import asyncio
import time
import psutil
import redis.asyncio as aioredis
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import statistics
import json

from ..core.logger import app_logger
from ..core.config import settings


class PerformanceLevel(Enum):
    """Performance alert levels"""
    EXCELLENT = "excellent"    # >95% performance
    GOOD = "good"             # 80-95% performance  
    DEGRADED = "degraded"     # 60-80% performance
    POOR = "poor"             # 40-60% performance
    CRITICAL = "critical"     # <40% performance


@dataclass
class PerformanceAlert:
    """Performance alert"""
    timestamp: datetime
    level: PerformanceLevel
    component: str
    metric_name: str
    current_value: float
    threshold_value: float
    description: str
    metadata: Dict[str, Any]
    auto_resolved: bool = False


@dataclass
class SystemMetrics:
    """System resource metrics"""
    cpu_usage_percent: float
    memory_usage_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    network_io_mbps: float
    active_connections: int
    thread_count: int


@dataclass
class DatabaseMetrics:
    """Database performance metrics"""
    redis_response_time_ms: float
    redis_memory_usage_mb: float
    redis_connected_clients: int
    redis_operations_per_sec: float
    postgres_active_connections: int
    postgres_query_avg_time_ms: float
    postgres_cache_hit_ratio: float


@dataclass
class AIMLMetrics:
    """AI/ML operation performance metrics"""
    embedding_avg_time_ms: float
    embedding_requests_per_min: int
    rag_query_avg_time_ms: float
    rag_queries_per_min: int
    langchain_avg_time_ms: float
    langchain_requests_per_min: int
    vector_search_avg_time_ms: float
    openai_api_avg_time_ms: float
    openai_api_error_rate: float


@dataclass
class APIMetrics:
    """API performance metrics"""
    requests_per_second: float
    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    error_rate_percent: float
    webhook_processing_time_ms: float
    concurrent_requests: int
    queue_size: int


@dataclass
class PerformanceDashboard:
    """Real-time performance dashboard"""
    timestamp: datetime
    overall_performance_score: float
    system_status: PerformanceLevel
    system_metrics: SystemMetrics
    database_metrics: DatabaseMetrics
    aiml_metrics: AIMLMetrics
    api_metrics: APIMetrics
    recent_alerts: List[PerformanceAlert]
    performance_trends: Dict[str, List[float]]


class PerformanceMonitor:
    """
    Real-time performance monitoring system
    
    Features:
    - System resource monitoring (CPU, memory, disk, network)
    - Database performance tracking (Redis, PostgreSQL)
    - AI/ML operations monitoring (embeddings, RAG, LangChain)
    - API performance analysis (response times, throughput)
    - Automated alerting with smart thresholds
    - Performance dashboard generation
    - Trend analysis and predictions
    - Resource optimization recommendations
    """
    
    def __init__(self):
        # Alert and metrics tracking
        self.active_alerts: List[PerformanceAlert] = []
        self.alert_history: List[PerformanceAlert] = []
        self.metrics_history: List[Dict[str, Any]] = []
        
        # Performance baselines (will be calculated dynamically)
        self.baselines: Dict[str, float] = {}
        
        # Monitoring configuration
        self.config = {
            # System thresholds
            "cpu_warning_percent": 70.0,
            "cpu_critical_percent": 90.0,
            "memory_warning_percent": 75.0,
            "memory_critical_percent": 90.0,
            "disk_warning_percent": 80.0,
            "disk_critical_percent": 95.0,
            
            # Database thresholds
            "redis_response_warning_ms": 50.0,
            "redis_response_critical_ms": 200.0,
            "postgres_connection_warning": 80,
            "postgres_connection_critical": 95,
            "postgres_query_warning_ms": 100.0,
            "postgres_query_critical_ms": 500.0,
            
            # AI/ML thresholds
            "embedding_warning_ms": 1000.0,
            "embedding_critical_ms": 3000.0,
            "rag_query_warning_ms": 2000.0,
            "rag_query_critical_ms": 5000.0,
            "openai_api_warning_ms": 3000.0,
            "openai_api_critical_ms": 10000.0,
            
            # API thresholds
            "api_response_warning_ms": 1000.0,
            "api_response_critical_ms": 3000.0,
            "api_error_warning_percent": 2.0,
            "api_error_critical_percent": 5.0,
            
            # Monitoring intervals
            "metrics_collection_interval_seconds": 15,
            "dashboard_update_interval_seconds": 5,
            "alert_processing_interval_seconds": 30,
            
            # Data retention
            "metrics_retention_hours": 48,
            "alert_retention_hours": 168,  # 7 days
            
            # Performance calculation
            "baseline_calculation_window_hours": 24,
            "performance_score_weights": {
                "system": 0.25,
                "database": 0.25,
                "aiml": 0.30,
                "api": 0.20
            }
        }
        
        # Redis connection for performance monitoring
        self.redis_client = None
        
        # Monitoring state
        self._monitoring_active = True
        
        app_logger.info("Performance Monitor initialized with comprehensive tracking")
    
    async def start_monitoring(self):
        """Start continuous performance monitoring"""
        
        app_logger.info("Starting comprehensive performance monitoring")
        
        # Initialize Redis connection for monitoring
        await self._initialize_redis_monitoring()
        
        # Start monitoring tasks
        await asyncio.gather(
            self._system_metrics_loop(),
            self._database_metrics_loop(), 
            self._aiml_metrics_loop(),
            self._api_metrics_loop(),
            self._alert_processing_loop(),
            self._baseline_calculation_loop(),
            return_exceptions=True
        )
    
    async def _initialize_redis_monitoring(self):
        """Initialize Redis connection for monitoring"""
        try:
            if settings.REDIS_URL:
                self.redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0
                )
                # Test connection
                await self.redis_client.ping()
                app_logger.info("Redis monitoring connection initialized")
            else:
                app_logger.warning("Redis URL not configured - Redis monitoring disabled")
                
        except Exception as e:
            app_logger.error(f"Failed to initialize Redis monitoring: {e}")
            self.redis_client = None
    
    async def _system_metrics_loop(self):
        """Monitor system resource metrics"""
        
        while self._monitoring_active:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(self.config["metrics_collection_interval_seconds"])
                
            except Exception as e:
                app_logger.error(f"System metrics collection error: {e}")
                await asyncio.sleep(self.config["metrics_collection_interval_seconds"])
    
    async def _collect_system_metrics(self):
        """Collect comprehensive system metrics"""
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)
            memory_available_mb = memory.available / (1024 * 1024)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Network metrics (simplified)
            network = psutil.net_io_counters()
            network_mbps = (network.bytes_sent + network.bytes_recv) / (1024 * 1024)
            
            # Process metrics
            process = psutil.Process()
            thread_count = process.num_threads()
            
            # Connection count (approximate)
            connections = len(psutil.net_connections())
            
            system_metrics = {
                "timestamp": datetime.now(),
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory_percent,
                "memory_used_mb": memory_used_mb,
                "memory_available_mb": memory_available_mb,
                "disk_usage_percent": disk_percent,
                "network_io_mbps": network_mbps,
                "active_connections": connections,
                "thread_count": thread_count
            }
            
            # Store metrics
            self._store_metrics("system", system_metrics)
            
            # Check thresholds
            await self._check_system_thresholds(system_metrics)
            
        except Exception as e:
            app_logger.error(f"System metrics collection failed: {e}")
    
    async def _database_metrics_loop(self):
        """Monitor database performance"""
        
        while self._monitoring_active:
            try:
                await self._collect_database_metrics()
                await asyncio.sleep(self.config["metrics_collection_interval_seconds"])
                
            except Exception as e:
                app_logger.error(f"Database metrics collection error: {e}")
                await asyncio.sleep(self.config["metrics_collection_interval_seconds"])
    
    async def _collect_database_metrics(self):
        """Collect database performance metrics"""
        
        database_metrics = {
            "timestamp": datetime.now(),
            "redis_response_time_ms": 0.0,
            "redis_memory_usage_mb": 0.0,
            "redis_connected_clients": 0,
            "redis_operations_per_sec": 0.0,
            "postgres_active_connections": 0,
            "postgres_query_avg_time_ms": 0.0,
            "postgres_cache_hit_ratio": 0.0
        }
        
        # Redis metrics
        if self.redis_client:
            try:
                start_time = time.time()
                await self.redis_client.ping()
                redis_response_time = (time.time() - start_time) * 1000
                
                info = await self.redis_client.info()
                redis_memory_mb = info.get('used_memory', 0) / (1024 * 1024)
                redis_clients = info.get('connected_clients', 0)
                redis_ops_per_sec = info.get('instantaneous_ops_per_sec', 0)
                
                database_metrics.update({
                    "redis_response_time_ms": redis_response_time,
                    "redis_memory_usage_mb": redis_memory_mb,
                    "redis_connected_clients": redis_clients,
                    "redis_operations_per_sec": redis_ops_per_sec
                })
                
            except Exception as e:
                app_logger.error(f"Redis metrics collection failed: {e}")
        
        # PostgreSQL metrics would go here
        # Note: Implementation depends on database connection availability
        
        # Store metrics
        self._store_metrics("database", database_metrics)
        
        # Check thresholds  
        await self._check_database_thresholds(database_metrics)
    
    async def _aiml_metrics_loop(self):
        """Monitor AI/ML operation performance"""
        
        while self._monitoring_active:
            try:
                await self._collect_aiml_metrics()
                await asyncio.sleep(self.config["metrics_collection_interval_seconds"] * 2)  # Longer interval
                
            except Exception as e:
                app_logger.error(f"AI/ML metrics collection error: {e}")
                await asyncio.sleep(self.config["metrics_collection_interval_seconds"] * 2)
    
    async def _collect_aiml_metrics(self):
        """Collect AI/ML performance metrics"""
        
        # These metrics would be collected from actual AI/ML operations
        # For now, we'll use placeholders and integrate with actual services
        
        aiml_metrics = {
            "timestamp": datetime.now(),
            "embedding_avg_time_ms": 0.0,
            "embedding_requests_per_min": 0,
            "rag_query_avg_time_ms": 0.0,
            "rag_queries_per_min": 0,
            "langchain_avg_time_ms": 0.0,
            "langchain_requests_per_min": 0,
            "vector_search_avg_time_ms": 0.0,
            "openai_api_avg_time_ms": 0.0,
            "openai_api_error_rate": 0.0
        }
        
        # TODO: Integrate with actual AI/ML services for real metrics
        # This would require instrumenting:
        # - EnhancedRAGEngine operations
        # - Vector store operations  
        # - OpenAI API calls
        # - LangChain operations
        
        # Store metrics
        self._store_metrics("aiml", aiml_metrics)
        
        # Check thresholds
        await self._check_aiml_thresholds(aiml_metrics)
    
    async def _api_metrics_loop(self):
        """Monitor API performance"""
        
        while self._monitoring_active:
            try:
                await self._collect_api_metrics()
                await asyncio.sleep(self.config["metrics_collection_interval_seconds"])
                
            except Exception as e:
                app_logger.error(f"API metrics collection error: {e}")
                await asyncio.sleep(self.config["metrics_collection_interval_seconds"])
    
    async def _collect_api_metrics(self):
        """Collect API performance metrics"""
        
        # These metrics would be collected from FastAPI middleware
        # For now, we'll use placeholders and integrate with actual API
        
        api_metrics = {
            "timestamp": datetime.now(),
            "requests_per_second": 0.0,
            "avg_response_time_ms": 0.0,
            "p95_response_time_ms": 0.0,
            "p99_response_time_ms": 0.0,
            "error_rate_percent": 0.0,
            "webhook_processing_time_ms": 0.0,
            "concurrent_requests": 0,
            "queue_size": 0
        }
        
        # TODO: Integrate with FastAPI middleware for real metrics
        # This would require:
        # - Request/response time tracking
        # - Error rate calculation
        # - Concurrent request counting
        # - Queue size monitoring
        
        # Store metrics
        self._store_metrics("api", api_metrics)
        
        # Check thresholds
        await self._check_api_thresholds(api_metrics)
    
    def _store_metrics(self, category: str, metrics: Dict[str, Any]):
        """Store metrics with category"""
        
        metrics["category"] = category
        self.metrics_history.append(metrics)
        
        # Clean up old metrics
        cutoff_time = datetime.now() - timedelta(hours=self.config["metrics_retention_hours"])
        self.metrics_history = [
            m for m in self.metrics_history
            if m["timestamp"] > cutoff_time
        ]
    
    async def _check_system_thresholds(self, metrics: Dict[str, Any]):
        """Check system metrics against thresholds"""
        
        # CPU usage alerts
        cpu_usage = metrics["cpu_usage_percent"]
        if cpu_usage >= self.config["cpu_critical_percent"]:
            await self._create_alert(
                PerformanceLevel.CRITICAL,
                "system",
                "cpu_usage",
                cpu_usage,
                self.config["cpu_critical_percent"],
                f"Critical CPU usage: {cpu_usage:.1f}%"
            )
        elif cpu_usage >= self.config["cpu_warning_percent"]:
            await self._create_alert(
                PerformanceLevel.DEGRADED,
                "system",
                "cpu_usage",
                cpu_usage,
                self.config["cpu_warning_percent"],
                f"High CPU usage: {cpu_usage:.1f}%"
            )
        
        # Memory usage alerts
        memory_usage = metrics["memory_usage_percent"]
        if memory_usage >= self.config["memory_critical_percent"]:
            await self._create_alert(
                PerformanceLevel.CRITICAL,
                "system",
                "memory_usage",
                memory_usage,
                self.config["memory_critical_percent"],
                f"Critical memory usage: {memory_usage:.1f}%"
            )
        elif memory_usage >= self.config["memory_warning_percent"]:
            await self._create_alert(
                PerformanceLevel.DEGRADED,
                "system",
                "memory_usage",
                memory_usage,
                self.config["memory_warning_percent"],
                f"High memory usage: {memory_usage:.1f}%"
            )
    
    async def _check_database_thresholds(self, metrics: Dict[str, Any]):
        """Check database metrics against thresholds"""
        
        # Redis response time alerts
        redis_response = metrics["redis_response_time_ms"]
        if redis_response >= self.config["redis_response_critical_ms"]:
            await self._create_alert(
                PerformanceLevel.CRITICAL,
                "database",
                "redis_response_time",
                redis_response,
                self.config["redis_response_critical_ms"],
                f"Critical Redis response time: {redis_response:.1f}ms"
            )
        elif redis_response >= self.config["redis_response_warning_ms"]:
            await self._create_alert(
                PerformanceLevel.DEGRADED,
                "database",
                "redis_response_time",
                redis_response,
                self.config["redis_response_warning_ms"],
                f"Slow Redis response time: {redis_response:.1f}ms"
            )
    
    async def _check_aiml_thresholds(self, metrics: Dict[str, Any]):
        """Check AI/ML metrics against thresholds"""
        
        # Embedding time alerts
        embedding_time = metrics["embedding_avg_time_ms"]
        if embedding_time >= self.config["embedding_critical_ms"]:
            await self._create_alert(
                PerformanceLevel.CRITICAL,
                "aiml",
                "embedding_time",
                embedding_time,
                self.config["embedding_critical_ms"],
                f"Critical embedding processing time: {embedding_time:.1f}ms"
            )
        elif embedding_time >= self.config["embedding_warning_ms"]:
            await self._create_alert(
                PerformanceLevel.DEGRADED,
                "aiml",
                "embedding_time",
                embedding_time,
                self.config["embedding_warning_ms"],
                f"Slow embedding processing: {embedding_time:.1f}ms"
            )
    
    async def _check_api_thresholds(self, metrics: Dict[str, Any]):
        """Check API metrics against thresholds"""
        
        # API response time alerts
        api_response = metrics["avg_response_time_ms"]
        if api_response >= self.config["api_response_critical_ms"]:
            await self._create_alert(
                PerformanceLevel.CRITICAL,
                "api",
                "response_time",
                api_response,
                self.config["api_response_critical_ms"],
                f"Critical API response time: {api_response:.1f}ms"
            )
        elif api_response >= self.config["api_response_warning_ms"]:
            await self._create_alert(
                PerformanceLevel.DEGRADED,
                "api",
                "response_time",
                api_response,
                self.config["api_response_warning_ms"],
                f"Slow API response time: {api_response:.1f}ms"
            )
    
    async def _create_alert(
        self,
        level: PerformanceLevel,
        component: str,
        metric_name: str,
        current_value: float,
        threshold_value: float,
        description: str
    ):
        """Create and process performance alert"""
        
        alert = PerformanceAlert(
            timestamp=datetime.now(),
            level=level,
            component=component,
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=threshold_value,
            description=description,
            metadata={
                "threshold_exceeded": current_value > threshold_value,
                "severity_ratio": current_value / threshold_value if threshold_value > 0 else 0
            }
        )
        
        # Check for duplicate alerts (prevent spam)
        recent_similar = [
            a for a in self.active_alerts[-5:]
            if (a.component == component and 
                a.metric_name == metric_name and
                (datetime.now() - a.timestamp).total_seconds() < 300)  # 5 minutes
        ]
        
        if not recent_similar:
            self.active_alerts.append(alert)
            self.alert_history.append(alert)
            
            # Log alert
            log_level = "critical" if level == PerformanceLevel.CRITICAL else "warning"
            app_logger.log(
                getattr(app_logger, log_level.upper()),
                f"Performance Alert [{level.value.upper()}]: {description}",
                extra={
                    "component": component,
                    "metric": metric_name,
                    "current_value": current_value,
                    "threshold": threshold_value
                }
            )
    
    async def _alert_processing_loop(self):
        """Process and manage performance alerts"""
        
        while self._monitoring_active:
            try:
                await self._process_performance_alerts()
                await asyncio.sleep(self.config["alert_processing_interval_seconds"])
                
            except Exception as e:
                app_logger.error(f"Alert processing error: {e}")
                await asyncio.sleep(self.config["alert_processing_interval_seconds"])
    
    async def _process_performance_alerts(self):
        """Process and potentially auto-resolve alerts"""
        
        current_time = datetime.now()
        
        # Auto-resolve old alerts
        for alert in self.active_alerts[:]:
            alert_age = (current_time - alert.timestamp).total_seconds()
            
            # Auto-resolve performance alerts after 15 minutes if conditions improve
            if alert_age > 900:  # 15 minutes
                alert.auto_resolved = True
                self.active_alerts.remove(alert)
                
                app_logger.info(f"Auto-resolved performance alert: {alert.component}.{alert.metric_name}")
        
        # Clean up old alert history
        cutoff_time = current_time - timedelta(hours=self.config["alert_retention_hours"])
        self.alert_history = [
            a for a in self.alert_history
            if a.timestamp > cutoff_time
        ]
    
    async def _baseline_calculation_loop(self):
        """Calculate performance baselines"""
        
        while self._monitoring_active:
            try:
                await self._calculate_baselines()
                await asyncio.sleep(3600)  # Update baselines hourly
                
            except Exception as e:
                app_logger.error(f"Baseline calculation error: {e}")
                await asyncio.sleep(3600)
    
    async def _calculate_baselines(self):
        """Calculate performance baselines from historical data"""
        
        if len(self.metrics_history) < 10:
            return  # Need more data
        
        try:
            # Calculate baselines for key metrics
            cutoff_time = datetime.now() - timedelta(hours=self.config["baseline_calculation_window_hours"])
            recent_metrics = [
                m for m in self.metrics_history
                if m["timestamp"] > cutoff_time
            ]
            
            if not recent_metrics:
                return
            
            # System baselines
            system_metrics = [m for m in recent_metrics if m.get("category") == "system"]
            if system_metrics:
                cpu_values = [m.get("cpu_usage_percent", 0) for m in system_metrics]
                memory_values = [m.get("memory_usage_percent", 0) for m in system_metrics]
                
                self.baselines["cpu_baseline"] = statistics.median(cpu_values)
                self.baselines["memory_baseline"] = statistics.median(memory_values)
            
            # Database baselines
            db_metrics = [m for m in recent_metrics if m.get("category") == "database"]
            if db_metrics:
                redis_values = [m.get("redis_response_time_ms", 0) for m in db_metrics]
                
                self.baselines["redis_response_baseline"] = statistics.median(redis_values)
            
            app_logger.info(f"Performance baselines updated: {self.baselines}")
            
        except Exception as e:
            app_logger.error(f"Baseline calculation failed: {e}")
    
    async def get_performance_dashboard(self) -> PerformanceDashboard:
        """Generate real-time performance dashboard"""
        
        try:
            # Get latest metrics by category
            system_data = self._get_latest_metrics("system")
            database_data = self._get_latest_metrics("database") 
            aiml_data = self._get_latest_metrics("aiml")
            api_data = self._get_latest_metrics("api")
            
            # Create metric objects
            system_metrics = SystemMetrics(
                cpu_usage_percent=system_data.get("cpu_usage_percent", 0.0),
                memory_usage_percent=system_data.get("memory_usage_percent", 0.0),
                memory_used_mb=system_data.get("memory_used_mb", 0.0),
                memory_available_mb=system_data.get("memory_available_mb", 0.0),
                disk_usage_percent=system_data.get("disk_usage_percent", 0.0),
                network_io_mbps=system_data.get("network_io_mbps", 0.0),
                active_connections=system_data.get("active_connections", 0),
                thread_count=system_data.get("thread_count", 0)
            )
            
            database_metrics = DatabaseMetrics(
                redis_response_time_ms=database_data.get("redis_response_time_ms", 0.0),
                redis_memory_usage_mb=database_data.get("redis_memory_usage_mb", 0.0),
                redis_connected_clients=database_data.get("redis_connected_clients", 0),
                redis_operations_per_sec=database_data.get("redis_operations_per_sec", 0.0),
                postgres_active_connections=database_data.get("postgres_active_connections", 0),
                postgres_query_avg_time_ms=database_data.get("postgres_query_avg_time_ms", 0.0),
                postgres_cache_hit_ratio=database_data.get("postgres_cache_hit_ratio", 0.0)
            )
            
            aiml_metrics = AIMLMetrics(
                embedding_avg_time_ms=aiml_data.get("embedding_avg_time_ms", 0.0),
                embedding_requests_per_min=aiml_data.get("embedding_requests_per_min", 0),
                rag_query_avg_time_ms=aiml_data.get("rag_query_avg_time_ms", 0.0),
                rag_queries_per_min=aiml_data.get("rag_queries_per_min", 0),
                langchain_avg_time_ms=aiml_data.get("langchain_avg_time_ms", 0.0),
                langchain_requests_per_min=aiml_data.get("langchain_requests_per_min", 0),
                vector_search_avg_time_ms=aiml_data.get("vector_search_avg_time_ms", 0.0),
                openai_api_avg_time_ms=aiml_data.get("openai_api_avg_time_ms", 0.0),
                openai_api_error_rate=aiml_data.get("openai_api_error_rate", 0.0)
            )
            
            api_metrics = APIMetrics(
                requests_per_second=api_data.get("requests_per_second", 0.0),
                avg_response_time_ms=api_data.get("avg_response_time_ms", 0.0),
                p95_response_time_ms=api_data.get("p95_response_time_ms", 0.0),
                p99_response_time_ms=api_data.get("p99_response_time_ms", 0.0),
                error_rate_percent=api_data.get("error_rate_percent", 0.0),
                webhook_processing_time_ms=api_data.get("webhook_processing_time_ms", 0.0),
                concurrent_requests=api_data.get("concurrent_requests", 0),
                queue_size=api_data.get("queue_size", 0)
            )
            
            # Calculate overall performance score
            overall_score = self._calculate_performance_score(
                system_metrics, database_metrics, aiml_metrics, api_metrics
            )
            
            # Determine system status
            if overall_score >= 0.95:
                status = PerformanceLevel.EXCELLENT
            elif overall_score >= 0.80:
                status = PerformanceLevel.GOOD
            elif overall_score >= 0.60:
                status = PerformanceLevel.DEGRADED
            elif overall_score >= 0.40:
                status = PerformanceLevel.POOR
            else:
                status = PerformanceLevel.CRITICAL
            
            # Get recent alerts
            recent_alerts = [
                alert for alert in self.active_alerts[-10:]
                if not alert.auto_resolved
            ]
            
            # Calculate performance trends
            trends = self._calculate_performance_trends()
            
            return PerformanceDashboard(
                timestamp=datetime.now(),
                overall_performance_score=overall_score,
                system_status=status,
                system_metrics=system_metrics,
                database_metrics=database_metrics,
                aiml_metrics=aiml_metrics,
                api_metrics=api_metrics,
                recent_alerts=recent_alerts,
                performance_trends=trends
            )
            
        except Exception as e:
            app_logger.error(f"Performance dashboard generation error: {e}")
            
            # Return minimal dashboard on error
            return PerformanceDashboard(
                timestamp=datetime.now(),
                overall_performance_score=0.0,
                system_status=PerformanceLevel.CRITICAL,
                system_metrics=SystemMetrics(0, 0, 0, 0, 0, 0, 0, 0),
                database_metrics=DatabaseMetrics(0, 0, 0, 0, 0, 0, 0),
                aiml_metrics=AIMLMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0),
                api_metrics=APIMetrics(0, 0, 0, 0, 0, 0, 0, 0),
                recent_alerts=[],
                performance_trends={}
            )
    
    def _get_latest_metrics(self, category: str) -> Dict[str, Any]:
        """Get latest metrics for a category"""
        
        category_metrics = [
            m for m in reversed(self.metrics_history)
            if m.get("category") == category
        ]
        
        return category_metrics[0] if category_metrics else {}
    
    def _calculate_performance_score(
        self,
        system: SystemMetrics,
        database: DatabaseMetrics,
        aiml: AIMLMetrics,
        api: APIMetrics
    ) -> float:
        """Calculate overall performance score"""
        
        weights = self.config["performance_score_weights"]
        
        # System score (inverse of resource usage)
        system_score = max(0.0, min(1.0, 
            1.0 - (system.cpu_usage_percent / 100) * 0.5 - 
                  (system.memory_usage_percent / 100) * 0.5
        ))
        
        # Database score (inverse of response times)
        db_score = max(0.0, min(1.0,
            1.0 - min(database.redis_response_time_ms / 1000, 1.0)  # Cap at 1 second
        ))
        
        # AI/ML score (inverse of processing times)
        aiml_score = max(0.0, min(1.0,
            1.0 - min(aiml.embedding_avg_time_ms / 5000, 1.0)  # Cap at 5 seconds
        ))
        
        # API score (inverse of response times and error rates)
        api_score = max(0.0, min(1.0,
            (1.0 - min(api.avg_response_time_ms / 3000, 1.0)) * 0.7 +  # Response time (70%)
            (1.0 - min(api.error_rate_percent / 100, 1.0)) * 0.3       # Error rate (30%)
        ))
        
        # Weighted overall score
        overall_score = (
            system_score * weights["system"] +
            db_score * weights["database"] +
            aiml_score * weights["aiml"] +
            api_score * weights["api"]
        )
        
        return max(0.0, min(1.0, overall_score))
    
    def _calculate_performance_trends(self) -> Dict[str, List[float]]:
        """Calculate performance trends over time"""
        
        if len(self.metrics_history) < 10:
            return {}
        
        try:
            # Get last 20 data points for trending
            recent_metrics = self.metrics_history[-20:]
            
            trends = {}
            
            # System trends
            system_metrics = [m for m in recent_metrics if m.get("category") == "system"]
            if system_metrics:
                trends["cpu_trend"] = [m.get("cpu_usage_percent", 0) for m in system_metrics]
                trends["memory_trend"] = [m.get("memory_usage_percent", 0) for m in system_metrics]
            
            # Database trends
            db_metrics = [m for m in recent_metrics if m.get("category") == "database"]
            if db_metrics:
                trends["redis_response_trend"] = [m.get("redis_response_time_ms", 0) for m in db_metrics]
            
            # API trends
            api_metrics = [m for m in recent_metrics if m.get("category") == "api"]
            if api_metrics:
                trends["api_response_trend"] = [m.get("avg_response_time_ms", 0) for m in api_metrics]
            
            return trends
            
        except Exception as e:
            app_logger.error(f"Trend calculation failed: {e}")
            return {}
    
    async def stop_monitoring(self):
        """Stop performance monitoring"""
        self._monitoring_active = False
        
        if self.redis_client:
            await self.redis_client.close()
        
        app_logger.info("Performance monitoring stopped")
    
    def get_metrics_history(self, category: Optional[str] = None, hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical metrics with optional category filter"""
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        filtered_metrics = [
            m for m in self.metrics_history
            if m["timestamp"] > cutoff_time
        ]
        
        if category:
            filtered_metrics = [
                m for m in filtered_metrics
                if m.get("category") == category
            ]
        
        return filtered_metrics


# Global performance monitor instance
performance_monitor = PerformanceMonitor()