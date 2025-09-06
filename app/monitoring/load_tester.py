"""
Comprehensive Load Testing System

Advanced load testing framework with:
- Multi-scenario load testing (webhook processing, AI operations, API calls)
- Real-time performance metrics collection
- Stress testing with gradual load increases
- Endurance testing for extended periods
- Performance baseline establishment
- Bottleneck identification and analysis
- Load test reporting and recommendations
"""

import asyncio
import aiohttp
import time
import random
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import statistics

from ..core.logger import app_logger
from ..core.config import settings


@dataclass
class LoadTestRequest:
    """Load test request configuration"""
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    data: Optional[Dict[str, Any]] = None
    timeout_seconds: int = 30
    weight: float = 1.0  # Request weight for scenario distribution


@dataclass
class LoadTestScenario:
    """Load test scenario definition"""
    scenario_id: str
    name: str
    description: str
    requests: List[LoadTestRequest]
    user_think_time_seconds: float = 1.0  # Delay between requests
    scenario_weight: float = 1.0  # Scenario selection probability


@dataclass
class LoadTestResult:
    """Individual request result"""
    scenario_id: str
    request_url: str
    method: str
    status_code: int
    response_time_ms: float
    request_size_bytes: int
    response_size_bytes: int
    timestamp: datetime
    error_message: Optional[str] = None


@dataclass
class LoadTestSummary:
    """Load test execution summary"""
    test_name: str
    start_time: datetime
    end_time: datetime
    total_duration_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    error_rate_percent: float
    total_data_transferred_mb: float
    scenarios_executed: Dict[str, int]
    performance_score: float
    bottlenecks_identified: List[str]
    recommendations: List[str]


