"""
Startup validation for production deployment
Ensures all critical systems are properly configured
"""

import os
import sys
import asyncio
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime

try:
    from .config import settings
    from .logger import app_logger
except ImportError:
    # Fallback for direct execution
    import warnings
    warnings.warn("Could not import settings or logger - using fallback configuration")
    
    class MockSettings:
        ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        VALIDATE_API_KEYS = os.getenv("VALIDATE_API_KEYS", "true").lower() == "true"
        JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
        BUSINESS_PHONE = os.getenv("BUSINESS_PHONE", "")
        BUSINESS_EMAIL = os.getenv("BUSINESS_EMAIL", "")
    
    settings = MockSettings()
    
    class MockLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def error(self, msg): print(f"ERROR: {msg}")
        def warning(self, msg): print(f"WARNING: {msg}")
    
    app_logger = MockLogger()

class ValidationResult:
    """Result of a validation check"""
    def __init__(self, success: bool, message: str, details: Dict[str, Any] = None):
        self.success = success
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now()

class StartupValidator:
    """Comprehensive startup validation system"""
    
    def __init__(self):
        self.validation_results: List[ValidationResult] = []
        self.critical_failures: List[str] = []
        self.warnings: List[str] = []
    
    async def validate_startup_requirements(self) -> bool:
        """
        Validate all startup requirements
        Returns True if all validations pass, False otherwise
        """
        app_logger.info("🔍 Starting comprehensive startup validation...")
        
        # Run all validation checks
        validations = [
            ("Environment Configuration", self._validate_environment()),
            ("Critical Secrets", self._validate_secrets()),
            ("Database Connections", self._validate_database_connections()),
            ("External Services", self._validate_external_services()),
            ("Business Configuration", self._validate_business_configuration()),
            ("Security Configuration", self._validate_security_configuration()),
            ("Performance Settings", self._validate_performance_settings())
        ]
        
        success_count = 0
        total_count = len(validations)
        
        for validation_name, validation_coro in validations:
            try:
                app_logger.info(f"🔎 Validating {validation_name}...")
                result = await validation_coro
                self.validation_results.append(result)
                
                if result.success:
                    success_count += 1
                    app_logger.info(f"✅ {validation_name}: {result.message}")
                else:
                    self.critical_failures.append(f"{validation_name}: {result.message}")
                    app_logger.error(f"❌ {validation_name}: {result.message}")
                    
            except Exception as e:
                error_msg = f"{validation_name} validation failed: {str(e)}"
                self.critical_failures.append(error_msg)
                app_logger.error(f"💥 {error_msg}")
        
        # Summary
        success_rate = (success_count / total_count) * 100
        app_logger.info(f"📊 Startup validation completed: {success_count}/{total_count} checks passed ({success_rate:.1f}%)")
        
        if self.critical_failures:
            app_logger.error("🚨 CRITICAL STARTUP FAILURES:")
            for failure in self.critical_failures:
                app_logger.error(f"   • {failure}")
            app_logger.error("💀 APPLICATION CANNOT START - Fix critical issues above")
            return False
        
        if self.warnings:
            app_logger.warning("⚠️ STARTUP WARNINGS:")
            for warning in self.warnings:
                app_logger.warning(f"   • {warning}")
        
        app_logger.info("🚀 All startup validations passed - Application ready!")
        return True
    
    async def _validate_environment(self) -> ValidationResult:
        """Validate environment configuration"""
        issues = []
        
        # Check environment setting
        if not settings.ENVIRONMENT:
            issues.append("ENVIRONMENT not set")
        elif settings.ENVIRONMENT not in ["development", "production", "testing"]:
            issues.append(f"Invalid ENVIRONMENT: {settings.ENVIRONMENT}")
        
        # Production-specific checks
        if settings.ENVIRONMENT == "production":
            if settings.DEBUG:
                issues.append("DEBUG must be False in production")
            
            if not settings.VALIDATE_API_KEYS:
                issues.append("VALIDATE_API_KEYS must be True in production")
            
            if not getattr(settings, 'REQUIRE_HTTPS', False):
                self.warnings.append("REQUIRE_HTTPS not enabled in production")
        
        if issues:
            return ValidationResult(False, f"Environment issues: {', '.join(issues)}")
        
        return ValidationResult(True, f"Environment properly configured: {settings.ENVIRONMENT}")
    
    async def _validate_secrets(self) -> ValidationResult:
        """Validate critical secrets are configured"""
        missing_secrets = []
        
        # Critical secrets for operation
        required_secrets = [
            ("JWT_SECRET_KEY", settings.JWT_SECRET_KEY),
            ("OPENAI_API_KEY", settings.OPENAI_API_KEY),
            ("EVOLUTION_API_KEY", settings.EVOLUTION_API_KEY),
        ]
        
        for name, value in required_secrets:
            if not value or value.strip() == "":
                missing_secrets.append(name)
        
        # Validate secret formats
        if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith('sk-'):
            missing_secrets.append("OPENAI_API_KEY (invalid format)")
        
        if settings.JWT_SECRET_KEY and len(settings.JWT_SECRET_KEY) < 32:
            missing_secrets.append("JWT_SECRET_KEY (too short)")
        
        if missing_secrets:
            return ValidationResult(
                False, 
                f"Missing or invalid secrets: {', '.join(missing_secrets)}",
                {"missing_secrets": missing_secrets}
            )
        
        return ValidationResult(True, "All critical secrets configured")
    
    async def _validate_database_connections(self) -> ValidationResult:
        """Validate database connections"""
        try:
            # Check if database URL is configured
            database_url = getattr(settings, 'DATABASE_URL', None) or os.getenv('DATABASE_URL')
            if not database_url:
                return ValidationResult(False, "DATABASE_URL not configured")
            
            # Check Redis URL if used
            redis_url = getattr(settings, 'MEMORY_REDIS_URL', None) or os.getenv('MEMORY_REDIS_URL')
            if not redis_url:
                self.warnings.append("Redis URL not configured - some features may be limited")
            
            # In a real implementation, you would test actual connections here
            # For now, just validate URL formats
            if 'postgresql://' not in database_url and 'postgres://' not in database_url:
                return ValidationResult(False, "Invalid PostgreSQL URL format")
            
            return ValidationResult(True, "Database configuration validated")
            
        except Exception as e:
            return ValidationResult(False, f"Database validation error: {str(e)}")
    
    async def _validate_external_services(self) -> ValidationResult:
        """Validate external service connectivity"""
        issues = []
        
        # Check Evolution API URL
        evolution_url = getattr(settings, 'EVOLUTION_API_URL', None)
        if not evolution_url:
            issues.append("Evolution API URL not configured")
        elif not evolution_url.startswith(('http://', 'https://')):
            issues.append("Invalid Evolution API URL format")
        
        # Check Google Calendar configuration (optional)
        google_calendar_id = getattr(settings, 'GOOGLE_CALENDAR_ID', None)
        if not google_calendar_id:
            self.warnings.append("Google Calendar ID not configured")
        
        if issues:
            return ValidationResult(False, f"External service issues: {', '.join(issues)}")
        
        return ValidationResult(True, "External services configuration validated")
    
    async def _validate_business_configuration(self) -> ValidationResult:
        """Validate business-specific configuration"""
        missing_config = []
        
        # Check business contact information
        if not settings.BUSINESS_PHONE:
            missing_config.append("BUSINESS_PHONE")
        
        if not settings.BUSINESS_EMAIL:
            missing_config.append("BUSINESS_EMAIL")
        
        business_name = getattr(settings, 'BUSINESS_NAME', None)
        if not business_name:
            missing_config.append("BUSINESS_NAME")
        
        if missing_config:
            return ValidationResult(
                False, 
                f"Missing business configuration: {', '.join(missing_config)}"
            )
        
        return ValidationResult(True, "Business configuration complete")
    
    async def _validate_security_configuration(self) -> ValidationResult:
        """Validate security configuration"""
        security_issues = []
        
        # Check security settings
        if settings.ENVIRONMENT == "production":
            if settings.DEBUG:
                security_issues.append("Debug mode enabled in production")
            
            # Check for secure settings
            require_https = getattr(settings, 'REQUIRE_HTTPS', False)
            if not require_https:
                security_issues.append("HTTPS not required in production")
            
            validate_keys = getattr(settings, 'VALIDATE_API_KEYS', False)
            if not validate_keys:
                security_issues.append("API key validation disabled")
        
        if security_issues:
            return ValidationResult(False, f"Security issues: {', '.join(security_issues)}")
        
        return ValidationResult(True, "Security configuration validated")
    
    async def _validate_performance_settings(self) -> ValidationResult:
        """Validate performance configuration"""
        warnings = []
        
        # Check LLM budget settings
        budget = getattr(settings, 'LLM_DAILY_BUDGET_BRL', 0)
        if budget <= 0:
            warnings.append("LLM daily budget not configured")
        elif budget > 10:
            warnings.append(f"LLM daily budget high: R${budget}")
        
        # Check timeout settings
        timeout = getattr(settings, 'LLM_REQUEST_TIMEOUT_SECONDS', 30)
        if timeout > 60:
            warnings.append(f"LLM timeout very high: {timeout}s")
        
        # Add warnings to global list
        self.warnings.extend(warnings)
        
        return ValidationResult(True, "Performance settings reviewed")

# Global validator instance
_startup_validator = None

async def validate_startup_requirements() -> bool:
    """
    Main entry point for startup validation
    Returns True if all validations pass, False otherwise
    """
    global _startup_validator
    
    if _startup_validator is None:
        _startup_validator = StartupValidator()
    
    return await _startup_validator.validate_startup_requirements()

def get_validation_results() -> List[ValidationResult]:
    """Get detailed validation results"""
    global _startup_validator
    return _startup_validator.validation_results if _startup_validator else []

# CLI execution support
if __name__ == "__main__":
    async def main():
        success = await validate_startup_requirements()
        sys.exit(0 if success else 1)
    
    asyncio.run(main())