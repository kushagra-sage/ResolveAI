import random
import time
from collections.abc import Callable
from dataclasses import dataclass


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int


ProviderCall = Callable[[str], ModelResponse]


class FallbackRouter:
    def __init__(
        self,
        providers: list[tuple[str, ProviderCall]],
        max_attempts_per_provider: int = 2,
        *,
        base_backoff_seconds: float = 0.0,
        max_backoff_seconds: float = 2.0,
        jitter_ratio: float = 0.2,
        circuit_failure_threshold: int = 3,
        circuit_recovery_seconds: float = 30.0,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        random_value: Callable[[], float] = random.random,
    ):
        if not providers:
            raise ValueError("at least one provider is required")
        if max_attempts_per_provider < 1 or max_attempts_per_provider > 3:
            raise ValueError("attempt bound must be between 1 and 3")
        self.providers = providers
        self.max_attempts_per_provider = max_attempts_per_provider
        self.base_backoff_seconds = max(0.0, base_backoff_seconds)
        self.max_backoff_seconds = max(self.base_backoff_seconds, max_backoff_seconds)
        self.jitter_ratio = min(max(jitter_ratio, 0.0), 1.0)
        self.circuit_failure_threshold = max(1, circuit_failure_threshold)
        self.circuit_recovery_seconds = max(0.0, circuit_recovery_seconds)
        self.sleeper = sleeper
        self.clock = clock
        self.random_value = random_value
        self._failures = {name: 0 for name, _provider in providers}
        self._opened_at: dict[str, float] = {}

    def _circuit_open(self, name: str) -> bool:
        opened_at = self._opened_at.get(name)
        if opened_at is None:
            return False
        if self.clock() - opened_at >= self.circuit_recovery_seconds:
            self._opened_at.pop(name, None)
            self._failures[name] = 0
            return False
        return True

    def _backoff(self, attempt: int) -> None:
        delay = min(self.max_backoff_seconds, self.base_backoff_seconds * (2**attempt))
        if delay <= 0:
            return
        jitter = delay * self.jitter_ratio * self.random_value()
        self.sleeper(delay + jitter)

    def complete(self, prompt: str) -> ModelResponse:
        failures: list[str] = []
        for name, provider in self.providers:
            if self._circuit_open(name):
                failures.append(f"{name}:CircuitOpen")
                continue
            for attempt in range(self.max_attempts_per_provider):
                try:
                    response = provider(prompt)
                    if not response.text.strip():
                        raise ProviderError("empty response")
                    self._failures[name] = 0
                    self._opened_at.pop(name, None)
                    return response
                except (TimeoutError, ProviderError) as exc:
                    failures.append(f"{name}:{type(exc).__name__}")
                    self._failures[name] += 1
                    if self._failures[name] >= self.circuit_failure_threshold:
                        self._opened_at[name] = self.clock()
                        break
                    if attempt + 1 < self.max_attempts_per_provider:
                        self._backoff(attempt)
        raise ProviderError("all providers failed: " + ",".join(failures))
