from __future__ import annotations
import os, sys, asyncio
from pathlib import Path
from sqlalchemy import text
from types import ModuleType
from typing import Optional, List

from product_kernel.db.session import async_session
from product_kernel.db.context import set_session, reset_session
from product_kernel.autodiscover import discover_seed_scripts

"""
──────────────────────────────────────────────────────────────
Unified Seed Runner
──────────────────────────────────────────────────────────────
Ensures:
  • One AsyncSession per seed (or shared if configured)
  • Session bound to ContextVar via set_session()
  • get_session() inside RepoBase / Service works automatically
  • @transactional reuses that session safely
──────────────────────────────────────────────────────────────
Each seed must define:
    async def run(db):
        svc = BootstrapService()
        await svc.initialize_system()
──────────────────────────────────────────────────────────────
"""

# ──────────────────────────────────────────────────────────────
# Utility loader
# ──────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────
# Utility loader (fixed)
# ──────────────────────────────────────────────────────────────
def _load_module(path: Path) -> Optional[ModuleType]:
    """
    Load a seed as a proper package module (so its imports keep context).
    Example: app/seeds/seed_terminal.py → app.seeds.seed_terminal
    """
    import importlib

    # Compute module name from path
    rel = path.with_suffix("")  # drop .py
    try:
        # find the subpath starting from "app"
        idx = rel.parts.index("app")
        modname = ".".join(rel.parts[idx:])  # e.g., app.seeds.seed_terminal
    except ValueError:
        # fallback if not found
        modname = rel.stem

    try:
        mod = importlib.import_module(modname)
        return mod
    except Exception as e:
        print(f"❌ Failed to import {modname}: {e}")
        return None


# ──────────────────────────────────────────────────────────────
# Single-seed runner
# ──────────────────────────────────────────────────────────────
async def _run_one_seed(path: Path) -> None:
    """Run a single seed within its own ContextVar-bound transaction."""
    mod = _load_module(path)
    if not mod or not hasattr(mod, "run"):
        print(f"⚠️  {path.name} missing async `run(db)`")
        return

    run_fn = getattr(mod, "run")
    if not asyncio.iscoroutinefunction(run_fn):
        print(f"⚠️  {path.name} has non-async run(), skipping.")
        return

    async with async_session() as sess:
        # 🔥 Bind session to ContextVar BEFORE transaction
        token = set_session(sess)
        try:
            async with sess.begin():
                print(f"▶️  Running {path.name} (isolated transaction)")

                # ✅ DB connectivity using the same bound session
                try:
                    result = await sess.execute(
                        text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
                    )
                    count = result.scalar() or 0
                    print(f"   🧩 DB connectivity OK — found {count} tables in public schema.")
                except Exception as e:
                    print(f"   ❌ DB connectivity test failed: {e}")
                    raise

                # ✅ Run the seed logic inside same ContextVar
                await run_fn(sess)
                print(f"✅  {path.name} completed")

                # product_kernel/db/seed_runner.py  (inside _run_one_seed, where you call `await run_fn(sess)`)
                try:
                    await run_fn(sess)
                    print(f"✅  {path.name} completed")
                except TypeError as te:
                    msg = str(te)
                    if "missing 1 required positional argument: 'self'" in msg:
                        print("💡 Hint: Did you accidentally call a method on the *class* instead of an instance?")
                        print("   e.g., BootstrapService.initialize_system()  ❌")
                        print("        BootstrapService().initialize_system() ✅")
                    raise
        except Exception as e:
            print(f"❌  {path.name} failed: {e}")
        finally:
            reset_session(token)


# ──────────────────────────────────────────────────────────────
# Shared transaction mode
# ──────────────────────────────────────────────────────────────
async def _run_all_shared(paths: List[Path]) -> None:
    async with async_session() as sess:
        token = set_session(sess)
        try:
            async with sess.begin():
                print(f"▶️  Running {len(paths)} seed(s) in shared transaction")

                result = await sess.execute(
                    text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
                )
                count = result.scalar() or 0
                print(f"   🧩 DB connectivity OK — found {count} tables in public schema.")

                for p in paths:
                    mod = _load_module(p)
                    if not mod or not hasattr(mod, "run"):
                        continue
                    run_fn = getattr(mod, "run")
                    if not asyncio.iscoroutinefunction(run_fn):
                        continue
                    print(f"▶️  Running {p.name}")
                    await run_fn(sess)
                    print(f"✅  {p.name} done")
        except Exception as e:
            print(f"❌  Shared transaction failed: {e}")
            raise
        finally:
            reset_session(token)


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────
async def execute_all(root: str = "app", shared_transaction: bool = False) -> None:
    seeds = discover_seed_scripts(root)
    if not seeds:
        print("🌱 No seed scripts found.")
        return

    print(f"🌱 Found {len(seeds)} seed(s):")
    for s in seeds:
        print(f"   → {s}")

    if shared_transaction:
        await _run_all_shared([Path(s) for s in seeds])
    else:
        for s in seeds:
            await _run_one_seed(Path(s))


def main():
    asyncio.run(execute_all())


if __name__ == "__main__":
    main()
