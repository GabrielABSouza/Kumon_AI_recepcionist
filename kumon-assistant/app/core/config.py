"""
Configuration settings for the Kumon AI Receptionist
Production-ready configuration with environment validation
"""
from pydantic_settings import BaseSettings
from pydantic import EmailStr, validator, Field
from typing import Optional, List, Dict, Any
import os
import sys
from enum import Enum


class Environment(str, Enum):
    """Application environment types"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    """Application settings"""
    
    # Environment Configuration
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    PROJECT_NAME: str = "Kumon AI Receptionist" 
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Production Configuration Validation
    REQUIRE_HTTPS: bool = True
    VALIDATE_API_KEYS: bool = True
    ENABLE_HEALTH_CHECKS: bool = True
    
    # Evolution API Configuration
    EVOLUTION_API_URL: str = "https://evolution-api.railway.app"
    EVOLUTION_API_KEY: str = ""
    EVOLUTION_GLOBAL_API_KEY: str = ""
    AUTHENTICATION_API_KEY: str = ""
    WEBHOOK_GLOBAL_URL: str = ""
    WEBHOOK_GLOBAL_ENABLED: bool = True
    CONFIG_SESSION_PHONE_CLIENT: str = "Kumon Assistant"
    
    # LLM Providers Configuration
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    
    # Anthropic Configuration  
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"
    
    # Twilio Configuration (WhatsApp/SMS Fallback)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = ""
    TWILIO_SMS_FROM: str = ""
    
    # LLM Service Configuration
    LLM_DAILY_BUDGET_BRL: float = 5.00
    LLM_COST_ALERT_THRESHOLD_BRL: float = 4.00
    LLM_CIRCUIT_BREAKER_THRESHOLD: int = 5
    LLM_REQUEST_TIMEOUT_SECONDS: int = 30
    
    # Embeddings Configuration - Hybrid Approach
    USE_GCP_EMBEDDINGS: bool = True  # Enable Gemini fallback (PAID - $0.025/1k chars)
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # Primary model
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_CACHE_DIR: str = "./cache/embeddings"
    
    # GCP Configuration (for Gemini fallback)
    GOOGLE_PROJECT_ID: str = ""
    GOOGLE_LOCATION: str = "us-central1"
    
    # Cache Management Settings (Added for memory optimization)
    EMBEDDING_CACHE_SIZE_MB: int = 50  # 50MB cache limit for production
    EMBEDDING_CACHE_FILES: int = 500   # Max 500 cached files
    CACHE_CLEANUP_INTERVAL: int = 1800  # 30 minutes cleanup interval
    
    # Conversation Flow Memory Management
    MAX_ACTIVE_CONVERSATIONS: int = 500  # Limit active conversations
    CONVERSATION_TIMEOUT_HOURS: int = 12  # 12 hours timeout for inactive conversations
    CONVERSATION_CLEANUP_INTERVAL: int = 1800  # 30 minutes cleanup interval
    
    # Google APIs
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""  # Base64 encoded service account JSON
    GOOGLE_CREDENTIALS_PATH: str = "google-service-account.json"  # Fallback file path
    GOOGLE_CALENDAR_ID: str = ""
    GOOGLE_PROJECT_ID: str = ""
    GOOGLE_SHEETS_ID: str = ""
    
    # Database
    DATABASE_URL: str = Field(default="", env="DATABASE_URL")
    
    # Database Connection Pooling (Production Optimization)
    DB_POOL_SIZE: int = 20  # Number of persistent connections
    DB_MAX_OVERFLOW: int = 10  # Maximum overflow connections
    DB_POOL_TIMEOUT: int = 30  # Seconds to wait for connection
    DB_POOL_RECYCLE: int = 1800  # Recycle connections after 30 minutes
    DB_ECHO: bool = False  # Disable SQL echo in production
    DB_POOL_PRE_PING: bool = True  # Verify connections before use
    
    # Memory System Configuration (Redis + PostgreSQL)
    MEMORY_REDIS_URL: str = Field(default="", env="REDIS_URL")
    MEMORY_POSTGRES_URL: str = Field(default="", env="DATABASE_URL")  # Use Railway DATABASE_URL
    MEMORY_ENABLE_SYSTEM: bool = True
    
    # Redis Configuration
    MEMORY_REDIS_MAX_CONNECTIONS: int = 20
    MEMORY_ACTIVE_SESSION_TTL: int = 7 * 24 * 3600  # 7 days
    MEMORY_USER_PROFILE_TTL: int = 30 * 24 * 3600   # 30 days
    MEMORY_ANALYTICS_CACHE_TTL: int = 3600           # 1 hour
    
    # PostgreSQL Configuration for Analytics
    MEMORY_POSTGRES_MIN_POOL_SIZE: int = 5
    MEMORY_POSTGRES_MAX_POOL_SIZE: int = 20
    MEMORY_POSTGRES_COMMAND_TIMEOUT: float = 30.0
    
    # Memory Performance Settings
    MEMORY_BATCH_WRITE_SIZE: int = 100
    MEMORY_BATCH_WRITE_INTERVAL: float = 2.0  # seconds
    MEMORY_ENABLE_CLIENT_SIDE_CACHE: bool = True
    
    # Qdrant (Vector Database)
    QDRANT_URL: str = Field(default="https://qdrant-production.up.railway.app", env="QDRANT_URL")
    QDRANT_API_KEY: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    QDRANT_COLLECTION_NAME: str = "kumon_knowledge"
    
    # Email
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: EmailStr = "kumonvilaa@gmail.com"
    
    # Business Configuration
    BUSINESS_NAME: str = "Kumon Vila A"
    BUSINESS_PHONE: str = "51996921999"
    BUSINESS_EMAIL: EmailStr = "kumonvilaa@gmail.com"
    BUSINESS_ADDRESS: str = "Rua Amoreira, 571. Salas 6 e 7. Jardim das Laranjeiras"
    BUSINESS_HOURS: str = "Segunda a Sexta: 08:00 às 12:00 e 14:00 às 18:00"
    
    # Business Hours Configuration (EXACT COMPLIANCE)
    BUSINESS_HOURS_START: int = 8  # 8 AM
    BUSINESS_HOURS_END_MORNING: int = 12  # 12 PM (noon)
    BUSINESS_HOURS_START_AFTERNOON: int = 14  # 2 PM
    BUSINESS_HOURS_END: int = 18   # 6 PM
    BUSINESS_DAYS: List[int] = [0, 1, 2, 3, 4]  # Monday to Friday
    APPOINTMENT_DURATION_MINUTES: int = 60
    BUFFER_TIME_MINUTES: int = 15
    
    # Timezone
    TIMEZONE: str = "America/Sao_Paulo"
    
    # AI Configuration
    MAX_CONVERSATION_HISTORY: int = 10
    INTENT_CONFIDENCE_THRESHOLD: float = 0.7
    RAG_SIMILARITY_THRESHOLD: float = 0.8
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "app.log"
    
    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_HOSTS: str = "*"
    FRONTEND_URL: Optional[str] = None
    
    # Production Performance Configuration
    RESPONSE_TIME_TARGET: float = 5.0  # ≤5s requirement
    RESPONSE_TIME_WARNING: float = 4.0  # Warning threshold
    
    # Pricing Configuration (EXACT VALUES)
    PRICE_PER_SUBJECT: float = 375.00  # R$ 375 per subject
    ENROLLMENT_FEE: float = 100.00  # R$ 100 enrollment fee
    
    # LangSmith Configuration
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "kumon-assistant"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_TRACING_V2: bool = False
    
    # Workflow Configuration
    USE_LANGGRAPH_WORKFLOW: bool = False
    WORKFLOW_ROLLOUT_PERCENTAGE: float = 0.1
    
    # Wave 1: Streaming Configuration - Legacy removed, CeciliaWorkflow handles streaming
    # USE_STREAMING_RESPONSES: bool = True
    STREAMING_FIRST_CHUNK_TARGET_MS: int = 200
    STREAMING_TOTAL_TARGET_MS: int = 2000
    STREAMING_FALLBACK_ENABLED: bool = True
    STREAMING_SECURITY_VALIDATION: bool = True
    
    # Wave 2: Enhanced Cache Configuration
    USE_ENHANCED_CACHE: bool = True
    CACHE_L1_MAX_ENTRIES: int = 1000
    CACHE_L1_TTL_SECONDS: int = 300  # 5 minutes
    CACHE_L2_TTL_SECONDS: int = 604800  # 7 days
    CACHE_L3_TTL_SECONDS: int = 2592000  # 30 days
    CACHE_HIT_RATE_TARGET: float = 80.0
    CACHE_COMPRESSION_ENABLED: bool = True
    
    # JWT Authentication Configuration
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 30
    
    # Security Configuration (Fase 5)
    USE_SECURE_PROCESSING: bool = True
    SECURE_ROLLOUT_PERCENTAGE: float = 100.0
    SECURITY_LOGGING_ENABLED: bool = True
    SECURITY_MONITORING_ENABLED: bool = True
    
    # Security Thresholds
    SECURITY_RATE_LIMIT_PER_MINUTE: int = 50
    SECURITY_MAX_MESSAGE_LENGTH: int = 2000
    SECURITY_THREAT_THRESHOLD: float = 0.6
    SECURITY_AUTO_ESCALATION_THRESHOLD: float = 0.8
    
    # Security Features Toggle
    ENABLE_PROMPT_INJECTION_DEFENSE: bool = True
    ENABLE_DDOS_PROTECTION: bool = True
    ENABLE_SCOPE_VALIDATION: bool = True
    ENABLE_INFORMATION_PROTECTION: bool = True
    ENABLE_ADVANCED_THREAT_DETECTION: bool = True
    
    # Calendar Service Resilience Configuration
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = 30
    CIRCUIT_BREAKER_SUCCESS_THRESHOLD: int = 2
    CIRCUIT_BREAKER_TIMEOUT: int = 10
    
    # Calendar Cache Configuration
    AVAILABILITY_CACHE_TTL: int = 1800  # 30 minutes
    CONFLICT_CHECK_TTL: int = 600       # 10 minutes
    EVENT_CACHE_TTL: int = 3600         # 1 hour
    MEMORY_CACHE_SIZE: int = 100        # Max entries
    
    # Calendar Rate Limiting Configuration
    GOOGLE_API_RATE_LIMIT: int = 90           # requests per 100 seconds
    GOOGLE_API_DAILY_QUOTA: int = 1000000     # daily request quota
    API_QUOTA_ALERT_THRESHOLD: float = 0.8    # 80% quota usage alert
    
    # Configuration Validation Methods
    @validator('ENVIRONMENT', pre=True)
    def validate_environment(cls, v):
        """Validate environment setting"""
        if isinstance(v, str):
            try:
                return Environment(v.lower())
            except ValueError:
                raise ValueError(f"Invalid environment: {v}. Must be one of: {list(Environment)}")
        return v
    
    @validator('OPENAI_API_KEY')
    def validate_openai_api_key(cls, v, values):
        """Validate OpenAI API key in production"""
        if values.get('ENVIRONMENT') == Environment.PRODUCTION and values.get('VALIDATE_API_KEYS', True):
            if not v or not v.startswith('sk-'):
                raise ValueError("OpenAI API key is required in production and must start with 'sk-'")
        return v
    
    @validator('ANTHROPIC_API_KEY')
    def validate_anthropic_api_key(cls, v, values):
        """Validate Anthropic API key if provided"""
        if v and not v.startswith('sk-ant-'):
            raise ValueError("Anthropic API key must start with 'sk-ant-' if provided")
        return v
    
    @validator('DEBUG')
    def validate_debug_production(cls, v, values):
        """Ensure DEBUG is False in production"""
        environment = values.get('ENVIRONMENT')
        if environment == Environment.PRODUCTION and v:
            raise ValueError("DEBUG must be False in production environment")
        return v

    @validator('FRONTEND_URL')
    def validate_frontend_url(cls, v):
        """Validate FRONTEND_URL is HTTPS in production"""
        if v and not v.startswith('https://'):
            raise ValueError("FRONTEND_URL must use HTTPS")
        return v

    @validator('EVOLUTION_API_KEY')
    def validate_evolution_api_key(cls, v, values):
        """Validate Evolution API key in production"""
        if values.get('ENVIRONMENT') == Environment.PRODUCTION and values.get('VALIDATE_API_KEYS', True):
            if not v:
                raise ValueError("Evolution API key is required in production")
        return v
    
    @validator('DATABASE_URL')
    def validate_database_url(cls, v, values):
        """Validate database URL format"""
        if values.get('ENVIRONMENT') == Environment.PRODUCTION:
            if not v or not v.startswith(('postgresql://', 'postgres://')):
                raise ValueError("Valid PostgreSQL database URL is required in production")
        return v
    
    @validator('LLM_DAILY_BUDGET_BRL')
    def validate_llm_budget(cls, v):
        """Validate LLM daily budget"""
        if v <= 0:
            raise ValueError("LLM daily budget must be positive")
        if v > 50:  # Safety check
            raise ValueError("LLM daily budget exceeds safety limit of R$50")
        return v
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENVIRONMENT == Environment.DEVELOPMENT
    
    def get_critical_missing_vars(self) -> List[str]:
        """Get list of critical missing environment variables for production"""
        missing = []
        
        if self.is_production():
            # Critical API keys for production
            if not self.OPENAI_API_KEY:
                missing.append("OPENAI_API_KEY")
            if not self.EVOLUTION_API_KEY:
                missing.append("EVOLUTION_API_KEY")
            if not self.DATABASE_URL or self.DATABASE_URL == "postgresql://user:password@localhost/kumon_db":
                missing.append("DATABASE_URL")
            if not self.MEMORY_REDIS_URL or "localhost" in self.MEMORY_REDIS_URL:
                missing.append("MEMORY_REDIS_URL")
            
        return missing
    
    def validate_production_config(self) -> Dict[str, Any]:
        """Comprehensive production configuration validation"""
        issues = []
        warnings = []
        
        # Check critical missing variables
        missing_vars = self.get_critical_missing_vars()
        if missing_vars:
            issues.extend([f"Missing critical environment variable: {var}" for var in missing_vars])
        
        # Check optional but recommended configurations
        if self.is_production():
            if not self.ANTHROPIC_API_KEY:
                warnings.append("Anthropic API key not configured - no LLM fallback available")
            if not self.TWILIO_ACCOUNT_SID or not self.TWILIO_AUTH_TOKEN:
                warnings.append("Twilio credentials not configured - no WhatsApp/SMS fallback")
            if not self.LANGSMITH_API_KEY:
                warnings.append("LangSmith API key not configured - no observability")
            if self.DEBUG:
                warnings.append("DEBUG mode enabled in production - should be disabled")
                
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "environment": self.ENVIRONMENT.value,
            "missing_critical_vars": missing_vars
        }
    
    def get_database_pool_config(self) -> Dict[str, Any]:
        """Get database connection pool configuration for SQLAlchemy"""
        return {
            "pool_size": self.DB_POOL_SIZE,
            "max_overflow": self.DB_MAX_OVERFLOW,
            "pool_timeout": self.DB_POOL_TIMEOUT,
            "pool_recycle": self.DB_POOL_RECYCLE,
            "echo": self.DB_ECHO,
            "pool_pre_ping": self.DB_POOL_PRE_PING,
            "connect_args": {
                "connect_timeout": 10,
                "application_name": "kumon_assistant",
                "options": "-c statement_timeout=30000"  # 30 second statement timeout
            }
        }

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Allow extra environment variables to be ignored


# Create settings instance
settings = Settings() 