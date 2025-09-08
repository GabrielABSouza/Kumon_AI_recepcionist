"""
Logging and tracing tests for Gemini Orchestrator.
Tests structured logging, trace propagation, and observability.
"""
import logging
import time

import pytest

from tests.helpers.factories import MessageFactory
from tests.orchestrator.test_orchestrator_contract import GeminiOrchestrator


# Enhanced orchestrator with logging
class LoggingGeminiOrchestrator(GeminiOrchestrator):
    """Orchestrator with structured logging."""

    def __init__(self, client=None, timeout_ms=150, retries=1):
        super().__init__(client, timeout_ms, retries)
        self.logger = logging.getLogger(__name__)

    async def classify(self, message):
        """Classify with structured logging."""
        start_time = time.perf_counter()
        trace_id = message.trace_id or "NO_TRACE"
        turn_id = message.turn_id or "NO_TURN"

        # Log start
        self.logger.info(
            f"ORCH|start|trace_id={trace_id}|turn_id={turn_id}|"
            f"phone={message.phone}|text_len={len(message.text or '')}"
        )

        try:
            # Call parent classify
            result = await super().classify(message)

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            result.latency_ms = latency_ms

            # Detect error via result (since mock doesn't raise exceptions)
            error_val = None
            if hasattr(result, "error") and result.error:
                error_val = result.error
            elif (
                hasattr(result, "meta")
                and isinstance(result.meta, dict)
                and result.meta.get("error")
            ):
                error_val = result.meta.get("error")
            elif getattr(result, "routing_hint", None) == "timeout":
                error_val = "timeout"
            # Also check for fallback with error field
            elif (
                result.intent == "fallback"
                and hasattr(result, "error")
                and result.error
            ):
                error_val = result.error

            # Log error if detected
            if error_val:
                self.logger.error(
                    f"ORCH|error|trace_id={trace_id}|turn_id={turn_id}|"
                    f"error={error_val}|latency_ms={latency_ms:.2f}"
                )

            # Log completion
            self.logger.info(
                f"ORCH|complete|trace_id={trace_id}|turn_id={turn_id}|"
                f"intent={result.intent}|confidence={result.confidence:.2f}|"
                f"latency_ms={latency_ms:.2f}"
            )

            return result

        except Exception as e:
            # Still handle exceptions (rare with mock, but keep for compatibility)
            latency_ms = (time.perf_counter() - start_time) * 1000
            self.logger.error(
                f"ORCH|error|trace_id={trace_id}|turn_id={turn_id}|"
                f"error={str(e)}|latency_ms={latency_ms:.2f}"
            )
            raise


@pytest.fixture
def orchestrator(gemini_stub):
    """Create logging orchestrator with stub."""
    return LoggingGeminiOrchestrator(client=gemini_stub, timeout_ms=120, retries=1)


# STRUCTURED LOGGING TESTS


@pytest.mark.asyncio
async def test_logging_structured_logs_present(
    orchestrator, base_msg, gemini_stub, caplog
):
    """Test that structured logs are generated."""
    # Given
    caplog.set_level(logging.INFO)
    gemini_stub.set_response("greeting", 0.92)

    # When
    await orchestrator.classify(base_msg)

    # Then - check structured logs
    logs = caplog.text
    assert "ORCH|start" in logs
    assert "ORCH|complete" in logs
    assert "trace_id=" in logs
    assert "turn_id=" in logs
    assert "intent=greeting" in logs
    assert "confidence=0.92" in logs
    assert "latency_ms=" in logs


@pytest.mark.asyncio
async def test_logging_includes_all_required_fields(orchestrator, gemini_stub, caplog):
    """Test that all required fields are in logs."""
    # Given
    caplog.set_level(logging.INFO)
    msg = MessageFactory.create_simple_message(
        text="test logging",
        trace_id="TRACE_123",
        turn_id="TURN_456",
        phone="5511999999999",
    )
    gemini_stub.set_response("information_request", 0.85)

    # When
    await orchestrator.classify(msg)

    # Then - verify all fields
    logs = caplog.text
    assert "trace_id=TRACE_123" in logs
    assert "turn_id=TURN_456" in logs
    assert "phone=5511999999999" in logs
    assert "text_len=12" in logs  # len("test logging")
    assert "intent=information_request" in logs
    assert "confidence=0.85" in logs


