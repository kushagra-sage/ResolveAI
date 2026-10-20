import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWKClient

from resolveai.config import Settings


class AuthenticationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class TokenIdentity:
    user_id: uuid.UUID | None
    tenant_id: uuid.UUID
    subject: str


def decode_access_token(token: str, settings: Settings) -> TokenIdentity:
    try:
        if settings.auth_mode == "oidc":
            if settings.oidc_jwks_url is None:
                raise AuthenticationError("OIDC JWKS URL is not configured")
            signing_key = PyJWKClient(settings.oidc_jwks_url).get_signing_key_from_jwt(token).key
            key: Any = signing_key
            algorithms = [item.strip() for item in settings.oidc_algorithms.split(",")]
        else:
            key = settings.jwt_secret.get_secret_value()
            algorithms = [settings.jwt_algorithm]
        payload = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "tenant_id", "roles"]},
        )
        if "permissions" not in payload and "scope" not in payload:
            raise AuthenticationError("token lacks permissions or scopes")
        if datetime.fromtimestamp(payload["exp"], tz=UTC) <= datetime.now(tz=UTC):
            raise AuthenticationError("token expired")
        return TokenIdentity(
            user_id=(
                uuid.UUID(str(payload["user_id"]))
                if settings.auth_mode == "local_hs256" and payload.get("user_id")
                else None
            ),
            tenant_id=uuid.UUID(str(payload["tenant_id"])),
            subject=str(payload["sub"]),
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError("invalid access token") from exc
