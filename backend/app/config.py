"""
Application configuration from environment variables.
"""

import json
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "moja_dzialka"
    postgres_user: str = "app"
    postgres_password: str = "secret"

    @property
    def postgres_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "secretpassword"

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017/moja_dzialka"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # External APIs
    anthropic_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Application
    app_secret_key: str = "change-me-in-production"
    cors_origins_str: str = '["http://localhost:3000"]'
    debug: bool = False
    persistence_backend: str = "memory"

    @property
    def cors_origins(self) -> List[str]:
        return json.loads(self.cors_origins_str)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
