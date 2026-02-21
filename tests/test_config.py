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

def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_NAME", "etl")
    monkeypatch.setenv("DB_USER", "etl_user")
    monkeypatch.setenv("DB_PASSWORD", "secret")

def test_config_rejects_out_of_range_db_port(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("DB_PORT", "0")
    with pytest.raises(ValidationError):
        EtlConfig()

    monkeypatch.setenv("DB_PORT", "70000")
    with pytest.raises(ValidationError):
        EtlConfig()

def test_config_rejects_empty_required_values(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("DB_HOST", "  ")
    with pytest.raises(ValidationError):
        EtlConfig()
