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
    
    # WhatsApp Business API (Legacy - kept for backward compatibility)
    WHATSAPP_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "kumon_verify_token_2024"
    WHATSAPP_WEBHOOK_URL: str = ""
    WHATSAPP_APP_ID: str = ""
    WHATSAPP_APP_SECRET: str = ""
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    
    # Embeddings Configuration
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_CACHE_DIR: str = "./cache/embeddings"
    
    # Google APIs
    GOOGLE_CREDENTIALS_PATH: str = ""
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
    FROM_EMAIL: EmailStr = "contato@kumon.com"
    
    # Business Configuration
    BUSINESS_NAME: str = "Kumon"
    BUSINESS_PHONE: str = ""
    BUSINESS_EMAIL: EmailStr = "contato@kumon.com"
    BUSINESS_ADDRESS: str = ""
    BUSINESS_HOURS: str = "Segunda a Sexta: 8h às 18h"
    
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


# Create settings instance
settings = Settings() 