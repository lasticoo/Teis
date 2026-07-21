import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Trading Edge Intelligence System (TEIS)"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database Configuration
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=3306)
    DB_USER: str = Field(default="teis_user")
    DB_PASSWORD: str = Field(default="teis_secure_pass")
    DB_NAME: str = Field(default="teis_db")

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Redis Configuration
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)

    # Celery Configuration
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0")

    # MinIO (S3-compatible) Configuration
    MINIO_ENDPOINT: str = Field(default="localhost:9000")
    MINIO_ACCESS_KEY: str = Field(default="teis_minio_admin")
    MINIO_SECRET_KEY: str = Field(default="teis_minio_secret_pass")
    MINIO_BUCKET_NAME: str = Field(default="teis-screenshots")

    # Security
    SECRET_KEY: str = Field(default="teis_super_secret_dev_key_1234567890")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    AES_ENCRYPTION_KEY: str = Field(default="dGVpc19kZXZlbG9wbWVudF9hZXNfMjU2X2tleV9leGFtcGxlPQ==")

    # Binance Configuration
    BINANCE_API_KEY: str = Field(default="")
    BINANCE_API_SECRET: str = Field(default="")
    BINANCE_USE_TESTNET: bool = True

    # SMTP Configuration
    SMTP_HOST: str = Field(default="localhost")
    SMTP_PORT: int = Field(default=1025)
    SMTP_USER: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    SMTP_FROM_EMAIL: str = Field(default="noreply@teis.local")

    # Web Push (VAPID) Configuration
    VAPID_PUBLIC_KEY: str = Field(default="")
    VAPID_PRIVATE_KEY: str = Field(default="")
    VAPID_ADMIN_EMAIL: str = Field(default="admin@teis.local")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
