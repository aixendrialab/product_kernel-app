from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Principal:
    """
    Canonical identity object produced by JWT decoding or auth deps.

    Attributes
    ----------
    uid : int
        Numeric user id (from JWT claim 'uid' or 'sub').
    sub : str
        JWT subject string (often same as uid, username, or email).
    roles : list[str]
        Role codes extracted from claims. Empty if none present.
    tenant_id : int | None
        Tenant id from claims if provided.
    claims : dict[str, Any]
        Full decoded JWT claims for advanced use.
    """

    uid: int
    sub: str
    roles: List[str]
    tenant_id: Optional[int]
    claims: Dict[str, Any]

    # ────────────────────────────────────────────────
    # Factory method
    # ────────────────────────────────────────────────
    @classmethod
    def from_claims(cls, claims: Dict[str, Any]) -> "Principal":
        """Build a Principal instance from JWT claims."""
        uid = claims.get("uid") or claims.get("sub") or claims.get("user_id")
        sub = claims.get("sub") or str(uid)
        roles = claims.get("roles", [])
        tenant_id = claims.get("tenant_id")
        return cls(uid=int(uid), sub=sub, roles=roles, tenant_id=tenant_id, claims=claims)

    # ────────────────────────────────────────────────
    # Role utilities
    # ────────────────────────────────────────────────
    def has_role(self, *role_codes: str) -> bool:
        """Check if principal has any of the specified roles."""
        return any(r in self.roles for r in role_codes)

    def is_sys_admin(self) -> bool:
        return "SYS_ADMIN" in self.roles

    def is_tenant_admin(self) -> bool:
        return "TENANT_ADMIN" in self.roles
