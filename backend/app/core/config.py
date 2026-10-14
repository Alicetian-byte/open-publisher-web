from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Open Publisher Web"
    app_env: str = "development"
    database_url: str = (
        "mysql+pymysql://opw:opw_password@localhost:3306/"
        "open_publisher_web?charset=utf8mb4"
    )
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
