from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://territorio:territorio@db:5432/territorio"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
