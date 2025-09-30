from dataclasses import dataclass

@dataclass(frozen=True)
class Principal:
    uid: int
    sub: str
    claims: dict
