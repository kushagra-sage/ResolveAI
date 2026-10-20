from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria

from resolveai.context import current_tenant_id
from resolveai.models import Base, TenantScoped


class TenantSession(Session):
    """Session that automatically scopes tenant-owned ORM reads and writes."""


@event.listens_for(TenantSession, "do_orm_execute")
def _add_tenant_filter(execute_state: Any) -> None:
    tenant_id = execute_state.session.info.get("tenant_id") or current_tenant_id()
    if tenant_id is None or execute_state.execution_options.get("skip_tenant_filter"):
        return
    if execute_state.is_select or execute_state.is_update or execute_state.is_delete:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantScoped,
                lambda model: model.tenant_id == tenant_id,
                include_aliases=True,
            )
        )


@event.listens_for(TenantSession, "before_flush")
def _validate_tenant_writes(session: Session, _flush_context: Any, _instances: Any) -> None:
    tenant_id = session.info.get("tenant_id") or current_tenant_id()
    if tenant_id is None:
        return
    for instance in session.new.union(session.dirty):
        if isinstance(instance, TenantScoped) and instance.tenant_id != tenant_id:
            raise ValueError("tenant-scoped write does not match the active tenant")


@event.listens_for(TenantSession, "after_begin")
def _set_postgres_tenant(session: Session, _transaction: Any, connection: Any) -> None:
    tenant_id = session.info.get("tenant_id") or current_tenant_id()
    if tenant_id is None or connection.dialect.name != "postgresql":
        return
    connection.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def create_database_engine(database_url: str) -> Engine:
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[TenantSession]:
    return sessionmaker(
        bind=engine,
        class_=TenantSession,
        expire_on_commit=False,
        autoflush=False,
    )


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def session_scope(factory: sessionmaker[TenantSession]) -> Iterator[TenantSession]:
    with factory() as session:
        yield session
