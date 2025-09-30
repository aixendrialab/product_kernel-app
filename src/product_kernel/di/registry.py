from __future__ import annotations
from typing import Any, Callable, Dict, Type

# Simple global registry: Type -> provider function (returns an instance)
_PROVIDERS: Dict[Type[Any], Callable[[], Any]] = {}

def register(type_: Type[Any], provider: Callable[[], Any]) -> None:
    _PROVIDERS[type_] = provider

def resolve(type_: Type[Any]) -> Any:
    try:
        return _PROVIDERS[type_]()
    except KeyError:
        raise RuntimeError(f"No provider registered for type {type_.__module__}.{type_.__name__}")
