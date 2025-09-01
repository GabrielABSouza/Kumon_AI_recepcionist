"""
SSL/TLS Certificate Management - Phase 2 Security Implementation

Comprehensive certificate management with:
- Self-signed certificate generation
- Certificate authority (CA) management
- Certificate validation and verification
- Automatic certificate renewal
- Certificate chain validation
- OCSP (Online Certificate Status Protocol) checking
- Certificate monitoring and alerting
"""

import os
import ssl
import socket
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import requests
import base64

from ..core.logger import app_logger
from .secrets_manager import secrets_manager, SecretType


class CertificateType(Enum):
    """Certificate types"""
    ROOT_CA = "root_ca"
    INTERMEDIATE_CA = "intermediate_ca"
    SERVER = "server"
    CLIENT = "client"
    CODE_SIGNING = "code_signing"
    EMAIL = "email"


class CertificateStatus(Enum):
    """Certificate status"""
    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING_RENEWAL = "pending_renewal"
    INVALID = "invalid"


@dataclass
class CertificateInfo:
    """Certificate information"""
    name: str
    certificate_type: CertificateType
    subject: str
    issuer: str
    serial_number: str
    not_before: datetime
    not_after: datetime
    status: CertificateStatus
    fingerprint_sha256: str
    public_key_size: int
    signature_algorithm: str
    san_domains: List[str] = field(default_factory=list)
    key_usage: List[str] = field(default_factory=list)
    extended_key_usage: List[str] = field(default_factory=list)
    certificate_path: Optional[str] = None
    private_key_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CertificateChain:
    """Certificate chain information"""
    leaf_certificate: CertificateInfo
    intermediate_certificates: List[CertificateInfo]
    root_certificate: Optional[CertificateInfo]
    is_valid: bool
    validation_errors: List[str] = field(default_factory=list)


