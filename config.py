"""
NEXUS Configuration
Centralized settings management with environment variable support
"""

from pydantic_settings import BaseSettings
from typing import Optional, List
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings with validation"""

    # ============================================
    # APPLICATION CONFIG
    # ============================================
    APP_NAME: str = "NEXUS"
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = False
    API_VERSION: str = "1.0.0"

    # ============================================
    # DATABASE
    # ============================================
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30

    # ============================================
    # AI PROVIDERS
    # ============================================
    # Groq (Primary - fastest, cheapest)
    GROQ_API_KEY: str
    GROQ_MODEL_SUSAN: str = "llama-3.3-70b-versatile"
    GROQ_MODEL_AGNES: str = "llama-3.3-70b-versatile"

    # Together AI (Secondary)
    TOGETHER_API_KEY: str
    TOGETHER_MODEL_SUSAN: str = "Qwen/Qwen2.5-72B-Instruct-Turbo"
    TOGETHER_MODEL_AGNES: str = "Qwen/Qwen2.5-72B-Instruct-Turbo"

    # OpenRouter (Backup)
    OPENROUTER_API_KEY: str
    OPENROUTER_MODEL: str = "auto"

    # OpenAI (For embeddings)
    OPENAI_API_KEY: str
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    # AI Configuration
    AI_TEMPERATURE: float = 0.7
    AI_MAX_TOKENS: int = 2048
    AI_REQUEST_TIMEOUT: int = 30

    # ============================================
    # EXTERNAL APIS
    # ============================================
    NOAA_API_KEY: Optional[str] = None
    WEATHER_API_BASE_URL: str = "https://api.weather.gov"

    # ============================================
    # SECURITY
    # ============================================
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Password requirements
    MIN_PASSWORD_LENGTH: int = 8
    REQUIRE_PASSWORD_UPPERCASE: bool = True
    REQUIRE_PASSWORD_LOWERCASE: bool = True
    REQUIRE_PASSWORD_DIGIT: bool = True
    REQUIRE_PASSWORD_SPECIAL: bool = True

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000

    # ============================================
    # CORS
    # ============================================
    FRONTEND_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    # ============================================
    # FILE UPLOADS
    # ============================================
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES: List[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "image/png",
        "image/jpeg",
    ]
    UPLOAD_DIR: str = "uploads"

    # ============================================
    # CACHING
    # ============================================
    REDIS_URL: Optional[str] = None
    CACHE_ENABLED: bool = False
    CACHE_TTL_SECONDS: int = 3600

    # ============================================
    # MONITORING
    # ============================================
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    # ============================================
    # EMAIL (Future)
    # ============================================
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[str] = None

    # ============================================
    # FEATURES FLAGS
    # ============================================
    ENABLE_RAG: bool = True
    ENABLE_EMAIL_GENERATOR: bool = True
    ENABLE_DOCUMENT_PROCESSING: bool = True
    ENABLE_WEATHER_API: bool = True
    ENABLE_VOICE_INPUT: bool = True

    # ============================================
    # AGNES TRAINING CONFIG
    # ============================================
    TRAINING_SESSION_TIMEOUT_MINUTES: int = 30
    MAX_SCENARIO_RETRIES: int = 3
    BADGE_SYSTEM_ENABLED: bool = True

    # ============================================
    # SUSAN AI CONFIG
    # ============================================
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.7
    CONVERSATION_MAX_HISTORY: int = 20

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

    def validate_config(self) -> bool:
        """Validate critical configuration"""
        required = [
            self.DATABASE_URL,
            self.GROQ_API_KEY,
            self.TOGETHER_API_KEY,
            self.OPENROUTER_API_KEY,
            self.OPENAI_API_KEY,
            self.JWT_SECRET,
        ]
        return all(required)

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

# Global settings instance
settings = get_settings()

# Validate on import
if not settings.validate_config():
    raise ValueError("Missing required configuration. Check your .env file.")