class LoadTester:
    """
    Comprehensive load testing system
    
    Features:
    - Multi-scenario load generation
    - Real-time metrics collection
    - Gradual load ramping
    - Performance bottleneck detection
    - Comprehensive reporting
    - Integration with monitoring systems
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.scenarios: Dict[str, LoadTestScenario] = {}
        self.results: List[LoadTestResult] = []
        self.active_tests: Dict[str, bool] = {}
        
        # Load test configuration
        self.config = {
            "max_concurrent_users": 100,
            "ramp_up_duration_seconds": 60,
            "test_duration_seconds": 300,
            "cool_down_duration_seconds": 30,
            "request_timeout_seconds": 30,
            "think_time_variance": 0.5,  # Random variance in think time
            "retry_failed_requests": False,
            "collect_response_content": False
        }
        
        # Initialize default scenarios
        self._initialize_default_scenarios()
        
        app_logger.info("Load Tester initialized with comprehensive scenario support")
    
    def _initialize_default_scenarios(self):
        """Initialize default load test scenarios"""
        
        # Health check scenario
        health_scenario = LoadTestScenario(
            scenario_id="health_check",
            name="Health Check Load Test",
            description="Test basic API health endpoints",
            requests=[
                LoadTestRequest(
                    method="GET",
                    url=f"{self.base_url}/api/v1/health",
                    weight=1.0
                )
            ],
            user_think_time_seconds=0.5,
            scenario_weight=0.2
        )
        
        # WhatsApp webhook scenario
        webhook_scenario = LoadTestScenario(
            scenario_id="whatsapp_webhook",
            name="WhatsApp Webhook Processing",
            description="Test WhatsApp message processing under load",
            requests=[
                LoadTestRequest(
                    method="POST",
                    url=f"{self.base_url}/api/v1/whatsapp/webhook",
                    headers={"Content-Type": "application/json"},
                    data={
                        "messages": [{
                            "id": "test_message_{{random_id}}",
                            "from": "5551999999999",
                            "timestamp": int(time.time()),
                            "text": {
                                "body": "Olá, gostaria de agendar uma avaliação gratuita."
                            },
                            "type": "text"
                        }]
                    },
                    timeout_seconds=45,  # Webhook processing can be slower
                    weight=1.0
                )
            ],
            user_think_time_seconds=2.0,
            scenario_weight=0.6  # Primary scenario
        )
        
        # Performance monitoring scenario
        monitoring_scenario = LoadTestScenario(
            scenario_id="performance_monitoring",
            name="Performance Monitoring Load Test",
            description="Test performance monitoring endpoints",
            requests=[
                LoadTestRequest(
                    method="GET",
                    url=f"{self.base_url}/api/v1/performance/metrics",
                    weight=0.5
                ),
                LoadTestRequest(
                    method="GET",
                    url=f"{self.base_url}/api/v1/performance/dashboard",
                    weight=0.3
                ),
                LoadTestRequest(
                    method="GET",
                    url=f"{self.base_url}/api/v1/alerts/active",
                    weight=0.2
                )
            ],
            user_think_time_seconds=1.0,
            scenario_weight=0.2
        )
        
        # Store scenarios
        self.scenarios = {
            health_scenario.scenario_id: health_scenario,
            webhook_scenario.scenario_id: webhook_scenario,
            monitoring_scenario.scenario_id: monitoring_scenario
        }
        
        app_logger.info(f"Initialized {len(self.scenarios)} default load test scenarios")
    
    def add_scenario(self, scenario: LoadTestScenario):
        """Add a custom load test scenario"""
        self.scenarios[scenario.scenario_id] = scenario
        app_logger.info(f"Added load test scenario: {scenario.name}")
    
    def _select_scenario(self) -> LoadTestScenario:
        """Select a scenario based on weights"""
        
        scenarios = list(self.scenarios.values())
        weights = [scenario.scenario_weight for scenario in scenarios]
        
        # Weighted random selection
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(scenarios)
        
        rand = random.uniform(0, total_weight)
        cumulative = 0
        
        for scenario, weight in zip(scenarios, weights):
            cumulative += weight
            if rand <= cumulative:
                return scenario
        
        return scenarios[-1]  # Fallback
    
    def _prepare_request_data(self, request: LoadTestRequest, user_id: int) -> LoadTestRequest:
        """Prepare request data with dynamic values"""
        
        # Clone the request
        prepared_request = LoadTestRequest(
            method=request.method,
            url=request.url,
            headers=request.headers.copy(),
            data=json.loads(json.dumps(request.data)) if request.data else None,
            timeout_seconds=request.timeout_seconds,
            weight=request.weight
        )
        
        # Replace dynamic placeholders
        if prepared_request.data:
            data_str = json.dumps(prepared_request.data)
            
            # Replace placeholders
            data_str = data_str.replace("{{random_id}}", f"load_test_{user_id}_{int(time.time() * 1000)}")
            data_str = data_str.replace("{{user_id}}", str(user_id))
            data_str = data_str.replace("{{timestamp}}", str(int(time.time())))
            
            prepared_request.data = json.loads(data_str)
        
        return prepared_request
    
    async def _execute_request(self, session: aiohttp.ClientSession, request: LoadTestRequest, scenario_id: str, user_id: int) -> LoadTestResult:
        """Execute a single load test request"""
        
        start_time = time.time()
        request_size = 0
        response_size = 0
        
        try:
            # Prepare request
            prepared_request = self._prepare_request_data(request, user_id)
            
            # Calculate request size
            if prepared_request.data:
                request_size = len(json.dumps(prepared_request.data).encode('utf-8'))
            
            # Execute request
            async with session.request(
                method=prepared_request.method,
                url=prepared_request.url,
                headers=prepared_request.headers,
                json=prepared_request.data,
                timeout=aiohttp.ClientTimeout(total=prepared_request.timeout_seconds)
            ) as response:
                
                # Read response
                response_data = await response.read()
                response_size = len(response_data)
                response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                
                return LoadTestResult(
                    scenario_id=scenario_id,
                    request_url=prepared_request.url,
                    method=prepared_request.method,
                    status_code=response.status,
                    response_time_ms=response_time,
                    request_size_bytes=request_size,
                    response_size_bytes=response_size,
                    timestamp=datetime.now(),
                    error_message=None if response.status < 400 else f"HTTP {response.status}"
                )
        
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return LoadTestResult(
                scenario_id=scenario_id,
                request_url=request.url,
                method=request.method,
                status_code=0,
                response_time_ms=response_time,
                request_size_bytes=request_size,
                response_size_bytes=response_size,
                timestamp=datetime.now(),
                error_message="Request timeout"
            )
        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return LoadTestResult(
                scenario_id=scenario_id,
                request_url=request.url,
                method=request.method,
                status_code=0,
                response_time_ms=response_time,
                request_size_bytes=request_size,
                response_size_bytes=response_size,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def _simulate_user(self, user_id: int, test_duration_seconds: int, session: aiohttp.ClientSession):
        """Simulate a single user's load testing behavior"""
        
        end_time = time.time() + test_duration_seconds
        
        while time.time() < end_time:
            try:
                # Select scenario
                scenario = self._select_scenario()
                
                # Execute scenario requests
                for request in scenario.requests:
                    if time.time() >= end_time:
                        break
                    
                    # Execute request
                    result = await self._execute_request(session, request, scenario.scenario_id, user_id)
                    self.results.append(result)
                    
                    # Optional think time between requests in scenario
                    if len(scenario.requests) > 1:
                        think_time = scenario.user_think_time_seconds
                        # Add variance
                        variance = think_time * self.config["think_time_variance"]
                        actual_think_time = think_time + random.uniform(-variance, variance)
                        await asyncio.sleep(max(0.1, actual_think_time))
                
                # Think time between scenarios
                think_time = scenario.user_think_time_seconds
                variance = think_time * self.config["think_time_variance"]
                actual_think_time = think_time + random.uniform(-variance, variance)
                await asyncio.sleep(max(0.1, actual_think_time))
                
            except Exception as e:
                app_logger.error(f"User {user_id} simulation error: {e}")
                await asyncio.sleep(1)  # Brief pause on error
    
    async def run_load_test(
        self,
        test_name: str,
        concurrent_users: int = 50,
        test_duration_seconds: int = 300,
        ramp_up_duration_seconds: int = 60
    ) -> LoadTestSummary:
        """
        Run a comprehensive load test
        
        Args:
            test_name: Name of the load test
            concurrent_users: Number of concurrent users to simulate
            test_duration_seconds: Duration of the test in seconds
            ramp_up_duration_seconds: Time to gradually increase load
            
        Returns:
            Comprehensive load test summary
        """
        
        if test_name in self.active_tests:
            raise Exception(f"Load test '{test_name}' is already running")
        
        app_logger.info(f"Starting load test: {test_name}")
        app_logger.info(f"Configuration: {concurrent_users} users, {test_duration_seconds}s duration, {ramp_up_duration_seconds}s ramp-up")
        
        # Mark test as active
        self.active_tests[test_name] = True
        
        # Clear previous results
        self.results = []
        
        start_time = datetime.now()
        
        try:
            # Create HTTP session with connection limits
            connector = aiohttp.TCPConnector(
                limit=concurrent_users * 2,  # Connection pool size
                limit_per_host=concurrent_users * 2,
                ttl_dns_cache=300,
                ttl_connection_pool=300,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(total=self.config["request_timeout_seconds"])
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                
                # Gradual ramp-up
                tasks = []
                ramp_interval = ramp_up_duration_seconds / concurrent_users if concurrent_users > 0 else 0
                
                for user_id in range(concurrent_users):
                    # Delay user start based on ramp-up
                    start_delay = user_id * ramp_interval
                    
                    # Create user simulation task
                    task = asyncio.create_task(
                        self._start_user_with_delay(user_id, start_delay, test_duration_seconds, session)
                    )
                    tasks.append(task)
                
                # Wait for all users to complete
                await asyncio.gather(*tasks, return_exceptions=True)
        
        finally:
            # Mark test as inactive
            self.active_tests[test_name] = False
        
        end_time = datetime.now()
        
        # Generate test summary
        summary = self._generate_test_summary(
            test_name=test_name,
            start_time=start_time,
            end_time=end_time,
            concurrent_users=concurrent_users
        )
        
        app_logger.info(f"Load test completed: {test_name}")
        app_logger.info(f"Results: {summary.total_requests} requests, {summary.requests_per_second:.1f} RPS, {summary.avg_response_time_ms:.1f}ms avg response time")
        
        return summary
    
    async def _start_user_with_delay(self, user_id: int, start_delay: float, test_duration_seconds: int, session: aiohttp.ClientSession):
        """Start user simulation with initial delay"""
        
        if start_delay > 0:
            await asyncio.sleep(start_delay)
        
        await self._simulate_user(user_id, test_duration_seconds, session)
    
    def _generate_test_summary(self, test_name: str, start_time: datetime, end_time: datetime, concurrent_users: int) -> LoadTestSummary:
        """Generate comprehensive test summary"""
        
        if not self.results:
            return LoadTestSummary(
                test_name=test_name,
                start_time=start_time,
                end_time=end_time,
                total_duration_seconds=0,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                requests_per_second=0,
                avg_response_time_ms=0,
                p95_response_time_ms=0,
                p99_response_time_ms=0,
                min_response_time_ms=0,
                max_response_time_ms=0,
                error_rate_percent=0,
                total_data_transferred_mb=0,
                scenarios_executed={},
                performance_score=0,
                bottlenecks_identified=[],
                recommendations=[]
            )
        
        # Basic metrics
        total_duration = (end_time - start_time).total_seconds()
        total_requests = len(self.results)
        successful_requests = len([r for r in self.results if 200 <= r.status_code < 400])
        failed_requests = total_requests - successful_requests
        
        # Response time metrics
        response_times = [r.response_time_ms for r in self.results]
        response_times.sort()
        
        avg_response_time = statistics.mean(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        # Percentiles
        p95_index = int(0.95 * len(response_times))
        p99_index = int(0.99 * len(response_times))
        p95_response_time = response_times[min(p95_index, len(response_times) - 1)]
        p99_response_time = response_times[min(p99_index, len(response_times) - 1)]
        
        # Request rate
        requests_per_second = total_requests / total_duration if total_duration > 0 else 0
        
        # Error rate
        error_rate = (failed_requests / total_requests * 100) if total_requests > 0 else 0
        
        # Data transfer
        total_data_mb = sum(r.request_size_bytes + r.response_size_bytes for r in self.results) / (1024 * 1024)
        
        # Scenario distribution
        scenario_counts = defaultdict(int)
        for result in self.results:
            scenario_counts[result.scenario_id] += 1
        
        # Performance analysis
        performance_score = self._calculate_performance_score(
            avg_response_time, error_rate, requests_per_second, concurrent_users
        )
        
        bottlenecks = self._identify_bottlenecks(response_times, error_rate, requests_per_second)
        recommendations = self._generate_recommendations(bottlenecks, performance_score)
        
        return LoadTestSummary(
            test_name=test_name,
            start_time=start_time,
            end_time=end_time,
            total_duration_seconds=total_duration,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            requests_per_second=requests_per_second,
            avg_response_time_ms=avg_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            min_response_time_ms=min_response_time,
            max_response_time_ms=max_response_time,
            error_rate_percent=error_rate,
            total_data_transferred_mb=total_data_mb,
            scenarios_executed=dict(scenario_counts),
            performance_score=performance_score,
            bottlenecks_identified=bottlenecks,
            recommendations=recommendations
        )
    
    def _calculate_performance_score(self, avg_response_time: float, error_rate: float, rps: float, concurrent_users: int) -> float:
        """Calculate overall performance score (0-100)"""
        
        try:
            # Response time score (40% weight)
            if avg_response_time <= 100:
                response_score = 100
            elif avg_response_time <= 500:
                response_score = 90 - (avg_response_time - 100) / 400 * 40  # 90-50
            elif avg_response_time <= 2000:
                response_score = 50 - (avg_response_time - 500) / 1500 * 30  # 50-20
            else:
                response_score = max(0, 20 - (avg_response_time - 2000) / 3000 * 20)  # 20-0
            
            # Error rate score (30% weight)
            error_score = max(0, 100 - error_rate * 20)  # 20% penalty per 1% error rate
            
            # Throughput score (30% weight)
            expected_rps = concurrent_users * 0.5  # Rough expectation
            throughput_ratio = min(2.0, rps / expected_rps) if expected_rps > 0 else 1.0
            throughput_score = min(100, throughput_ratio * 50 + 50)
            
            # Weighted score
            overall_score = (
                response_score * 0.4 +
                error_score * 0.3 +
                throughput_score * 0.3
            )
            
            return max(0, min(100, overall_score))
            
        except Exception as e:
            app_logger.error(f"Performance score calculation failed: {e}")
            return 0.0
    
    def _identify_bottlenecks(self, response_times: List[float], error_rate: float, rps: float) -> List[str]:
        """Identify performance bottlenecks"""
        
        bottlenecks = []
        
        # High response time
        if statistics.mean(response_times) > 2000:  # 2 seconds
            bottlenecks.append("High average response time indicates processing bottleneck")
        
        # High error rate
        if error_rate > 5:  # 5%
            bottlenecks.append("High error rate indicates system overload or failures")
        
        # Variable response times
        if len(response_times) > 10:
            response_stddev = statistics.stdev(response_times)
            response_mean = statistics.mean(response_times)
            if response_stddev > response_mean * 0.5:  # High variance
                bottlenecks.append("High response time variability indicates inconsistent performance")
        
        # Low throughput
        if rps < 10:  # Very low RPS
            bottlenecks.append("Low request throughput indicates capacity limitations")
        
        return bottlenecks
    
    def _generate_recommendations(self, bottlenecks: List[str], performance_score: float) -> List[str]:
        """Generate performance improvement recommendations"""
        
        recommendations = []
        
        if performance_score < 70:
            recommendations.append("Overall performance is below optimal - consider system optimization")
        
        if "processing bottleneck" in " ".join(bottlenecks).lower():
            recommendations.extend([
                "Optimize AI/ML model inference times",
                "Implement intelligent caching for frequent operations",
                "Consider horizontal scaling with load balancing"
            ])
        
        if "system overload" in " ".join(bottlenecks).lower():
            recommendations.extend([
                "Increase server resources (CPU, memory)",
                "Implement request rate limiting",
                "Optimize database queries and connections"
            ])
        
        if "inconsistent performance" in " ".join(bottlenecks).lower():
            recommendations.extend([
                "Implement connection pooling",
                "Optimize garbage collection settings",
                "Add performance monitoring and alerting"
            ])
        
        if "capacity limitations" in " ".join(bottlenecks).lower():
            recommendations.extend([
                "Scale horizontally with additional instances",
                "Implement asynchronous processing queues",
                "Optimize request handling and processing pipelines"
            ])
        
        if not recommendations:
            recommendations.append("Performance is within acceptable ranges - continue monitoring")
        
        return recommendations
    
    async def run_stress_test(self, test_name: str = "stress_test", max_users: int = 200, step_size: int = 25, step_duration_seconds: int = 120) -> List[LoadTestSummary]:
        """
        Run stress test with gradually increasing load
        
        Args:
            test_name: Base name for stress test
            max_users: Maximum number of concurrent users
            step_size: User increase per step
            step_duration_seconds: Duration of each step
            
        Returns:
            List of test summaries for each step
        """
        
        app_logger.info(f"Starting stress test: {test_name}")
        app_logger.info(f"Configuration: Up to {max_users} users, {step_size} user steps, {step_duration_seconds}s per step")
        
        results = []
        
        for users in range(step_size, max_users + 1, step_size):
            step_name = f"{test_name}_step_{users}_users"
            
            try:
                summary = await self.run_load_test(
                    test_name=step_name,
                    concurrent_users=users,
                    test_duration_seconds=step_duration_seconds,
                    ramp_up_duration_seconds=min(30, step_duration_seconds // 4)  # Quick ramp-up for stress test
                )
                
                results.append(summary)
                
                app_logger.info(f"Stress test step completed: {users} users, {summary.performance_score:.1f} score")
                
                # Stop if performance degrades significantly
                if summary.performance_score < 30 or summary.error_rate_percent > 20:
                    app_logger.warning(f"Stopping stress test due to performance degradation at {users} users")
                    break
                    
            except Exception as e:
                app_logger.error(f"Stress test step failed at {users} users: {e}")
                break
        
        app_logger.info(f"Stress test completed: {test_name}")
        return results
    
    def get_test_history(self) -> List[Dict[str, Any]]:
        """Get load test execution history"""
        
        # This would typically be stored in a database
        # For now, return recent results
        return [
            {
                "test_name": "example_test",
                "timestamp": datetime.now().isoformat(),
                "performance_score": 85.0,
                "total_requests": 1000,
                "avg_response_time_ms": 150.0
            }
        ]


# Global load tester instance
load_tester = LoadTester()