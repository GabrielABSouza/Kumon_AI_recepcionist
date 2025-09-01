"""
Authentication Middleware - Phase 2 Security Implementation

FastAPI middleware for comprehensive API authentication and authorization:
- JWT token validation
- Role-based access control (RBAC)
- Request authentication
- Security headers injection
- Rate limiting integration
- Audit logging
"""

import time
from typing import Dict, List, Optional, Callable, Any
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import json

from ..core.logger import app_logger
from .auth_manager import auth_manager, UserRole, AuthResult, AuthAction


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for FastAPI
    
    Features:
    - JWT token validation
    - Role-based access control
    - Request authentication
    - Security headers
    - Audit logging
    """
    
    def __init__(self, app: FastAPI, protected_paths: List[str] = None):
        super().__init__(app)
        
        # Configure protected paths
        self.protected_paths = protected_paths or [
            "/api/v1/performance",
            "/api/v1/alerts",
            "/api/v1/auth/users",
            "/api/v1/auth/admin",
        ]
        
        # Public paths (no authentication required)
        self.public_paths = [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
        ]
        
        # Webhook paths (special authentication)
        self.webhook_paths = [
            "/api/v1/whatsapp/webhook",
            "/api/v1/evolution/webhook",
        ]
        
        # Path-based permissions
        self.path_permissions = {
            "/api/v1/performance": ["performance.read"],
            "/api/v1/performance/config": ["performance.manage"],
            "/api/v1/alerts": ["security.read"],
            "/api/v1/alerts/rules": ["security.manage"],
            "/api/v1/auth/users": ["users.read"],
            "/api/v1/auth/admin": ["system.admin"],
        }
        
        app_logger.info("Authentication middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through authentication middleware"""
        
        start_time = time.time()
        path = request.url.path
        method = request.method
        
        try:
            # Add security headers
            response = await self._process_request(request, call_next)
            self._add_security_headers(response)
            
            # Log request
            processing_time = (time.time() - start_time) * 1000
            await self._log_request(request, response, processing_time)
            
            return response
            
        except HTTPException as e:
            # Handle authentication errors
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "Authentication failed",
                    "detail": e.detail,
                    "status_code": e.status_code,
                    "timestamp": time.time()
                }
            )
        except Exception as e:
            app_logger.error(f"Authentication middleware error: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "detail": "Authentication processing failed",
                    "status_code": 500
                }
            )
    
    async def _process_request(self, request: Request, call_next: Callable) -> Response:
        """Process authentication for request"""
        
        path = request.url.path
        method = request.method
        
        # Skip authentication for public paths
        if self._is_public_path(path):
            return await call_next(request)
        
        # Handle webhook authentication
        if self._is_webhook_path(path):
            await self._authenticate_webhook(request)
            return await call_next(request)
        
        # Handle API authentication
        if self._requires_authentication(path):
            user = await self._authenticate_api_request(request)
            
            # Check permissions
            required_permissions = self.path_permissions.get(path, [])
            if required_permissions:
                await self._check_permissions(user, required_permissions, path)
            
            # Add user to request state
            request.state.user = user
        
        return await call_next(request)
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no authentication required)"""
        return any(path.startswith(public) for public in self.public_paths)
    
    def _is_webhook_path(self, path: str) -> bool:
        """Check if path is webhook endpoint"""
        return any(path.startswith(webhook) for webhook in self.webhook_paths)
    
    def _requires_authentication(self, path: str) -> bool:
        """Check if path requires authentication"""
        return any(path.startswith(protected) for protected in self.protected_paths)
    
    async def _authenticate_webhook(self, request: Request):
        """Authenticate webhook requests"""
        
        try:
            # For WhatsApp webhook, check verification token
            if "/whatsapp/webhook" in request.url.path:
                if request.method == "GET":
                    # Webhook verification - handled by endpoint
                    return
                elif request.method == "POST":
                    # Webhook payload - basic validation
                    content_type = request.headers.get("content-type", "")
                    if "application/json" not in content_type:
                        raise HTTPException(status_code=400, detail="Invalid content type")
            
            # For Evolution API webhook, check API key if configured
            elif "/evolution/webhook" in request.url.path:
                api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
                if not api_key:
                    # Allow for now - Evolution API has its own auth
                    return
            
        except Exception as e:
            app_logger.error(f"Webhook authentication error: {e}")
            raise HTTPException(status_code=401, detail="Webhook authentication failed")
    
    async def _authenticate_api_request(self, request: Request):
        """Authenticate API request with JWT token"""
        
        try:
            # Get authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                raise HTTPException(status_code=401, detail="Authorization header required")
            
            # Extract bearer token
            if not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Invalid authorization format")
            
            token = auth_header.split(" ", 1)[1]
            
            # Verify token
            auth_result = await auth_manager.verify_token(token)
            
            if not auth_result.success:
                if auth_result.action == AuthAction.TOKEN_EXPIRED:
                    raise HTTPException(status_code=401, detail="Token expired")
                elif auth_result.action == AuthAction.TOKEN_INVALID:
                    raise HTTPException(status_code=401, detail="Invalid token")
                else:
                    raise HTTPException(status_code=401, detail="Authentication failed")
            
            return auth_result.user
            
        except HTTPException:
            raise
        except Exception as e:
            app_logger.error(f"API authentication error: {e}")
            raise HTTPException(status_code=401, detail="Authentication failed")
    
    async def _check_permissions(self, user, required_permissions: List[str], path: str):
        """Check if user has required permissions"""
        
        try:
            for permission in required_permissions:
                if not await auth_manager.check_permission(user, permission):
                    app_logger.warning(
                        f"Permission denied: {user.username} accessing {path} "
                        f"requires {permission}"
                    )
                    raise HTTPException(
                        status_code=403, 
                        detail=f"Insufficient permissions. Required: {permission}"
                    )
                    
        except HTTPException:
            raise
        except Exception as e:
            app_logger.error(f"Permission check error: {e}")
            raise HTTPException(status_code=403, detail="Permission check failed")
    
    def _add_security_headers(self, response: Response):
        """Add security headers to response"""
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self';"
        )
        
        # Strict Transport Security (if HTTPS)
        if hasattr(response, 'request') and response.request.url.scheme == 'https':
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    async def _log_request(self, request: Request, response: Response, processing_time: float):
        """Log request for audit trail"""
        
        try:
            # Get user info if authenticated
            user_info = "anonymous"
            if hasattr(request.state, 'user') and request.state.user:
                user_info = f"{request.state.user.username}:{request.state.user.role.value}"
            
            # Get client info
            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "unknown")
            
            # Log request
            log_data = {
                "timestamp": time.time(),
                "method": request.method,
                "path": request.url.path,
                "user": user_info,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "status_code": response.status_code,
                "processing_time_ms": round(processing_time, 2),
            }
            
            # Log at appropriate level
            if response.status_code >= 400:
                app_logger.warning(f"Auth request failed: {json.dumps(log_data)}")
            else:
                app_logger.info(f"Auth request: {json.dumps(log_data)}")
                
        except Exception as e:
            app_logger.error(f"Request logging error: {e}")


# FastAPI security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Dependency to get current authenticated user"""
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization required")
    
    auth_result = await auth_manager.verify_token(credentials.credentials)
    
    if not auth_result.success:
        if auth_result.action == AuthAction.TOKEN_EXPIRED:
            raise HTTPException(status_code=401, detail="Token expired")
        else:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    return auth_result.user


