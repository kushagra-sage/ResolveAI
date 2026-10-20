import argparse
import os
from datetime import UTC, datetime, timedelta

import jwt

from resolveai.config import get_settings
from resolveai.seed import seed_id

IDENTITIES = {
    "customer": ("user:acme:customer", "demo-customer", ["customer"]),
    "agent": ("user:acme:agent", "demo-agent", ["support_agent"]),
    "admin": ("user:acme:admin", "demo-admin", ["admin"]),
    "supervisor": ("user:acme:supervisor", "demo-supervisor", ["supervisor"]),
}


def create_dev_token(identity: str) -> str:
    if os.getenv("RESOLVEAI_ENVIRONMENT", "local") not in {"local", "test"}:
        raise RuntimeError("development tokens are disabled outside local/test environments")
    settings = get_settings()
    if settings.environment not in {"local", "test"}:
        raise RuntimeError("development tokens are disabled outside local/test environments")
    user_seed, subject, roles = IDENTITIES[identity]
    now = datetime.now(tz=UTC)
    return jwt.encode(
        {
            "sub": subject,
            "user_id": str(seed_id(user_seed)),
            "tenant_id": str(seed_id("tenant:acme")),
            "roles": roles,
            "permissions": [],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local ResolveAI demo JWT")
    parser.add_argument("identity", choices=sorted(IDENTITIES))
    args = parser.parse_args()
    print(create_dev_token(args.identity))


if __name__ == "__main__":
    main()
