"""
Security Audit Logger - Phase 3 Security Hardening

Comprehensive audit logging system with:
- Security event tracking
- User activity monitoring
- System access auditing
- Compliance reporting
- Log integrity verification
- Threat intelligence integration
"""

import json
import hashlib
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
import threading
from queue import Queue, Empty
import gzip
import os

from ..core.logger import app_logger
from .encryption_service import encryption_service


class AuditEventType(Enum):
    """Types of audit events"""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTRATION = "user_registration"
    PASSWORD_CHANGE = "password_change"
    PERMISSION_CHANGE = "permission_change"
    SYSTEM_ACCESS = "system_access"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SECURITY_VIOLATION = "security_violation"
    AUTHENTICATION_FAILURE = "authentication_failure"
    CONFIGURATION_CHANGE = "configuration_change"
    PRIVILEGED_OPERATION = "privileged_operation"
    API_ACCESS = "api_access"
    FILE_ACCESS = "file_access"
    SYSTEM_ERROR = "system_error"


class AuditSeverity(Enum):
    """Audit event severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditOutcome(Enum):
    """Audit event outcomes"""
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    ERROR = "error"


@dataclass
class AuditEvent:
    """Audit event record"""
    event_id: str
    timestamp: datetime
    event_type: AuditEventType
    severity: AuditSeverity
    outcome: AuditOutcome
    user_id: Optional[str] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0
    tags: List[str] = field(default_factory=list)
    correlation_id: Optional[str] = None


@dataclass
class AuditLogFile:
    """Audit log file metadata"""
    filename: str
    start_time: datetime
    end_time: Optional[datetime]
    event_count: int = 0
    file_size: int = 0
    checksum: Optional[str] = None
    compressed: bool = False
    encrypted: bool = False


class AuditLogger:
    """
    Comprehensive security audit logging system
    
    Features:
    - Real-time audit event logging
    - Log file rotation and compression
    - Log integrity verification
    - Compliance reporting
    - Threat intelligence correlation
    - Performance monitoring
    """
    
    def __init__(self, log_directory: str = "audit_logs"):
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(exist_ok=True)
        
        # Configuration
        self.config = {
            "max_log_file_size": 100 * 1024 * 1024,  # 100MB
            "max_log_files": 365,  # Keep 1 year of logs
            "enable_compression": True,
            "enable_encryption": True,
            "enable_integrity_check": True,
            "batch_size": 100,
            "flush_interval_seconds": 60,
            "enable_real_time_alerts": True
        }
        
        # Current log file
        self.current_log_file = None
        self.current_log_metadata = None
        
        # Event queue for batch processing
        self.event_queue = Queue()
        self.log_worker_thread = None
        self.shutdown_flag = threading.Event()
        
        # Statistics
        self.stats = {
            "total_events": 0,
            "events_by_type": {},
            "events_by_severity": {},
            "events_by_outcome": {},
            "last_event_time": None,
            "log_files_created": 0,
            "bytes_logged": 0
        }
        
        # Initialize logging
        self._initialize_logging()
        
        app_logger.info("Security Audit Logger initialized")
    
    def _initialize_logging(self):
        """Initialize audit logging system"""
        
        try:
            # Create new log file
            self._create_new_log_file()
            
            # Start background logging thread
            self._start_log_worker()
            
        except Exception as e:
            app_logger.error(f"Failed to initialize audit logging: {e}")
    
    def _create_new_log_file(self):
        """Create a new audit log file"""
        
        try:
            current_time = datetime.now()
            filename = f"audit_{current_time.strftime('%Y%m%d_%H%M%S')}.log"
            filepath = self.log_directory / filename
            
            # Close current log file if exists
            if self.current_log_file:
                self._finalize_log_file()
            
            # Create new log file
            self.current_log_file = open(filepath, 'w', encoding='utf-8')
            self.current_log_metadata = AuditLogFile(
                filename=filename,
                start_time=current_time,
                end_time=None
            )
            
            # Write header
            header = {
                "log_format": "kumon_audit_v1",
                "start_time": current_time.isoformat(),
                "hostname": os.uname().nodename if hasattr(os, 'uname') else "unknown",
                "version": "1.0"
            }
            
            self._write_log_entry(header)
            self.stats["log_files_created"] += 1
            
        except Exception as e:
            app_logger.error(f"Failed to create audit log file: {e}")
    
    def _finalize_log_file(self):
        """Finalize current log file"""
        
        try:
            if not self.current_log_file or not self.current_log_metadata:
                return
            
            # Write footer
            footer = {
                "log_finalized": True,
                "end_time": datetime.now().isoformat(),
                "total_events": self.current_log_metadata.event_count
            }
            
            self._write_log_entry(footer)
            
            # Close file
            self.current_log_file.close()
            
            # Update metadata
            filepath = self.log_directory / self.current_log_metadata.filename
            self.current_log_metadata.end_time = datetime.now()
            self.current_log_metadata.file_size = filepath.stat().st_size
            
            # Calculate checksum
            if self.config["enable_integrity_check"]:
                self.current_log_metadata.checksum = self._calculate_file_checksum(filepath)
            
            # Compress if enabled
            if self.config["enable_compression"]:
                self._compress_log_file(filepath)
            
            # Encrypt if enabled
            if self.config["enable_encryption"]:
                self._encrypt_log_file(filepath)
            
            app_logger.info(f"Finalized audit log: {self.current_log_metadata.filename}")
            
        except Exception as e:
            app_logger.error(f"Failed to finalize audit log file: {e}")
    
    def _write_log_entry(self, entry: Dict[str, Any]):
        """Write entry to current log file"""
        
        try:
            if not self.current_log_file:
                return
            
            # Add timestamp if not present
            if "timestamp" not in entry:
                entry["timestamp"] = datetime.now().isoformat()
            
            # Write JSON line
            json_line = json.dumps(entry, default=str, separators=(',', ':'))
            self.current_log_file.write(json_line + '\n')
            self.current_log_file.flush()
            
            # Update metadata
            if self.current_log_metadata:
                self.current_log_metadata.event_count += 1
            
            self.stats["bytes_logged"] += len(json_line) + 1
            
        except Exception as e:
            app_logger.error(f"Failed to write audit log entry: {e}")
    
    def _start_log_worker(self):
        """Start background thread for processing audit events"""
        
        def log_worker():
            batch = []
            last_flush = time.time()
            
            while not self.shutdown_flag.is_set():
                try:
                    # Get events from queue
                    try:
                        event = self.event_queue.get(timeout=1)
                        batch.append(event)
                    except Empty:
                        pass
                    
                    current_time = time.time()
                    
                    # Flush batch if full or time interval reached
                    if (len(batch) >= self.config["batch_size"] or 
                        (batch and current_time - last_flush >= self.config["flush_interval_seconds"])):
                        
                        self._flush_batch(batch)
                        batch.clear()
                        last_flush = current_time
                    
                    # Check if log rotation is needed
                    self._check_log_rotation()
                    
                except Exception as e:
                    app_logger.error(f"Audit log worker error: {e}")
            
            # Flush remaining events on shutdown
            if batch:
                self._flush_batch(batch)
        
        self.log_worker_thread = threading.Thread(target=log_worker, daemon=True)
        self.log_worker_thread.start()
    
    def _flush_batch(self, batch: List[AuditEvent]):
        """Flush batch of audit events to log file"""
        
        try:
            for event in batch:
                # Convert to dictionary
                log_entry = asdict(event)
                
                # Convert datetime objects to ISO format
                if isinstance(log_entry["timestamp"], datetime):
                    log_entry["timestamp"] = log_entry["timestamp"].isoformat()
                
                # Convert enums to values
                log_entry["event_type"] = log_entry["event_type"].value
                log_entry["severity"] = log_entry["severity"].value
                log_entry["outcome"] = log_entry["outcome"].value
                
                # Write to log file
                self._write_log_entry(log_entry)
                
                # Update statistics
                self._update_statistics(event)
            
        except Exception as e:
            app_logger.error(f"Failed to flush audit log batch: {e}")
    
    def _check_log_rotation(self):
        """Check if log file rotation is needed"""
        
        try:
            if not self.current_log_file or not self.current_log_metadata:
                return
            
            filepath = self.log_directory / self.current_log_metadata.filename
            
            # Check file size
            if filepath.stat().st_size >= self.config["max_log_file_size"]:
                app_logger.info("Rotating audit log file due to size limit")
                self._create_new_log_file()
                return
            
            # Check time (rotate daily)
            if (datetime.now() - self.current_log_metadata.start_time).days >= 1:
                app_logger.info("Rotating audit log file due to time limit")
                self._create_new_log_file()
                return
            
            # Clean up old log files
            self._cleanup_old_logs()
            
        except Exception as e:
            app_logger.error(f"Log rotation check error: {e}")
    
    def _cleanup_old_logs(self):
        """Clean up old audit log files"""
        
        try:
            # Get all log files sorted by creation time
            log_files = []
            for filepath in self.log_directory.glob("audit_*.log*"):
                stat = filepath.stat()
                log_files.append((filepath, stat.st_mtime))
            
            log_files.sort(key=lambda x: x[1], reverse=True)
            
            # Remove files exceeding the limit
            if len(log_files) > self.config["max_log_files"]:
                for filepath, _ in log_files[self.config["max_log_files"]:]:
                    app_logger.info(f"Removing old audit log: {filepath.name}")
                    filepath.unlink()
            
        except Exception as e:
            app_logger.error(f"Audit log cleanup error: {e}")
    
    def _calculate_file_checksum(self, filepath: Path) -> str:
        """Calculate SHA-256 checksum of log file"""
        
        try:
            hash_sha256 = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
            
        except Exception as e:
            app_logger.error(f"Checksum calculation error: {e}")
            return None
    
    def _compress_log_file(self, filepath: Path):
        """Compress log file using gzip"""
        
        try:
            compressed_path = filepath.with_suffix(filepath.suffix + '.gz')
            
            with open(filepath, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    f_out.writelines(f_in)
            
            # Remove original file
            filepath.unlink()
            
            if self.current_log_metadata:
                self.current_log_metadata.compressed = True
                self.current_log_metadata.filename = compressed_path.name
            
        except Exception as e:
            app_logger.error(f"Log compression error: {e}")
    
    def _encrypt_log_file(self, filepath: Path):
        """Encrypt log file"""
        
        try:
            # Read file content
            with open(filepath, 'rb') as f:
                content = f.read()
            
            # Encrypt content
            encrypted_data = encryption_service.encrypt_data(
                content, 
                encryption_service.EncryptionPurpose.FILE_STORAGE
            )
            
            # Write encrypted file
            encrypted_path = filepath.with_suffix(filepath.suffix + '.enc')
            with open(encrypted_path, 'wb') as f:
                # Store encryption metadata
                metadata = {
                    "algorithm": encrypted_data.algorithm.value,
                    "key_id": encrypted_data.key_id,
                    "encrypted_at": encrypted_data.encrypted_at.isoformat()
                }
                
                f.write(json.dumps(metadata).encode('utf-8') + b'\n---\n')
                f.write(encrypted_data.ciphertext)
                
                if encrypted_data.iv_or_nonce:
                    f.write(b'\n---\n')
                    f.write(encrypted_data.iv_or_nonce)
                
                if encrypted_data.auth_tag:
                    f.write(b'\n---\n')
                    f.write(encrypted_data.auth_tag)
            
            # Remove original file
            filepath.unlink()
            
            if self.current_log_metadata:
                self.current_log_metadata.encrypted = True
                self.current_log_metadata.filename = encrypted_path.name
            
        except Exception as e:
            app_logger.error(f"Log encryption error: {e}")
    
    def _update_statistics(self, event: AuditEvent):
        """Update audit statistics"""
        
        self.stats["total_events"] += 1
        self.stats["last_event_time"] = event.timestamp
        
        # Update by type
        event_type = event.event_type.value
        self.stats["events_by_type"][event_type] = self.stats["events_by_type"].get(event_type, 0) + 1
        
        # Update by severity
        severity = event.severity.value
        self.stats["events_by_severity"][severity] = self.stats["events_by_severity"].get(severity, 0) + 1
        
        # Update by outcome
        outcome = event.outcome.value
        self.stats["events_by_outcome"][outcome] = self.stats["events_by_outcome"].get(outcome, 0) + 1
    
    def log_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity,
        outcome: AuditOutcome,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        risk_score: float = 0.0,
        tags: Optional[List[str]] = None,
        correlation_id: Optional[str] = None
    ):
        """Log an audit event"""
        
        try:
            # Generate event ID
            import uuid
            event_id = str(uuid.uuid4())
            
            # Create audit event
            event = AuditEvent(
                event_id=event_id,
                timestamp=datetime.now(),
                event_type=event_type,
                severity=severity,
                outcome=outcome,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
                resource=resource,
                action=action,
                details=details or {},
                risk_score=risk_score,
                tags=tags or [],
                correlation_id=correlation_id
            )
            
            # Add to queue for processing
            self.event_queue.put(event)
            
            # Real-time alerts for critical events
            if (self.config["enable_real_time_alerts"] and 
                severity == AuditSeverity.CRITICAL):
                self._send_real_time_alert(event)
            
        except Exception as e:
            app_logger.error(f"Failed to log audit event: {e}")
    
    def _send_real_time_alert(self, event: AuditEvent):
        """Send real-time alert for critical events"""
        
        try:
            alert_message = (
                f"CRITICAL AUDIT EVENT: {event.event_type.value} "
                f"by {event.username or 'unknown'} "
                f"from {event.ip_address or 'unknown'} "
                f"with outcome {event.outcome.value}"
            )
            
            app_logger.critical(alert_message)
            
            # In production, integrate with alerting systems like:
            # - Slack/Teams notifications
            # - Email alerts
            # - SIEM integration
            # - SMS alerts for super critical events
            
        except Exception as e:
            app_logger.error(f"Real-time alert error: {e}")
    
    def get_audit_statistics(self) -> Dict[str, Any]:
        """Get audit logging statistics"""
        
        return {
            "total_events": self.stats["total_events"],
            "events_by_type": dict(self.stats["events_by_type"]),
            "events_by_severity": dict(self.stats["events_by_severity"]),
            "events_by_outcome": dict(self.stats["events_by_outcome"]),
            "last_event_time": self.stats["last_event_time"].isoformat() if self.stats["last_event_time"] else None,
            "log_files_created": self.stats["log_files_created"],
            "bytes_logged": self.stats["bytes_logged"],
            "current_log_file": self.current_log_metadata.filename if self.current_log_metadata else None,
            "queue_size": self.event_queue.qsize(),
            "configuration": dict(self.config)
        }
    
    def search_events(
        self,
        event_type: Optional[AuditEventType] = None,
        severity: Optional[AuditSeverity] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search audit events (simplified implementation)"""
        
        # In production, implement with proper database/search engine
        # For now, return empty list as file-based search would be complex
        
        return []
    
    def shutdown(self):
        """Shutdown audit logging system"""
        
        try:
            app_logger.info("Shutting down audit logging system...")
            
            # Signal shutdown
            self.shutdown_flag.set()
            
            # Wait for worker thread
            if self.log_worker_thread:
                self.log_worker_thread.join(timeout=5)
            
            # Finalize current log file
            self._finalize_log_file()
            
            app_logger.info("Audit logging system shutdown complete")
            
        except Exception as e:
            app_logger.error(f"Audit logging shutdown error: {e}")


# Global audit logger instance
audit_logger = AuditLogger()