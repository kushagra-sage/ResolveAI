import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    content: str
    heading_path: tuple[str, ...] = ()

    @property
    def token_count(self) -> int:
        return len(self.content.split())


def _windows(tokens: list[str], size: int, overlap: int) -> list[str]:
    if not tokens:
        return []
    step = size - overlap
    return [" ".join(tokens[start : start + size]) for start in range(0, len(tokens), step)]


def fixed_token_chunks(content: str, size: int, overlap: int) -> list[ChunkDraft]:
    return [ChunkDraft(text) for text in _windows(content.split(), size, overlap) if text]


def recursive_chunks(content: str, size: int, overlap: int) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    for paragraph in re.split(r"\n\s*\n", content):
        normalized = " ".join(paragraph.split())
        if not normalized:
            continue
        drafts.extend(
            ChunkDraft(text) for text in _windows(normalized.split(), size, overlap) if text
        )
    return drafts


def heading_aware_chunks(content: str, size: int, overlap: int) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    headings: list[str] = []
    body: list[str] = []

    def flush() -> None:
        normalized = " ".join(body).strip()
        if normalized:
            drafts.extend(
                ChunkDraft(text, tuple(headings))
                for text in _windows(normalized.split(), size, overlap)
                if text
            )
        body.clear()

    for line in content.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if match:
            flush()
            level = len(match.group(1))
            headings[:] = headings[: level - 1]
            headings.append(match.group(2).strip())
        elif line.strip():
            body.append(line.strip())
    flush()
    return drafts


def semantic_chunks(content: str, size: int, overlap: int) -> list[ChunkDraft]:
    """Deterministic sentence-boundary baseline for controlled experiments."""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", content) if part.strip()]
    drafts: list[ChunkDraft] = []
    current: list[str] = []
    for sentence in sentences:
        candidate = " ".join([*current, sentence])
        if current and len(candidate.split()) > size:
            drafts.append(ChunkDraft(" ".join(current)))
            current = current[-overlap:] if overlap else []
        current.append(sentence)
    if current:
        drafts.append(ChunkDraft(" ".join(current)))
    return drafts


def parent_child_chunks(content: str, size: int, overlap: int) -> list[ChunkDraft]:
    parents = recursive_chunks(content, size * 3, min(overlap, size * 3 - 1))
    children: list[ChunkDraft] = []
    for parent_index, parent in enumerate(parents):
        for child in fixed_token_chunks(parent.content, size, overlap):
            children.append(ChunkDraft(child.content, heading_path=(f"parent:{parent_index}",)))
    return children


def chunk_document(strategy: str, content: str, size: int, overlap: int) -> list[ChunkDraft]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("invalid chunk size or overlap")
    chunkers = {
        "fixed_token": fixed_token_chunks,
        "recursive": recursive_chunks,
        "heading_aware": heading_aware_chunks,
        "semantic": semantic_chunks,
        "parent_child": parent_child_chunks,
    }
    try:
        chunker = chunkers[strategy]
    except KeyError as exc:
        raise ValueError(f"unsupported chunking strategy: {strategy}") from exc
    return chunker(content, size, overlap)
