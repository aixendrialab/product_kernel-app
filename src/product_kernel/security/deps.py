# product_kernel/security/deps.py
from __future__ import annotations

from typing import List
from fastapi import Request, HTTPException, status
from product_kernel.security.principal import Principal


def get_principal(request: Request) -> Principal:
    """
    Access the authenticated Principal object injected by KernelAuthMiddleware.
    Raises 401 if not found (should never happen if middleware is active).
    """
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return principal


def require_roles(allowed: List[str]):
    """
    Role-based access helper for routers or services.

    Usage:
        from product_kernel.security.deps import require_roles
        check_roles = require_roles(["SYS_ADMIN"])
        await check_roles(request)  # raises 403 if not allowed
    """
    allowed_set = set(allowed or [])

    async def _check_roles(request: Request):
        principal = get_principal(request)
        if not set(principal.roles or []).intersection(allowed_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return principal

    return _check_roles
