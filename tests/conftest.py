import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from resolveai.config import Settings
from resolveai.database import create_database_engine, create_schema
from resolveai.main import create_app
from resolveai.seed import seed_database, seed_id

TEST_SECRET = "test-secret-that-is-long-enough-for-hs256"


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    path = tmp_path / "resolveai-test.db"
    url = f"sqlite+pysqlite:///{path.as_posix()}"
    engine = create_database_engine(url)
    create_schema(engine)
    engine.dispose()
    seed_database(url)
    return url


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        database_url="sqlite+pysqlite://",
        auth_mode="local_hs256",
        jwt_algorithm="HS256",
        jwt_secret=SecretStr(TEST_SECRET),
        jwt_issuer="resolveai-test",
        jwt_audience="resolveai-api-test",
        oidc_jwks_url=None,
    )


@pytest.fixture
def client(database_url: str, settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings=settings, database_url=database_url)) as test_client:
        yield test_client


def make_token(
    settings: Settings,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    subject: str,
    expires_delta: timedelta = timedelta(minutes=10),
) -> str:
    now = datetime.now(tz=UTC)
    return jwt.encode(
        {
            "sub": subject,
            "user_id": str(user_id),
            "tenant_id": str(tenant_id),
            "roles": [],
            "permissions": [],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + expires_delta,
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


@pytest.fixture
def customer_token(settings: Settings) -> str:
    return make_token(
        settings,
        user_id=seed_id("user:acme:customer"),
        tenant_id=seed_id("tenant:acme"),
        subject="demo-customer",
    )


@pytest.fixture
def agent_token(settings: Settings) -> str:
    return make_token(
        settings,
        user_id=seed_id("user:acme:agent"),
        tenant_id=seed_id("tenant:acme"),
        subject="demo-agent",
    )


@pytest.fixture
def admin_token(settings: Settings) -> str:
    return make_token(
        settings,
        user_id=seed_id("user:acme:admin"),
        tenant_id=seed_id("tenant:acme"),
        subject="demo-admin",
    )


@pytest.fixture
def supervisor_token(settings: Settings) -> str:
    return make_token(
        settings,
        user_id=seed_id("user:acme:supervisor"),
        tenant_id=seed_id("tenant:acme"),
        subject="demo-supervisor",
    )
