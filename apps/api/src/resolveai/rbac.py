import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from resolveai.models import Customer, Permission, Role, RolePermission, UserRole


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    subject: str
    roles: frozenset[str]
    permissions: frozenset[str]
    customer_id: uuid.UUID | None


class AuthorizationError(Exception):
    pass


def load_access(
    session: Session, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> tuple[frozenset[str], frozenset[str], uuid.UUID | None]:
    rows = session.execute(
        select(Role.name, Permission.code)
        .select_from(UserRole)
        .join(Role, (Role.id == UserRole.role_id) & (Role.tenant_id == UserRole.tenant_id))
        .join(
            RolePermission,
            (RolePermission.role_id == Role.id) & (RolePermission.tenant_id == Role.tenant_id),
        )
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(UserRole.tenant_id == tenant_id, UserRole.user_id == user_id)
    ).all()
    roles = frozenset(row.name for row in rows)
    permissions = frozenset(row.code for row in rows)
    customer_id = session.scalar(
        select(Customer.id).where(Customer.tenant_id == tenant_id, Customer.user_id == user_id)
    )
    return roles, permissions, customer_id


def require_permission(
    principal: Principal,
    permission: str,
    *,
    customer_id: uuid.UUID | None = None,
) -> None:
    if permission in principal.permissions:
        return
    own_permission = f"{permission}_own"
    if (
        customer_id is not None
        and own_permission in principal.permissions
        and principal.customer_id == customer_id
    ):
        return
    raise AuthorizationError(f"missing permission: {permission}")
