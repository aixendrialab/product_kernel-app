# product_kernel/db/alembic_env_template.py
from __future__ import annotations
import os
import sys
from logging.config import fileConfig
from typing import Sequence, Iterable, List
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool, MetaData
from sqlalchemy.schema import CreateTable, CreateIndex

# kernel imports

from product_kernel.db.base import Base
from product_kernel.autodiscover import discover_models


def _log(msg: str) -> None:
    print(msg, flush=True)


def _load_env(app_root: str) -> None:
    # .dbstack.env first, then .env overrides
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(app_root, ".dbstack.env"))
        load_dotenv(os.path.join(app_root, ".env"), override=True)
        _log(f"📄 Loaded env from {app_root}/.dbstack.env and {app_root}/.env")
    except Exception:
        pass


def _normalize_sync_url(url: str) -> str:
    if not url:
        raise RuntimeError("No DB URL provided.")
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def _ensure_db_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if url:
        return _normalize_sync_url(url)
    # fallback to PG_* vars
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "8432")
    user = os.getenv("PG_USER", "postgres")
    pw   = os.getenv("PGPASSWORD", "postgres")
    db   = os.getenv("PG_DB", "tos")
    url  = f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}"
    _log(f"⚙️  Constructed DATABASE_URL: {url}")
    return url


def _iterable_roots(roots: str | Iterable[str]) -> List[str]:
    if isinstance(roots, (list, tuple, set)):
        return list(roots)
    return [str(roots)]


def _union_metadata(metadatas: Sequence[MetaData]) -> MetaData:
    merged = MetaData()
    for md in metadatas:
        for tbl in md.tables.values():
            if tbl.name not in merged.tables:
                tbl.tometadata(merged)
    return merged


def _write_schema_sql(metadata: MetaData, sync_url: str, path: Path) -> None:
    if not metadata.tables:
        _log("⚠️  No tables in metadata; schema.sql not written.")
        return
    eng = create_engine(sync_url, poolclass=pool.NullPool, future=True)
    try:
        metadata.bind = eng
        chunks = []
        for tbl in metadata.sorted_tables:
            chunks.append(str(CreateTable(tbl).compile(dialect=eng.dialect)))
            for idx in tbl.indexes:
                chunks.append(str(CreateIndex(idx).compile(dialect=eng.dialect)))
            chunks.append("")  # spacer
        path.write_text("\n".join(chunks), encoding="utf-8")
        _log(f"🧾 schema.sql written → {path} ({len(metadata.tables)} tables)")
    finally:
        eng.dispose()


def run_alembic_env(autodiscover_roots: str | Iterable[str]) -> None:
    """
    Minimal, verbose Alembic env runner living in product-kernel.

    In your app's alembic/env.py:
        from product_kernel.db.alembic_env_template import run_alembic_env
        run_alembic_env(autodiscover_roots=["app", "app.domain"])
    """
    # Put app + kernel on sys.path
    alembic_dir = Path(__file__).resolve().parent.parent.parent  # product_kernel/db/.. → product_kernel
    app_root = Path(os.getcwd()).resolve()
    pk_src = alembic_dir  # already importable as installed package
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    if str(pk_src) not in sys.path:
        sys.path.insert(0, str(pk_src))

    # Load env
    _load_env(str(app_root))

    # Alembic config + logging
    cfg = context.config
    if cfg.config_file_name:
        fileConfig(cfg.config_file_name)

    # DB URL
    sync_url = _ensure_db_url()
    cfg.set_main_option("sqlalchemy.url", sync_url)
    _log(f"🔍 Alembic DB URL: {sync_url}")

    # Discover models
    roots = _iterable_roots(autodiscover_roots)
    all_models = []
    for root in roots:
        models = list(discover_models(root))
        _log(f"📦 Root '{root}': discovered {len(models)} model classes → {[m.__name__ for m in models]}")
        all_models.extend(models)

    if not all_models:
        _log("⚠️  No SQLAlchemy models discovered. Expect only 'alembic_version' to exist.")

    # Merge metadata and list table names
    metadatas = [Base.metadata] + [m.metadata for m in all_models]
    target_metadata = _union_metadata(metadatas)
    table_names = list(target_metadata.tables.keys())
    _log(f"📊 Merged table count: {len(table_names)}")
    if table_names:
        _log(f"   └─ {table_names}")
    else:
        _log("   └─ (no tables)")

    # schema.sql snapshot
    try:
        _write_schema_sql(target_metadata, sync_url, app_root / "schema.sql")
    except Exception as e:
        _log(f"⚠️  Could not write schema.sql: {e!r}")

    # If no revisions exist, be explicit (and optionally create tables)
    versions_dir = app_root / "alembic" / "versions"
    has_revisions = versions_dir.exists() and any(versions_dir.iterdir())
    if not has_revisions:
        _log("⚠️  No Alembic revisions found in alembic/versions.")
        if os.getenv("PK_ALEMBIC_FALLBACK_CREATE", "1") == "1":
            _log("🛟 PK_ALEMBIC_FALLBACK_CREATE=1 → creating tables directly via metadata.create_all()")
            eng = create_engine(sync_url, poolclass=pool.NullPool, future=True)
            try:
                with eng.begin() as conn:
                    target_metadata.create_all(conn, checkfirst=True)
                _log(f"✅ Tables created → {list(target_metadata.tables.keys())}")
            finally:
                eng.dispose()
        else:
            _log("➡️  Add a revision under alembic/versions and run: alembic upgrade head")

    # --- Detect empty upgrade() and auto-create if needed ---
    else:
        try:
            from alembic.script import ScriptDirectory
            script_dir = ScriptDirectory.from_config(cfg)
            heads = script_dir.get_heads()
            if heads:
                current_rev = script_dir.get_revision(heads[0])
                upgrade_fn = getattr(current_rev.module, "upgrade", None)
                if upgrade_fn and not upgrade_fn.__code__.co_consts[1:]:
                    _log("🛠️  Detected empty upgrade() → creating tables directly from metadata.")
                    eng = create_engine(sync_url, poolclass=pool.NullPool, future=True)
                    with eng.begin() as conn:
                        target_metadata.create_all(conn, checkfirst=True)
                    _log(f"✅ Tables created → {list(target_metadata.tables.keys())}")
        except Exception as e:
            _log(f"⚠️  Could not auto-create tables from empty revision: {e!r}")

    # Run migrations (if there are revisions, this applies them)
    def run_migrations_offline() -> None:
        context.configure(
            url=sync_url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()

    def run_migrations_online() -> None:
        eng = create_engine(sync_url, poolclass=pool.NullPool, future=True)
        try:
            with eng.connect() as conn:
                context.configure(connection=conn, target_metadata=target_metadata)
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            eng.dispose()

    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()

    _log("✅ Alembic migration environment completed successfully.")
