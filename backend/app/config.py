from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 720  # 30 days
    ODDSAPI_KEY: str
    ESPN_API_BASE: str = "https://site.api.espn.com/apis/site/v2"
    ENVIRONMENT: str = "development"

@lru_cache()
def get_settings():
    return Settings()
