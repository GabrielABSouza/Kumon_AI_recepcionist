"""
Security Headers Configuration - Phase 3 Security Hardening

Advanced HTTP security headers with:
- Content Security Policy (CSP)
- HTTP Strict Transport Security (HSTS)
- X-Frame-Options protection
- X-Content-Type-Options
- Referrer Policy configuration
- Feature Policy controls
- Cross-Origin policies
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from ..core.logger import app_logger


class SecurityLevel(Enum):
    """Security header strictness levels"""
    BASIC = "basic"
    STRICT = "strict"
    PARANOID = "paranoid"


@dataclass
class CSPPolicy:
    """Content Security Policy configuration"""
    default_src: List[str] = field(default_factory=lambda: ["'self'"])
    script_src: List[str] = field(default_factory=lambda: ["'self'"])
    style_src: List[str] = field(default_factory=lambda: ["'self'", "'unsafe-inline'"])
    img_src: List[str] = field(default_factory=lambda: ["'self'", "data:", "https:"])
    font_src: List[str] = field(default_factory=lambda: ["'self'"])
    connect_src: List[str] = field(default_factory=lambda: ["'self'"])
    media_src: List[str] = field(default_factory=lambda: ["'self'"])
    object_src: List[str] = field(default_factory=lambda: ["'none'"])
    frame_src: List[str] = field(default_factory=lambda: ["'none'"])
    worker_src: List[str] = field(default_factory=lambda: ["'self'"])
    base_uri: List[str] = field(default_factory=lambda: ["'self'"])
    form_action: List[str] = field(default_factory=lambda: ["'self'"])
    frame_ancestors: List[str] = field(default_factory=lambda: ["'none'"])
    upgrade_insecure_requests: bool = True
    report_uri: Optional[str] = None


class SecurityHeaders:
    """
    HTTP Security Headers Configuration and Management
    
    Features:
    - Content Security Policy (CSP) configuration
    - HSTS (HTTP Strict Transport Security)
    - X-Frame-Options protection
    - CORS security configuration
    - Feature Policy controls
    - Security header validation
    """
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.STRICT):
        self.security_level = security_level
        
        # CSP configurations for different security levels
        self.csp_policies = {
            SecurityLevel.BASIC: CSPPolicy(
                script_src=["'self'", "'unsafe-inline'", "'unsafe-eval'"],
                style_src=["'self'", "'unsafe-inline'"],
                img_src=["'self'", "data:", "https:", "http:"],
                frame_src=["'self'"],
                upgrade_insecure_requests=False
            ),
            
            SecurityLevel.STRICT: CSPPolicy(
                script_src=["'self'", "'unsafe-inline'"],  # Limited unsafe-inline
                style_src=["'self'", "'unsafe-inline'"],
                img_src=["'self'", "data:", "https:"],
                connect_src=["'self'", "https:"],
                frame_src=["'none'"],
                upgrade_insecure_requests=True
            ),
            
            SecurityLevel.PARANOID: CSPPolicy(
                default_src=["'none'"],
                script_src=["'self'"],  # No unsafe-inline
                style_src=["'self'"],   # No unsafe-inline
                img_src=["'self'", "data:"],  # No external images
                connect_src=["'self'"],
                font_src=["'self'"],
                media_src=["'none'"],
                object_src=["'none'"],
                frame_src=["'none'"],
                worker_src=["'none'"],
                base_uri=["'none'"],
                form_action=["'self'"],
                frame_ancestors=["'none'"],
                upgrade_insecure_requests=True
            )
        }
        
        # HSTS configuration
        self.hsts_config = {
            SecurityLevel.BASIC: {
                "max_age": 31536000,  # 1 year
                "include_subdomains": False,
                "preload": False
            },
            SecurityLevel.STRICT: {
                "max_age": 31536000,  # 1 year
                "include_subdomains": True,
                "preload": False
            },
            SecurityLevel.PARANOID: {
                "max_age": 63072000,  # 2 years
                "include_subdomains": True,
                "preload": True
            }
        }
        
        # Feature Policy configuration
        self.feature_policies = {
            SecurityLevel.BASIC: {
                "camera": ["'none'"],
                "microphone": ["'none'"],
                "geolocation": ["'none'"],
                "payment": ["'none'"]
            },
            SecurityLevel.STRICT: {
                "camera": ["'none'"],
                "microphone": ["'none'"],
                "geolocation": ["'none'"],
                "payment": ["'none'"],
                "usb": ["'none'"],
                "midi": ["'none'"],
                "sync-xhr": ["'none'"]
            },
            SecurityLevel.PARANOID: {
                "camera": ["'none'"],
                "microphone": ["'none'"],
                "geolocation": ["'none'"],
                "payment": ["'none'"],
                "usb": ["'none'"],
                "midi": ["'none'"],
                "sync-xhr": ["'none'"],
                "fullscreen": ["'none'"],
                "encrypted-media": ["'none'"],
                "picture-in-picture": ["'none'"]
            }
        }
        
        app_logger.info(f"Security Headers initialized with level: {security_level.value}")
    
    def get_security_headers(
        self,
        request_path: str = "/",
        is_api: bool = False,
        custom_csp: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, str]:
        """Generate security headers for response"""
        
        headers = {}
        
        try:
            # Content Security Policy
            csp = self._build_csp(custom_csp, is_api)
            if csp:
                headers["Content-Security-Policy"] = csp
            
            # HTTP Strict Transport Security
            hsts = self._build_hsts()
            if hsts:
                headers["Strict-Transport-Security"] = hsts
            
            # X-Frame-Options
            headers["X-Frame-Options"] = "DENY"
            
            # X-Content-Type-Options
            headers["X-Content-Type-Options"] = "nosniff"
            
            # X-XSS-Protection (deprecated but still useful for older browsers)
            headers["X-XSS-Protection"] = "1; mode=block"
            
            # Referrer Policy
            headers["Referrer-Policy"] = self._get_referrer_policy()
            
            # Feature Policy / Permissions Policy
            feature_policy = self._build_feature_policy()
            if feature_policy:
                headers["Permissions-Policy"] = feature_policy
            
            # Additional API-specific headers
            if is_api:
                headers.update(self._get_api_headers())
            
            # Cache control for sensitive content
            if self._is_sensitive_path(request_path):
                headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                headers["Pragma"] = "no-cache"
                headers["Expires"] = "0"
            
            return headers
            
        except Exception as e:
            app_logger.error(f"Error generating security headers: {e}")
            return self._get_fallback_headers()
    
    def _build_csp(self, custom_csp: Optional[Dict[str, List[str]]], is_api: bool) -> str:
        """Build Content Security Policy header"""
        
        try:
            policy = self.csp_policies[self.security_level]
            
            # API endpoints have different CSP requirements
            if is_api:
                policy = CSPPolicy(
                    default_src=["'none'"],
                    script_src=["'none'"],
                    style_src=["'none'"],
                    img_src=["'none'"],
                    connect_src=["'self'"],
                    object_src=["'none'"],
                    frame_src=["'none'"]
                )
            
            # Apply custom CSP if provided
            if custom_csp:
                for directive, values in custom_csp.items():
                    if hasattr(policy, directive):
                        setattr(policy, directive, values)
            
            # Build CSP string
            csp_parts = []
            
            # Add each directive
            directives = [
                ("default-src", policy.default_src),
                ("script-src", policy.script_src),
                ("style-src", policy.style_src),
                ("img-src", policy.img_src),
                ("font-src", policy.font_src),
                ("connect-src", policy.connect_src),
                ("media-src", policy.media_src),
                ("object-src", policy.object_src),
                ("frame-src", policy.frame_src),
                ("worker-src", policy.worker_src),
                ("base-uri", policy.base_uri),
                ("form-action", policy.form_action),
                ("frame-ancestors", policy.frame_ancestors)
            ]
            
            for directive, values in directives:
                if values:
                    csp_parts.append(f"{directive} {' '.join(values)}")
            
            # Add upgrade-insecure-requests if enabled
            if policy.upgrade_insecure_requests:
                csp_parts.append("upgrade-insecure-requests")
            
            # Add report-uri if configured
            if policy.report_uri:
                csp_parts.append(f"report-uri {policy.report_uri}")
            
            return "; ".join(csp_parts)
            
        except Exception as e:
            app_logger.error(f"CSP build error: {e}")
            return "default-src 'self'; object-src 'none'"
    
    def _build_hsts(self) -> str:
        """Build HTTP Strict Transport Security header"""
        
        try:
            config = self.hsts_config[self.security_level]
            
            hsts_parts = [f"max-age={config['max_age']}"]
            
            if config["include_subdomains"]:
                hsts_parts.append("includeSubDomains")
            
            if config["preload"]:
                hsts_parts.append("preload")
            
            return "; ".join(hsts_parts)
            
        except Exception as e:
            app_logger.error(f"HSTS build error: {e}")
            return "max-age=31536000; includeSubDomains"
    
    def _build_feature_policy(self) -> str:
        """Build Feature Policy / Permissions Policy header"""
        
        try:
            policies = self.feature_policies[self.security_level]
            
            policy_parts = []
            for feature, allowlist in policies.items():
                allowlist_str = "(" + " ".join(allowlist) + ")"
                policy_parts.append(f"{feature}={allowlist_str}")
            
            return ", ".join(policy_parts)
            
        except Exception as e:
            app_logger.error(f"Feature Policy build error: {e}")
            return "camera=(), microphone=(), geolocation=()"
    
    def _get_referrer_policy(self) -> str:
        """Get appropriate Referrer Policy"""
        
        referrer_policies = {
            SecurityLevel.BASIC: "strict-origin-when-cross-origin",
            SecurityLevel.STRICT: "strict-origin",
            SecurityLevel.PARANOID: "no-referrer"
        }
        
        return referrer_policies.get(self.security_level, "strict-origin")
    
    def _get_api_headers(self) -> Dict[str, str]:
        """Get additional headers for API endpoints"""
        
        return {
            "X-Robots-Tag": "noindex, nofollow, nosnippet, noarchive",
            "Cross-Origin-Resource-Policy": "cross-origin",
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin"
        }
    
    def _is_sensitive_path(self, path: str) -> bool:
        """Check if path contains sensitive content"""
        
        sensitive_patterns = [
            "/api/v1/auth/",
            "/api/v1/users/",
            "/admin/",
            "/dashboard/",
            "/profile/",
            "/settings/"
        ]
        
        return any(pattern in path for pattern in sensitive_patterns)
    
    def _get_fallback_headers(self) -> Dict[str, str]:
        """Fallback security headers in case of errors"""
        
        return {
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; object-src 'none'"
        }
    
    def get_cors_headers(
        self,
        origin: Optional[str] = None,
        allowed_origins: List[str] = None,
        allowed_methods: List[str] = None,
        allowed_headers: List[str] = None,
        expose_headers: List[str] = None,
        max_age: int = 86400
    ) -> Dict[str, str]:
        """Generate CORS headers with security considerations"""
        
        headers = {}
        
        try:
            # Default allowed origins (be restrictive)
            if allowed_origins is None:
                allowed_origins = ["http://localhost:3000", "https://kumon.local"]
            
            # Validate origin
            if origin and origin in allowed_origins:
                headers["Access-Control-Allow-Origin"] = origin
                headers["Vary"] = "Origin"
            elif "*" in allowed_origins:
                headers["Access-Control-Allow-Origin"] = "*"
            else:
                # Don't set CORS headers for unauthorized origins
                return {}
            
            # Allowed methods
            if allowed_methods:
                headers["Access-Control-Allow-Methods"] = ", ".join(allowed_methods)
            else:
                headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            
            # Allowed headers
            if allowed_headers:
                headers["Access-Control-Allow-Headers"] = ", ".join(allowed_headers)
            else:
                headers["Access-Control-Allow-Headers"] = "Accept, Authorization, Content-Type, X-Requested-With"
            
            # Exposed headers
            if expose_headers:
                headers["Access-Control-Expose-Headers"] = ", ".join(expose_headers)
            
            # Preflight cache
            headers["Access-Control-Max-Age"] = str(max_age)
            
            # Credentials (be careful with this)
            if self.security_level != SecurityLevel.PARANOID:
                headers["Access-Control-Allow-Credentials"] = "true"
            
            return headers
            
        except Exception as e:
            app_logger.error(f"CORS headers error: {e}")
            return {}
    
    def validate_request_headers(self, request_headers: Dict[str, str]) -> Dict[str, Any]:
        """Validate incoming request headers for security issues"""
        
        issues = []
        warnings = []
        risk_score = 0.0
        
        try:
            # Check for suspicious User-Agent
            user_agent = request_headers.get("user-agent", "").lower()
            suspicious_agents = ["sqlmap", "nikto", "nessus", "openvas", "nmap"]
            
            if any(agent in user_agent for agent in suspicious_agents):
                issues.append("Suspicious user agent detected")
                risk_score += 0.8
            
            # Check for injection in headers
            for header_name, header_value in request_headers.items():
                if header_value:
                    # Basic injection detection
                    suspicious_chars = ["<script", "javascript:", "vbscript:", "onload=", "eval("]
                    if any(char in header_value.lower() for char in suspicious_chars):
                        issues.append(f"Suspicious content in {header_name} header")
                        risk_score += 0.6
            
            # Check for missing security headers in request
            if not request_headers.get("x-requested-with"):
                warnings.append("Missing X-Requested-With header (potential CSRF)")
            
            # Check for overly long headers (potential buffer overflow)
            for header_name, header_value in request_headers.items():
                if len(header_value) > 8192:  # 8KB limit
                    issues.append(f"Overly long {header_name} header")
                    risk_score += 0.4
            
            return {
                "is_safe": len(issues) == 0 and risk_score < 0.5,
                "issues": issues,
                "warnings": warnings,
                "risk_score": min(risk_score, 1.0)
            }
            
        except Exception as e:
            app_logger.error(f"Header validation error: {e}")
            return {
                "is_safe": False,
                "issues": ["Header validation failed"],
                "warnings": [],
                "risk_score": 1.0
            }
    
    def get_security_report(self) -> Dict[str, Any]:
        """Generate security headers configuration report"""
        
        return {
            "security_level": self.security_level.value,
            "csp_configured": True,
            "hsts_enabled": True,
            "frame_protection": True,
            "content_type_protection": True,
            "xss_protection": True,
            "feature_policy_enabled": True,
            "cors_configured": True,
            "api_security_headers": True,
            "cache_control_sensitive": True,
            "header_validation": True,
            "configuration": {
                "hsts_max_age": self.hsts_config[self.security_level]["max_age"],
                "hsts_include_subdomains": self.hsts_config[self.security_level]["include_subdomains"],
                "csp_directives": len([attr for attr in dir(self.csp_policies[self.security_level]) if not attr.startswith('_')]),
                "feature_policies": len(self.feature_policies[self.security_level])
            },
            "last_updated": datetime.now().isoformat()
        }


# Global security headers instance
security_headers = SecurityHeaders(SecurityLevel.STRICT)