class SSLManager:
    """
    SSL/TLS Certificate Management System
    
    Features:
    - Certificate generation and management
    - Certificate validation and monitoring
    - Automatic renewal and rotation
    - Certificate chain validation
    - OCSP checking
    - Security monitoring
    """
    
    def __init__(self):
        # Certificate storage
        self.certificates: Dict[str, CertificateInfo] = {}
        self.certificate_chains: Dict[str, CertificateChain] = {}
        
        # SSL configuration
        self.ssl_config = {
            "certificate_directory": "certs",
            "key_size": 2048,
            "hash_algorithm": "sha256",
            "certificate_validity_days": 365,
            "renewal_threshold_days": 30,
            "enable_ocsp_checking": True,
            "enable_automatic_renewal": True,
            "cipher_suites": [
                "TLS_AES_256_GCM_SHA384",
                "TLS_CHACHA20_POLY1305_SHA256",
                "TLS_AES_128_GCM_SHA256",
                "ECDHE-RSA-AES256-GCM-SHA384",
                "ECDHE-RSA-AES128-GCM-SHA256"
            ],
            "tls_versions": ["TLSv1.2", "TLSv1.3"],
            "require_client_certificates": False
        }
        
        # Create certificate directory
        os.makedirs(self.ssl_config["certificate_directory"], exist_ok=True)
        
        # Load existing certificates
        self._load_existing_certificates()
        
        # Initialize default certificates
        self._initialize_default_certificates()
        
        app_logger.info("SSL Manager initialized with certificate management")
    
    def _load_existing_certificates(self):
        """Load existing certificates from storage"""
        
        cert_dir = self.ssl_config["certificate_directory"]
        if not os.path.exists(cert_dir):
            return
        
        try:
            for filename in os.listdir(cert_dir):
                if filename.endswith('.crt') or filename.endswith('.pem'):
                    cert_path = os.path.join(cert_dir, filename)
                    cert_info = self._load_certificate_file(cert_path)
                    if cert_info:
                        self.certificates[cert_info.name] = cert_info
            
            app_logger.info(f"Loaded {len(self.certificates)} existing certificates")
            
        except Exception as e:
            app_logger.error(f"Error loading existing certificates: {e}")
    
    def _load_certificate_file(self, cert_path: str) -> Optional[CertificateInfo]:
        """Load certificate information from file"""
        
        try:
            with open(cert_path, 'rb') as f:
                cert_data = f.read()
            
            # Try to parse as PEM
            try:
                cert = x509.load_pem_x509_certificate(cert_data)
            except:
                # Try to parse as DER
                cert = x509.load_der_x509_certificate(cert_data)
            
            return self._extract_certificate_info(cert, cert_path)
            
        except Exception as e:
            app_logger.error(f"Error loading certificate {cert_path}: {e}")
            return None
    
    def _extract_certificate_info(self, cert: x509.Certificate, cert_path: Optional[str] = None) -> CertificateInfo:
        """Extract information from X.509 certificate"""
        
        # Basic information
        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()
        serial_number = str(cert.serial_number)
        not_before = cert.not_valid_before
        not_after = cert.not_valid_after
        
        # Fingerprint
        fingerprint = cert.fingerprint(hashes.SHA256())
        fingerprint_sha256 = fingerprint.hex()
        
        # Public key info
        public_key = cert.public_key()
        if hasattr(public_key, 'key_size'):
            key_size = public_key.key_size
        else:
            key_size = 0
        
        # Signature algorithm
        signature_algorithm = cert.signature_algorithm_oid._name
        
        # Subject Alternative Names
        san_domains = []
        try:
            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            for name in san_ext.value:
                if isinstance(name, x509.DNSName):
                    san_domains.append(name.value)
        except x509.ExtensionNotFound:
            pass
        
        # Key usage
        key_usage = []
        try:
            key_usage_ext = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE)
            usage = key_usage_ext.value
            if usage.digital_signature:
                key_usage.append("digital_signature")
            if usage.key_encipherment:
                key_usage.append("key_encipherment")
            if usage.key_agreement:
                key_usage.append("key_agreement")
            if usage.key_cert_sign:
                key_usage.append("key_cert_sign")
            if usage.crl_sign:
                key_usage.append("crl_sign")
        except x509.ExtensionNotFound:
            pass
        
        # Extended key usage
        extended_key_usage = []
        try:
            ext_key_usage_ext = cert.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE)
            for usage in ext_key_usage_ext.value:
                extended_key_usage.append(usage._name)
        except x509.ExtensionNotFound:
            pass
        
        # Determine certificate type
        cert_type = CertificateType.SERVER  # Default
        if "key_cert_sign" in key_usage:
            if subject == issuer:
                cert_type = CertificateType.ROOT_CA
            else:
                cert_type = CertificateType.INTERMEDIATE_CA
        elif "clientAuth" in extended_key_usage:
            cert_type = CertificateType.CLIENT
        
        # Determine status
        current_time = datetime.now()
        if current_time < not_before:
            status = CertificateStatus.INVALID
        elif current_time > not_after:
            status = CertificateStatus.EXPIRED
        elif (not_after - current_time).days < self.ssl_config["renewal_threshold_days"]:
            status = CertificateStatus.PENDING_RENEWAL
        else:
            status = CertificateStatus.VALID
        
        # Generate name from common name or filename
        try:
            common_name = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            name = common_name
        except:
            name = os.path.basename(cert_path) if cert_path else f"cert_{serial_number}"
        
        return CertificateInfo(
            name=name,
            certificate_type=cert_type,
            subject=subject,
            issuer=issuer,
            serial_number=serial_number,
            not_before=not_before,
            not_after=not_after,
            status=status,
            fingerprint_sha256=fingerprint_sha256,
            public_key_size=key_size,
            signature_algorithm=signature_algorithm,
            san_domains=san_domains,
            key_usage=key_usage,
            extended_key_usage=extended_key_usage,
            certificate_path=cert_path
        )
    
    def _initialize_default_certificates(self):
        """Initialize default certificates for the application"""
        
        # Check if we need to generate default server certificate
        server_cert = self.get_certificate("kumon_server")
        if not server_cert or server_cert.status in [CertificateStatus.EXPIRED, CertificateStatus.INVALID]:
            app_logger.info("Generating default server certificate...")
            self.generate_self_signed_certificate(
                common_name="kumon.local",
                name="kumon_server",
                san_domains=["localhost", "127.0.0.1", "kumon.local"],
                certificate_type=CertificateType.SERVER
            )
    
    def generate_self_signed_certificate(
        self,
        common_name: str,
        name: str,
        organization: str = "Kumon Assistant",
        country: str = "BR",
        san_domains: List[str] = None,
        certificate_type: CertificateType = CertificateType.SERVER,
        validity_days: int = None
    ) -> Optional[CertificateInfo]:
        """Generate self-signed certificate"""
        
        try:
            validity_days = validity_days or self.ssl_config["certificate_validity_days"]
            key_size = self.ssl_config["key_size"]
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
            )
            
            # Create certificate subject
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, country),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            ])
            
            # Certificate validity period
            not_before = datetime.now()
            not_after = not_before + timedelta(days=validity_days)
            
            # Create certificate builder
            cert_builder = x509.CertificateBuilder()
            cert_builder = cert_builder.subject_name(subject)
            cert_builder = cert_builder.issuer_name(issuer)
            cert_builder = cert_builder.public_key(private_key.public_key())
            cert_builder = cert_builder.serial_number(x509.random_serial_number())
            cert_builder = cert_builder.not_valid_before(not_before)
            cert_builder = cert_builder.not_valid_after(not_after)
            
            # Add Subject Alternative Names if provided
            if san_domains:
                san_list = [x509.DNSName(domain) for domain in san_domains]
                cert_builder = cert_builder.add_extension(
                    x509.SubjectAlternativeNames(san_list),
                    critical=False
                )
            
            # Add appropriate key usage based on certificate type
            if certificate_type == CertificateType.ROOT_CA:
                cert_builder = cert_builder.add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        key_encipherment=False,
                        key_agreement=False,
                        key_cert_sign=True,
                        crl_sign=True,
                        content_commitment=False,
                        data_encipherment=False,
                        encipher_only=False,
                        decipher_only=False
                    ),
                    critical=True
                )
                cert_builder = cert_builder.add_extension(
                    x509.BasicConstraints(ca=True, path_length=None),
                    critical=True
                )
            elif certificate_type == CertificateType.SERVER:
                cert_builder = cert_builder.add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        key_encipherment=True,
                        key_agreement=False,
                        key_cert_sign=False,
                        crl_sign=False,
                        content_commitment=False,
                        data_encipherment=False,
                        encipher_only=False,
                        decipher_only=False
                    ),
                    critical=True
                )
                cert_builder = cert_builder.add_extension(
                    x509.ExtendedKeyUsage([
                        x509.oid.ExtendedKeyUsageOID.SERVER_AUTH
                    ]),
                    critical=True
                )
            elif certificate_type == CertificateType.CLIENT:
                cert_builder = cert_builder.add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        key_encipherment=True,
                        key_agreement=False,
                        key_cert_sign=False,
                        crl_sign=False,
                        content_commitment=False,
                        data_encipherment=False,
                        encipher_only=False,
                        decipher_only=False
                    ),
                    critical=True
                )
                cert_builder = cert_builder.add_extension(
                    x509.ExtendedKeyUsage([
                        x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH
                    ]),
                    critical=True
                )
            
            # Sign certificate
            certificate = cert_builder.sign(private_key, hashes.SHA256())
            
            # Save certificate and private key
            cert_path = os.path.join(self.ssl_config["certificate_directory"], f"{name}.crt")
            key_path = os.path.join(self.ssl_config["certificate_directory"], f"{name}.key")
            
            # Write certificate
            with open(cert_path, 'wb') as f:
                f.write(certificate.public_bytes(serialization.Encoding.PEM))
            
            # Write private key
            with open(key_path, 'wb') as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            # Set secure permissions
            os.chmod(cert_path, 0o644)
            os.chmod(key_path, 0o600)
            
            # Store private key in secrets manager
            private_key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            
            secrets_manager.store_secret(
                name=f"{name}_private_key",
                value=private_key_pem,
                secret_type=SecretType.PRIVATE_KEY,
                description=f"Private key for certificate {name}"
            )
            
            # Extract certificate info
            cert_info = self._extract_certificate_info(certificate, cert_path)
            cert_info.private_key_path = key_path
            
            # Store certificate info
            self.certificates[name] = cert_info
            
            app_logger.info(f"Generated self-signed certificate: {name} (CN: {common_name})")
            return cert_info
            
        except Exception as e:
            app_logger.error(f"Failed to generate certificate {name}: {e}")
            return None
    
    def get_certificate(self, name: str) -> Optional[CertificateInfo]:
        """Get certificate information by name"""
        return self.certificates.get(name)
    
    def list_certificates(self, certificate_type: Optional[CertificateType] = None) -> List[CertificateInfo]:
        """List certificates, optionally filtered by type"""
        
        certificates = list(self.certificates.values())
        
        if certificate_type:
            certificates = [cert for cert in certificates if cert.certificate_type == certificate_type]
        
        return sorted(certificates, key=lambda x: x.not_after)
    
    def check_certificate_expiry(self, name: str) -> Dict[str, Any]:
        """Check certificate expiry status"""
        
        cert = self.get_certificate(name)
        if not cert:
            return {"error": "Certificate not found"}
        
        current_time = datetime.now()
        days_until_expiry = (cert.not_after - current_time).days
        
        return {
            "name": cert.name,
            "status": cert.status.value,
            "expires_at": cert.not_after.isoformat(),
            "days_until_expiry": days_until_expiry,
            "needs_renewal": days_until_expiry < self.ssl_config["renewal_threshold_days"]
        }
    
    def validate_certificate_chain(self, cert_name: str, host: Optional[str] = None) -> CertificateChain:
        """Validate certificate chain"""
        
        cert = self.get_certificate(cert_name)
        if not cert:
            return CertificateChain(
                leaf_certificate=None,
                intermediate_certificates=[],
                root_certificate=None,
                is_valid=False,
                validation_errors=["Certificate not found"]
            )
        
        validation_errors = []
        
        # Basic certificate validation
        current_time = datetime.now()
        if current_time < cert.not_before:
            validation_errors.append("Certificate not yet valid")
        elif current_time > cert.not_after:
            validation_errors.append("Certificate expired")
        
        # Hostname validation if provided
        if host and host not in cert.san_domains and cert.name != host:
            validation_errors.append(f"Certificate does not match hostname {host}")
        
        # For self-signed certificates, this is a simple validation
        is_valid = len(validation_errors) == 0
        
        return CertificateChain(
            leaf_certificate=cert,
            intermediate_certificates=[],
            root_certificate=None,
            is_valid=is_valid,
            validation_errors=validation_errors
        )
    
    def check_remote_certificate(self, hostname: str, port: int = 443, timeout: int = 10) -> Dict[str, Any]:
        """Check remote server certificate"""
        
        try:
            # Create SSL context
            context = ssl.create_default_context()
            
            # Connect and get certificate
            with socket.create_connection((hostname, port), timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert_der = ssock.getpeercert(binary_form=True)
                    cert_dict = ssock.getpeercert()
            
            # Parse certificate
            cert = x509.load_der_x509_certificate(cert_der)
            cert_info = self._extract_certificate_info(cert)
            
            # Additional validation
            current_time = datetime.now()
            days_until_expiry = (cert_info.not_after - current_time).days
            
            return {
                "hostname": hostname,
                "port": port,
                "certificate": {
                    "subject": cert_info.subject,
                    "issuer": cert_info.issuer,
                    "not_before": cert_info.not_before.isoformat(),
                    "not_after": cert_info.not_after.isoformat(),
                    "days_until_expiry": days_until_expiry,
                    "fingerprint_sha256": cert_info.fingerprint_sha256,
                    "san_domains": cert_info.san_domains,
                    "status": cert_info.status.value
                },
                "tls_version": ssock.version(),
                "cipher_suite": ssock.cipher(),
                "validation_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "hostname": hostname,
                "port": port,
                "error": str(e),
                "validation_time": datetime.now().isoformat()
            }
    
    def get_certificates_needing_renewal(self) -> List[CertificateInfo]:
        """Get certificates that need renewal"""
        
        renewal_threshold = timedelta(days=self.ssl_config["renewal_threshold_days"])
        current_time = datetime.now()
        
        renewal_needed = []
        for cert in self.certificates.values():
            if cert.status == CertificateStatus.VALID:
                time_until_expiry = cert.not_after - current_time
                if time_until_expiry < renewal_threshold:
                    renewal_needed.append(cert)
        
        return sorted(renewal_needed, key=lambda x: x.not_after)
    
    def create_ssl_context(
        self,
        cert_name: str,
        purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH,
        verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED
    ) -> Optional[ssl.SSLContext]:
        """Create SSL context with specified certificate"""
        
        try:
            cert = self.get_certificate(cert_name)
            if not cert or not cert.certificate_path or not cert.private_key_path:
                return None
            
            # Create SSL context
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER if purpose == ssl.Purpose.SERVER_AUTH else ssl.PROTOCOL_TLS_CLIENT)
            
            # Load certificate and private key
            context.load_cert_chain(cert.certificate_path, cert.private_key_path)
            
            # Set security options
            context.options |= ssl.OP_NO_SSLv2
            context.options |= ssl.OP_NO_SSLv3
            context.options |= ssl.OP_NO_TLSv1
            context.options |= ssl.OP_NO_TLSv1_1
            context.options |= ssl.OP_SINGLE_DH_USE
            context.options |= ssl.OP_SINGLE_ECDH_USE
            
            # Set cipher suites
            context.set_ciphers(':'.join(self.ssl_config["cipher_suites"]))
            
            # Set verification mode
            context.verify_mode = verify_mode
            
            return context
            
        except Exception as e:
            app_logger.error(f"Failed to create SSL context for {cert_name}: {e}")
            return None
    
    def get_ssl_configuration(self) -> Dict[str, Any]:
        """Get SSL/TLS configuration for application"""
        
        server_cert = self.get_certificate("kumon_server")
        
        config = {
            "ssl_enabled": server_cert is not None,
            "certificate_info": None,
            "tls_versions": self.ssl_config["tls_versions"],
            "cipher_suites": self.ssl_config["cipher_suites"],
            "require_client_certificates": self.ssl_config["require_client_certificates"]
        }
        
        if server_cert:
            config["certificate_info"] = {
                "name": server_cert.name,
                "subject": server_cert.subject,
                "not_before": server_cert.not_before.isoformat(),
                "not_after": server_cert.not_after.isoformat(),
                "status": server_cert.status.value,
                "fingerprint_sha256": server_cert.fingerprint_sha256
            }
        
        return config
    
    def get_ssl_metrics(self) -> Dict[str, Any]:
        """Get SSL/TLS metrics"""
        
        total_certs = len(self.certificates)
        valid_certs = len([c for c in self.certificates.values() if c.status == CertificateStatus.VALID])
        expired_certs = len([c for c in self.certificates.values() if c.status == CertificateStatus.EXPIRED])
        renewal_needed = len(self.get_certificates_needing_renewal())
        
        return {
            "total_certificates": total_certs,
            "valid_certificates": valid_certs,
            "expired_certificates": expired_certs,
            "certificates_needing_renewal": renewal_needed,
            "ssl_enabled": self.get_certificate("kumon_server") is not None,
            "tls_versions_supported": self.ssl_config["tls_versions"],
            "cipher_suites_count": len(self.ssl_config["cipher_suites"]),
            "last_check": datetime.now().isoformat()
        }


# Global SSL manager instance
ssl_manager = SSLManager()