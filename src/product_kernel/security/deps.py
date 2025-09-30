from __future__ import annotations
import typing as t
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .jwt_provider import get_provider
from .principal import Principal
from functools import wraps
from inspect import iscoroutinefunction

# FastAPI’s built-in bearer parser (no manual “Authorization” header parsing)
_bearer = HTTPBearer(auto_error=True)

async def _require_principal(
    creds: HTTPAuthorizationCredentials = Depends(_bearer)
) -> Principal:
    try:
        prov = get_provider()
        claims = prov.decode(creds.credentials)
        uid = int(claims.get("uid", 0))
        sub = str(claims.get("sub", ""))
        if not uid or not sub:
            raise ValueError("missing uid/sub")
        return Principal(uid=uid, sub=sub, claims=claims)
    except Exception:
        # keep message stable (tests expect a simple 401)
        raise HTTPException(status_code=401, detail="Invalid token")

PrincipalParam = t.Annotated[Principal, Depends(_require_principal)]

# Convenience alias you can pass to APIRouter(..., dependencies=[Depends(require_auth)])
def require_auth():
    return Depends(_require_principal)

# Dependency to inject the principal as a function argument (e.g., def me(principal: Principal))
def principal_dep():
    return Depends(_require_principal)

# --- Token generation for OTP-verify (decorator, not middleware) ---

def generates_token(claims_builder: t.Callable[[dict], dict] | None = None):
    """
    Wrap a handler that returns {"uid": ..., "phone": ...}
    and merge {"type":"actual","token":"..."} into the JSON result.

    Optionally pass claims_builder(result_dict) -> claims if your shape differs.
    """
    def decorator(fn):
        if iscoroutinefunction(fn):
            @wraps(fn)
            async def _async(*args, **kwargs):
                result = await fn(*args, **kwargs)
                claims = (
                    claims_builder(result) if claims_builder
                    else {"uid": int(result["uid"]), "sub": str(result["phone"])}
                )
                token = get_provider().encode(claims)
                # merge and return
                out = dict(result)
                out.update({"type": "actual", "token": token})
                return out
            return _async
        else:
            @wraps(fn)
            def _sync(*args, **kwargs):
                result = fn(*args, **kwargs)
                claims = (
                    claims_builder(result) if claims_builder
                    else {"uid": int(result["uid"]), "sub": str(result["phone"])}
                )
                token = get_provider().encode(claims)
                out = dict(result)
                out.update({"type": "actual", "token": token})
                return out
            return _sync
    return decorator
