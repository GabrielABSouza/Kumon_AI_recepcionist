"""
Gemini Orchestrator for intent classification.
Only classifies intent, does NOT generate response text.
"""
import asyncio
import logging
import time
from typing import Optional

from tests.helpers.factories import ClassificationResult, PreprocessedMessage

logger = logging.getLogger(__name__)


class GeminiOrchestrator:
    """Orchestrator that classifies messages using Gemini."""

    def __init__(self, client=None, timeout_ms: int = 150, retries: int = 1):
        self.client = client
        self.timeout_ms = timeout_ms
        self.retries = retries

    async def classify(self, message: PreprocessedMessage) -> ClassificationResult:
        """
        Classify a preprocessed message into an intent.
        Returns ClassificationResult with intent, confidence, entities.
        NEVER returns generated text.
        """
        start_time = time.perf_counter()
        trace_id = message.trace_id or "NO_TRACE"
        turn_id = message.turn_id or "NO_TURN"

        # Log start
        logger.info(f"ORCH|start|trace_id={trace_id}|turn_id={turn_id}")

        # Normalize text input - treat None as empty string
        text = message.text
        if text is None:
            text = ""
        text = str(text).strip()

        # Handle empty text
        if not text:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.info("ORCH|empty_text|action=fallback")
            logger.info(
                f"ORCH|complete|trace_id={trace_id}|turn_id={turn_id}|"
                f"intent=fallback|confidence=0.00|"
                f"latency_ms={latency_ms:.2f}"
            )
            return ClassificationResult(
                intent="fallback",
                confidence=0.0,
                entities={},
                routing_hint=None,
                latency_ms=latency_ms,
            )

        try:
            # Build prompt with context
            prompt = self._build_prompt(message)

            # Call Gemini with retry
            response = None
            last_error: Optional[Exception] = None

            for attempt in range(self.retries + 1):
                try:
                    # Apply timeout
                    response = await asyncio.wait_for(
                        self.client.classify(prompt), timeout=self.timeout_ms / 1000.0
                    )
                    break
                except asyncio.TimeoutError as e:
                    last_error = e
                    logger.info(f"ORCH|retry|attempt={attempt + 1}|error=TimeoutError")
                    if attempt < self.retries:
                        await asyncio.sleep(0.05 * (2**attempt))
                    else:
                        logger.info("ORCH|retry_exhausted|strategy=fallback")
                except ConnectionError as e:
                    # Retry on connection errors
                    last_error = e
                    logger.info(
                        f"ORCH|retry|attempt={attempt + 1}|error=ConnectionError"
                    )
                    if attempt < self.retries:
                        await asyncio.sleep(0.05 * (2**attempt))
                    else:
                        logger.info("ORCH|retry_exhausted|strategy=fallback")
                except Exception as e:
                    # Non-transient errors - don't retry
                    last_error = e
                    logger.error(
                        f"ORCH|error|trace_id={trace_id}|turn_id={turn_id}|"
                        f"error={type(e).__name__}: {str(e)}"
                    )
                    break

            if response is None:
                # All attempts failed - return fallback
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    f"ORCH|complete|trace_id={trace_id}|turn_id={turn_id}|"
                    f"intent=fallback|confidence=0.00|"
                    f"latency_ms={latency_ms:.2f}"
                )
                return ClassificationResult(
                    intent="fallback",
                    confidence=0.0,
                    entities={},
                    routing_hint=None,
                    latency_ms=latency_ms,
                    error=str(last_error) if last_error else "Classification failed",
                )

            # Validate and normalize response
            try:
                # Handle malformed response
                if not isinstance(response, dict) or "intent" not in response:
                    raise ValueError("Malformed response")

                # Normalize confidence value
                raw_confidence = response.get("confidence", 0.0)
                try:
                    confidence = float(raw_confidence)
                except (ValueError, TypeError):
                    logger.info(
                        f"ORCH|confidence_normalized|from={raw_confidence}|to=0.0"
                    )
                    confidence = 0.0

                # Ensure confidence is in valid range
                confidence = max(0.0, min(1.0, confidence))

                # Ensure entities is always a dict
                entities = response.get("entities", {})
                if not isinstance(entities, dict):
                    entities = {}

                result = ClassificationResult(
                    intent=response.get("intent", "fallback"),
                    confidence=confidence,
                    entities=entities,
                    routing_hint=response.get("routing_hint"),
                )
            except (ValueError, TypeError, KeyError) as e:
                # Malformed response - return fallback
                logger.info(f"ORCH|malformed_response|error={str(e)}")
                result = ClassificationResult(
                    intent="fallback",
                    confidence=0.0,
                    entities={},
                    routing_hint=None,
                )

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            result.latency_ms = latency_ms

            # Log completion
            logger.info(
                f"ORCH|complete|trace_id={trace_id}|turn_id={turn_id}|"
                f"intent={result.intent}|confidence={result.confidence:.2f}|"
                f"latency_ms={latency_ms:.2f}"
            )

            return result

        except Exception as e:
            # Log error and return fallback
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"ORCH|error|trace_id={trace_id}|turn_id={turn_id}|"
                f"error={str(e)}|latency_ms={latency_ms:.2f}"
            )

            return ClassificationResult(
                intent="fallback",
                confidence=0.0,
                entities={},
                routing_hint=None,
                latency_ms=latency_ms,
                error=str(e),
            )

    def _build_prompt(self, message: PreprocessedMessage) -> str:
        """Build classification prompt from message."""
        prompt_parts = []

        # Add history if present
        if message.history:
            prompt_parts.append("Histórico:")
            for turn in message.history[-3:]:  # Last 3 turns
                prompt_parts.append(f"{turn.role}: {turn.text}")

        # Add current message
        prompt_parts.append(f"Mensagem atual: {message.text or ''}")

        # Add classification instruction
        prompt_parts.append(
            "\nClassifique em: greeting, information_request, "
            "qualification, scheduling ou fallback. "
            "Retorne JSON com intent, confidence e entities."
        )

        return "\n".join(prompt_parts)
