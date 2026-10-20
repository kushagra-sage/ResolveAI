import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select

from resolveai.auth import AuthenticationError, decode_access_token
from resolveai.config import Settings
from resolveai.database import TenantSession
from resolveai.models import Tenant, User
from resolveai.rbac import Principal, load_access

bearer = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class RequestContext:
    principal: Principal
    session: TenantSession
    settings: Settings


def get_request_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Iterator[RequestContext]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    try:
        identity = decode_access_token(credentials.credentials, request.app.state.settings)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
        ) from exc

    with request.app.state.session_factory() as session:
        session.info["tenant_id"] = identity.tenant_id
        tenant = session.get(Tenant, identity.tenant_id)
        identity_match = User.external_subject == identity.subject
        if identity.user_id is not None:
            identity_match = or_(identity_match, User.id == identity.user_id)
        else:
            try:
                subject_user_id = uuid.UUID(identity.subject)
            except ValueError:
                subject_user_id = None
            if subject_user_id is not None:
                identity_match = or_(identity_match, User.id == subject_user_id)
        user = session.scalar(
            select(User).where(User.tenant_id == identity.tenant_id, identity_match)
        )
        inactive = (
            tenant is None or tenant.status != "active" or user is None or user.status != "active"
        )
        if inactive:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="inactive or unknown principal",
            )

        roles, permissions, customer_id = load_access(session, user.id, identity.tenant_id)
        principal = Principal(
            user_id=user.id,
            tenant_id=identity.tenant_id,
            subject=identity.subject,
            roles=roles,
            permissions=permissions,
            customer_id=customer_id,
        )
        yield RequestContext(
            principal=principal,
            session=session,
            settings=request.app.state.settings,
        )
