"""
Configuration settings for the Kumon AI Receptionist
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    
    # WhatsApp Configuration
    WHATSAPP_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_VERIFY_TOKEN: str
    WHATSAPP_WEBHOOK_URL: str
    
    # Google APIs Configuration
    GOOGLE_CREDENTIALS_PATH: str
    GOOGLE_CALENDAR_ID: str
    GOOGLE_SHEETS_ID: str
    
    # OpenAI Configuration
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4"
    
    # Qdrant Configuration
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "kumon_docs"
    
    # Database Configuration
    DATABASE_URL: str
    
    # Business Configuration
    BUSINESS_HOURS_START: int = 9  # 9 AM
    BUSINESS_HOURS_END: int = 18   # 6 PM
    BUSINESS_DAYS: list = [0, 1, 2, 3, 4]  # Monday to Friday
    APPOINTMENT_DURATION_MINUTES: int = 60
    BUFFER_TIME_MINUTES: int = 15
    
    # Timezone
    TIMEZONE: str = "America/Sao_Paulo"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings() 