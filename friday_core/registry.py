"""Capability Registry — registro central de capacidades do FRIDAY."""

from __future__ import annotations
from typing import Optional
from .types import Capability, CapabilityCategory, CapabilityImpl, RiskLevel


class CapabilityRegistry:
    def __init__(self):
        self._caps: dict[str, Capability] = {}

    def register(self, cap: Capability) -> None:
        if cap.name in self._caps:
            raise ValueError(f"Capability já registada: {cap.name}")
        self._caps[cap.name] = cap

    def get(self, name: str) -> Optional[Capability]:
        return self._caps.get(name)

    def require(self, name: str) -> Capability:
        cap = self._caps.get(name)
        if cap is None:
            raise KeyError(f"Capability não registada: {name}")
        return cap

    def by_category(self, cat: CapabilityCategory) -> list[Capability]:
        return [c for c in self._caps.values() if c.category == cat]

    def all(self) -> list[Capability]:
        return list(self._caps.values())

    def healthy(self) -> list[Capability]:
        return [c for c in self._caps.values() if c.impl.health()]

    def summary(self) -> dict:
        return {
            "total": len(self._caps),
            "by_category": {cat.value: len(self.by_category(cat)) for cat in CapabilityCategory},
            "healthy": len(self.healthy()),
            "names": list(self._caps.keys()),
        }
