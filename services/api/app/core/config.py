from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, RedisDsn, SecretStr, computed_field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../../.env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    ENV: str = "development"
    
    # Database
    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn
    
    # S3
    S3_ENDPOINT: str
    S3_BUCKET: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: SecretStr
    
    # Auth
    JWT_SECRET: SecretStr
    JWT_REFRESH_SECRET: SecretStr
    TOKEN_ENCRYPTION_KEY: SecretStr
    
    # OAuth
    GOOGLE_OAUTH_CLIENT_ID: str
    GOOGLE_OAUTH_CLIENT_SECRET: SecretStr
    
    # LLM
    ANTHROPIC_API_KEY: SecretStr
    OPENAI_COMPAT_BASE_URL: str
    
    # Integrations
    DATAFORSEO_LOGIN: str
    DATAFORSEO_PASSWORD: SecretStr
    DFS_AUDIT_BUDGET_USD: float
    PSI_API_KEY: SecretStr
    MOZ_ACCESS_ID: str
    MOZ_SECRET_KEY: SecretStr
    
    # Observability
    SENTRY_DSN: Optional[str] = None
    
    # Frontend
    NEXT_PUBLIC_API_BASE_URL: str
    NEXT_PUBLIC_SENTRY_DSN: Optional[str] = None

    @computed_field
    def is_dev(self) -> bool:
        return self.ENV.lower() == "development"

settings = Settings()
