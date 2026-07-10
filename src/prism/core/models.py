"""Shared domain-neutral data classes for Prism.

These models support all three layers without depending on any renderer,
compressor, or research engine implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Ontology:
    """Runtime vocabulary and visual mapping for one Prism domain."""

    name: str
    description: str
    roles: dict[str, dict[str, Any]]
    edge_types: dict[str, dict[str, Any]]
    weights: dict[str, dict[str, Any]]
    perspectives: list[dict[str, str]] = field(default_factory=list)

    def role_style(self, role: str) -> dict[str, Any]:
        """Return visual metadata for a role, or an empty mapping."""

        return self.roles.get(role, {})

    def role_visual(self, role: str) -> dict[str, Any]:
        """Return renderer-facing visual fields for a role."""

        return self.role_style(role).get("visual", {})

    def edge_style(self, edge_type: str) -> dict[str, Any]:
        """Return visual metadata for an edge type, or an empty mapping."""

        return self.edge_types.get(edge_type, {})

    def edge_visual(self, edge_type: str) -> dict[str, Any]:
        """Return renderer-facing visual fields for an edge type."""

        return self.edge_style(edge_type).get("visual", {})

    def weight_style(self, weight: str) -> dict[str, Any]:
        """Return visual metadata for a node weight, or an empty mapping."""

        return self.weights.get(weight, {})
