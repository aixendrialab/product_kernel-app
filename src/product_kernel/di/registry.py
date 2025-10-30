from __future__ import annotations
from typing import Any, Callable, Dict, Type

"""
──────────────────────────────────────────────────────────────────────────────
Simple Dependency Injection Registry
──────────────────────────────────────────────────────────────────────────────
Purpose:
    Maintain a global mapping of types → provider functions.

APIs:
    - register(type, provider_fn)
    - resolve(type) → instance

Used by:
    - RepoBase.__init_subclass__() → auto-registers repos
    - autowire() → injects dependencies into services

Usage:
    register(MyRepo, lambda: MyRepo())
    repo = resolve(MyRepo)
"""

# Simple global registry: Type -> provider function (returns an instance)
_PROVIDERS: Dict[Type[Any], Callable[[], Any]] = {}

def register(type_: Type[Any], provider: Callable[[], Any]) -> None:
    _PROVIDERS[type_] = provider

def resolve(type_: Type[Any]) -> Any:
    try:
        return _PROVIDERS[type_]()
    except KeyError:
        raise RuntimeError(f"No provider registered for type {type_.__module__}.{type_.__name__}")
