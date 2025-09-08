"""
FASE 1 - Unit Tests for Message Preprocessor
Tests auth, sanitization, fromMe, and rate limiting
"""
import time

import pytest


class MessagePreprocessor:
    """Minimal preprocessor implementation for testing."""

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.rate_limit_window = 60  # seconds
        self.rate_limit_max = 10  # messages per window

    def process(self, message_data: dict, headers: dict) -> dict:
        """
        Process incoming message with validation and sanitization.
        Returns dict with: success, error_code, sanitized_text, should_ignore
        """
        result = {
            "success": True,
            "error_code": None,
            "sanitized_text": "",
            "should_ignore": False,
            "auth_valid": False,
            "rate_limited": False,
        }

        # 1. Auth validation
        if not self._validate_auth(headers):
            result["success"] = False
            result["error_code"] = "AUTH_FAILED"
            result["auth_valid"] = False
            return result
        result["auth_valid"] = True

        # 2. Check fromMe
        from_me = message_data.get("key", {}).get("fromMe", False)
        if from_me:
            result["should_ignore"] = True
            return result

        # 3. Extract and sanitize text
        text = self._extract_text(message_data)
        sanitized = self._sanitize_text(text)
        result["sanitized_text"] = sanitized

        # 4. Rate limiting
        phone = self._extract_phone(message_data)
        if phone and self.redis_client:
            if not self._check_rate_limit(phone):
                result["success"] = False
                result["error_code"] = "RATE_LIMITED"
                result["rate_limited"] = True
                return result

        return result

    def _validate_auth(self, headers: dict) -> bool:
        """Validate Evolution API headers."""
        # Check for valid Evolution/Railway headers
        required_indicators = [
            "x-evolution-instance",
            "x-railway-edge",
            "authorization",
        ]

        # At least one indicator must be present
        for indicator in required_indicators:
            if headers.get(indicator):
                return True

        # Also accept if it has evolution user-agent
        if "evolution" in headers.get("user-agent", "").lower():
            return True

        return False

    def _extract_text(self, message_data: dict) -> str:
        """Extract text from various message types."""
        message = message_data.get("message", {})

        # Try different message formats
        text = (
            message.get("conversation")
            or message.get("extendedTextMessage", {}).get("text")
            or message.get("imageMessage", {}).get("caption")
            or message.get("videoMessage", {}).get("caption")
            or ""
        )

        return text

    def _extract_phone(self, message_data: dict) -> str:
        """Extract phone number from message."""
        remote_jid = message_data.get("key", {}).get("remoteJid", "")
        if "@" in remote_jid:
            return remote_jid.split("@")[0]
        return remote_jid

    def _sanitize_text(self, text: str) -> str:
        """Sanitize and normalize text."""
        import re

        # Remove script tags and dangerous content
        text = re.sub(
            r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL
        )
        text = re.sub(r"<[^>]+>", "", text)  # Remove all HTML tags

        # Normalize whitespace
        text = " ".join(text.split())

        # Limit length to 1000 chars
        if len(text) > 1000:
            text = text[:1000]

        return text.strip()

    def _check_rate_limit(self, phone: str) -> bool:
        """Check if phone is within rate limit."""
        if not self.redis_client:
            return True

        key = f"rate_limit:{phone}"
        current = self.redis_client.incr(key)

        if current == 1:
            # First message in window, set expiry
            self.redis_client.expire(key, self.rate_limit_window)

        return current <= self.rate_limit_max


# Test fixtures
@pytest.fixture
def fake_redis():
    """Simple fake Redis for testing."""

    class FakeRedis:
        def __init__(self):
            self.data = {}
            self.expiry = {}

        def incr(self, key):
            self.data[key] = self.data.get(key, 0) + 1
            return self.data[key]

        def expire(self, key, seconds):
            self.expiry[key] = time.time() + seconds
            return True

        def get(self, key):
            # Check expiry
            if key in self.expiry and time.time() > self.expiry[key]:
                self.data.pop(key, None)
                self.expiry.pop(key, None)
                return None
            return self.data.get(key)

    return FakeRedis()


@pytest.fixture
def preprocessor():
    """Preprocessor without Redis."""
    return MessagePreprocessor()


@pytest.fixture
def preprocessor_with_redis(fake_redis):
    """Preprocessor with fake Redis."""
    return MessagePreprocessor(redis_client=fake_redis)


@pytest.fixture
def valid_headers():
    """Valid Evolution API headers."""
    return {
        "x-evolution-instance": "test-instance",
        "user-agent": "evolution-webhook/1.0",
        "content-type": "application/json",
    }


@pytest.fixture
def invalid_headers():
    """Invalid/missing headers."""
    return {"content-type": "application/json"}


@pytest.fixture
def sample_message():
    """Sample message data."""
    return {
        "key": {
            "id": "MSG123",
            "fromMe": False,
            "remoteJid": "5511999999999@s.whatsapp.net",
        },
        "message": {"conversation": "Hello, test message"},
    }


# TESTS - Auth validation
def test_auth_accepts_valid_headers(preprocessor, valid_headers, sample_message):
    """Test that valid Evolution headers pass authentication."""
    result = preprocessor.process(sample_message, valid_headers)

    assert result["success"] is True
    assert result["error_code"] is None
    assert result["auth_valid"] is True


def test_auth_rejects_missing_headers(preprocessor, invalid_headers, sample_message):
    """Test that missing/invalid headers fail authentication."""
    result = preprocessor.process(sample_message, invalid_headers)

    assert result["success"] is False
    assert result["error_code"] == "AUTH_FAILED"
    assert result["auth_valid"] is False


