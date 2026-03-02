from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DbConfig(BaseModel):
    host: str
    port: int = 5432
    name: str
    user: str
    password: str
    sslmode: str = "prefer"

    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
            f"?sslmode={self.sslmode}"
        )


class EtlConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    db_host: str = Field(alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT", ge=1, le=65535)
    db_name: str = Field(alias="DB_NAME")
    db_user: str = Field(alias="DB_USER")
    db_password: str = Field(alias="DB_PASSWORD")
    db_sslmode: str = Field(default="prefer", alias="DB_SSLMODE")
    etl_log_level: str = Field(default="INFO", alias="ETL_LOG_LEVEL")
    etl_rejects_path: str = Field(default="/tmp/rejects.ndjson", alias="ETL_REJECTS_PATH")

    @field_validator("db_host", "db_name", "db_user", "db_password")
    @classmethod
    def _required_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must be non-empty")
        return stripped

    def db(self) -> DbConfig:
        return DbConfig(
            host=self.db_host,
            port=self.db_port,
            name=self.db_name,
            user=self.db_user,
            password=self.db_password,
            sslmode=self.db_sslmode,
        )
