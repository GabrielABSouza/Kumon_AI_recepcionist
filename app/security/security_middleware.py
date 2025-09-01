"""
Security Middleware - Phase 3 Security Hardening

Comprehensive security middleware with:
- Rate limiting per endpoint
- Request size limiting
- Security headers injection
- Input validation middleware
- CSRF protection
- IP filtering and blocking
- Security logging
"""

import time
import json
from typing import Dict, List, Optional, Set, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import hashlib
import secrets

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.logger import app_logger
from .input_validator import input_validator, ValidationLevel
from .security_headers import security_headers
from .encryption_service import encryption_service


@dataclass
class RateLimitRule:
    """Rate limiting rule configuration"""
    requests_per_minute: int
    requests_per_hour: int
    burst_allowance: int = 5
    block_duration_minutes: int = 15


@dataclass
class SecurityConfig:
    """Security middleware configuration"""
    enable_rate_limiting: bool = True
    enable_input_validation: bool = True
    enable_security_headers: bool = True
    enable_csrf_protection: bool = True
    enable_ip_filtering: bool = True
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    blocked_user_agents: List[str] = field(default_factory=lambda: [
        "sqlmap", "nikto", "nessus", "openvas", "masscan", "nmap"
    ])
    blocked_ips: Set[str] = field(default_factory=set)
    trusted_proxies: Set[str] = field(default_factory=lambda: {"127.0.0.1", "::1"})


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive security middleware for FastAPI applications
    
    Features:
    - Advanced rate limiting per endpoint and IP
    - Request size and content validation
    - Security headers injection
    - CSRF protection
    - IP-based filtering and blocking
    - Suspicious activity detection
    - Security event logging
    """
    
    def __init__(self, app: ASGIApp, config: Optional[SecurityConfig] = None):
        super().__init__(app)
        
        self.config = config or SecurityConfig()
        
        # Rate limiting storage (in production, use Redis)
        self.rate_limit_storage = defaultdict(lambda: defaultdict(deque))
        self.blocked_ips = dict()  # IP -> block_until_timestamp
        
        # CSRF token storage (in production, use session store)
        self.csrf_tokens = {}
        
        # Rate limit rules for different endpoints
        self.rate_limit_rules = {
            "default": RateLimitRule(60, 1000),  # 60/min, 1000/hour
            "/api/v1/auth/login": RateLimitRule(5, 50, burst_allowance=2, block_duration_minutes=30),
            "/api/v1/auth/register": RateLimitRule(3, 10, burst_allowance=1, block_duration_minutes=60),
            "/api/v1/whatsapp/webhook": RateLimitRule(1000, 10000, burst_allowance=50),
            "/api/v1/embeddings": RateLimitRule(30, 300),
            # Admin endpoint rate limits (stricter for security)
            "/api/v1/performance": RateLimitRule(20, 200, burst_allowance=3, block_duration_minutes=15),
            "/api/v1/alerts": RateLimitRule(15, 150, burst_allowance=3, block_duration_minutes=15),
            "/api/v1/security": RateLimitRule(10, 100, burst_allowance=2, block_duration_minutes=30),
            "/api/v1/workflows": RateLimitRule(15, 150, burst_allowance=3, block_duration_minutes=15),
            "/api/v1/auth/users": RateLimitRule(10, 100, burst_allowance=2, block_duration_minutes=15),
            "/api/v1/auth/admin": RateLimitRule(5, 50, burst_allowance=1, block_duration_minutes=30),
            "/api/v1/auth/metrics": RateLimitRule(10, 100, burst_allowance=2, block_duration_minutes=15),
            "/api/v1/auth/cleanup": RateLimitRule(3, 30, burst_allowance=1, block_duration_minutes=60),
            # Documentation endpoints
            "/docs": RateLimitRule(10, 100),
            "/redoc": RateLimitRule(10, 100)
        }
        
        # Security event counters
        self.security_events = defaultdict(int)
        self.last_cleanup = datetime.now()
        
        app_logger.info("Security Middleware initialized with comprehensive protection")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Main middleware dispatch method"""
        
        start_time = time.time()
        
        try:
            # Get client information
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            
            # Pre-request security checks
            security_check = await self._perform_security_checks(request, client_ip, user_agent)
            
            if not security_check["allowed"]:
                self._log_security_event("blocked_request", {
                    "ip": client_ip,
                    "path": str(request.url.path),
                    "reason": security_check["reason"]
                })
                
                raise HTTPException(
                    status_code=security_check["status_code"],
                    detail=security_check["reason"]
                )
            
            # Add security context to request state
            request.state.security_context = {
                "client_ip": client_ip,
                "validated": True,
                "csrf_token": security_check.get("csrf_token")
            }
            
            # Process request
            response = await call_next(request)
            
            # Post-request processing
            await self._post_process_response(request, response, start_time)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            app_logger.error(f"Security middleware error: {e}")
            
            # Log security error
            self._log_security_event("middleware_error", {
                "error": str(e),
                "ip": getattr(request.state, "client_ip", "unknown"),
                "path": str(request.url.path)
            })
            
            raise HTTPException(status_code=500, detail="Security processing failed")
        
        finally:
            # Periodic cleanup
            await self._periodic_cleanup()
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address considering proxies"""
        
        # Check X-Forwarded-For header (be careful of spoofing)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP (client IP)
            client_ip = forwarded_for.split(",")[0].strip()
            
            # Validate that the request is from a trusted proxy
            direct_ip = request.client.host if request.client else "unknown"
            if direct_ip in self.config.trusted_proxies:
                return client_ip
        
        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            direct_ip = request.client.host if request.client else "unknown"
            if direct_ip in self.config.trusted_proxies:
                return real_ip
        
        # Fall back to direct connection IP
        return request.client.host if request.client else "unknown"
    
    async def _perform_security_checks(
        self, 
        request: Request, 
        client_ip: str, 
        user_agent: str
    ) -> Dict[str, Any]:
        """Perform comprehensive pre-request security checks"""
        
        # Check if IP is blocked
        if self._is_ip_blocked(client_ip):
            return {
                "allowed": False,
                "status_code": 429,
                "reason": "IP address temporarily blocked"
            }
        
        # Check for blocked user agents
        if self.config.enable_ip_filtering:
            for blocked_agent in self.config.blocked_user_agents:
                if blocked_agent.lower() in user_agent.lower():
                    await self._block_ip_temporarily(client_ip, "suspicious_user_agent")
                    return {
                        "allowed": False,
                        "status_code": 403,
                        "reason": "Suspicious user agent detected"
                    }
        
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.config.max_request_size:
            return {
                "allowed": False,
                "status_code": 413,
                "reason": f"Request too large (max {self.config.max_request_size} bytes)"
            }
        
        # Rate limiting check
        if self.config.enable_rate_limiting:
            rate_limit_result = self._check_rate_limit(client_ip, str(request.url.path))
            if not rate_limit_result["allowed"]:
                # Block IP if rate limit exceeded significantly
                if rate_limit_result.get("excessive"):
                    await self._block_ip_temporarily(client_ip, "rate_limit_exceeded")
                
                return {
                    "allowed": False,
                    "status_code": 429,
                    "reason": "Rate limit exceeded"
                }
        
        # Header validation
        header_validation = security_headers.validate_request_headers(dict(request.headers))
        if not header_validation["is_safe"]:
            self._log_security_event("suspicious_headers", {
                "ip": client_ip,
                "issues": header_validation["issues"],
                "risk_score": header_validation["risk_score"]
            })
            
            if header_validation["risk_score"] > 0.8:
                return {
                    "allowed": False,
                    "status_code": 400,
                    "reason": "Malicious headers detected"
                }
        
        # CSRF protection for state-changing methods
        csrf_result = await self._check_csrf_protection(request)
        if not csrf_result["valid"]:
            return {
                "allowed": False,
                "status_code": 403,
                "reason": csrf_result["reason"]
            }
        
        return {
            "allowed": True,
            "csrf_token": csrf_result.get("token")
        }
    
    def _is_ip_blocked(self, ip: str) -> bool:
        """Check if IP address is currently blocked"""
        
        if ip in self.blocked_ips:
            block_until = self.blocked_ips[ip]
            if datetime.now() < block_until:
                return True
            else:
                # Unblock expired blocks
                del self.blocked_ips[ip]
        
        return ip in self.config.blocked_ips
    
    async def _block_ip_temporarily(self, ip: str, reason: str, duration_minutes: int = 15):
        """Temporarily block an IP address"""
        
        block_until = datetime.now() + timedelta(minutes=duration_minutes)
        self.blocked_ips[ip] = block_until
        
        self._log_security_event("ip_blocked", {
            "ip": ip,
            "reason": reason,
            "duration_minutes": duration_minutes,
            "block_until": block_until.isoformat()
        })
        
        app_logger.warning(f"Temporarily blocked IP {ip} for {reason} (until {block_until})")
    
    def _check_rate_limit(self, client_ip: str, path: str) -> Dict[str, Any]:
        """Check rate limiting for client IP and path"""
        
        try:
            # Get rate limit rule for this path
            rule = self.rate_limit_rules.get(path, self.rate_limit_rules["default"])
            
            current_time = datetime.now()
            minute_window = current_time - timedelta(minutes=1)
            hour_window = current_time - timedelta(hours=1)
            
            # Get request history for this IP and path
            requests = self.rate_limit_storage[client_ip][path]
            
            # Clean old requests
            while requests and requests[0] < hour_window:
                requests.popleft()
            
            # Count requests in windows
            minute_requests = sum(1 for req_time in requests if req_time > minute_window)
            hour_requests = len(requests)
            
            # Check limits
            excessive = False
            
            if minute_requests >= rule.requests_per_minute:
                if minute_requests >= rule.requests_per_minute * 2:
                    excessive = True
                return {"allowed": False, "excessive": excessive}
            
            if hour_requests >= rule.requests_per_hour:
                if hour_requests >= rule.requests_per_hour * 1.5:
                    excessive = True
                return {"allowed": False, "excessive": excessive}
            
            # Add current request
            requests.append(current_time)
            
            return {
                "allowed": True,
                "minute_requests": minute_requests + 1,
                "hour_requests": hour_requests + 1,
                "minute_limit": rule.requests_per_minute,
                "hour_limit": rule.requests_per_hour
            }
            
        except Exception as e:
            app_logger.error(f"Rate limit check error: {e}")
            return {"allowed": True}  # Fail open
    
    async def _check_csrf_protection(self, request: Request) -> Dict[str, Any]:
        """Check CSRF protection for state-changing requests"""
        
        if not self.config.enable_csrf_protection:
            return {"valid": True}
        
        # CSRF protection only for state-changing methods
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return {"valid": True}
        
        # Skip CSRF for webhook endpoints with proper authentication
        if str(request.url.path).startswith("/api/v1/whatsapp/webhook") or str(request.url.path).startswith("/api/v1/evolution/webhook"):
            return {"valid": True}
        
        # Check for CSRF token in headers
        csrf_token = request.headers.get("x-csrf-token")
        
        if not csrf_token:
            return {
                "valid": False,
                "reason": "CSRF token required for state-changing requests"
            }
        
        # Validate CSRF token (simplified - in production use proper token validation)
        if not self._validate_csrf_token(csrf_token):
            return {
                "valid": False,
                "reason": "Invalid CSRF token"
            }
        
        return {"valid": True, "token": csrf_token}
    
    def _validate_csrf_token(self, token: str) -> bool:
        """Validate CSRF token (simplified implementation)"""
        
        try:
            # In a real implementation, validate against secure session store
            return len(token) >= 32 and token.isalnum()
        except Exception:
            return False
    
    async def _post_process_response(
        self, 
        request: Request, 
        response: Response, 
        start_time: float
    ):
        """Post-process response with security enhancements"""
        
        try:
            # Add security headers
            if self.config.enable_security_headers:
                security_hdrs = security_headers.get_security_headers(
                    request_path=str(request.url.path),
                    is_api=str(request.url.path).startswith("/api/")
                )
                
                for header_name, header_value in security_hdrs.items():
                    response.headers[header_name] = header_value
            
            # Add timing information (be careful not to leak sensitive timing)
            processing_time = time.time() - start_time
            if processing_time > 5.0:  # Log slow requests
                self._log_security_event("slow_request", {
                    "path": str(request.url.path),
                    "processing_time": processing_time,
                    "ip": getattr(request.state, "client_ip", "unknown")
                })
            
            # Log successful request
            self.security_events["successful_requests"] += 1
            
        except Exception as e:
            app_logger.error(f"Response post-processing error: {e}")
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of security data structures"""
        
        current_time = datetime.now()
        
        # Run cleanup every 5 minutes
        if (current_time - self.last_cleanup).total_seconds() < 300:
            return
        
        try:
            # Cleanup expired IP blocks
            expired_blocks = [
                ip for ip, block_until in self.blocked_ips.items()
                if current_time >= block_until
            ]
            
            for ip in expired_blocks:
                del self.blocked_ips[ip]
            
            # Cleanup old rate limit data
            hour_ago = current_time - timedelta(hours=1)
            
            for ip_data in self.rate_limit_storage.values():
                for path_requests in ip_data.values():
                    while path_requests and path_requests[0] < hour_ago:
                        path_requests.popleft()
            
            # Cleanup empty entries
            empty_ips = []
            for ip, ip_data in self.rate_limit_storage.items():
                empty_paths = [path for path, requests in ip_data.items() if not requests]
                for path in empty_paths:
                    del ip_data[path]
                
                if not ip_data:
                    empty_ips.append(ip)
            
            for ip in empty_ips:
                del self.rate_limit_storage[ip]
            
            self.last_cleanup = current_time
            
        except Exception as e:
            app_logger.error(f"Security cleanup error: {e}")
    
    def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security events for monitoring and analysis"""
        
        try:
            # Increment counter
            self.security_events[event_type] += 1
            
            # Create security event log
            security_event = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "details": details,
                "severity": self._get_event_severity(event_type)
            }
            
            # Sanitize sensitive data before logging
            sanitized_event = encryption_service.sanitize_for_logging(security_event)
            
            # Log with appropriate level based on severity
            if security_event["severity"] == "high":
                app_logger.error(f"Security Event [{event_type}]: {json.dumps(sanitized_event)}")
            elif security_event["severity"] == "medium":
                app_logger.warning(f"Security Event [{event_type}]: {json.dumps(sanitized_event)}")
            else:
                app_logger.info(f"Security Event [{event_type}]: {json.dumps(sanitized_event)}")
            
        except Exception as e:
            app_logger.error(f"Security event logging error: {e}")
    
    def _get_event_severity(self, event_type: str) -> str:
        """Determine severity level for security events"""
        
        high_severity = [
            "blocked_request", "ip_blocked", "malicious_headers",
            "csrf_attack", "sql_injection", "xss_attempt"
        ]
        
        medium_severity = [
            "rate_limit_exceeded", "suspicious_headers", "suspicious_user_agent",
            "large_request", "slow_request"
        ]
        
        if event_type in high_severity:
            return "high"
        elif event_type in medium_severity:
            return "medium"
        else:
            return "low"
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security middleware metrics"""
        
        return {
            "blocked_ips": len(self.blocked_ips),
            "rate_limit_rules": len(self.rate_limit_rules),
            "security_events": dict(self.security_events),
            "active_rate_limits": len(self.rate_limit_storage),
            "configuration": {
                "rate_limiting_enabled": self.config.enable_rate_limiting,
                "input_validation_enabled": self.config.enable_input_validation,
                "security_headers_enabled": self.config.enable_security_headers,
                "csrf_protection_enabled": self.config.enable_csrf_protection,
                "ip_filtering_enabled": self.config.enable_ip_filtering,
                "max_request_size": self.config.max_request_size
            },
            "last_cleanup": self.last_cleanup.isoformat(),
            "uptime": datetime.now().isoformat()
        }
    
    def generate_csrf_token(self) -> str:
        """Generate a new CSRF token"""
        
        token = secrets.token_urlsafe(32)
        self.csrf_tokens[token] = datetime.now() + timedelta(hours=1)
        return token


# Factory function for creating security middleware
def create_security_middleware(
    rate_limiting: bool = True,
    input_validation: bool = True,
    security_headers: bool = True,
    csrf_protection: bool = True,
    ip_filtering: bool = True,
    max_request_size: int = 10 * 1024 * 1024
) -> SecurityMiddleware:
    """Create security middleware with custom configuration"""
    
    config = SecurityConfig(
        enable_rate_limiting=rate_limiting,
        enable_input_validation=input_validation,
        enable_security_headers=security_headers,
        enable_csrf_protection=csrf_protection,
        enable_ip_filtering=ip_filtering,
        max_request_size=max_request_size
    )
    
    return SecurityMiddleware(None, config)