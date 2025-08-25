"""
Enterprise Authentication Manager - Phase 2 Security Implementation

Comprehensive authentication system with:
- JWT token management with refresh tokens
- Multi-factor authentication (MFA)
- Role-based access control (RBAC)
- Session management with security
- Password policies and validation
- Account lockout and security policies
- OAuth2 compliance and integration
"""

import asyncio
import time
import hashlib
import secrets
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import jwt
import bcrypt
import pyotp
import qrcode
from io import BytesIO
import base64

from ..core.logger import app_logger
from ..core.config import settings


class UserRole(Enum):
    """User role definitions"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"
    VIEWER = "viewer"
    API_CLIENT = "api_client"


class AuthAction(Enum):
    """Authentication action results"""
    AUTHENTICATED = "authenticated"
    FAILED_LOGIN = "failed_login"
    ACCOUNT_LOCKED = "account_locked"
    MFA_REQUIRED = "mfa_required"
    PASSWORD_EXPIRED = "password_expired"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"


@dataclass
class User:
    """User account model"""
    user_id: str
    username: str
    email: str
    password_hash: str
    role: UserRole
    is_active: bool = True
    is_verified: bool = False
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    account_locked_until: Optional[datetime] = None
    password_changed_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthSession:
    """Active authentication session"""
    session_id: str
    user_id: str
    access_token: str
    refresh_token: str
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True


@dataclass
class Permission:
    """Permission definition"""
    name: str
    description: str
    resource: str
    action: str


@dataclass
class AuthResult:
    """Authentication operation result"""
    success: bool
    action: AuthAction
    user: Optional[User] = None
    session: Optional[AuthSession] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    mfa_qr_code: Optional[str] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuthenticationManager:
    """
    Enterprise-grade authentication manager
    
    Features:
    - JWT access and refresh tokens
    - Multi-factor authentication (TOTP)
    - Role-based access control (RBAC)
    - Account security policies
    - Session management
    - Password policies
    - OAuth2 compliance
    """
    
    def __init__(self):
        # In-memory storage for development (should use database in production)
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, AuthSession] = {}
        self.refresh_tokens: Dict[str, str] = {}  # token -> user_id
        
        # JWT configuration
        self.jwt_secret = self._get_or_generate_jwt_secret()
        self.jwt_algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 30
        
        # Security policies
        self.security_config = {
            "max_failed_attempts": 5,
            "lockout_duration_minutes": 30,
            "password_min_length": 8,
            "password_require_special": True,
            "password_require_numbers": True,
            "password_expire_days": 90,
            "session_timeout_minutes": 60,
            "require_mfa_for_admins": True,
            "max_concurrent_sessions": 3,
        }
        
        # Role-based permissions
        self.permissions = self._initialize_permissions()
        self.role_permissions = self._initialize_role_permissions()
        
        # Initialize default admin user (deferred until first usage)
        self._admin_initialized = False
        
        app_logger.info("Authentication Manager initialized with enterprise security")
    
    def _get_or_generate_jwt_secret(self) -> str:
        """Get or generate JWT secret key"""
        # In production, this should be stored securely (environment variable or secret manager)
        secret = getattr(settings, 'JWT_SECRET_KEY', None)
        if not secret:
            secret = secrets.token_urlsafe(32)
            app_logger.warning("Generated new JWT secret. Store this securely in production!")
        return secret
    
    def _initialize_permissions(self) -> Dict[str, Permission]:
        """Initialize system permissions"""
        permissions = {
            # User management
            "users.create": Permission("users.create", "Create users", "users", "create"),
            "users.read": Permission("users.read", "Read user information", "users", "read"),
            "users.update": Permission("users.update", "Update users", "users", "update"),
            "users.delete": Permission("users.delete", "Delete users", "users", "delete"),
            
            # WhatsApp management
            "whatsapp.webhook": Permission("whatsapp.webhook", "Access WhatsApp webhooks", "whatsapp", "webhook"),
            "whatsapp.send": Permission("whatsapp.send", "Send WhatsApp messages", "whatsapp", "send"),
            "whatsapp.read": Permission("whatsapp.read", "Read WhatsApp messages", "whatsapp", "read"),
            
            # Performance monitoring
            "performance.read": Permission("performance.read", "Read performance metrics", "performance", "read"),
            "performance.manage": Permission("performance.manage", "Manage performance settings", "performance", "manage"),
            
            # Security management
            "security.read": Permission("security.read", "Read security metrics", "security", "read"),
            "security.manage": Permission("security.manage", "Manage security settings", "security", "manage"),
            
            # System administration
            "system.admin": Permission("system.admin", "Full system administration", "system", "admin"),
            "system.config": Permission("system.config", "System configuration", "system", "config"),
        }
        return permissions
    
    def _initialize_role_permissions(self) -> Dict[UserRole, List[str]]:
        """Initialize role-based permissions"""
        return {
            UserRole.SUPER_ADMIN: [
                "users.create", "users.read", "users.update", "users.delete",
                "whatsapp.webhook", "whatsapp.send", "whatsapp.read",
                "performance.read", "performance.manage",
                "security.read", "security.manage",
                "system.admin", "system.config"
            ],
            UserRole.ADMIN: [
                "users.read", "users.update",
                "whatsapp.webhook", "whatsapp.send", "whatsapp.read",
                "performance.read", "performance.manage",
                "security.read"
            ],
            UserRole.MANAGER: [
                "users.read",
                "whatsapp.read", "whatsapp.send",
                "performance.read"
            ],
            UserRole.OPERATOR: [
                "whatsapp.read", "whatsapp.send",
                "performance.read"
            ],
            UserRole.VIEWER: [
                "whatsapp.read",
                "performance.read"
            ],
            UserRole.API_CLIENT: [
                "whatsapp.webhook", "whatsapp.read"
            ]
        }
    
    async def _ensure_admin_initialized(self):
        """Ensure default admin user exists (call this before authentication operations)"""
        if not self._admin_initialized:
            await self._create_default_admin()
            self._admin_initialized = True
    
    async def _create_default_admin(self):
        """Create default admin user if none exists"""
        if not any(user.role == UserRole.SUPER_ADMIN for user in self.users.values()):
            admin_password = "KumonAdmin2025!"  # Should be changed immediately
            
            admin_user = await self.create_user(
                username="admin",
                email="admin@kumon.local",
                password=admin_password,
                role=UserRole.SUPER_ADMIN
            )
            
            if admin_user.success:
                app_logger.warning(
                    "Created default admin user. "
                    "Username: admin, Password: KumonAdmin2025! "
                    "Change this password immediately!"
                )
    
    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.VIEWER,
        require_mfa: bool = None
    ) -> AuthResult:
        """Create a new user account"""
        
        try:
            # Validate input
            if len(username) < 3:
                return AuthResult(False, AuthAction.FAILED_LOGIN, message="Username too short")
            
            if len(password) < self.security_config["password_min_length"]:
                return AuthResult(False, AuthAction.FAILED_LOGIN, message="Password too short")
            
            if not self._validate_password_policy(password):
                return AuthResult(False, AuthAction.FAILED_LOGIN, 
                    message="Password doesn't meet security requirements")
            
            # Check if user exists
            existing_user = next((u for u in self.users.values() 
                                if u.username == username or u.email == email), None)
            
            if existing_user:
                return AuthResult(False, AuthAction.FAILED_LOGIN, message="User already exists")
            
            # Create user
            user_id = secrets.token_urlsafe(16)
            password_hash = self._hash_password(password)
            
            # Determine MFA requirement
            if require_mfa is None:
                require_mfa = (role in [UserRole.SUPER_ADMIN, UserRole.ADMIN] and
                              self.security_config["require_mfa_for_admins"])
            
            user = User(
                user_id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                role=role,
                mfa_enabled=require_mfa,
                mfa_secret=pyotp.random_base32() if require_mfa else None
            )
            
            self.users[user_id] = user
            
            result = AuthResult(True, AuthAction.AUTHENTICATED, user=user, 
                              message="User created successfully")
            
            # Generate MFA QR code if required
            if require_mfa and user.mfa_secret:
                result.mfa_qr_code = self._generate_mfa_qr_code(user)
            
            app_logger.info(f"Created user: {username} with role: {role.value}")
            return result
            
        except Exception as e:
            app_logger.error(f"User creation error: {e}")
            return AuthResult(False, AuthAction.FAILED_LOGIN, 
                            message=f"User creation failed: {str(e)}")
    
    async def authenticate_user(
        self,
        username: str,
        password: str,
        mfa_code: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuthResult:
        """Authenticate user with credentials and optional MFA"""
        
        try:
            # Ensure admin user exists
            await self._ensure_admin_initialized()
            # Find user
            user = next((u for u in self.users.values() 
                        if u.username == username or u.email == username), None)
            
            if not user:
                app_logger.warning(f"Login attempt for non-existent user: {username}")
                return AuthResult(False, AuthAction.FAILED_LOGIN, message="Invalid credentials")
            
            # Check account status
            if not user.is_active:
                return AuthResult(False, AuthAction.ACCOUNT_LOCKED, message="Account deactivated")
            
            # Check if account is locked
            if user.account_locked_until and datetime.now() < user.account_locked_until:
                return AuthResult(False, AuthAction.ACCOUNT_LOCKED, 
                    message=f"Account locked until {user.account_locked_until}")
            
            # Verify password
            if not self._verify_password(password, user.password_hash):
                await self._handle_failed_login(user)
                return AuthResult(False, AuthAction.FAILED_LOGIN, message="Invalid credentials")
            
            # Check if MFA is required
            if user.mfa_enabled:
                if not mfa_code:
                    return AuthResult(False, AuthAction.MFA_REQUIRED, user=user, 
                        message="MFA code required")
                
                if not self._verify_mfa_code(user.mfa_secret, mfa_code):
                    await self._handle_failed_login(user)
                    return AuthResult(False, AuthAction.FAILED_LOGIN, message="Invalid MFA code")
            
            # Check password expiration
            if self._is_password_expired(user):
                return AuthResult(False, AuthAction.PASSWORD_EXPIRED, user=user,
                    message="Password expired")
            
            # Successful authentication
            await self._handle_successful_login(user)
            
            # Create session
            session_result = await self._create_user_session(user, ip_address, user_agent)
            
            app_logger.info(f"User authenticated successfully: {username}")
            return session_result
            
        except Exception as e:
            app_logger.error(f"Authentication error: {e}")
            return AuthResult(False, AuthAction.FAILED_LOGIN, 
                            message="Authentication failed")
    
    async def refresh_token(self, refresh_token: str) -> AuthResult:
        """Refresh access token using refresh token"""
        
        try:
            # Validate refresh token
            if refresh_token not in self.refresh_tokens:
                return AuthResult(False, AuthAction.TOKEN_INVALID, 
                    message="Invalid refresh token")
            
            user_id = self.refresh_tokens[refresh_token]
            user = self.users.get(user_id)
            
            if not user or not user.is_active:
                # Clean up invalid token
                if refresh_token in self.refresh_tokens:
                    del self.refresh_tokens[refresh_token]
                return AuthResult(False, AuthAction.TOKEN_INVALID, 
                    message="Invalid refresh token")
            
            # Generate new access token
            access_token = self._generate_access_token(user)
            
            # Update session activity
            session = next((s for s in self.sessions.values() 
                          if s.user_id == user_id and s.is_active), None)
            
            if session:
                session.last_activity = datetime.now()
                session.access_token = access_token
            
            app_logger.info(f"Token refreshed for user: {user.username}")
            return AuthResult(True, AuthAction.AUTHENTICATED, user=user,
                            access_token=access_token, refresh_token=refresh_token)
            
        except Exception as e:
            app_logger.error(f"Token refresh error: {e}")
            return AuthResult(False, AuthAction.TOKEN_INVALID, 
                            message="Token refresh failed")
    
    async def verify_token(self, token: str) -> AuthResult:
        """Verify and decode access token"""
        
        try:
            # Ensure admin user exists
            await self._ensure_admin_initialized()
            # Decode JWT token
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            user_id = payload.get("user_id")
            
            if not user_id:
                return AuthResult(False, AuthAction.TOKEN_INVALID, 
                    message="Invalid token payload")
            
            user = self.users.get(user_id)
            if not user or not user.is_active:
                return AuthResult(False, AuthAction.TOKEN_INVALID, 
                    message="Invalid user")
            
            # Check session
            session = next((s for s in self.sessions.values() 
                          if s.user_id == user_id and s.access_token == token and s.is_active), None)
            
            if not session:
                return AuthResult(False, AuthAction.TOKEN_INVALID, 
                    message="Session not found")
            
            # Check session expiration
            if datetime.now() > session.expires_at:
                session.is_active = False
                return AuthResult(False, AuthAction.TOKEN_EXPIRED, 
                    message="Session expired")
            
            # Update session activity
            session.last_activity = datetime.now()
            
            return AuthResult(True, AuthAction.AUTHENTICATED, user=user, session=session)
            
        except jwt.ExpiredSignatureError:
            return AuthResult(False, AuthAction.TOKEN_EXPIRED, message="Token expired")
        except jwt.InvalidTokenError:
            return AuthResult(False, AuthAction.TOKEN_INVALID, message="Invalid token")
        except Exception as e:
            app_logger.error(f"Token verification error: {e}")
            return AuthResult(False, AuthAction.TOKEN_INVALID, 
                            message="Token verification failed")
    
    async def check_permission(self, user: User, permission: str) -> bool:
        """Check if user has specific permission"""
        
        try:
            role_permissions = self.role_permissions.get(user.role, [])
            return permission in role_permissions
            
        except Exception as e:
            app_logger.error(f"Permission check error: {e}")
            return False
    
    async def logout_user(self, session_id: str) -> bool:
        """Logout user and invalidate session"""
        
        try:
            session = self.sessions.get(session_id)
            if session:
                session.is_active = False
                
                # Remove refresh token
                refresh_token_to_remove = None
                for token, user_id in self.refresh_tokens.items():
                    if user_id == session.user_id and session.refresh_token == token:
                        refresh_token_to_remove = token
                        break
                
                if refresh_token_to_remove:
                    del self.refresh_tokens[refresh_token_to_remove]
                
                app_logger.info(f"User logged out: session {session_id}")
                return True
            
            return False
            
        except Exception as e:
            app_logger.error(f"Logout error: {e}")
            return False
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def _verify_password(self, password: str, hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hash.encode('utf-8'))
    
    def _validate_password_policy(self, password: str) -> bool:
        """Validate password against security policy"""
        if len(password) < self.security_config["password_min_length"]:
            return False
        
        if self.security_config["password_require_numbers"]:
            if not any(c.isdigit() for c in password):
                return False
        
        if self.security_config["password_require_special"]:
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special_chars for c in password):
                return False
        
        return True
    
    def _generate_access_token(self, user: User) -> str:
        """Generate JWT access token"""
        payload = {
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "exp": datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes),
            "iat": datetime.utcnow(),
            "iss": "kumon-assistant"
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def _generate_refresh_token(self) -> str:
        """Generate secure refresh token"""
        return secrets.token_urlsafe(32)
    
    def _generate_mfa_qr_code(self, user: User) -> str:
        """Generate MFA QR code for setup"""
        totp_uri = pyotp.totp.TOTP(user.mfa_secret).provisioning_uri(
            name=user.email,
            issuer_name="Kumon Assistant"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    def _verify_mfa_code(self, secret: str, code: str) -> bool:
        """Verify MFA TOTP code"""
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    
    async def _create_user_session(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuthResult:
        """Create authenticated user session"""
        
        # Clean up old sessions for user
        await self._cleanup_user_sessions(user.user_id)
        
        # Generate tokens
        access_token = self._generate_access_token(user)
        refresh_token = self._generate_refresh_token()
        
        # Create session
        session_id = secrets.token_urlsafe(16)
        expires_at = datetime.now() + timedelta(minutes=self.security_config["session_timeout_minutes"])
        
        session = AuthSession(
            session_id=session_id,
            user_id=user.user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.sessions[session_id] = session
        self.refresh_tokens[refresh_token] = user.user_id
        
        return AuthResult(True, AuthAction.AUTHENTICATED, user=user, session=session,
                        access_token=access_token, refresh_token=refresh_token)
    
    async def _cleanup_user_sessions(self, user_id: str):
        """Clean up old sessions for user"""
        user_sessions = [s for s in self.sessions.values() 
                        if s.user_id == user_id and s.is_active]
        
        # If too many sessions, deactivate oldest ones
        max_sessions = self.security_config["max_concurrent_sessions"]
        if len(user_sessions) >= max_sessions:
            # Sort by last activity (oldest first)
            user_sessions.sort(key=lambda x: x.last_activity)
            sessions_to_remove = user_sessions[:-max_sessions+1]
            
            for session in sessions_to_remove:
                session.is_active = False
                # Remove refresh token
                if session.refresh_token in self.refresh_tokens:
                    del self.refresh_tokens[session.refresh_token]
    
    async def _handle_failed_login(self, user: User):
        """Handle failed login attempt"""
        user.failed_login_attempts += 1
        
        if user.failed_login_attempts >= self.security_config["max_failed_attempts"]:
            lockout_duration = timedelta(minutes=self.security_config["lockout_duration_minutes"])
            user.account_locked_until = datetime.now() + lockout_duration
            app_logger.warning(f"Account locked due to failed attempts: {user.username}")
    
    async def _handle_successful_login(self, user: User):
        """Handle successful login"""
        user.failed_login_attempts = 0
        user.account_locked_until = None
        user.last_login = datetime.now()
    
    def _is_password_expired(self, user: User) -> bool:
        """Check if user password is expired"""
        if not user.password_changed_at:
            return False
        
        expire_days = self.security_config["password_expire_days"]
        expire_date = user.password_changed_at + timedelta(days=expire_days)
        return datetime.now() > expire_date
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions and tokens"""
        current_time = datetime.now()
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if not session.is_active or current_time > session.expires_at:
                expired_sessions.append(session_id)
                
                # Remove associated refresh token
                if session.refresh_token in self.refresh_tokens:
                    del self.refresh_tokens[session.refresh_token]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        if expired_sessions:
            app_logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    def get_auth_metrics(self) -> Dict[str, Any]:
        """Get authentication system metrics"""
        active_sessions = len([s for s in self.sessions.values() if s.is_active])
        total_users = len(self.users)
        active_users = len([u for u in self.users.values() if u.is_active])
        locked_users = len([u for u in self.users.values() 
                           if u.account_locked_until and datetime.now() < u.account_locked_until])
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "locked_users": locked_users,
            "active_sessions": active_sessions,
            "total_sessions": len(self.sessions),
            "mfa_enabled_users": len([u for u in self.users.values() if u.mfa_enabled]),
            "admin_users": len([u for u in self.users.values() 
                              if u.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]]),
            "security_config": self.security_config,
            "timestamp": datetime.now().isoformat()
        }


# Global authentication manager instance
auth_manager = AuthenticationManager()