@pytest.mark.asyncio
async def test_logging_error_logs_on_failure(
    orchestrator, base_msg, gemini_stub, caplog
):
    """Test that errors are logged properly."""
    # Given
    caplog.set_level(logging.INFO)
    gemini_stub.behavior = "error"

    # When
    result = await orchestrator.classify(base_msg)

    # Then
    logs = caplog.text
    assert "ORCH|error" in logs
    assert "error=" in logs
    assert "latency_ms=" in logs
    assert result.intent == "fallback"


# TRACE PROPAGATION TESTS


@pytest.mark.asyncio
async def test_tracing_propagates_trace_id(orchestrator, gemini_stub, caplog):
    """Test that trace_id is propagated through the flow."""
    # Given
    caplog.set_level(logging.INFO)
    msg = MessageFactory.create_simple_message(
        text="trace test", trace_id="TRACE_PROP_001"
    )
    gemini_stub.set_response("greeting", 0.9)

    # When
    await orchestrator.classify(msg)

    # Then - trace_id should appear in all logs
    log_records = [r for r in caplog.records if "ORCH" in r.message]
    for record in log_records:
        assert "trace_id=TRACE_PROP_001" in record.message


@pytest.mark.asyncio
async def test_tracing_propagates_turn_id(orchestrator, gemini_stub, caplog):
    """Test that turn_id is propagated."""
    # Given
    caplog.set_level(logging.INFO)
    msg = MessageFactory.create_simple_message(
        text="turn test", turn_id="TURN_PROP_002"
    )
    gemini_stub.set_response("information_request", 0.8)

    # When
    await orchestrator.classify(msg)

    # Then
    logs = caplog.text
    assert "turn_id=TURN_PROP_002" in logs


@pytest.mark.asyncio
async def test_tracing_handles_missing_ids(orchestrator, gemini_stub, caplog):
    """Test that missing trace/turn IDs are handled."""
    # Given - message without trace_id or turn_id
    caplog.set_level(logging.INFO)
    msg = MessageFactory.create_simple_message(text="no ids")
    msg.trace_id = None
    msg.turn_id = None
    gemini_stub.set_response("greeting", 0.9)

    # When
    await orchestrator.classify(msg)

    # Then - should use placeholder
    logs = caplog.text
    assert "trace_id=NO_TRACE" in logs
    assert "turn_id=NO_TURN" in logs


# LATENCY TRACKING TESTS


@pytest.mark.asyncio
async def test_logging_tracks_latency(orchestrator, base_msg, gemini_stub, caplog):
    """Test that latency is tracked and logged."""
    # Given
    caplog.set_level(logging.INFO)
    gemini_stub.delay_ms = 50  # Controlled delay
    gemini_stub.set_response("greeting", 0.9)

    # When
    result = await orchestrator.classify(base_msg)

    # Then
    assert result.latency_ms is not None
    assert result.latency_ms >= 50  # At least the delay
    assert result.latency_ms < 200  # Reasonable upper bound

    # Check logs
    logs = caplog.text
    assert "latency_ms=" in logs


@pytest.mark.asyncio
async def test_logging_latency_on_error(orchestrator, base_msg, gemini_stub, caplog):
    """Test that latency is logged even on errors."""
    # Given
    caplog.set_level(logging.INFO)
    gemini_stub.behavior = "timeout"

    # When
    await orchestrator.classify(base_msg)

    # Then - error log should have latency
    error_logs = [r for r in caplog.records if "ORCH|error" in r.message]
    assert len(error_logs) > 0
    assert "latency_ms=" in error_logs[0].message


# LOG FORMAT TESTS


@pytest.mark.asyncio
async def test_logging_consistent_format(orchestrator, gemini_stub, caplog):
    """Test that log format is consistent."""
    # Given
    caplog.set_level(logging.INFO)
    msgs = [MessageFactory.create_simple_message(text=f"msg {i}") for i in range(3)]
    gemini_stub.set_response("greeting", 0.9)

    # When
    for msg in msgs:
        await orchestrator.classify(msg)

    # Then - all logs should follow format
    orch_logs = [r.message for r in caplog.records if "ORCH|" in r.message]
    for log in orch_logs:
        # Should have pipe-separated format
        assert log.count("|") >= 2
        # Should have key=value pairs
        assert "=" in log
        # Should start with ORCH|
        assert log.startswith("ORCH|")


