"""
Minimal configuration for ONE_TURN architecture.
Only essential settings for the simplified flow.
"""
import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Evolution API Configuration
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://evo.whatlead.com.br")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")

# Instance Configuration
DEFAULT_INSTANCE = os.getenv("DEFAULT_INSTANCE", "recepcionistakumon")

# Timeout Configuration
TURN_TTL_SECONDS = int(os.getenv("TURN_TTL_SECONDS", "60"))
API_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT_SECONDS", "5"))
