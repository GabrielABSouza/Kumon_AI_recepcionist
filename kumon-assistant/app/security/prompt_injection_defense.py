"""
Prompt Injection Defense System for Kumon Assistant

Implements OWASP Top 10 for LLMs security protections:
- Input sanitization and validation
- Prompt injection detection using ML techniques
- Context isolation and sandboxing
- Real-time threat pattern recognition
- Defensive prompt engineering
"""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..core.config import settings
from ..core.logger import app_logger


class InjectionType(Enum):
    """Types of prompt injection attacks"""

    DIRECT_INJECTION = "direct_injection"  # Direct system prompt override
    INDIRECT_INJECTION = "indirect_injection"  # Via external data
    JAILBREAKING = "jailbreaking"  # Attempt to bypass restrictions
    ROLE_PLAYING = "role_playing"  # Impersonation attacks
    INSTRUCTION_FOLLOWING = "instruction_following"  # Malicious instructions
    CONTEXT_SWITCHING = "context_switching"  # Context manipulation
    SYSTEM_DISCLOSURE = "system_disclosure"  # Attempt to reveal system info


@dataclass
class InjectionPattern:
    """Pattern for detecting prompt injections"""

    name: str
    pattern: str
    injection_type: InjectionType
    severity: float  # 0.0 to 1.0
    description: str
    confidence_threshold: float = 0.8


@dataclass
class InjectionResult:
    """Result of prompt injection analysis"""

    is_injection: bool
    injection_type: Optional[InjectionType]
    confidence: float
    severity: float
    matched_patterns: List[str]
    sanitized_input: str
    threat_indicators: Dict[str, Any]
    risk_assessment: str