@pytest.mark.asyncio
async def test_logging_no_sensitive_data(orchestrator, gemini_stub, caplog):
    """Test that sensitive data is not logged."""
    # Given
    caplog.set_level(logging.INFO)
    msg = MessageFactory.create_simple_message(
        text="meu cpf é 123.456.789-00 e senha abc123",
        headers={"authorization": "Bearer secret_token"},
    )
    gemini_stub.set_response("information_request", 0.8)

    # When
    await orchestrator.classify(msg)

    # Then - sensitive data should not be in logs
    logs = caplog.text
    assert "123.456.789-00" not in logs  # CPF not logged
    assert "abc123" not in logs  # Password not logged
    assert "secret_token" not in logs  # Auth token not logged
    # But should log text length
    assert "text_len=" in logs


# CONCURRENT LOGGING TESTS


@pytest.mark.asyncio
async def test_logging_concurrent_requests_isolated(orchestrator, gemini_stub, caplog):
    """Test that concurrent requests have isolated logging."""
    # Given
    caplog.set_level(logging.INFO)
    msgs = [
        MessageFactory.create_simple_message(
            text=f"concurrent {i}",
            trace_id=f"TRACE_{i:03d}",
            turn_id=f"TURN_{i:03d}",
        )
        for i in range(5)
    ]
    gemini_stub.set_response("greeting", 0.9)

    # When - process concurrently
    import asyncio

    await asyncio.gather(*[orchestrator.classify(msg) for msg in msgs])

    # Then - each should have its own trace
    for i in range(5):
        assert f"trace_id=TRACE_{i:03d}" in caplog.text
        assert f"turn_id=TURN_{i:03d}" in caplog.text


# METRICS TESTS


@pytest.mark.asyncio
async def test_logging_intent_distribution(orchestrator, gemini_stub, caplog):
    """Test logging of different intent types."""
    # Given
    caplog.set_level(logging.INFO)
    test_cases = [
        ("olá", "greeting", 0.95),
        ("quanto custa?", "information_request", 0.85),
        ("quero matricular", "qualification", 0.88),
        ("agendar visita", "scheduling", 0.82),
        ("ok", "fallback", 0.4),
    ]

    # When
    for text, intent, confidence in test_cases:
        msg = MessageFactory.create_simple_message(text=text)
        gemini_stub.set_response(intent, confidence)
        await orchestrator.classify(msg)

    # Then - all intents should be logged
    logs = caplog.text
    assert "intent=greeting" in logs
    assert "intent=information_request" in logs
    assert "intent=qualification" in logs
    assert "intent=scheduling" in logs
    assert "intent=fallback" in logs


@pytest.mark.asyncio
async def test_logging_confidence_ranges(orchestrator, gemini_stub, caplog):
    """Test logging of different confidence levels."""
    # Given
    caplog.set_level(logging.INFO)
    confidence_levels = [0.95, 0.7, 0.4, 0.1]

    # When
    for conf in confidence_levels:
        msg = MessageFactory.create_simple_message(text=f"conf {conf}")
        gemini_stub.set_response("greeting", conf)
        await orchestrator.classify(msg)

    # Then - all confidence levels logged
    logs = caplog.text
    assert "confidence=0.95" in logs
    assert "confidence=0.70" in logs
    assert "confidence=0.40" in logs
    assert "confidence=0.10" in logs


@pytest.mark.asyncio
async def test_logging_performance_monitoring(orchestrator, gemini_stub, caplog):
    """Test that logs contain performance monitoring data."""
    # Given
    caplog.set_level(logging.INFO)
    msg = MessageFactory.create_simple_message(text="perf test")
    gemini_stub.set_response("greeting", 0.9)
    gemini_stub.delay_ms = 75

    # When
    result = await orchestrator.classify(msg)

    # Then - should have performance data
    complete_logs = [r for r in caplog.records if "ORCH|complete" in r.message]
    assert len(complete_logs) == 1
    log = complete_logs[0].message

    # Extract latency from log
    import re

    match = re.search(r"latency_ms=([\d.]+)", log)
    assert match is not None
    logged_latency = float(match.group(1))
    assert logged_latency >= 75  # At least the delay
    assert logged_latency == pytest.approx(result.latency_ms, rel=0.1)  # Match result
