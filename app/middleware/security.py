"""
Production Security Middleware
Phase 3 - Day 6: Security hardening for Railway deployment
Compliance: Rate limits 50 req/min, LGPD compliance, threat detection
"""
from fastapi import Request, Response, HTTPException, status
from fastapi.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any, Optional
import time
import hashlib
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
import redis
from app.core.config import settings
from app.core.logger import app_logger as logger


class SecurityMiddleware(BaseHTTPMiddleware):
    """Production security middleware with rate limiting, threat detection, and LGPD compliance"""
    
    def __init__(self, app, redis_client: Optional[redis.Redis] = None):
        super().__init__(app)
        self.redis_client = redis_client
        self.rate_limiters: Dict[str, deque] = defaultdict(lambda: deque())
        self.threat_scores: Dict[str, float] = defaultdict(float)
        self.blocked_ips: Dict[str, datetime] = {}
        
        # Security patterns for threat detection
        self.threat_patterns = [
            b'<script',
            b'javascript:',
            b'onload=',
            b'onerror=',
            b'eval(',
            b'Function(',
            b'setTimeout(',
            b'setInterval(',
            b'../../../',
            b'../../../../',
            b'SELECT * FROM',
            b'DROP TABLE',
            b'UNION SELECT',
            b'INSERT INTO',
            b'DELETE FROM',
            b'UPDATE SET',
            b"' OR '1'='1",
            b'" OR "1"="1',
            b'<?php',
            b'<%',
            b'{{',
            b'${',
            b'cmd=',
            b'system(',
            b'exec(',
            b'shell_exec(',
        ]
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Main security processing pipeline"""
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        
        try:
            # Step 1: Check if IP is blocked
            if self._is_ip_blocked(client_ip):
                logger.warning(f"Blocked IP attempted access: {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="IP temporarily blocked due to security violations"
                )
            
            # Step 2: Rate limiting check
            if not await self._check_rate_limit(client_ip, request):
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {settings.SECURITY_RATE_LIMIT_PER_MINUTE} requests per minute"
                )
            
            # Step 3: Request security scanning
            threat_score = await self._scan_request_threats(request)
            if threat_score >= settings.SECURITY_THREAT_THRESHOLD:
                await self._handle_security_threat(client_ip, threat_score, request)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Request blocked due to security policy violation"
                )
            
            # Step 4: LGPD compliance headers
            response = await call_next(request)
            self._add_security_headers(response)
            self._add_lgpd_headers(response)
            
            # Step 5: Log security metrics
            processing_time = time.time() - start_time
            await self._log_security_metrics(client_ip, request, response, processing_time, threat_score)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            # Continue processing on middleware errors to avoid blocking legitimate requests
            response = await call_next(request)
            self._add_security_headers(response)
            return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP considering Railway/proxy headers"""
        # Railway specific headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Fallback headers
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
            
        # Direct connection IP
        return getattr(request.client, "host", "unknown")
    
    def _is_ip_blocked(self, client_ip: str) -> bool:
        """Check if IP is temporarily blocked"""
        if client_ip in self.blocked_ips:
            block_time = self.blocked_ips[client_ip]
            if datetime.now() - block_time < timedelta(minutes=15):  # 15-minute block
                return True
            else:
                # Remove expired block
                del self.blocked_ips[client_ip]
        return False
    
    async def _check_rate_limit(self, client_ip: str, request: Request) -> bool:
        """Check rate limiting (50 requests per minute)"""
        if not settings.ENABLE_DDOS_PROTECTION:
            return True
        
        current_time = time.time()
        minute_ago = current_time - 60
        
        # Use Redis if available for distributed rate limiting
        if self.redis_client:
            try:
                key = f"rate_limit:{client_ip}"
                pipe = self.redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, minute_ago)
                pipe.zadd(key, {str(current_time): current_time})
                pipe.zcard(key)
                pipe.expire(key, 60)
                results = pipe.execute()
                
                request_count = results[2]
                return request_count <= settings.SECURITY_RATE_LIMIT_PER_MINUTE
                
            except Exception as e:
                logger.error(f"Redis rate limiting error: {e}")
                # Fallback to in-memory rate limiting
        
        # In-memory rate limiting fallback
        request_times = self.rate_limiters[client_ip]
        
        # Remove old requests
        while request_times and request_times[0] < minute_ago:
            request_times.popleft()
        
        # Add current request
        request_times.append(current_time)
        
        return len(request_times) <= settings.SECURITY_RATE_LIMIT_PER_MINUTE
    
    async def _scan_request_threats(self, request: Request) -> float:
        """Scan request for security threats and return threat score"""
        if not settings.ENABLE_ADVANCED_THREAT_DETECTION:
            return 0.0
        
        threat_score = 0.0
        
        try:
            # Get request body
            body = await request.body()
            
            # Check URL path
            path = str(request.url.path).lower()
            
            # Check query parameters
            query_string = str(request.url.query).lower() if request.url.query else ""
            
            # Check headers
            headers_str = json.dumps(dict(request.headers)).lower()
            
            # Combine all content for scanning
            content_to_scan = (path + query_string + headers_str + body.decode('utf-8', errors='ignore')).encode()
            
            # Pattern matching
            for pattern in self.threat_patterns:
                if pattern in content_to_scan:
                    threat_score += 0.2
                    logger.warning(f"Threat pattern detected: {pattern}")
            
            # SQL injection detection
            if any(sql_word in content_to_scan.lower() for sql_word in [b'union', b'select', b'insert', b'delete', b'drop']):
                threat_score += 0.3
            
            # XSS detection
            if any(xss_word in content_to_scan.lower() for xss_word in [b'<script', b'javascript:', b'onload=']):
                threat_score += 0.4
            
            # Path traversal detection
            if b'../' in content_to_scan or b'..\\' in content_to_scan:
                threat_score += 0.3
            
            # Excessive payload size
            if len(body) > settings.SECURITY_MAX_MESSAGE_LENGTH:
                threat_score += 0.2
            
            return min(threat_score, 1.0)  # Cap at 1.0
            
        except Exception as e:
            logger.error(f"Threat scanning error: {e}")
            return 0.0
    
    async def _handle_security_threat(self, client_ip: str, threat_score: float, request: Request):
        """Handle detected security threats"""
        self.threat_scores[client_ip] += threat_score
        
        # Auto-escalation for high threat scores
        if threat_score >= settings.SECURITY_AUTO_ESCALATION_THRESHOLD:
            self.blocked_ips[client_ip] = datetime.now()
            logger.error(f"IP {client_ip} blocked due to high threat score: {threat_score}")
        
        # Security incident logging
        incident_data = {
            "timestamp": datetime.now().isoformat(),
            "client_ip": client_ip,
            "threat_score": threat_score,
            "cumulative_score": self.threat_scores[client_ip],
            "url": str(request.url),
            "method": request.method,
            "user_agent": request.headers.get("user-agent", "unknown"),
            "action": "blocked" if threat_score >= settings.SECURITY_AUTO_ESCALATION_THRESHOLD else "logged"
        }
        
        logger.error(f"Security incident: {json.dumps(incident_data)}")
    
    def _add_security_headers(self, response: Response):
        """Add comprehensive security headers"""
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "X-Robots-Tag": "noindex, nofollow",
            "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
    
    def _add_lgpd_headers(self, response: Response):
        """Add LGPD compliance headers"""
        lgpd_headers = {
            "X-Data-Processing-Basis": "legitimate-interest",
            "X-Data-Retention-Policy": "7-days-conversation-history",
            "X-Privacy-Policy": f"{settings.BUSINESS_EMAIL}",
            "X-Data-Controller": settings.BUSINESS_NAME,
            "X-LGPD-Compliance": "enabled"
        }
        
        for header, value in lgpd_headers.items():
            response.headers[header] = value
    
    async def _log_security_metrics(
        self, 
        client_ip: str, 
        request: Request, 
        response: Response, 
        processing_time: float,
        threat_score: float
    ):
        """Log security metrics for monitoring"""
        if settings.SECURITY_LOGGING_ENABLED:
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "client_ip": client_ip,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "processing_time_ms": round(processing_time * 1000, 2),
                "threat_score": threat_score,
                "user_agent": request.headers.get("user-agent", "unknown")[:200],  # Truncate long user agents
                "rate_limited": response.status_code == 429,
                "blocked": response.status_code == 400 and threat_score >= settings.SECURITY_THREAT_THRESHOLD
            }
            
            logger.info(f"Security metrics: {json.dumps(metrics)}")


class CORSSecurityMiddleware(BaseHTTPMiddleware):
    """CORS middleware with security considerations for Railway deployment"""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response()
            self._add_cors_headers(response, request)
            return response
        
        response = await call_next(request)
        self._add_cors_headers(response, request)
        return response
    
    def _add_cors_headers(self, response: Response, request: Request):
        """Add secure CORS headers"""
        origin = request.headers.get("origin")
        
        # Allow specific origins only
        allowed_origins = [
            "https://api.evolution-api.com",
            "https://*.railway.app",
            "https://localhost:3000"  # Development only
        ]
        
        # In production, be more restrictive
        if settings.is_production():
            if origin and any(
                origin.endswith(domain.replace("*", "")) or origin == domain 
                for domain in ["https://api.evolution-api.com", "https://*.railway.app"]
            ):
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                response.headers["Access-Control-Allow-Origin"] = "null"
        else:
            # Development mode - more permissive
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
        
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours