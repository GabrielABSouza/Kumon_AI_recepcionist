"""
Secrets Management System - Phase 2 Security Implementation

Enterprise-grade secrets management with:
- Encrypted secrets storage
- Secret rotation and versioning
- Environment-based configuration
- Audit logging for secret access
- Integration with external secret managers
- Secure secret injection
"""

import os
import json
import time
import secrets
import base64
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..core.logger import app_logger
from ..core.config import settings


class SecretType(Enum):
    """Types of secrets managed by the system"""
    API_KEY = "api_key"
    DATABASE_PASSWORD = "database_password"
    JWT_SECRET = "jwt_secret"
    ENCRYPTION_KEY = "encryption_key"
    WEBHOOK_SECRET = "webhook_secret"
    THIRD_PARTY_TOKEN = "third_party_token"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"


class SecretStatus(Enum):
    """Secret lifecycle status"""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class SecretMetadata:
    """Secret metadata without sensitive data"""
    secret_id: str
    name: str
    secret_type: SecretType
    status: SecretStatus
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    rotation_interval_days: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class Secret:
    """Complete secret with encrypted value"""
    metadata: SecretMetadata
    encrypted_value: bytes
    version: int = 1
    previous_versions: List[bytes] = field(default_factory=list)


@dataclass
class SecretAccess:
    """Secret access audit record"""
    secret_id: str
    accessed_by: str
    accessed_at: datetime
    access_type: str  # read, write, rotate, delete
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class SecretsManager:
    """
    Enterprise secrets management system
    
    Features:
    - Encrypted secret storage
    - Secret rotation and versioning
    - Access auditing
    - Environment-based configuration
    - Integration with external providers
    - Secure secret injection
    """
    
    def __init__(self, encryption_password: Optional[str] = None):
        # Initialize encryption
        self.encryption_password = encryption_password or self._get_master_password()
        self.cipher_suite = self._initialize_encryption()
        
        # Secret storage
        self.secrets: Dict[str, Secret] = {}
        self.access_log: List[SecretAccess] = []
        
        # Configuration
        self.config = {
            "default_rotation_days": 90,
            "max_secret_age_days": 365,
            "audit_retention_days": 730,
            "max_access_log_size": 10000,
            "require_rotation_warning_days": 30,
            "enable_access_logging": True,
            "enable_automatic_rotation": True,
        }
        
        # Load secrets from secure storage
        self._load_secrets_from_storage()
        
        # Initialize default secrets
        self._initialize_default_secrets()
        
        app_logger.info("Secrets Manager initialized with encryption")
    
    def _get_master_password(self) -> str:
        """Get master encryption password from environment or generate new one"""
        
        # Try to get from environment
        master_password = os.getenv("SECRETS_MASTER_PASSWORD")
        
        if not master_password:
            # Check if we have a stored master password file
            master_file = ".secrets_master"
            if os.path.exists(master_file):
                with open(master_file, 'rb') as f:
                    master_password = f.read().decode('utf-8')
            else:
                # Generate new master password
                master_password = secrets.token_urlsafe(32)
                
                # Store securely (in production, use proper key management)
                with open(master_file, 'wb') as f:
                    f.write(master_password.encode('utf-8'))
                os.chmod(master_file, 0o600)  # Read-write owner only
                
                app_logger.warning(
                    "Generated new master password for secrets encryption. "
                    "Store this securely in production!"
                )
        
        return master_password
    
    def _initialize_encryption(self) -> Fernet:
        """Initialize Fernet encryption with password-derived key"""
        
        # Use password-based key derivation
        password = self.encryption_password.encode()
        salt = b'kumon_secrets_salt'  # In production, use random salt
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return Fernet(key)
    
    def _load_secrets_from_storage(self):
        """Load encrypted secrets from storage file"""
        
        storage_file = ".secrets_store"
        if not os.path.exists(storage_file):
            return
        
        try:
            with open(storage_file, 'rb') as f:
                encrypted_data = f.read()
            
            if encrypted_data:
                decrypted_data = self.cipher_suite.decrypt(encrypted_data)
                secrets_data = json.loads(decrypted_data.decode('utf-8'))
                
                # Reconstruct secrets
                for secret_data in secrets_data:
                    metadata = SecretMetadata(
                        secret_id=secret_data["secret_id"],
                        name=secret_data["name"],
                        secret_type=SecretType(secret_data["secret_type"]),
                        status=SecretStatus(secret_data["status"]),
                        created_at=datetime.fromisoformat(secret_data["created_at"]),
                        expires_at=datetime.fromisoformat(secret_data["expires_at"]) if secret_data.get("expires_at") else None,
                        last_accessed=datetime.fromisoformat(secret_data["last_accessed"]) if secret_data.get("last_accessed") else None,
                        access_count=secret_data.get("access_count", 0),
                        rotation_interval_days=secret_data.get("rotation_interval_days"),
                        tags=secret_data.get("tags", []),
                        description=secret_data.get("description", "")
                    )
                    
                    secret = Secret(
                        metadata=metadata,
                        encrypted_value=base64.b64decode(secret_data["encrypted_value"]),
                        version=secret_data.get("version", 1),
                        previous_versions=[base64.b64decode(v) for v in secret_data.get("previous_versions", [])]
                    )
                    
                    self.secrets[secret.metadata.secret_id] = secret
                
                app_logger.info(f"Loaded {len(self.secrets)} secrets from storage")
                
        except Exception as e:
            app_logger.error(f"Failed to load secrets from storage: {e}")
    
    def _save_secrets_to_storage(self):
        """Save encrypted secrets to storage file"""
        
        try:
            # Serialize secrets
            secrets_data = []
            for secret in self.secrets.values():
                secret_data = {
                    "secret_id": secret.metadata.secret_id,
                    "name": secret.metadata.name,
                    "secret_type": secret.metadata.secret_type.value,
                    "status": secret.metadata.status.value,
                    "created_at": secret.metadata.created_at.isoformat(),
                    "expires_at": secret.metadata.expires_at.isoformat() if secret.metadata.expires_at else None,
                    "last_accessed": secret.metadata.last_accessed.isoformat() if secret.metadata.last_accessed else None,
                    "access_count": secret.metadata.access_count,
                    "rotation_interval_days": secret.metadata.rotation_interval_days,
                    "tags": secret.metadata.tags,
                    "description": secret.metadata.description,
                    "encrypted_value": base64.b64encode(secret.encrypted_value).decode('utf-8'),
                    "version": secret.version,
                    "previous_versions": [base64.b64encode(v).decode('utf-8') for v in secret.previous_versions]
                }
                secrets_data.append(secret_data)
            
            # Encrypt and save
            json_data = json.dumps(secrets_data).encode('utf-8')
            encrypted_data = self.cipher_suite.encrypt(json_data)
            
            storage_file = ".secrets_store"
            with open(storage_file, 'wb') as f:
                f.write(encrypted_data)
            
            os.chmod(storage_file, 0o600)  # Read-write owner only
            
        except Exception as e:
            app_logger.error(f"Failed to save secrets to storage: {e}")
    
    def _initialize_default_secrets(self):
        """Initialize default system secrets"""
        
        # JWT secret key
        if not self.get_secret_metadata("jwt_secret_key"):
            jwt_secret = secrets.token_urlsafe(32)
            self.store_secret(
                name="jwt_secret_key",
                value=jwt_secret,
                secret_type=SecretType.JWT_SECRET,
                description="JWT token signing secret",
                rotation_interval_days=180
            )
        
        # Webhook verification secrets
        if not self.get_secret_metadata("whatsapp_webhook_secret"):
            webhook_secret = secrets.token_urlsafe(24)
            self.store_secret(
                name="whatsapp_webhook_secret",
                value=webhook_secret,
                secret_type=SecretType.WEBHOOK_SECRET,
                description="WhatsApp webhook verification secret"
            )
        
        # Evolution API key (if not configured)
        if not self.get_secret_metadata("evolution_api_key") and not getattr(settings, 'EVOLUTION_API_KEY', None):
            evolution_key = secrets.token_urlsafe(24)
            self.store_secret(
                name="evolution_api_key",
                value=evolution_key,
                secret_type=SecretType.API_KEY,
                description="Evolution API authentication key"
            )
    
    def store_secret(
        self,
        name: str,
        value: str,
        secret_type: SecretType,
        description: str = "",
        rotation_interval_days: Optional[int] = None,
        expires_in_days: Optional[int] = None,
        tags: List[str] = None,
        accessed_by: str = "system"
    ) -> str:
        """Store a new secret or update existing secret"""
        
        try:
            # Generate secret ID
            secret_id = f"{secret_type.value}_{secrets.token_hex(8)}"
            
            # Calculate expiration
            expires_at = None
            if expires_in_days:
                expires_at = datetime.now() + timedelta(days=expires_in_days)
            
            # Create metadata
            metadata = SecretMetadata(
                secret_id=secret_id,
                name=name,
                secret_type=secret_type,
                status=SecretStatus.ACTIVE,
                created_at=datetime.now(),
                expires_at=expires_at,
                rotation_interval_days=rotation_interval_days or self.config["default_rotation_days"],
                tags=tags or [],
                description=description
            )
            
            # Encrypt secret value
            encrypted_value = self.cipher_suite.encrypt(value.encode('utf-8'))
            
            # Check if secret with same name exists (update scenario)
            existing_secret = next((s for s in self.secrets.values() if s.metadata.name == name), None)
            
            if existing_secret:
                # Archive old version
                existing_secret.previous_versions.append(existing_secret.encrypted_value)
                existing_secret.encrypted_value = encrypted_value
                existing_secret.version += 1
                existing_secret.metadata.status = SecretStatus.ACTIVE
                secret_id = existing_secret.metadata.secret_id
            else:
                # Create new secret
                secret = Secret(
                    metadata=metadata,
                    encrypted_value=encrypted_value
                )
                self.secrets[secret_id] = secret
            
            # Save to storage
            self._save_secrets_to_storage()
            
            # Log access
            self._log_access(secret_id, accessed_by, "write", success=True)
            
            app_logger.info(f"Secret stored: {name} (type: {secret_type.value})")
            return secret_id
            
        except Exception as e:
            app_logger.error(f"Failed to store secret {name}: {e}")
            self._log_access("", accessed_by, "write", success=False, error_message=str(e))
            raise
    
    def get_secret(
        self, 
        name_or_id: str, 
        accessed_by: str = "system",
        ip_address: Optional[str] = None
    ) -> Optional[str]:
        """Retrieve secret value by name or ID"""
        
        try:
            # Find secret by name or ID
            secret = None
            for s in self.secrets.values():
                if s.metadata.name == name_or_id or s.metadata.secret_id == name_or_id:
                    secret = s
                    break
            
            if not secret:
                self._log_access(name_or_id, accessed_by, "read", success=False, 
                               error_message="Secret not found", ip_address=ip_address)
                return None
            
            # Check if secret is active
            if secret.metadata.status != SecretStatus.ACTIVE:
                self._log_access(secret.metadata.secret_id, accessed_by, "read", success=False,
                               error_message="Secret not active", ip_address=ip_address)
                return None
            
            # Check expiration
            if secret.metadata.expires_at and datetime.now() > secret.metadata.expires_at:
                secret.metadata.status = SecretStatus.EXPIRED
                self._save_secrets_to_storage()
                self._log_access(secret.metadata.secret_id, accessed_by, "read", success=False,
                               error_message="Secret expired", ip_address=ip_address)
                return None
            
            # Update access tracking
            secret.metadata.last_accessed = datetime.now()
            secret.metadata.access_count += 1
            
            # Decrypt value
            decrypted_value = self.cipher_suite.decrypt(secret.encrypted_value).decode('utf-8')
            
            # Log successful access
            self._log_access(secret.metadata.secret_id, accessed_by, "read", success=True, ip_address=ip_address)
            
            return decrypted_value
            
        except Exception as e:
            app_logger.error(f"Failed to retrieve secret {name_or_id}: {e}")
            self._log_access(name_or_id, accessed_by, "read", success=False, 
                           error_message=str(e), ip_address=ip_address)
            return None
    
    def get_secret_metadata(self, name_or_id: str) -> Optional[SecretMetadata]:
        """Get secret metadata without decrypting value"""
        
        for secret in self.secrets.values():
            if secret.metadata.name == name_or_id or secret.metadata.secret_id == name_or_id:
                return secret.metadata
        
        return None
    
    def list_secrets(self, secret_type: Optional[SecretType] = None, tags: List[str] = None) -> List[SecretMetadata]:
        """List secret metadata (without values)"""
        
        secrets_list = []
        for secret in self.secrets.values():
            # Filter by type if specified
            if secret_type and secret.metadata.secret_type != secret_type:
                continue
            
            # Filter by tags if specified
            if tags and not any(tag in secret.metadata.tags for tag in tags):
                continue
            
            secrets_list.append(secret.metadata)
        
        return secrets_list
    
    def rotate_secret(self, name_or_id: str, new_value: str, accessed_by: str = "system") -> bool:
        """Rotate secret with new value"""
        
        try:
            secret = None
            for s in self.secrets.values():
                if s.metadata.name == name_or_id or s.metadata.secret_id == name_or_id:
                    secret = s
                    break
            
            if not secret:
                return False
            
            # Archive current version
            secret.previous_versions.append(secret.encrypted_value)
            
            # Store new value
            secret.encrypted_value = self.cipher_suite.encrypt(new_value.encode('utf-8'))
            secret.version += 1
            secret.metadata.status = SecretStatus.ACTIVE
            
            # Save to storage
            self._save_secrets_to_storage()
            
            # Log rotation
            self._log_access(secret.metadata.secret_id, accessed_by, "rotate", success=True)
            
            app_logger.info(f"Secret rotated: {secret.metadata.name} (version {secret.version})")
            return True
            
        except Exception as e:
            app_logger.error(f"Failed to rotate secret {name_or_id}: {e}")
            self._log_access(name_or_id, accessed_by, "rotate", success=False, error_message=str(e))
            return False
    
    def delete_secret(self, name_or_id: str, accessed_by: str = "system") -> bool:
        """Delete secret (mark as revoked)"""
        
        try:
            secret = None
            secret_id = None
            for sid, s in self.secrets.items():
                if s.metadata.name == name_or_id or s.metadata.secret_id == name_or_id:
                    secret = s
                    secret_id = sid
                    break
            
            if not secret:
                return False
            
            # Mark as revoked instead of deleting
            secret.metadata.status = SecretStatus.REVOKED
            
            # Save to storage
            self._save_secrets_to_storage()
            
            # Log deletion
            self._log_access(secret.metadata.secret_id, accessed_by, "delete", success=True)
            
            app_logger.info(f"Secret revoked: {secret.metadata.name}")
            return True
            
        except Exception as e:
            app_logger.error(f"Failed to delete secret {name_or_id}: {e}")
            self._log_access(name_or_id, accessed_by, "delete", success=False, error_message=str(e))
            return False
    
    def check_rotation_required(self) -> List[SecretMetadata]:
        """Check which secrets need rotation"""
        
        rotation_needed = []
        warning_threshold = self.config["require_rotation_warning_days"]
        
        for secret in self.secrets.values():
            if secret.metadata.status != SecretStatus.ACTIVE:
                continue
            
            if not secret.metadata.rotation_interval_days:
                continue
            
            # Calculate next rotation date
            rotation_due = secret.metadata.created_at + timedelta(days=secret.metadata.rotation_interval_days)
            warning_date = rotation_due - timedelta(days=warning_threshold)
            
            if datetime.now() >= warning_date:
                rotation_needed.append(secret.metadata)
        
        return rotation_needed
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with secret resolution"""
        
        # Try to get from settings first
        value = getattr(settings, key, default)
        
        # If value looks like a secret reference (starts with 'secret:')
        if isinstance(value, str) and value.startswith('secret:'):
            secret_name = value[7:]  # Remove 'secret:' prefix
            secret_value = self.get_secret(secret_name, accessed_by="config_system")
            if secret_value:
                return secret_value
        
        return value
    
    def _log_access(
        self,
        secret_id: str,
        accessed_by: str,
        access_type: str,
        success: bool = True,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log secret access for audit trail"""
        
        if not self.config["enable_access_logging"]:
            return
        
        access_record = SecretAccess(
            secret_id=secret_id,
            accessed_by=accessed_by,
            accessed_at=datetime.now(),
            access_type=access_type,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message
        )
        
        self.access_log.append(access_record)
        
        # Limit log size
        max_size = self.config["max_access_log_size"]
        if len(self.access_log) > max_size:
            self.access_log = self.access_log[-max_size:]
    
    def get_access_audit(self, secret_name_or_id: Optional[str] = None, days: int = 30) -> List[SecretAccess]:
        """Get access audit logs"""
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        filtered_logs = []
        for log in self.access_log:
            # Filter by date
            if log.accessed_at < cutoff_date:
                continue
            
            # Filter by secret if specified
            if secret_name_or_id:
                secret = next((s for s in self.secrets.values() 
                             if s.metadata.name == secret_name_or_id or s.metadata.secret_id == secret_name_or_id), None)
                if secret and log.secret_id != secret.metadata.secret_id:
                    continue
            
            filtered_logs.append(log)
        
        return sorted(filtered_logs, key=lambda x: x.accessed_at, reverse=True)
    
    def get_secrets_metrics(self) -> Dict[str, Any]:
        """Get secrets management metrics"""
        
        active_secrets = len([s for s in self.secrets.values() if s.metadata.status == SecretStatus.ACTIVE])
        expired_secrets = len([s for s in self.secrets.values() if s.metadata.status == SecretStatus.EXPIRED])
        rotation_needed = len(self.check_rotation_required())
        
        access_last_24h = len([log for log in self.access_log 
                              if log.accessed_at > datetime.now() - timedelta(hours=24)])
        
        return {
            "total_secrets": len(self.secrets),
            "active_secrets": active_secrets,
            "expired_secrets": expired_secrets,
            "rotation_needed": rotation_needed,
            "access_last_24h": access_last_24h,
            "total_access_logs": len(self.access_log),
            "encryption_enabled": True,
            "storage_encrypted": True,
            "last_rotation_check": datetime.now().isoformat()
        }


# Global secrets manager instance
secrets_manager = SecretsManager()