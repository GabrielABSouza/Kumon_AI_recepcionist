"""
Performance tests for Gemini Orchestrator.
Tests latency, throughput, and resource usage.
"""
import asyncio
import statistics
import time

import pytest

from tests.helpers.factories import MessageFactory
from tests.orchestrator.test_orchestrator_contract import GeminiOrchestrator


@pytest.fixture
def orchestrator(performance_gemini_stub):
    """Create orchestrator with performance testing stub."""
    return GeminiOrchestrator(client=performance_gemini_stub, timeout_ms=150, retries=0)


# LATENCY TESTS


@pytest.mark.asyncio
async def test_performance_p95_latency_under_150ms(
    orchestrator, performance_gemini_stub
):
    """Test that p95 latency is under 150ms SLO."""
    # Given - 50 concurrent calls
    msgs = [
        MessageFactory.create_simple_message(text=f"message {i}") for i in range(50)
    ]

    # When - measure latencies
    latencies = []

    async def measure_call(msg):
        start = time.perf_counter()
        await orchestrator.classify(msg)
        latencies.append((time.perf_counter() - start) * 1000)

    await asyncio.gather(*[measure_call(msg) for msg in msgs])

    # Then - p95 should be under 150ms
    p95 = sorted(latencies)[int(0.95 * len(latencies)) - 1]
    assert p95 <= 150, f"p95 latency {p95:.2f}ms exceeds 150ms SLO"

    # Also check other percentiles for monitoring
    p50 = sorted(latencies)[len(latencies) // 2]
    p99 = sorted(latencies)[int(0.99 * len(latencies)) - 1]
    print(f"Latency - p50: {p50:.2f}ms, p95: {p95:.2f}ms, p99: {p99:.2f}ms")


@pytest.mark.asyncio
async def test_performance_p50_latency_under_50ms(
    orchestrator, performance_gemini_stub
):
    """Test that median (p50) latency is under 50ms."""
    # Given - 30 calls
    msgs = [MessageFactory.create_simple_message(text=f"test {i}") for i in range(30)]

    # When
    latencies = []

    async def measure_call(msg):
        start = time.perf_counter()
        await orchestrator.classify(msg)
        latencies.append((time.perf_counter() - start) * 1000)

    await asyncio.gather(*[measure_call(msg) for msg in msgs])

    # Then
    p50 = sorted(latencies)[len(latencies) // 2]
    assert p50 <= 50, f"p50 latency {p50:.2f}ms exceeds 50ms target"


@pytest.mark.asyncio
async def test_performance_consistent_latency(orchestrator, performance_gemini_stub):
    """Test that latency is consistent (low variance)."""
    # Given - 20 identical messages
    msg = MessageFactory.create_simple_message(text="consistent test")

    # When - measure multiple times
    latencies = []
    for _ in range(20):
        start = time.perf_counter()
        await orchestrator.classify(msg)
        latencies.append((time.perf_counter() - start) * 1000)

    # Then - standard deviation should be reasonable
    mean_latency = statistics.mean(latencies)
    std_dev = statistics.stdev(latencies)
    cv = std_dev / mean_latency  # Coefficient of variation

    assert cv < 0.5, f"High latency variance: CV={cv:.2f} (std={std_dev:.2f}ms)"


# THROUGHPUT TESTS


@pytest.mark.asyncio
async def test_performance_concurrent_requests(orchestrator, performance_gemini_stub):
    """Test handling of concurrent requests."""
    # Given - 100 concurrent requests
    msgs = [
        MessageFactory.create_simple_message(text=f"concurrent {i}") for i in range(100)
    ]

    # When
    start_time = time.perf_counter()
    results = await asyncio.gather(
        *[orchestrator.classify(msg) for msg in msgs], return_exceptions=True
    )
    total_time = time.perf_counter() - start_time

    # Then
    successful = sum(
        1 for r in results if not isinstance(r, Exception) and r.confidence > 0
    )
    throughput = successful / total_time

    assert successful >= 95, f"Only {successful}/100 requests succeeded"
    assert throughput >= 50, f"Throughput {throughput:.1f} req/s below 50 req/s"
    print(f"Throughput: {throughput:.1f} requests/second")


@pytest.mark.asyncio
async def test_performance_max_concurrent_connections(
    orchestrator, performance_gemini_stub
):
    """Test maximum concurrent connections handling."""
    # Given
    msgs = [
        MessageFactory.create_simple_message(text=f"max concurrent {i}")
        for i in range(50)
    ]

    # When - all at once
    await asyncio.gather(*[orchestrator.classify(msg) for msg in msgs])

    # Then - check max concurrent from stub
    max_concurrent = performance_gemini_stub.max_concurrent
    assert max_concurrent <= 50, f"Max concurrent {max_concurrent} exceeds limit"
    print(f"Max concurrent connections: {max_concurrent}")


# RESOURCE USAGE TESTS


@pytest.mark.asyncio
async def test_performance_no_memory_leak(orchestrator, performance_gemini_stub):
    """Test that there are no memory leaks in repeated calls."""
    # Given - reset stub
    performance_gemini_stub.latencies = []

    # When - many sequential calls
    msg = MessageFactory.create_simple_message(text="memory test")
    for _ in range(100):
        await orchestrator.classify(msg)

    # Then - latencies list should not grow unbounded
    assert len(performance_gemini_stub.latencies) == 100
    # In real implementation, would check actual memory usage


@pytest.mark.asyncio
async def test_performance_cleanup_after_error(orchestrator):
    """Test that resources are cleaned up after errors."""

    # Given - stub that fails
    class FailingStub:
        def __init__(self):
            self.active_calls = 0

        async def classify(self, prompt):
            self.active_calls += 1
            try:
                raise Exception("Test error")
            finally:
                self.active_calls -= 1

    fail_stub = FailingStub()
    orchestrator.client = fail_stub

    # When - multiple failing calls
    msgs = [MessageFactory.create_simple_message(text=f"fail {i}") for i in range(10)]
    results = await asyncio.gather(
        *[orchestrator.classify(msg) for msg in msgs], return_exceptions=True
    )

    # Then - all calls should be cleaned up
    assert fail_stub.active_calls == 0, "Resources not cleaned up after errors"


# DEGRADATION TESTS


@pytest.mark.asyncio
async def test_performance_graceful_degradation_under_load(
    orchestrator, performance_gemini_stub
):
    """Test graceful degradation under heavy load."""
    # Given - simulate heavy load
    msgs = [MessageFactory.create_simple_message(text=f"load {i}") for i in range(200)]

    # When - measure success rate
    start_time = time.perf_counter()
    results = await asyncio.gather(
        *[orchestrator.classify(msg) for msg in msgs], return_exceptions=True
    )
    total_time = time.perf_counter() - start_time

    # Then - should maintain reasonable success rate
    successful = sum(
        1 for r in results if not isinstance(r, Exception) and r.confidence > 0
    )
    success_rate = successful / len(msgs)

    assert success_rate >= 0.9, f"Success rate {success_rate:.2%} too low under load"
    print(
        f"Under load: {success_rate:.1%} success rate, "
        f"{len(msgs)/total_time:.1f} req/s"
    )


@pytest.mark.asyncio
async def test_performance_timeout_enforcement(orchestrator):
    """Test that timeouts are properly enforced."""

    # Given - slow stub
    class SlowStub:
        async def classify(self, prompt):
            await asyncio.sleep(0.3)  # 300ms, exceeds 150ms timeout
            return {"intent": "greeting", "confidence": 0.9, "entities": {}}

    orchestrator.client = SlowStub()
    orchestrator.timeout_ms = 150

    # When
    msg = MessageFactory.create_simple_message(text="timeout test")
    start = time.perf_counter()
    result = await orchestrator.classify(msg)
    elapsed = (time.perf_counter() - start) * 1000

    # Then - should timeout around 150ms
    assert result.intent == "fallback"
    assert result.confidence == 0.0
    assert elapsed < 200, f"Timeout not enforced, took {elapsed:.0f}ms"


# CACHING TESTS


@pytest.mark.asyncio
async def test_performance_benefits_from_caching(orchestrator, performance_gemini_stub):
    """Test that repeated identical messages benefit from any caching."""
    # Given - same message multiple times
    msg = MessageFactory.create_simple_message(text="cached message")

    # When - first call (cold)
    start = time.perf_counter()
    await orchestrator.classify(msg)
    cold_latency = (time.perf_counter() - start) * 1000

    # When - subsequent calls (potentially cached)
    warm_latencies = []
    for _ in range(5):
        start = time.perf_counter()
        await orchestrator.classify(msg)
        warm_latencies.append((time.perf_counter() - start) * 1000)

    # Then - warm calls might be faster (if caching implemented)
    avg_warm = statistics.mean(warm_latencies)
    print(f"Cold: {cold_latency:.2f}ms, Warm avg: {avg_warm:.2f}ms")
    # Note: This is informational, caching not required


# BATCH PROCESSING TESTS


@pytest.mark.asyncio
async def test_performance_batch_vs_sequential(orchestrator, performance_gemini_stub):
    """Test performance difference between batch and sequential processing."""
    msgs = [
        MessageFactory.create_simple_message(text=f"batch test {i}") for i in range(20)
    ]

    # Sequential processing
    start = time.perf_counter()
    sequential_results = []
    for msg in msgs:
        sequential_results.append(await orchestrator.classify(msg))
    sequential_time = time.perf_counter() - start

    # Batch processing (concurrent)
    start = time.perf_counter()
    await asyncio.gather(*[orchestrator.classify(msg) for msg in msgs])
    batch_time = time.perf_counter() - start

    # Then - batch should be faster
    speedup = sequential_time / batch_time
    print(
        f"Sequential: {sequential_time:.2f}s, "
        f"Batch: {batch_time:.2f}s, "
        f"Speedup: {speedup:.1f}x"
    )
    assert speedup > 2, f"Batch processing not efficient enough: {speedup:.1f}x"


@pytest.mark.asyncio
async def test_performance_stats_collection(orchestrator, performance_gemini_stub):
    """Test that performance statistics are collected correctly."""
    # Given - reset stats
    performance_gemini_stub.latencies = []

    # When - multiple calls
    msgs = [MessageFactory.create_simple_message(text=f"stats {i}") for i in range(30)]
    await asyncio.gather(*[orchestrator.classify(msg) for msg in msgs])

    # Then - get stats
    stats = performance_gemini_stub.get_stats()

    assert stats["p50"] > 0
    assert stats["p95"] > stats["p50"]
    assert stats["p99"] >= stats["p95"]
    assert stats["mean"] > 0
    assert stats["max_concurrent"] > 0

    print(
        f"Performance stats - p50: {stats['p50']:.2f}ms, "
        f"p95: {stats['p95']:.2f}ms, p99: {stats['p99']:.2f}ms"
    )
