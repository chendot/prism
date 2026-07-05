"""Research interface for optional Layer 1."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from prism.core.models import Ontology


class ResearchEngine(ABC):
    """Abstract base class for optional multi-perspective research."""

    @abstractmethod
    def research(self, topic: str, ontology: Ontology) -> dict[str, Any]:
        """Run multi-perspective research and return raw findings."""
