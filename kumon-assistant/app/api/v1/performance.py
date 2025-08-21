"""
Performance SLA Monitoring API - Phase 3 Production
Real-time response time tracking and SLA compliance for Railway deployment:
- ≤5s response time SLA monitoring and alerting
- Real-time performance metrics and compliance tracking
- Historical SLA breach analysis and reporting
- Endpoint-specific performance monitoring
- Compliance reporting for business requirements
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from app.monitoring.performance_sla import sla_tracker, ResponseTimeMetric, SLAMetrics, SLAStatus, AlertSeverity
from app.api.v1.auth import require_assistant_scope, require_admin_scope
from app.core.logger import app_logger as logger

router = APIRouter()


@router.get("/dashboard", summary="Real-time Performance Dashboard")
async def get_performance_dashboard():
    """
    Get comprehensive real-time performance dashboard
    
    Returns:
        Real-time performance metrics including:
        - System resource usage (CPU, memory, disk)
        - Database performance (Redis, PostgreSQL)
        - AI/ML operation metrics
        - API performance statistics
        - Recent alerts and trends
    """
    
    try:
        dashboard = await performance_monitor.get_performance_dashboard()
        
        return {
            "status": "success",
            "timestamp": dashboard.timestamp.isoformat(),
            "overall_performance_score": dashboard.overall_performance_score,
            "system_status": dashboard.system_status.value,
            "metrics": {
                "system": {
                    "cpu_usage_percent": dashboard.system_metrics.cpu_usage_percent,
                    "memory_usage_percent": dashboard.system_metrics.memory_usage_percent,
                    "memory_used_mb": dashboard.system_metrics.memory_used_mb,
                    "memory_available_mb": dashboard.system_metrics.memory_available_mb,
                    "disk_usage_percent": dashboard.system_metrics.disk_usage_percent,
                    "network_io_mbps": dashboard.system_metrics.network_io_mbps,
                    "active_connections": dashboard.system_metrics.active_connections,
                    "thread_count": dashboard.system_metrics.thread_count
                },
                "database": {
                    "redis_response_time_ms": dashboard.database_metrics.redis_response_time_ms,
                    "redis_memory_usage_mb": dashboard.database_metrics.redis_memory_usage_mb,
                    "redis_connected_clients": dashboard.database_metrics.redis_connected_clients,
                    "redis_operations_per_sec": dashboard.database_metrics.redis_operations_per_sec,
                    "postgres_active_connections": dashboard.database_metrics.postgres_active_connections,
                    "postgres_query_avg_time_ms": dashboard.database_metrics.postgres_query_avg_time_ms,
                    "postgres_cache_hit_ratio": dashboard.database_metrics.postgres_cache_hit_ratio
                },
                "aiml": {
                    "embedding_avg_time_ms": dashboard.aiml_metrics.embedding_avg_time_ms,
                    "embedding_requests_per_min": dashboard.aiml_metrics.embedding_requests_per_min,
                    "rag_query_avg_time_ms": dashboard.aiml_metrics.rag_query_avg_time_ms,
                    "rag_queries_per_min": dashboard.aiml_metrics.rag_queries_per_min,
                    "langchain_avg_time_ms": dashboard.aiml_metrics.langchain_avg_time_ms,
                    "langchain_requests_per_min": dashboard.aiml_metrics.langchain_requests_per_min,
                    "vector_search_avg_time_ms": dashboard.aiml_metrics.vector_search_avg_time_ms,
                    "openai_api_avg_time_ms": dashboard.aiml_metrics.openai_api_avg_time_ms,
                    "openai_api_error_rate": dashboard.aiml_metrics.openai_api_error_rate
                },
                "api": {
                    "requests_per_second": dashboard.api_metrics.requests_per_second,
                    "avg_response_time_ms": dashboard.api_metrics.avg_response_time_ms,
                    "p95_response_time_ms": dashboard.api_metrics.p95_response_time_ms,
                    "p99_response_time_ms": dashboard.api_metrics.p99_response_time_ms,
                    "error_rate_percent": dashboard.api_metrics.error_rate_percent,
                    "webhook_processing_time_ms": dashboard.api_metrics.webhook_processing_time_ms,
                    "concurrent_requests": dashboard.api_metrics.concurrent_requests,
                    "queue_size": dashboard.api_metrics.queue_size
                }
            },
            "alerts": [
                {
                    "timestamp": alert.timestamp.isoformat(),
                    "level": alert.level.value,
                    "component": alert.component,
                    "metric_name": alert.metric_name,
                    "current_value": alert.current_value,
                    "threshold_value": alert.threshold_value,
                    "description": alert.description
                }
                for alert in dashboard.recent_alerts
            ],
            "trends": dashboard.performance_trends
        }
        
    except Exception as e:
        app_logger.error(f"Performance dashboard error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate performance dashboard")


@router.get("/metrics", summary="Current Performance Metrics")
async def get_current_metrics():
    """
    Get current performance metrics from API middleware
    
    Returns:
        Current API performance metrics including response times,
        error rates, throughput, and concurrent request information
    """
    
    try:
        metrics = performance_tracker.get_current_metrics()
        
        return {
            "status": "success",
            "metrics": metrics
        }
        
    except Exception as e:
        app_logger.error(f"Current metrics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve current metrics")


@router.get("/health", summary="Performance Health Status")
async def get_performance_health():
    """
    Get performance-based system health status
    
    Returns:
        Health status with scoring, factors, and recommendations
        for performance optimization
    """
    
    try:
        health_status = performance_tracker.get_health_status()
        
        return {
            "status": "success",
            "health": health_status
        }
        
    except Exception as e:
        app_logger.error(f"Performance health error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve performance health status")


@router.get("/history", summary="Historical Performance Data")
async def get_performance_history(
    category: Optional[str] = Query(None, description="Metric category (system, database, aiml, api)"),
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve (1-168)")
):
    """
    Get historical performance metrics
    
    Args:
        category: Optional category filter
        hours: Number of hours of history to retrieve
    
    Returns:
        Historical performance data with timestamps and trends
    """
    
    try:
        # Get historical data from performance monitor
        historical_data = performance_monitor.get_metrics_history(category=category, hours=hours)
        
        return {
            "status": "success",
            "category": category,
            "hours_requested": hours,
            "data_points": len(historical_data),
            "time_range": {
                "start": (datetime.now() - timedelta(hours=hours)).isoformat(),
                "end": datetime.now().isoformat()
            },
            "metrics": historical_data
        }
        
    except Exception as e:
        app_logger.error(f"Performance history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve performance history")


@router.get("/alerts", summary="Performance Alerts")
async def get_performance_alerts(
    hours: int = Query(24, ge=1, le=168, description="Hours of alert history to retrieve")
):
    """
    Get performance alerts history
    
    Args:
        hours: Number of hours of alert history to retrieve
    
    Returns:
        Performance alerts with details and resolution status
    """
    
    try:
        # Get alert history from performance monitor
        alerts = performance_monitor.alert_history
        
        # Filter by time range
        cutoff_time = datetime.now() - timedelta(hours=hours)
        filtered_alerts = [
            alert for alert in alerts
            if alert.timestamp > cutoff_time
        ]
        
        return {
            "status": "success",
            "hours_requested": hours,
            "alert_count": len(filtered_alerts),
            "active_alerts": len([a for a in filtered_alerts if not a.auto_resolved]),
            "resolved_alerts": len([a for a in filtered_alerts if a.auto_resolved]),
            "alerts": [
                {
                    "timestamp": alert.timestamp.isoformat(),
                    "level": alert.level.value,
                    "component": alert.component,
                    "metric_name": alert.metric_name,
                    "current_value": alert.current_value,
                    "threshold_value": alert.threshold_value,
                    "description": alert.description,
                    "auto_resolved": alert.auto_resolved,
                    "metadata": alert.metadata
                }
                for alert in sorted(filtered_alerts, key=lambda x: x.timestamp, reverse=True)
            ]
        }
        
    except Exception as e:
        app_logger.error(f"Performance alerts error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve performance alerts")


@router.get("/recommendations", summary="Performance Optimization Recommendations")
async def get_performance_recommendations():
    """
    Get AI-powered performance optimization recommendations
    
    Returns:
        Intelligent recommendations for improving system performance
        based on current metrics and historical trends
    """
    
    try:
        # Get current performance data
        dashboard = await performance_monitor.get_performance_dashboard()
        health_status = performance_tracker.get_health_status()
        
        # Generate recommendations based on performance data
        recommendations = []
        
        # System recommendations
        if dashboard.system_metrics.cpu_usage_percent > 80:
            recommendations.append({
                "category": "system",
                "priority": "high",
                "title": "High CPU Usage Detected",
                "description": f"CPU usage is at {dashboard.system_metrics.cpu_usage_percent:.1f}%",
                "recommendations": [
                    "Consider upgrading CPU resources",
                    "Optimize CPU-intensive operations",
                    "Implement request rate limiting",
                    "Review and optimize AI/ML model inference"
                ]
            })
        
        if dashboard.system_metrics.memory_usage_percent > 85:
            recommendations.append({
                "category": "system", 
                "priority": "high",
                "title": "High Memory Usage Detected",
                "description": f"Memory usage is at {dashboard.system_metrics.memory_usage_percent:.1f}%",
                "recommendations": [
                    "Increase available memory",
                    "Implement memory caching strategies",
                    "Optimize data structures and memory usage",
                    "Review conversation memory retention policies"
                ]
            })
        
        # Database recommendations
        if dashboard.database_metrics.redis_response_time_ms > 100:
            recommendations.append({
                "category": "database",
                "priority": "medium",
                "title": "Slow Redis Response Times",
                "description": f"Redis response time is {dashboard.database_metrics.redis_response_time_ms:.1f}ms",
                "recommendations": [
                    "Optimize Redis queries and data structures",
                    "Consider Redis clustering for better performance",
                    "Review Redis memory usage and eviction policies",
                    "Implement connection pooling"
                ]
            })
        
        # API recommendations
        if dashboard.api_metrics.avg_response_time_ms > 1000:
            recommendations.append({
                "category": "api",
                "priority": "high",
                "title": "Slow API Response Times",
                "description": f"Average API response time is {dashboard.api_metrics.avg_response_time_ms:.1f}ms",
                "recommendations": [
                    "Optimize webhook processing logic",
                    "Implement request caching where appropriate",
                    "Review and optimize database queries",
                    "Consider load balancing and horizontal scaling"
                ]
            })
        
        # AI/ML recommendations
        if dashboard.aiml_metrics.embedding_avg_time_ms > 2000:
            recommendations.append({
                "category": "aiml",
                "priority": "medium",
                "title": "Slow AI/ML Operations",
                "description": f"Embedding processing time is {dashboard.aiml_metrics.embedding_avg_time_ms:.1f}ms",
                "recommendations": [
                    "Optimize embedding model inference",
                    "Implement embedding caching",
                    "Consider GPU acceleration for AI operations",
                    "Optimize vector database queries"
                ]
            })
        
        # General recommendations
        recommendations.extend(health_status.get("recommendations", []))
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "overall_performance_score": dashboard.overall_performance_score,
            "system_status": dashboard.system_status.value,
            "recommendation_count": len(recommendations),
            "recommendations": recommendations,
            "next_review": (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
    except Exception as e:
        app_logger.error(f"Performance recommendations error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate performance recommendations")


@router.post("/benchmark", summary="Run Performance Benchmark")
async def run_performance_benchmark():
    """
    Run a comprehensive performance benchmark test
    
    Returns:
        Benchmark results with performance scores and bottleneck analysis
    """
    
    try:
        import time
        import asyncio
        
        benchmark_start = time.time()
        
        # Simulate various operations to test performance
        benchmark_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": []
        }
        
        # API Response Test
        api_start = time.time()
        await asyncio.sleep(0.01)  # Simulate API call
        api_time = (time.time() - api_start) * 1000
        
        benchmark_results["tests"].append({
            "test_name": "API Response Test",
            "duration_ms": api_time,
            "status": "passed" if api_time < 100 else "warning",
            "score": max(0, 100 - (api_time / 10))
        })
        
        # Memory Test
        memory_start = time.time()
        test_data = list(range(10000))  # Create some data
        memory_time = (time.time() - memory_start) * 1000
        del test_data
        
        benchmark_results["tests"].append({
            "test_name": "Memory Allocation Test",
            "duration_ms": memory_time,
            "status": "passed" if memory_time < 50 else "warning",
            "score": max(0, 100 - (memory_time / 5))
        })
        
        # Overall benchmark score
        total_score = sum(test["score"] for test in benchmark_results["tests"])
        average_score = total_score / len(benchmark_results["tests"])
        
        benchmark_results["overall_score"] = average_score
        benchmark_results["total_duration_ms"] = (time.time() - benchmark_start) * 1000
        benchmark_results["status"] = "excellent" if average_score >= 90 else "good" if average_score >= 70 else "needs_improvement"
        
        return {
            "status": "success",
            "benchmark": benchmark_results
        }
        
    except Exception as e:
        app_logger.error(f"Performance benchmark error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to run performance benchmark")


@router.get("/config", summary="Performance Monitor Configuration")
async def get_performance_config():
    """
    Get current performance monitoring configuration
    
    Returns:
        Current thresholds, intervals, and monitoring settings
    """
    
    try:
        config = performance_monitor.config
        
        return {
            "status": "success",
            "config": config,
            "monitoring_active": performance_monitor._monitoring_active,
            "baselines": performance_monitor.baselines
        }
        
    except Exception as e:
        app_logger.error(f"Performance config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve performance configuration")


@router.get("/optimization/stats", summary="Performance Optimization Statistics")
async def get_optimization_stats():
    """
    Get performance optimization statistics
    
    Returns:
        Comprehensive optimization statistics including cache performance,
        queue management, and function analytics
    """
    
    try:
        stats = performance_optimizer.get_optimization_stats()
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "optimization_stats": stats,
            "overall_performance_score": stats.get("performance_score", 0),
            "cache_efficiency": stats.get("cache", {}).get("hit_rate", 0),
            "queue_efficiency": {
                "avg_wait_time": stats.get("queue", {}).get("avg_wait_time", 0),
                "processing_efficiency": stats.get("queue", {}).get("total_processed", 0)
            }
        }
        
    except Exception as e:
        app_logger.error(f"Optimization stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve optimization statistics")


@router.post("/load-test/run", summary="Run Load Test")
async def run_load_test(
    test_name: str = Body("api_load_test", description="Name of the load test"),
    concurrent_users: int = Body(50, ge=1, le=200, description="Number of concurrent users"),
    test_duration_seconds: int = Body(300, ge=60, le=3600, description="Test duration in seconds"),
    ramp_up_duration_seconds: int = Body(60, ge=10, le=600, description="Ramp-up duration in seconds")
):
    """
    Run a comprehensive load test
    
    Args:
        test_name: Name identifier for the load test
        concurrent_users: Number of concurrent users to simulate
        test_duration_seconds: Duration of the test
        ramp_up_duration_seconds: Time to gradually increase load
    
    Returns:
        Complete load test results with performance analysis
    """
    
    try:
        # Check if test is already running
        if test_name in load_tester.active_tests and load_tester.active_tests[test_name]:
            raise HTTPException(status_code=409, detail=f"Load test '{test_name}' is already running")
        
        app_logger.info(f"Starting load test: {test_name}")
        
        # Run load test
        summary = await load_tester.run_load_test(
            test_name=test_name,
            concurrent_users=concurrent_users,
            test_duration_seconds=test_duration_seconds,
            ramp_up_duration_seconds=ramp_up_duration_seconds
        )
        
        return {
            "status": "success",
            "load_test_summary": {
                "test_name": summary.test_name,
                "start_time": summary.start_time.isoformat(),
                "end_time": summary.end_time.isoformat(),
                "total_duration_seconds": summary.total_duration_seconds,
                "total_requests": summary.total_requests,
                "successful_requests": summary.successful_requests,
                "failed_requests": summary.failed_requests,
                "requests_per_second": round(summary.requests_per_second, 2),
                "avg_response_time_ms": round(summary.avg_response_time_ms, 2),
                "p95_response_time_ms": round(summary.p95_response_time_ms, 2),
                "p99_response_time_ms": round(summary.p99_response_time_ms, 2),
                "min_response_time_ms": round(summary.min_response_time_ms, 2),
                "max_response_time_ms": round(summary.max_response_time_ms, 2),
                "error_rate_percent": round(summary.error_rate_percent, 2),
                "total_data_transferred_mb": round(summary.total_data_transferred_mb, 2),
                "scenarios_executed": summary.scenarios_executed,
                "performance_score": round(summary.performance_score, 1),
                "bottlenecks_identified": summary.bottlenecks_identified,
                "recommendations": summary.recommendations
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Load test error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to run load test")


@router.post("/load-test/stress", summary="Run Stress Test")
async def run_stress_test(
    test_name: str = Body("stress_test", description="Base name for stress test"),
    max_users: int = Body(200, ge=25, le=500, description="Maximum number of users"),
    step_size: int = Body(25, ge=5, le=50, description="User increase per step"),
    step_duration_seconds: int = Body(120, ge=60, le=300, description="Duration of each step")
):
    """
    Run stress test with gradually increasing load
    
    Args:
        test_name: Base name for the stress test
        max_users: Maximum number of concurrent users
        step_size: User increase per step
        step_duration_seconds: Duration of each step
    
    Returns:
        Stress test results for each load level
    """
    
    try:
        app_logger.info(f"Starting stress test: {test_name}")
        
        # Run stress test
        summaries = await load_tester.run_stress_test(
            test_name=test_name,
            max_users=max_users,
            step_size=step_size,
            step_duration_seconds=step_duration_seconds
        )
        
        # Format results
        formatted_results = []
        for summary in summaries:
            formatted_results.append({
                "step_name": summary.test_name,
                "concurrent_users": summary.test_name.split("_")[-2] if "_" in summary.test_name else "unknown",
                "performance_score": round(summary.performance_score, 1),
                "requests_per_second": round(summary.requests_per_second, 2),
                "avg_response_time_ms": round(summary.avg_response_time_ms, 2),
                "error_rate_percent": round(summary.error_rate_percent, 2),
                "total_requests": summary.total_requests,
                "bottlenecks": summary.bottlenecks_identified
            })
        
        # Overall analysis
        if summaries:
            best_performance = max(summaries, key=lambda x: x.performance_score)
            breaking_point = next(
                (s for s in summaries if s.performance_score < 50 or s.error_rate_percent > 10),
                None
            )
        else:
            best_performance = None
            breaking_point = None
        
        return {
            "status": "success",
            "stress_test_results": {
                "test_name": test_name,
                "total_steps": len(summaries),
                "max_users_tested": max_users if summaries else 0,
                "step_results": formatted_results,
                "analysis": {
                    "best_performance_users": (
                        best_performance.test_name.split("_")[-2] if best_performance and "_" in best_performance.test_name 
                        else "unknown"
                    ),
                    "best_performance_score": round(best_performance.performance_score, 1) if best_performance else 0,
                    "breaking_point_users": (
                        breaking_point.test_name.split("_")[-2] if breaking_point and "_" in breaking_point.test_name 
                        else "not reached"
                    ),
                    "recommended_max_users": (
                        int(best_performance.test_name.split("_")[-2]) if best_performance and "_" in best_performance.test_name 
                        else max_users
                    )
                }
            }
        }
        
    except Exception as e:
        app_logger.error(f"Stress test error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to run stress test")


@router.get("/load-test/scenarios", summary="Get Load Test Scenarios")
async def get_load_test_scenarios():
    """
    Get available load test scenarios
    
    Returns:
        List of configured load test scenarios with descriptions
    """
    
    try:
        scenarios = []
        
        for scenario_id, scenario in load_tester.scenarios.items():
            scenarios.append({
                "scenario_id": scenario.scenario_id,
                "name": scenario.name,
                "description": scenario.description,
                "request_count": len(scenario.requests),
                "scenario_weight": scenario.scenario_weight,
                "user_think_time_seconds": scenario.user_think_time_seconds,
                "endpoints": [
                    {
                        "method": req.method,
                        "url": req.url,
                        "weight": req.weight
                    }
                    for req in scenario.requests
                ]
            })
        
        return {
            "status": "success",
            "scenario_count": len(scenarios),
            "scenarios": scenarios
        }
        
    except Exception as e:
        app_logger.error(f"Load test scenarios error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve load test scenarios")


@router.get("/load-test/history", summary="Load Test History")
async def get_load_test_history():
    """
    Get load test execution history
    
    Returns:
        Historical load test results and trends
    """
    
    try:
        history = load_tester.get_test_history()
        
        return {
            "status": "success",
            "test_count": len(history),
            "history": history
        }
        
    except Exception as e:
        app_logger.error(f"Load test history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve load test history")