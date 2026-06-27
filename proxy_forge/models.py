from dataclasses import dataclass


@dataclass(frozen=True)
class ProxyInput:
    proxy: str
    grade: str = ""
    source: str = ""
