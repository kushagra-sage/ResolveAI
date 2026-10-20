from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine


class EmbeddingVector(TypeDecorator[list[float]]):
    """pgvector in PostgreSQL and JSON arrays in deterministic local tests."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(
        self, value: list[float] | None, _dialect: Dialect
    ) -> list[float] | None:
        if value is not None and len(value) != self.dimensions:
            raise ValueError(f"expected {self.dimensions} embedding dimensions")
        return value
