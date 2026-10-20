from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from uuid import UUID

_tenant_id: ContextVar[UUID | None] = ContextVar("resolveai_tenant_id", default=None)


def current_tenant_id() -> UUID | None:
    return _tenant_id.get()


@contextmanager
def tenant_scope(tenant_id: UUID) -> Iterator[None]:
    token: Token[UUID | None] = _tenant_id.set(tenant_id)
    try:
        yield
    finally:
        _tenant_id.reset(token)