def test_auth_accepts_railway_headers(preprocessor, sample_message):
    """Test that Railway-specific headers pass authentication."""
    headers = {"x-railway-edge": "true", "content-type": "application/json"}

    result = preprocessor.process(sample_message, headers)

    assert result["success"] is True
    assert result["auth_valid"] is True


# TESTS - Sanitization
def test_sanitization_removes_scripts(preprocessor, valid_headers):
    """Test that script tags are removed from text."""
    message = {
        "key": {"fromMe": False, "remoteJid": "5511999999999@s.whatsapp.net"},
        "message": {"conversation": "<script>alert('xss')</script>Hello world"},
    }

    result = preprocessor.process(message, valid_headers)

    assert result["success"] is True
    assert "<script>" not in result["sanitized_text"]
    assert "alert" not in result["sanitized_text"]
    assert "Hello world" in result["sanitized_text"]


def test_sanitization_limits_length(preprocessor, valid_headers):
    """Test that text is truncated to 1000 characters."""
    long_text = "x" * 2000
    message = {
        "key": {"fromMe": False, "remoteJid": "5511999999999@s.whatsapp.net"},
        "message": {"conversation": long_text},
    }

    result = preprocessor.process(message, valid_headers)

    assert result["success"] is True
    assert len(result["sanitized_text"]) == 1000


def test_sanitization_normalizes_whitespace(preprocessor, valid_headers):
    """Test that multiple spaces are normalized."""
    message = {
        "key": {"fromMe": False, "remoteJid": "5511999999999@s.whatsapp.net"},
        "message": {"conversation": "Hello    \n\n  world   test"},
    }

    result = preprocessor.process(message, valid_headers)

    assert result["sanitized_text"] == "Hello world test"


# TESTS - fromMe handling
def test_from_me_messages_are_ignored(preprocessor, valid_headers):
    """Test that messages from bot itself are marked to ignore."""
    message = {
        "key": {
            "fromMe": True,  # Message from bot
            "remoteJid": "5511999999999@s.whatsapp.net",
        },
        "message": {"conversation": "Bot response"},
    }

    result = preprocessor.process(message, valid_headers)

    assert result["success"] is True
    assert result["should_ignore"] is True
    assert result["error_code"] is None


def test_from_me_false_processes_normally(preprocessor, valid_headers):
    """Test that user messages (fromMe=False) are processed."""
    message = {
        "key": {
            "fromMe": False,  # User message
            "remoteJid": "5511999999999@s.whatsapp.net",
        },
        "message": {"conversation": "User message"},
    }

    result = preprocessor.process(message, valid_headers)

    assert result["success"] is True
    assert result["should_ignore"] is False
    assert result["sanitized_text"] == "User message"


# TESTS - Rate limiting
def test_rate_limit_allows_under_threshold(preprocessor_with_redis, valid_headers):
    """Test that messages under rate limit (10/min) are allowed."""
    phone = "5511999999999@s.whatsapp.net"

    # Send 5 messages (under limit of 10)
    for i in range(5):
        message = {
            "key": {"fromMe": False, "remoteJid": phone},
            "message": {"conversation": f"Message {i}"},
        }
        result = preprocessor_with_redis.process(message, valid_headers)

        assert result["success"] is True
        assert result["error_code"] is None
        assert result["rate_limited"] is False


def test_rate_limit_blocks_over_threshold(preprocessor_with_redis, valid_headers):
    """Test that 11th message in 60s window is blocked."""
    phone = "5511888888888@s.whatsapp.net"

    # Send 10 messages (at limit)
    for i in range(10):
        message = {
            "key": {"fromMe": False, "remoteJid": phone},
            "message": {"conversation": f"Message {i}"},
        }
        result = preprocessor_with_redis.process(message, valid_headers)
        assert result["success"] is True

    # 11th message should be rate limited
    message = {
        "key": {"fromMe": False, "remoteJid": phone},
        "message": {"conversation": "Message 11"},
    }
    result = preprocessor_with_redis.process(message, valid_headers)

    assert result["success"] is False
    assert result["error_code"] == "RATE_LIMITED"
    assert result["rate_limited"] is True


def test_rate_limit_different_phones_independent(
    preprocessor_with_redis, valid_headers
):
    """Test that rate limits are per-phone."""
    phone1 = "5511111111111@s.whatsapp.net"
    phone2 = "5511222222222@s.whatsapp.net"

    # Send 10 messages from phone1
    for i in range(10):
        message = {
            "key": {"fromMe": False, "remoteJid": phone1},
            "message": {"conversation": f"Phone1 msg {i}"},
        }
        result = preprocessor_with_redis.process(message, valid_headers)
        assert result["success"] is True

    # Phone2 should still be able to send
    message = {
        "key": {"fromMe": False, "remoteJid": phone2},
        "message": {"conversation": "Phone2 message"},
    }
    result = preprocessor_with_redis.process(message, valid_headers)

    assert result["success"] is True
    assert result["error_code"] is None


# TESTS - Edge cases
def test_handles_image_message_with_caption(preprocessor, valid_headers):
    """Test extraction of caption from image messages."""
    message = {
        "key": {"fromMe": False, "remoteJid": "5511999999999@s.whatsapp.net"},
        "message": {"imageMessage": {"caption": "Check this image"}},
    }

    result = preprocessor.process(message, valid_headers)

    assert result["success"] is True
    assert result["sanitized_text"] == "Check this image"


def test_handles_empty_message(preprocessor, valid_headers):
    """Test handling of empty message text."""
    message = {
        "key": {"fromMe": False, "remoteJid": "5511999999999@s.whatsapp.net"},
        "message": {},
    }

    result = preprocessor.process(message, valid_headers)

    assert result["success"] is True
    assert result["sanitized_text"] == ""
