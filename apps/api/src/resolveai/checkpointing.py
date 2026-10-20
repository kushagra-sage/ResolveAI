from typing import Protocol


class CheckpointRepository(Protocol):
    """Port for a maintained LangGraph PostgreSQL checkpointer adapter."""

    def save(self, *, tenant_id: str, thread_id: str, checkpoint: dict[str, object]) -> None: ...

    def load(self, *, tenant_id: str, thread_id: str) -> dict[str, object] | None: ...

    def delete(self, *, tenant_id: str, thread_id: str) -> None: ...
