import hashlib
import math
import re
from typing import Protocol


class EmbeddingProvider(Protocol):
    model_name: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbeddingProvider:
    """Deterministic local embedding used for development and offline tests.

    This is not presented as a semantic production embedding model. It provides
    stable token-overlap behavior without network calls or invented quality claims.
    """

    model_name = "local-hash-embedding-v1"

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"[\w'-]+", text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimensions
            sign = 1.0 if value & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(component * component for component in vector))
        if norm:
            return [component / norm for component in vector]
        return vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    denominator = math.sqrt(sum(v * v for v in left)) * math.sqrt(sum(v * v for v in right))
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator
