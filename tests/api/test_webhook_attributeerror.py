"""
Tests for webhook AttributeError scenarios.
Reproduces and fixes the 'list' object has no attribute 'get' error.
"""
from unittest.mock import patch

import pytest

from app.api.evolution import webhook


class TestWebhookAttributeError:
    """Test suite for webhook AttributeError scenarios."""

    def test_webhook_handles_list_in_data_field(self):
        """Test that webhook handles when data field is a list instead of dict."""
        # Simulate Evolution API sending data as a list instead of dict
        payload_with_list_data = {
            "instance": "kumon_assistant",
            "data": [],  # This should be a dict but Evolution sends empty list sometimes
        }

        with patch("app.api.evolution.langgraph_flow.run") as mock_run:
            with patch("app.api.evolution.turn_controller") as mock_turn:
                mock_turn.start_turn.return_value = True
                mock_run.return_value = {
                    "sent": "false",
                    "response": "",
                    "intent": "fallback",
                    "confidence": 0.0,
                    "entities": {},
                }

                import asyncio


                async def test_request():
                    # Create mock request
                    class MockRequest:
                        async def json(self):
                            return payload_with_list_data

                    request = MockRequest()

                    # This should NOT raise AttributeError
                    try:
                        result = await webhook(request)
                        # Should handle gracefully and return normalized response
                        assert result["status"] == "ignored"
                        assert (
                            result["reason"] == "invalid_data_type"
                        )  # Updated expected reason
                        assert result["sent"] == "false"
                        return True
                    except AttributeError as e:
                        if "'list' object has no attribute 'get'" in str(e):
                            # This is the bug we're testing for
                            pytest.fail(f"AttributeError not handled: {e}")
                        else:
                            raise
                    except Exception:
                        # Other exceptions are acceptable for now
                        pass

                # Run async test
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(test_request())
                    assert result is True, "Test should pass after bug fix"
                finally:
                    loop.close()

    def test_webhook_handles_list_in_key_field(self):
        """Test that webhook handles when key field is a list instead of dict."""
        payload_with_list_key = {
            "instance": "kumon_assistant",
            "data": {
                "key": [],  # This should be a dict but sometimes comes as empty list
                "message": {"conversation": "Olá"},
            },
        }

        with patch("app.api.evolution.langgraph_flow.run") as mock_run:
            with patch("app.api.evolution.turn_controller") as mock_turn:
                mock_turn.start_turn.return_value = True
                mock_run.return_value = {
                    "sent": "false",
                    "response": "",
                    "intent": "fallback",
                    "confidence": 0.0,
                    "entities": {},
                }

                import asyncio


                async def test_request():
                    # Create mock request
                    class MockRequest:
                        async def json(self):
                            return payload_with_list_key

                    request = MockRequest()

                    # This should NOT raise AttributeError
                    try:
                        result = await webhook(request)
                        # Should handle gracefully and continue processing
                        assert "sent" in result
                        return True
                    except AttributeError as e:
                        if "'list' object has no attribute 'get'" in str(e):
                            # This is the bug we're testing for
                            pytest.fail(f"AttributeError not handled: {e}")
                        else:
                            raise
                    except Exception:
                        # Other exceptions are acceptable for now
                        pass

                # Run async test
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(test_request())
                    assert result is True, "Test should pass after bug fix"
                finally:
                    loop.close()

    def test_webhook_handles_list_in_message_field(self):
        """Test that webhook handles when message field is a list instead of dict."""
        payload_with_list_message = {
            "instance": "kumon_assistant",
            "data": {
                "key": {
                    "id": "MSG123",
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                },
                "message": [],  # This should be a dict but sometimes comes as empty list
            },
        }

        with patch("app.api.evolution.langgraph_flow.run") as mock_run:
            with patch("app.api.evolution.turn_controller") as mock_turn:
                mock_turn.start_turn.return_value = True
                mock_run.return_value = {
                    "sent": "false",
                    "response": "",
                    "intent": "fallback",
                    "confidence": 0.0,
                    "entities": {},
                }

                import asyncio


                async def test_request():
                    # Create mock request
                    class MockRequest:
                        async def json(self):
                            return payload_with_list_message

                    request = MockRequest()

                    # This should NOT raise AttributeError
                    try:
                        result = await webhook(request)
                        # Should handle gracefully - no text extracted means ignored
                        assert result["reason"] == "no_text"
                        assert result["sent"] == "false"
                        return True
                    except AttributeError as e:
                        if "'list' object has no attribute 'get'" in str(e):
                            # This is the bug we're testing for
                            pytest.fail(f"AttributeError not handled: {e}")
                        else:
                            raise
                    except Exception:
                        # Other exceptions are acceptable for now
                        pass

                # Run async test
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(test_request())
                    assert result is True, "Test should pass after bug fix"
                finally:
                    loop.close()
