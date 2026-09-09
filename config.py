import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "default-dev-secret-key-123")
    
    # JWT Configuration
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "default-dev-jwt-secret-key-456")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "60"))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "7"))
    )
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_SECURE = False  # Set to True in production (HTTPS)
    JWT_COOKIE_CSRF_PROTECT = False  # Enabled per endpoint or form CSRF
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_ACCESS_COOKIE_NAME = "access_token_cookie"
    JWT_REFRESH_COOKIE_NAME = "refresh_token_cookie"

    # MongoDB Configuration
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/cgpa_analytics")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "cgpa_analytics")

    # Redis / Caching Configuration
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # CORS
    CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:5000")

    # Rate Limiting
    RATELIMIT_DEFAULT = "200 per day; 50 per hour"
    RATELIMIT_STORAGE_URI = os.getenv("REDIS_URL", "memory://")

    # Uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max file upload
    ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

    # ML Model Storage
    ML_MODEL_DIR = os.path.join(os.path.dirname(__file__), "ml_engine", "saved_models")


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = False
    TESTING = True
    MONGO_URI = "mongomock://localhost/cgpa_test_db"
    MONGO_DB_NAME = "cgpa_test_db"
    RATELIMIT_ENABLED = False
    JWT_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_SAMESITE = "Strict"


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
