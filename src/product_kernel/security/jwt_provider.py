import os, time, typing as t
from functools import lru_cache
import jwt  # PyJWT

"""
──────────────────────────────────────────────────────────────────────────────
JwtProvider: Simple JWT Encode/Decode Service
──────────────────────────────────────────────────────────────────────────────
Purpose:
    Provide a consistent JWT implementation (based on PyJWT).

Features:
    - Encodes claims with iat/exp fields.
    - Decodes tokens and validates signature.
    - Caches singleton provider via get_provider().

Environment variables:
    JWT_SECRET  → secret key (default: 'dev-secret')
    JWT_ALG     → algorithm (default: HS256)
    JWT_TTL     → default TTL seconds (default: 3600)

Usage:
    from product_kernel.security.jwt_provider import get_provider
    jwt = get_provider()

    token = jwt.encode({"uid": 1, "sub": "user@example.com"})
    claims = jwt.decode(token)
"""

class JwtProvider:
    def __init__(self,
                 secret: str | None = None,
                 algorithm: str = "HS256",
                 ttl_seconds: int | None = None):
        self.secret = secret or os.getenv("JWT_SECRET", "dev-secret")
        self.algorithm = algorithm or os.getenv("JWT_ALG", "HS256")
        # default TTL = 1 hour
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else int(os.getenv("JWT_TTL", "3600"))

    def encode(self, claims: dict, ttl_seconds: int | None = None) -> str:
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        now = int(time.time())
        payload = dict(claims)
        payload.setdefault("iat", now)
        payload.setdefault("exp", now + ttl)
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def decode(self, token: str) -> dict:
        return jwt.decode(token, self.secret, algorithms=[self.algorithm])

@lru_cache(maxsize=1)
def get_provider() -> JwtProvider:
    # singleton (reads env once)
    return JwtProvider()