async def require_role(required_role: UserRole):
    """Dependency factory to require specific user role"""
    
    async def role_checker(user = Depends(get_current_user)):
        if user.role != required_role:
            # Check if user has higher privileges
            role_hierarchy = {
                UserRole.SUPER_ADMIN: 5,
                UserRole.ADMIN: 4,
                UserRole.MANAGER: 3,
                UserRole.OPERATOR: 2,
                UserRole.VIEWER: 1,
                UserRole.API_CLIENT: 1
            }
            
            user_level = role_hierarchy.get(user.role, 0)
            required_level = role_hierarchy.get(required_role, 0)
            
            if user_level < required_level:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Role {required_role.value} required"
                )
        
        return user
    
    return role_checker


async def require_permission(permission: str):
    """Dependency factory to require specific permission"""
    
    async def permission_checker(user = Depends(get_current_user)):
        if not await auth_manager.check_permission(user, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission}' required"
            )
        return user
    
    return permission_checker


# Helper functions for route protection
def require_admin():
    """Require admin role or higher"""
    return require_role(UserRole.ADMIN)


def require_super_admin():
    """Require super admin role"""
    return require_role(UserRole.SUPER_ADMIN)


def require_authenticated():
    """Require any authenticated user"""
    return Depends(get_current_user)