class PromptInjectionDefense:
    """
    Advanced prompt injection detection and prevention system

    Based on OWASP Top 10 for LLMs and 2024 security research:
    - Multi-layer detection (pattern matching + ML + behavioral)
    - Real-time sanitization
    - Adaptive threat learning
    - Zero-day injection detection
    """

    def __init__(self):
        # Known injection patterns (constantly updated)
        self.injection_patterns = self._load_injection_patterns()

        # Behavioral tracking for adaptive detection
        self.user_behavior: Dict[str, List[Dict]] = {}
        self.injection_attempts: Dict[str, List[datetime]] = {}

        # Sanitization rules
        self.sanitization_rules = self._load_sanitization_rules()

        # ML-based detection (simplified - would use trained model)
        self.ml_features = [
            "unusual_keywords",
            "instruction_patterns",
            "role_switches",
            "system_references",
            "escape_sequences",
            "prompt_delimiters",
        ]

        # Context isolation settings
        self.isolation_config = {
            "max_context_length": 4000,
            "safe_context_markers": ["user:", "assistant:", "system:"],
            "dangerous_markers": ["ignore", "forget", "new instructions", "system:"],
            "escape_sequences": ["\\n", "\\t", "\\r", "```", "---"],
        }

        app_logger.info("Prompt Injection Defense initialized with OWASP LLM protections")

    async def detect_injection(
        self, user_input: str, request_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive prompt injection detection

        Args:
            user_input: The user's message content
            request_metadata: Additional request context

        Returns:
            Detection result with threat assessment
        """

        # Multi-layer detection approach
        results = await asyncio.gather(
            self._pattern_based_detection(user_input),
            self._behavioral_detection(user_input, request_metadata),
            self._ml_based_detection(user_input),
            self._context_analysis(user_input, request_metadata),
            return_exceptions=True,
        )

        # Combine results from all detection layers
        pattern_result, behavioral_result, ml_result, context_result = results

        # Calculate overall confidence and severity
        confidence_scores = []
        severity_scores = []
        matched_patterns = []
        threat_indicators = {}

        if isinstance(pattern_result, dict):
            confidence_scores.append(pattern_result["confidence"])
            severity_scores.append(pattern_result["severity"])
            matched_patterns.extend(pattern_result["matched_patterns"])
            threat_indicators.update(pattern_result.get("indicators", {}))

        if isinstance(behavioral_result, dict):
            confidence_scores.append(behavioral_result["confidence"])
            severity_scores.append(behavioral_result["severity"])
            threat_indicators.update(behavioral_result.get("indicators", {}))

        if isinstance(ml_result, dict):
            confidence_scores.append(ml_result["confidence"])
            severity_scores.append(ml_result["severity"])
            threat_indicators.update(ml_result.get("indicators", {}))

        if isinstance(context_result, dict):
            confidence_scores.append(context_result["confidence"])
            severity_scores.append(context_result["severity"])
            threat_indicators.update(context_result.get("indicators", {}))

        # Calculate weighted average
        overall_confidence = (
            sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        )
        overall_severity = max(severity_scores) if severity_scores else 0.0  # Take highest severity

        # Determine if this is an injection attempt
        is_injection = overall_confidence >= 0.7 or overall_severity >= 0.8

        # Sanitize input regardless of detection result
        sanitized_input = await self.sanitize_input(user_input)

        # Track injection attempts
        if is_injection and request_metadata:
            source_id = request_metadata.get("source_identifier", "unknown")
            self.injection_attempts.setdefault(source_id, []).append(datetime.now())

        return {
            "is_injection": is_injection,
            "confidence": overall_confidence,
            "severity": overall_severity,
            "matched_patterns": matched_patterns,
            "sanitized_input": sanitized_input,
            "threat_indicators": threat_indicators,
            "detection_layers": {
                "pattern_based": bool(
                    isinstance(pattern_result, dict) and pattern_result["confidence"] > 0.5
                ),
                "behavioral": bool(
                    isinstance(behavioral_result, dict) and behavioral_result["confidence"] > 0.5
                ),
                "ml_based": bool(isinstance(ml_result, dict) and ml_result["confidence"] > 0.5),
                "context": bool(
                    isinstance(context_result, dict) and context_result["confidence"] > 0.5
                ),
            },
        }

    async def _pattern_based_detection(self, user_input: str) -> Dict[str, Any]:
        """Pattern-based injection detection using known attack signatures"""
        matched_patterns = []
        max_confidence = 0.0
        max_severity = 0.0
        indicators = {}

        input_lower = user_input.lower()

        for pattern in self.injection_patterns:
            if re.search(pattern.pattern, input_lower, re.IGNORECASE | re.MULTILINE):
                matched_patterns.append(pattern.name)
                max_confidence = max(max_confidence, pattern.confidence_threshold)
                max_severity = max(max_severity, pattern.severity)

                indicators[pattern.name] = {
                    "type": pattern.injection_type.value,
                    "severity": pattern.severity,
                    "description": pattern.description,
                }

        return {
            "confidence": max_confidence,
            "severity": max_severity,
            "matched_patterns": matched_patterns,
            "indicators": indicators,
        }

    async def _behavioral_detection(
        self, user_input: str, metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Behavioral analysis for injection detection"""

        confidence = 0.0
        severity = 0.0
        indicators = {}

        if not metadata:
            return {"confidence": confidence, "severity": severity, "indicators": indicators}

        source_id = metadata.get("source_identifier", "unknown")

        # Track user behavior patterns
        behavior_entry = {
            "timestamp": datetime.now(),
            "message_length": len(user_input),
            "contains_code": bool(re.search(r"```|<code>|<script>", user_input, re.IGNORECASE)),
            "contains_instructions": bool(
                re.search(r"ignore|forget|new task|system", user_input, re.IGNORECASE)
            ),
            "unusual_formatting": bool(re.search(r"\\n|\\t|\\r|---|\*\*\*", user_input)),
            "suspicious_keywords": len(
                re.findall(
                    r"prompt|instruction|system|admin|root|bypass", user_input, re.IGNORECASE
                )
            ),
        }

        self.user_behavior.setdefault(source_id, []).append(behavior_entry)

        # Keep only recent behavior (last 50 messages)
        if len(self.user_behavior[source_id]) > 50:
            self.user_behavior[source_id] = self.user_behavior[source_id][-50:]

        # Analyze behavior patterns
        recent_behavior = self.user_behavior[source_id][-10:]  # Last 10 messages

        if len(recent_behavior) >= 3:
            # Sudden increase in suspicious keywords
            recent_keywords = sum(b["suspicious_keywords"] for b in recent_behavior)
            if recent_keywords > 5:
                confidence += 0.3
                severity += 0.4
                indicators["suspicious_keyword_spike"] = recent_keywords

            # Unusual formatting patterns
            formatting_count = sum(b["unusual_formatting"] for b in recent_behavior)
            if formatting_count > len(recent_behavior) * 0.5:
                confidence += 0.2
                severity += 0.3
                indicators["unusual_formatting_pattern"] = formatting_count

            # Code injection attempts
            code_attempts = sum(b["contains_code"] for b in recent_behavior)
            if code_attempts > 2:
                confidence += 0.4
                severity += 0.5
                indicators["code_injection_attempts"] = code_attempts

            # Instruction override attempts
            instruction_attempts = sum(b["contains_instructions"] for b in recent_behavior)
            if instruction_attempts > 3:
                confidence += 0.5
                severity += 0.6
                indicators["instruction_override_attempts"] = instruction_attempts

        return {
            "confidence": min(1.0, confidence),
            "severity": min(1.0, severity),
            "indicators": indicators,
        }

    async def _ml_based_detection(self, user_input: str) -> Dict[str, Any]:
        """ML-based detection (simplified implementation)"""

        # Extract features for ML analysis
        features = self._extract_ml_features(user_input)

        # Simplified ML scoring (would use trained model in production)
        confidence = 0.0
        severity = 0.0
        indicators = {}

        # Feature-based scoring
        if features["unusual_keywords"] > 3:
            confidence += 0.3
            severity += 0.4
            indicators["high_unusual_keywords"] = features["unusual_keywords"]

        if features["instruction_patterns"] > 2:
            confidence += 0.4
            severity += 0.5
            indicators["instruction_patterns"] = features["instruction_patterns"]

        if features["role_switches"] > 1:
            confidence += 0.3
            severity += 0.4
            indicators["role_switches"] = features["role_switches"]

        if features["system_references"] > 0:
            confidence += 0.5
            severity += 0.7
            indicators["system_references"] = features["system_references"]

        if features["escape_sequences"] > 2:
            confidence += 0.2
            severity += 0.3
            indicators["escape_sequences"] = features["escape_sequences"]

        if features["prompt_delimiters"] > 1:
            confidence += 0.4
            severity += 0.5
            indicators["prompt_delimiters"] = features["prompt_delimiters"]

        return {
            "confidence": min(1.0, confidence),
            "severity": min(1.0, severity),
            "indicators": indicators,
            "features": features,
        }

    def _extract_ml_features(self, user_input: str) -> Dict[str, int]:
        """Extract features for ML-based detection"""
        input_lower = user_input.lower()

        return {
            "unusual_keywords": len(
                re.findall(
                    r"ignore|forget|bypass|override|jailbreak|prompt|instruction|system",
                    input_lower,
                )
            ),
            "instruction_patterns": len(
                re.findall(
                    r"(?:now|from now on|instead|actually|really|truly)\s+(?:you|your|do|are|will)",
                    input_lower,
                )
            ),
            "role_switches": len(
                re.findall(
                    r"(?:you are|act as|pretend|imagine|roleplay|play the role)", input_lower
                )
            ),
            "system_references": len(
                re.findall(r"system|admin|root|developer|programmer|creator|anthropic", input_lower)
            ),
            "escape_sequences": len(re.findall(r"\\n|\\t|\\r|```|---|===|\*\*\*", user_input)),
            "prompt_delimiters": len(
                re.findall(r'###|"""|\[INST\]|\[/INST\]|<\|.*\|>', user_input)
            ),
        }

    async def _context_analysis(
        self, user_input: str, metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Context-aware injection detection"""

        confidence = 0.0
        severity = 0.0
        indicators = {}

        # Check for context manipulation attempts
        if re.search(r"forget (?:previous|earlier|all|everything)", user_input, re.IGNORECASE):
            confidence += 0.6
            severity += 0.7
            indicators["context_reset_attempt"] = True

        if re.search(r"new (?:conversation|session|task|instruction)", user_input, re.IGNORECASE):
            confidence += 0.5
            severity += 0.6
            indicators["session_reset_attempt"] = True

        # Check for information extraction attempts
        if re.search(
            r"what (?:are|is) your (?:instruction|prompt|system|rule)", user_input, re.IGNORECASE
        ):
            confidence += 0.7
            severity += 0.8
            indicators["information_extraction"] = True

        # Check for boundary testing
        if re.search(r"can you|are you (?:able|allowed) to", user_input, re.IGNORECASE):
            boundary_tests = len(
                re.findall(r"can you|are you (?:able|allowed) to", user_input, re.IGNORECASE)
            )
            if boundary_tests > 1:
                confidence += 0.3
                severity += 0.4
                indicators["boundary_testing"] = boundary_tests

        return {
            "confidence": min(1.0, confidence),
            "severity": min(1.0, severity),
            "indicators": indicators,
        }

    async def sanitize_input(self, user_input: str) -> str:
        """Sanitize user input to remove potential injection vectors"""

        sanitized = user_input

        # Apply sanitization rules
        for rule in self.sanitization_rules:
            sanitized = re.sub(rule["pattern"], rule["replacement"], sanitized, flags=re.IGNORECASE)

        # Remove or neutralize dangerous sequences
        sanitized = self._neutralize_escape_sequences(sanitized)
        sanitized = self._remove_system_references(sanitized)
        sanitized = self._limit_length(sanitized)

        return sanitized

    def _neutralize_escape_sequences(self, text: str) -> str:
        """Neutralize escape sequences and formatting"""

        # Replace escape sequences with safe equivalents
        replacements = {
            "\\n": " ",
            "\\t": " ",
            "\\r": " ",
            "```": "(code block)",
            "---": "(separator)",
            "===": "(separator)",
            "***": "(emphasis)",
            "###": "(heading)",
        }

        result = text
        for dangerous, safe in replacements.items():
            result = result.replace(dangerous, safe)

        return result

    def _remove_system_references(self, text: str) -> str:
        """Remove or neutralize system-level references"""

        # Replace system references with neutral terms
        system_patterns = [
            (r"\bsystem\b", "assistant", re.IGNORECASE),
            (r"\badmin\b", "helper", re.IGNORECASE),
            (r"\broot\b", "main", re.IGNORECASE),
            (r"\bprompt\b", "message", re.IGNORECASE),
            (r"\binstruction\b", "information", re.IGNORECASE),
        ]

        result = text
        for pattern, replacement, flags in system_patterns:
            result = re.sub(pattern, replacement, result, flags=flags)

        return result

    def _limit_length(self, text: str) -> str:
        """Limit input length to prevent overflows"""
        max_length = self.isolation_config["max_context_length"]

        if len(text) > max_length:
            return text[:max_length] + "...(truncated)"

        return text

    def _load_injection_patterns(self) -> List[InjectionPattern]:
        """Load known injection attack patterns"""

        patterns = [
            # Direct injection attempts
            InjectionPattern(
                name="direct_system_override",
                pattern=r"(?:ignore|forget|disregard).*(?:previous|earlier|above).*(?:instruction|prompt|system)",
                injection_type=InjectionType.DIRECT_INJECTION,
                severity=0.9,
                description="Attempt to override system instructions",
            ),
            # Jailbreaking attempts
            InjectionPattern(
                name="jailbreak_roleplay",
                pattern=r"(?:pretend|act as|you are now|from now on).*(?:not|no longer|different|evil|harmful)",
                injection_type=InjectionType.JAILBREAKING,
                severity=0.8,
                description="Jailbreak attempt via roleplay",
            ),
            # Context switching
            InjectionPattern(
                name="context_switch",
                pattern=r"(?:new conversation|fresh start|restart|begin again|clear context)",
                injection_type=InjectionType.CONTEXT_SWITCHING,
                severity=0.7,
                description="Attempt to reset conversation context",
            ),
            # System disclosure
            InjectionPattern(
                name="system_disclosure",
                pattern=r"(?:what are|show me|tell me).*(?:your|the).*(?:instruction|prompt|system|rules|guidelines)",
                injection_type=InjectionType.SYSTEM_DISCLOSURE,
                severity=0.8,
                description="Attempt to extract system information",
            ),
            # Instruction following attacks
            InjectionPattern(
                name="malicious_instructions",
                pattern=r"(?:always|never|must|should).*(?:say|respond|answer|tell).*(?:exactly|only|just)",
                injection_type=InjectionType.INSTRUCTION_FOLLOWING,
                severity=0.7,
                description="Attempt to inject malicious instructions",
            ),
            # Developer/system references
            InjectionPattern(
                name="developer_reference",
                pattern=r"(?:developer|programmer|creator|anthropic|openai|claude).*(?:told|said|wants|programmed)",
                injection_type=InjectionType.ROLE_PLAYING,
                severity=0.6,
                description="False claims about developer instructions",
            ),
            # Prompt delimiter attacks
            InjectionPattern(
                name="prompt_delimiters",
                pattern=r"(?:\\[INST\\]|\\[/INST\\]|<\\|.*\\|>|###|\"\"\")",
                injection_type=InjectionType.DIRECT_INJECTION,
                severity=0.8,
                description="Use of prompt delimiter sequences",
            ),
        ]

        return patterns

    def _load_sanitization_rules(self) -> List[Dict[str, str]]:
        """Load input sanitization rules"""

        rules = [
            {
                "name": "remove_prompt_delimiters",
                "pattern": r"(\[INST\]|\[/INST\]|<\|.*\|>|###|\"\"\")",
                "replacement": "",
            },
            {
                "name": "neutralize_system_commands",
                "pattern": r"(ignore|forget|disregard)\s+(previous|earlier|above|all)",
                "replacement": "consider the previous",
            },
            {"name": "remove_escape_sequences", "pattern": r"(\\n|\\t|\\r)", "replacement": " "},
            {
                "name": "neutralize_role_switches",
                "pattern": r"(you are now|from now on|act as|pretend to be)",
                "replacement": "imagine if you were",
            },
        ]

        return rules

    def get_injection_stats(self, source_identifier: Optional[str] = None) -> Dict[str, Any]:
        """Get injection attempt statistics"""

        if source_identifier:
            attempts = self.injection_attempts.get(source_identifier, [])
            recent_attempts = [
                attempt for attempt in attempts if attempt > datetime.now() - timedelta(hours=24)
            ]

            return {
                "source": source_identifier,
                "total_attempts": len(attempts),
                "recent_attempts": len(recent_attempts),
                "first_attempt": attempts[0] if attempts else None,
                "last_attempt": attempts[-1] if attempts else None,
            }
        else:
            total_attempts = sum(len(attempts) for attempts in self.injection_attempts.values())
            total_sources = len(self.injection_attempts)

            return {
                "total_attempts": total_attempts,
                "affected_sources": total_sources,
                "patterns_loaded": len(self.injection_patterns),
                "sanitization_rules": len(self.sanitization_rules),
                "detection_layers": len(self.ml_features),
            }
