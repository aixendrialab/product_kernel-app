from __future__ import annotations
from typing import Any, get_type_hints, Optional, get_origin, get_args, Type
from .registry import resolve

def _unwrap_optional(typ: Type[Any]) -> Type[Any]:
    origin = get_origin(typ)
    if origin is Optional:
        return get_args(typ)[0]
    return typ

def autowire(obj: Any) -> None:
    """
    Injects attributes on 'obj' based on its type annotations.
    For each annotated attr that's None/missing, resolve a provider and set it.
    Supports Optional[T].
    """
    hints = get_type_hints(obj.__class__)
    for name, typ in hints.items():
        # skip non-injectables (dunder, private, methods)
        if name.startswith("_"):
            continue
        # already set? skip
        if hasattr(obj, name) and getattr(obj, name) is not None:
            continue
        t = _unwrap_optional(typ)
        try:
            instance = resolve(t)
        except RuntimeError:
            continue  # silently ignore if no provider; allows non-repo fields
        setattr(obj, name, instance)
