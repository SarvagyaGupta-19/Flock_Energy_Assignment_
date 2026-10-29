from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    portal_url: str = "https://urja-ops.flockenergy.tech"
    portal_email: str = "operator@urja.local"
    portal_password: str = "urja-ops-2026"

    cache_ttl_meters: int = 300       # 5 minutes
    cache_ttl_readings: int = 60      # 1 minute
    cache_ttl_transformers: int = 300 # 5 minutes

    portal_timeout: int = 30
    portal_max_concurrency: int = 3

    model_config = {"env_file": ".env"}


settings = Settings()

