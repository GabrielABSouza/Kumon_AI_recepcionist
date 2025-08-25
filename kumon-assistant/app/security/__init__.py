"""
Advanced Security Module for Kumon Assistant

This package provides military-grade security protection against:
- DDoS attacks and repetitive message abuse
- Prompt injection attacks
- Information disclosure attempts  
- Out-of-scope requests and abuse
- Malicious user behavior

Based on 2024 industry benchmarks and OWASP Top 10 for LLMs.
"""

try:
    from .security_manager import SecurityManager, security_manager
    from .rate_limiter import RateLimiter, DDoSProtection
    from .prompt_injection_defense import PromptInjectionDefense
    from .scope_validator import ScopeValidator
    from .information_protection import InformationProtectionSystem
    from .threat_detector import ThreatDetectionSystem
    
    __all__ = [
        "SecurityManager",
        "security_manager", 
        "RateLimiter",
        "DDoSProtection",
        "PromptInjectionDefense",
        "ScopeValidator",
        "InformationProtectionSystem",
        "ThreatDetectionSystem"
    ]
except ImportError as e:
    print(f"Warning: Could not import security components: {e}")
    __all__ = []