from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 720  # 30 days
    ODDSAPI_KEY: str
    ESPN_API_BASE: str = "https://site.api.espn.com/apis/site/v2"
    ENVIRONMENT: str = "development"

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        # An unresolved platform variable reference arrives as an empty string,
        # which otherwise fails much later with an opaque SQLAlchemy error.
        v = v.strip()
        if not v:
            raise ValueError(
                "DATABASE_URL is empty. On Railway this usually means the "
                "${{ ServiceName.VARIABLE }} reference does not match the "
                "Postgres service name or variable name."
            )
        # SQLAlchemy 2.x dropped the legacy postgres:// scheme.
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        return v

    @field_validator("JWT_SECRET", "ODDSAPI_KEY")
    @classmethod
    def require_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()

@lru_cache()
def get_settings():
    return Settings()
