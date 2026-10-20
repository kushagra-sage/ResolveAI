import argparse
from pathlib import Path

from resolveai.config import get_settings
from resolveai.database import create_database_engine, create_session_factory
from resolveai.embeddings import HashEmbeddingProvider
from resolveai.rag import ingest_document
from resolveai.seed import seed_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a local document into ResolveAI")
    parser.add_argument("path", type=Path)
    parser.add_argument("--tenant", default="acme")
    parser.add_argument("--audience", default="internal")
    parser.add_argument("--document-type", default="documentation")
    args = parser.parse_args()
    content = args.path.read_text(encoding="utf-8")
    tenant_id = seed_id(f"tenant:{args.tenant}")
    engine = create_database_engine(get_settings().database_url)
    factory = create_session_factory(engine)
    with factory() as session:
        session.info["tenant_id"] = tenant_id
        result = ingest_document(
            session,
            HashEmbeddingProvider(),
            tenant_id=tenant_id,
            source_uri=f"file://{args.path.resolve().as_posix()}",
            title=args.path.stem,
            content=content,
            document_type=args.document_type,
            audience=args.audience,
        )
        session.commit()
        print(
            f"document={result.document_id} version={result.version_number} "
            f"chunks={result.chunk_count} created={result.created}"
        )
    engine.dispose()


if __name__ == "__main__":
    main()
