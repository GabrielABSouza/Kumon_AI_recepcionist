"""
Configuration settings for the Kumon AI Receptionist
"""
from pydantic_settings import BaseSettings
from pydantic import EmailStr
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # General
    PROJECT_NAME: str = "Kumon AI Receptionist"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Evolution API Configuration
    EVOLUTION_API_URL: str = "http://localhost:8080"
    EVOLUTION_API_KEY: str = ""
    EVOLUTION_GLOBAL_API_KEY: str = ""
    AUTHENTICATION_API_KEY: str = ""
    WEBHOOK_GLOBAL_URL: str = ""
    WEBHOOK_GLOBAL_ENABLED: bool = True
    CONFIG_SESSION_PHONE_CLIENT: str = "Kumon Assistant"
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    
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
    GOOGLE_CREDENTIALS_PATH: str = "google-service-account.json"
    GOOGLE_CALENDAR_ID: str = ""
    GOOGLE_SHEETS_ID: str = ""
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/kumon_db"
    
    # Qdrant (Vector Database)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
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
    BUSINESS_HOURS: str = "Segunda a Sexta: 08:00 às 18:00"
    
    # Business Hours Configuration
    BUSINESS_HOURS_START: int = 8  # 8 AM
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Allow extra environment variables to be ignored


# Create settings instance
settings = Settings() 