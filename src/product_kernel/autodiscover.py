# product_kernel/autodiscover.py
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from typing import Iterable, List, Type

def _iter_model_module_specs(root: str = "app") -> Iterable[importlib.util.spec_from_file_location]:
    """
    Yield importlib specs for files named 'models.py' under the given root.
    We do NOT import arbitrary packages to avoid pulling in routers during Alembic.
    """
    base = Path(root)
    for path in base.rglob("models.py"):
        # Build a unique module name like: app.domain.admin.models
        rel = path.with_suffix("").relative_to(base)
        modname = ".".join((root, *rel.parts))
        spec = importlib.util.spec_from_file_location(modname, str(path))
        if spec and spec.loader:
            yield spec

def discover_models(root: str = "app") -> List[Type]:
    """Return SQLAlchemy Declarative Base subclasses by loading only *models.py* files."""
    from product_kernel.db.base import Base
    out: List[Type] = []
    for spec in _iter_model_module_specs(root):
        # Load module WITHOUT walk_packages to avoid importing routes
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)  # type: ignore

        # Collect ORM classes
        for name, obj in vars(module).items():
            try:
                if isinstance(obj, type) and issubclass(obj, Base) and obj is not Base:
                    out.append(obj)
            except Exception:
                # Ignore non-class or unrelated objects
                pass
    return out

def discover_seed_scripts(root: str = "app"):
    """Find all seed_*.py files under app/**/seeds/ without importing the package."""
    return [str(p) for p in Path(root).rglob("seeds/seed_*.py")]
