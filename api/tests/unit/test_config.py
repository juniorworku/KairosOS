import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://", "postgresql+asyncpg://"])
def test_normalizes_postgres_url(scheme: str) -> None:
    settings = Settings(database_url=f"{scheme}user:pass@localhost/kairos", _env_file=None)
    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost/kairos"


def test_rejects_non_postgres_url() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///local.db", _env_file=None)


def test_signup_is_closed_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGNUP_MODE", raising=False)
    assert Settings(_env_file=None).signup_mode == "closed"
