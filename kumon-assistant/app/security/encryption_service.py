"""
Advanced Encryption Service - Phase 3 Security Hardening

Enterprise-grade encryption with:
- Data encryption at rest and in transit
- Field-level encryption for sensitive data
- Key management and rotation
- Secure data transmission protocols
- Database encryption integration
- File system encryption
- Advanced cryptographic algorithms
"""

import os
import hashlib
import hmac
import time
import base64
import secrets
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json

# Cryptography imports
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend

from ..core.logger import app_logger
from .secrets_manager import secrets_manager, SecretType


class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms"""
    FERNET = "fernet"           # Symmetric, high-level
    AES_256_GCM = "aes_256_gcm" # Symmetric, authenticated
    RSA_2048 = "rsa_2048"       # Asymmetric
    RSA_4096 = "rsa_4096"       # Asymmetric, stronger
    CHACHA20_POLY1305 = "chacha20_poly1305"  # Modern symmetric


class EncryptionPurpose(Enum):
    """Purpose classification for encryption"""
    DATABASE_FIELD = "database_field"
    FILE_STORAGE = "file_storage"
    NETWORK_TRANSPORT = "network_transport"
    SESSION_DATA = "session_data"
    API_PAYLOAD = "api_payload"
    BACKUP_DATA = "backup_data"
    LOG_SANITIZATION = "log_sanitization"


@dataclass
class EncryptionKey:
    """Encryption key information"""
    key_id: str
    algorithm: EncryptionAlgorithm
    purpose: EncryptionPurpose
    key_data: bytes
    created_at: datetime
    expires_at: Optional[datetime] = None
    rotation_interval_days: int = 90
    usage_count: int = 0
    is_active: bool = True


@dataclass
class EncryptedData:
    """Encrypted data container"""
    algorithm: EncryptionAlgorithm
    key_id: str
    ciphertext: bytes
    iv_or_nonce: Optional[bytes] = None
    auth_tag: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    encrypted_at: datetime = field(default_factory=datetime.now)


class EncryptionService:
    """
    Advanced encryption service for enterprise security
    
    Features:
    - Multiple encryption algorithms
    - Automatic key management and rotation
    - Field-level database encryption
    - File system encryption
    - Network transport encryption
    - Key derivation functions
    - Secure random generation
    """
    
    def __init__(self):
        # Encryption keys storage
        self.encryption_keys: Dict[str, EncryptionKey] = {}
        
        # Configuration
        self.config = {
            "default_algorithm": EncryptionAlgorithm.AES_256_GCM,
            "key_rotation_interval_days": 90,
            "enable_automatic_rotation": True,
            "pbkdf2_iterations": 100000,
            "scrypt_n": 2**14,  # CPU/memory cost parameter
            "scrypt_r": 8,      # Block size
            "scrypt_p": 1,      # Parallelization
            "max_key_usage_count": 1000000,
            "enable_key_usage_tracking": True,
            "secure_deletion": True,
        }
        
        # Algorithm configurations
        self.algorithm_configs = {
            EncryptionAlgorithm.AES_256_GCM: {
                "key_size": 32,     # 256 bits
                "nonce_size": 12,   # 96 bits for GCM
                "tag_size": 16      # 128 bits
            },
            EncryptionAlgorithm.CHACHA20_POLY1305: {
                "key_size": 32,     # 256 bits
                "nonce_size": 12,   # 96 bits
                "tag_size": 16      # 128 bits
            },
            EncryptionAlgorithm.FERNET: {
                "key_size": 32      # 256 bits (URL-safe base64 encoded)
            },
            EncryptionAlgorithm.RSA_2048: {
                "key_size": 2048    # bits
            },
            EncryptionAlgorithm.RSA_4096: {
                "key_size": 4096    # bits
            }
        }
        
        # Initialize default encryption keys
        self._initialize_default_keys()
        
        app_logger.info("Encryption Service initialized with enterprise-grade algorithms")
    
    def _initialize_default_keys(self):
        """Initialize default encryption keys for different purposes"""
        
        # Database field encryption key
        if not self._get_key_by_purpose(EncryptionPurpose.DATABASE_FIELD):
            self.generate_encryption_key(
                purpose=EncryptionPurpose.DATABASE_FIELD,
                algorithm=EncryptionAlgorithm.AES_256_GCM
            )
        
        # File storage encryption key
        if not self._get_key_by_purpose(EncryptionPurpose.FILE_STORAGE):
            self.generate_encryption_key(
                purpose=EncryptionPurpose.FILE_STORAGE,
                algorithm=EncryptionAlgorithm.FERNET
            )
        
        # Session data encryption key
        if not self._get_key_by_purpose(EncryptionPurpose.SESSION_DATA):
            self.generate_encryption_key(
                purpose=EncryptionPurpose.SESSION_DATA,
                algorithm=EncryptionAlgorithm.CHACHA20_POLY1305
            )
        
        # Network transport encryption (RSA for key exchange)
        if not self._get_key_by_purpose(EncryptionPurpose.NETWORK_TRANSPORT):
            self.generate_encryption_key(
                purpose=EncryptionPurpose.NETWORK_TRANSPORT,
                algorithm=EncryptionAlgorithm.RSA_2048
            )
    
    def generate_encryption_key(
        self,
        purpose: EncryptionPurpose,
        algorithm: EncryptionAlgorithm,
        rotation_interval_days: int = None
    ) -> str:
        """Generate new encryption key for specified purpose"""
        
        try:
            key_id = f"{purpose.value}_{algorithm.value}_{secrets.token_hex(8)}"
            rotation_days = rotation_interval_days or self.config["key_rotation_interval_days"]
            
            # Generate key based on algorithm
            if algorithm == EncryptionAlgorithm.FERNET:
                key_data = Fernet.generate_key()
                
            elif algorithm == EncryptionAlgorithm.AES_256_GCM:
                key_data = secrets.token_bytes(self.algorithm_configs[algorithm]["key_size"])
                
            elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                key_data = secrets.token_bytes(self.algorithm_configs[algorithm]["key_size"])
                
            elif algorithm in [EncryptionAlgorithm.RSA_2048, EncryptionAlgorithm.RSA_4096]:
                # Generate RSA key pair
                key_size = self.algorithm_configs[algorithm]["key_size"]
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=key_size,
                    backend=default_backend()
                )
                
                # Serialize private key
                key_data = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                
                # Store public key separately in secrets manager
                public_key = private_key.public_key()
                public_key_pem = public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ).decode('utf-8')
                
                secrets_manager.store_secret(
                    name=f"{key_id}_public",
                    value=public_key_pem,
                    secret_type=SecretType.CERTIFICATE,
                    description=f"Public key for {purpose.value} ({algorithm.value})"
                )
                
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
            
            # Create encryption key
            encryption_key = EncryptionKey(
                key_id=key_id,
                algorithm=algorithm,
                purpose=purpose,
                key_data=key_data,
                created_at=datetime.now(),
                rotation_interval_days=rotation_days
            )
            
            # Store key
            self.encryption_keys[key_id] = encryption_key
            
            # Store key in secrets manager for persistence
            secrets_manager.store_secret(
                name=f"encryption_key_{key_id}",
                value=base64.b64encode(key_data).decode('utf-8'),
                secret_type=SecretType.ENCRYPTION_KEY,
                description=f"Encryption key for {purpose.value} ({algorithm.value})",
                rotation_interval_days=rotation_days
            )
            
            app_logger.info(f"Generated encryption key: {key_id} ({algorithm.value})")
            return key_id
            
        except Exception as e:
            app_logger.error(f"Failed to generate encryption key: {e}")
            raise
    
    def _get_key_by_purpose(self, purpose: EncryptionPurpose) -> Optional[EncryptionKey]:
        """Get active encryption key by purpose"""
        for key in self.encryption_keys.values():
            if key.purpose == purpose and key.is_active:
                return key
        return None
    
    def encrypt_data(
        self,
        data: Union[str, bytes],
        purpose: EncryptionPurpose,
        algorithm: Optional[EncryptionAlgorithm] = None
    ) -> EncryptedData:
        """Encrypt data for specified purpose"""
        
        try:
            # Get encryption key
            if algorithm:
                # Find key with specific algorithm
                key = next((k for k in self.encryption_keys.values() 
                           if k.purpose == purpose and k.algorithm == algorithm and k.is_active), None)
            else:
                # Get any active key for purpose
                key = self._get_key_by_purpose(purpose)
            
            if not key:
                # Generate new key if none exists
                algorithm = algorithm or self.config["default_algorithm"]
                key_id = self.generate_encryption_key(purpose, algorithm)
                key = self.encryption_keys[key_id]
            
            # Convert string to bytes if necessary
            if isinstance(data, str):
                plaintext = data.encode('utf-8')
            else:
                plaintext = data
            
            # Encrypt based on algorithm
            if key.algorithm == EncryptionAlgorithm.FERNET:
                cipher_suite = Fernet(key.key_data)
                ciphertext = cipher_suite.encrypt(plaintext)
                
                return EncryptedData(
                    algorithm=key.algorithm,
                    key_id=key.key_id,
                    ciphertext=ciphertext
                )
            
            elif key.algorithm == EncryptionAlgorithm.AES_256_GCM:
                # Generate random nonce
                nonce = secrets.token_bytes(self.algorithm_configs[key.algorithm]["nonce_size"])
                
                # Create cipher
                cipher = Cipher(
                    algorithms.AES(key.key_data),
                    modes.GCM(nonce),
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                
                # Encrypt and get auth tag
                ciphertext = encryptor.update(plaintext) + encryptor.finalize()
                auth_tag = encryptor.tag
                
                return EncryptedData(
                    algorithm=key.algorithm,
                    key_id=key.key_id,
                    ciphertext=ciphertext,
                    iv_or_nonce=nonce,
                    auth_tag=auth_tag
                )
            
            elif key.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                # Generate random nonce
                nonce = secrets.token_bytes(self.algorithm_configs[key.algorithm]["nonce_size"])
                
                # Create cipher
                cipher = Cipher(
                    algorithms.ChaCha20(key.key_data, nonce),
                    modes.GCM(),  # ChaCha20-Poly1305 uses AEAD
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                
                # Encrypt and get auth tag
                ciphertext = encryptor.update(plaintext) + encryptor.finalize()
                auth_tag = encryptor.tag
                
                return EncryptedData(
                    algorithm=key.algorithm,
                    key_id=key.key_id,
                    ciphertext=ciphertext,
                    iv_or_nonce=nonce,
                    auth_tag=auth_tag
                )
            
            elif key.algorithm in [EncryptionAlgorithm.RSA_2048, EncryptionAlgorithm.RSA_4096]:
                # Load private key
                private_key = serialization.load_pem_private_key(
                    key.key_data,
                    password=None,
                    backend=default_backend()
                )
                
                # Use public key for encryption
                public_key = private_key.public_key()
                
                # RSA can only encrypt limited data size, use OAEP padding
                ciphertext = public_key.encrypt(
                    plaintext,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
                return EncryptedData(
                    algorithm=key.algorithm,
                    key_id=key.key_id,
                    ciphertext=ciphertext
                )
            
            else:
                raise ValueError(f"Encryption not implemented for algorithm: {key.algorithm}")
            
        except Exception as e:
            app_logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt_data(self, encrypted_data: EncryptedData) -> bytes:
        """Decrypt encrypted data"""
        
        try:
            # Get decryption key
            key = self.encryption_keys.get(encrypted_data.key_id)
            if not key:
                raise ValueError(f"Decryption key not found: {encrypted_data.key_id}")
            
            # Decrypt based on algorithm
            if encrypted_data.algorithm == EncryptionAlgorithm.FERNET:
                cipher_suite = Fernet(key.key_data)
                plaintext = cipher_suite.decrypt(encrypted_data.ciphertext)
                
            elif encrypted_data.algorithm == EncryptionAlgorithm.AES_256_GCM:
                if not encrypted_data.iv_or_nonce or not encrypted_data.auth_tag:
                    raise ValueError("AES-GCM requires nonce and auth tag")
                
                # Create cipher
                cipher = Cipher(
                    algorithms.AES(key.key_data),
                    modes.GCM(encrypted_data.iv_or_nonce, encrypted_data.auth_tag),
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                
                # Decrypt and verify auth tag
                plaintext = decryptor.update(encrypted_data.ciphertext) + decryptor.finalize()
                
            elif encrypted_data.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                if not encrypted_data.iv_or_nonce or not encrypted_data.auth_tag:
                    raise ValueError("ChaCha20-Poly1305 requires nonce and auth tag")
                
                # Create cipher
                cipher = Cipher(
                    algorithms.ChaCha20(key.key_data, encrypted_data.iv_or_nonce),
                    modes.GCM(encrypted_data.auth_tag),
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                
                # Decrypt and verify auth tag
                plaintext = decryptor.update(encrypted_data.ciphertext) + decryptor.finalize()
                
            elif encrypted_data.algorithm in [EncryptionAlgorithm.RSA_2048, EncryptionAlgorithm.RSA_4096]:
                # Load private key
                private_key = serialization.load_pem_private_key(
                    key.key_data,
                    password=None,
                    backend=default_backend()
                )
                
                # Decrypt with OAEP padding
                plaintext = private_key.decrypt(
                    encrypted_data.ciphertext,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
            else:
                raise ValueError(f"Decryption not implemented for algorithm: {encrypted_data.algorithm}")
            
            # Update key usage if tracking enabled
            if self.config["enable_key_usage_tracking"]:
                key.usage_count += 1
            
            return plaintext
            
        except Exception as e:
            app_logger.error(f"Decryption failed: {e}")
            raise
    
    def encrypt_database_field(self, field_value: Any, field_name: str = None) -> str:
        """Encrypt database field value"""
        
        try:
            # Convert value to string
            if field_value is None:
                return None
            
            value_str = json.dumps(field_value) if not isinstance(field_value, str) else field_value
            
            # Encrypt for database storage
            encrypted_data = self.encrypt_data(
                value_str,
                EncryptionPurpose.DATABASE_FIELD,
                EncryptionAlgorithm.AES_256_GCM
            )
            
            # Serialize encrypted data
            encrypted_payload = {
                "algorithm": encrypted_data.algorithm.value,
                "key_id": encrypted_data.key_id,
                "ciphertext": base64.b64encode(encrypted_data.ciphertext).decode('utf-8'),
                "nonce": base64.b64encode(encrypted_data.iv_or_nonce).decode('utf-8') if encrypted_data.iv_or_nonce else None,
                "auth_tag": base64.b64encode(encrypted_data.auth_tag).decode('utf-8') if encrypted_data.auth_tag else None,
                "encrypted_at": encrypted_data.encrypted_at.isoformat()
            }
            
            return base64.b64encode(json.dumps(encrypted_payload).encode('utf-8')).decode('utf-8')
            
        except Exception as e:
            app_logger.error(f"Database field encryption failed: {e}")
            raise
    
    def decrypt_database_field(self, encrypted_field: str) -> Any:
        """Decrypt database field value"""
        
        try:
            if not encrypted_field:
                return None
            
            # Deserialize encrypted data
            encrypted_payload = json.loads(base64.b64decode(encrypted_field.encode('utf-8')))
            
            # Reconstruct EncryptedData
            encrypted_data = EncryptedData(
                algorithm=EncryptionAlgorithm(encrypted_payload["algorithm"]),
                key_id=encrypted_payload["key_id"],
                ciphertext=base64.b64decode(encrypted_payload["ciphertext"]),
                iv_or_nonce=base64.b64decode(encrypted_payload["nonce"]) if encrypted_payload["nonce"] else None,
                auth_tag=base64.b64decode(encrypted_payload["auth_tag"]) if encrypted_payload["auth_tag"] else None,
                encrypted_at=datetime.fromisoformat(encrypted_payload["encrypted_at"])
            )
            
            # Decrypt
            plaintext = self.decrypt_data(encrypted_data)
            value_str = plaintext.decode('utf-8')
            
            # Try to parse as JSON, fall back to string
            try:
                return json.loads(value_str)
            except:
                return value_str
                
        except Exception as e:
            app_logger.error(f"Database field decryption failed: {e}")
            raise
    
    def derive_key_from_password(
        self,
        password: str,
        salt: bytes = None,
        algorithm: str = "pbkdf2"
    ) -> Tuple[bytes, bytes]:
        """Derive encryption key from password"""
        
        try:
            if salt is None:
                salt = secrets.token_bytes(32)
            
            if algorithm == "pbkdf2":
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,  # 256 bits
                    salt=salt,
                    iterations=self.config["pbkdf2_iterations"],
                    backend=default_backend()
                )
            elif algorithm == "scrypt":
                kdf = Scrypt(
                    algorithm=hashes.SHA256(),
                    length=32,  # 256 bits
                    salt=salt,
                    n=self.config["scrypt_n"],
                    r=self.config["scrypt_r"],
                    p=self.config["scrypt_p"],
                    backend=default_backend()
                )
            else:
                raise ValueError(f"Unsupported KDF algorithm: {algorithm}")
            
            key = kdf.derive(password.encode('utf-8'))
            return key, salt
            
        except Exception as e:
            app_logger.error(f"Key derivation failed: {e}")
            raise
    
    def generate_secure_hash(self, data: Union[str, bytes], algorithm: str = "sha256") -> str:
        """Generate secure hash of data"""
        
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            if algorithm == "sha256":
                hash_obj = hashlib.sha256(data)
            elif algorithm == "sha512":
                hash_obj = hashlib.sha512(data)
            elif algorithm == "sha3_256":
                hash_obj = hashlib.sha3_256(data)
            elif algorithm == "blake2b":
                hash_obj = hashlib.blake2b(data)
            else:
                raise ValueError(f"Unsupported hash algorithm: {algorithm}")
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            app_logger.error(f"Hash generation failed: {e}")
            raise
    
    def generate_hmac(self, data: Union[str, bytes], key: bytes = None, algorithm: str = "sha256") -> str:
        """Generate HMAC for data integrity"""
        
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            if key is None:
                # Use session data encryption key
                session_key = self._get_key_by_purpose(EncryptionPurpose.SESSION_DATA)
                key = session_key.key_data if session_key else secrets.token_bytes(32)
            
            if algorithm == "sha256":
                mac = hmac.new(key, data, hashlib.sha256)
            elif algorithm == "sha512":
                mac = hmac.new(key, data, hashlib.sha512)
            else:
                raise ValueError(f"Unsupported HMAC algorithm: {algorithm}")
            
            return mac.hexdigest()
            
        except Exception as e:
            app_logger.error(f"HMAC generation failed: {e}")
            raise
    
    def sanitize_for_logging(self, data: Union[str, Dict[str, Any]], sensitive_fields: List[str] = None) -> Union[str, Dict[str, Any]]:
        """Sanitize data for safe logging by encrypting sensitive fields"""
        
        try:
            if sensitive_fields is None:
                sensitive_fields = [
                    "password", "token", "secret", "key", "credential",
                    "email", "phone", "cpf", "cnpj", "credit_card"
                ]
            
            if isinstance(data, str):
                # Simple string sanitization
                for field in sensitive_fields:
                    if field.lower() in data.lower():
                        # Encrypt the entire string for logging
                        encrypted = self.encrypt_data(data, EncryptionPurpose.LOG_SANITIZATION)
                        return f"[ENCRYPTED:{encrypted.key_id[:8]}]"
                return data
            
            elif isinstance(data, dict):
                # Dictionary sanitization
                sanitized = {}
                for key, value in data.items():
                    key_lower = key.lower()
                    if any(sensitive in key_lower for sensitive in sensitive_fields):
                        # Encrypt sensitive field
                        encrypted = self.encrypt_data(str(value), EncryptionPurpose.LOG_SANITIZATION)
                        sanitized[key] = f"[ENCRYPTED:{encrypted.key_id[:8]}]"
                    elif isinstance(value, dict):
                        # Recursively sanitize nested dictionaries
                        sanitized[key] = self.sanitize_for_logging(value, sensitive_fields)
                    else:
                        sanitized[key] = value
                
                return sanitized
            
            else:
                return data
                
        except Exception as e:
            app_logger.error(f"Log sanitization failed: {e}")
            return "[SANITIZATION_ERROR]"
    
    def rotate_encryption_keys(self, purpose: Optional[EncryptionPurpose] = None) -> List[str]:
        """Rotate encryption keys that need rotation"""
        
        rotated_keys = []
        current_time = datetime.now()
        
        try:
            keys_to_rotate = []
            
            # Find keys that need rotation
            for key in self.encryption_keys.values():
                if purpose and key.purpose != purpose:
                    continue
                
                if not key.is_active:
                    continue
                
                # Check if rotation is needed
                rotation_needed = False
                
                # Time-based rotation
                if key.expires_at and current_time >= key.expires_at:
                    rotation_needed = True
                elif (current_time - key.created_at).days >= key.rotation_interval_days:
                    rotation_needed = True
                
                # Usage-based rotation
                if (self.config["enable_key_usage_tracking"] and 
                    key.usage_count >= self.config["max_key_usage_count"]):
                    rotation_needed = True
                
                if rotation_needed:
                    keys_to_rotate.append(key)
            
            # Rotate keys
            for old_key in keys_to_rotate:
                # Generate new key
                new_key_id = self.generate_encryption_key(
                    purpose=old_key.purpose,
                    algorithm=old_key.algorithm,
                    rotation_interval_days=old_key.rotation_interval_days
                )
                
                # Deactivate old key (don't delete for decryption of old data)
                old_key.is_active = False
                
                rotated_keys.append(new_key_id)
                app_logger.info(f"Rotated encryption key: {old_key.key_id} -> {new_key_id}")
            
            if rotated_keys:
                app_logger.info(f"Rotated {len(rotated_keys)} encryption keys")
            
            return rotated_keys
            
        except Exception as e:
            app_logger.error(f"Key rotation failed: {e}")
            return rotated_keys
    
    def get_encryption_metrics(self) -> Dict[str, Any]:
        """Get encryption service metrics"""
        
        total_keys = len(self.encryption_keys)
        active_keys = len([k for k in self.encryption_keys.values() if k.is_active])
        keys_by_purpose = {}
        keys_by_algorithm = {}
        
        for key in self.encryption_keys.values():
            # Count by purpose
            purpose = key.purpose.value
            keys_by_purpose[purpose] = keys_by_purpose.get(purpose, 0) + 1
            
            # Count by algorithm
            algorithm = key.algorithm.value
            keys_by_algorithm[algorithm] = keys_by_algorithm.get(algorithm, 0) + 1
        
        # Check for keys needing rotation
        keys_needing_rotation = []
        current_time = datetime.now()
        
        for key in self.encryption_keys.values():
            if not key.is_active:
                continue
            
            days_since_creation = (current_time - key.created_at).days
            if days_since_creation >= (key.rotation_interval_days - 7):  # 7-day warning
                keys_needing_rotation.append({
                    "key_id": key.key_id,
                    "purpose": key.purpose.value,
                    "algorithm": key.algorithm.value,
                    "days_since_creation": days_since_creation,
                    "rotation_due": days_since_creation >= key.rotation_interval_days
                })
        
        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "inactive_keys": total_keys - active_keys,
            "keys_by_purpose": keys_by_purpose,
            "keys_by_algorithm": keys_by_algorithm,
            "keys_needing_rotation": len([k for k in keys_needing_rotation if k["rotation_due"]]),
            "keys_rotation_warning": len(keys_needing_rotation),
            "rotation_details": keys_needing_rotation,
            "encryption_enabled": True,
            "algorithms_supported": [algo.value for algo in EncryptionAlgorithm],
            "last_check": current_time.isoformat()
        }


# Global encryption service instance
encryption_service = EncryptionService()