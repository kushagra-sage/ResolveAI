import pytest
from resolveai.auth import decode_access_token
from resolveai.config import get_settings
from resolveai.dev_token import create_dev_token
from resolveai.seed import seed_id


def test_local_dev_token_matches_seeded_customer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESOLVEAI_ENVIRONMENT", "local")
    monkeypatch.setenv("RESOLVEAI_AUTH_MODE", "local_hs256")
    monkeypatch.setenv("RESOLVEAI_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("RESOLVEAI_JWT_ISSUER", "resolveai-local")
    monkeypatch.setenv("RESOLVEAI_JWT_AUDIENCE", "resolveai-api")
    monkeypatch.delenv("RESOLVEAI_OIDC_JWKS_URL", raising=False)
    get_settings.cache_clear()

    token = create_dev_token("customer")
    identity = decode_access_token(token, get_settings())

    assert identity.user_id == seed_id("user:acme:customer")
    assert identity.tenant_id == seed_id("tenant:acme")
    get_settings.cache_clear()


def test_dev_token_is_disabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESOLVEAI_ENVIRONMENT", "production")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="disabled"):
        create_dev_token("agent")
    get_settings.cache_clear()
