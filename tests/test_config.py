import pytest
from pydantic import ValidationError

from etl.config import EtlConfig


def test_config_requires_db_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.delenv("DB_USER", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)

    with pytest.raises(ValidationError):
        EtlConfig()


def test_config_builds_sqlalchemy_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "etl")
    monkeypatch.setenv("DB_USER", "etl_user")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_SSLMODE", "prefer")

    config = EtlConfig()
    url = config.db().sqlalchemy_url()

    assert "postgresql+psycopg://" in url
    assert "etl_user:secret@localhost:5432/etl?sslmode=prefer" in url
