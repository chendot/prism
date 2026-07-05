"""Renderer interface for Layer 3.

Renderers consume only validated ``PrismDoc`` objects plus their ontology.
This keeps output targets pluggable and isolated from research/compression.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from prism.core.models import Ontology
from prism.core.schema import PrismDoc


class Renderer(ABC):
    """Abstract base class for deterministic Prism renderers."""

    @abstractmethod
    def render(self, prism: PrismDoc, ontology: Ontology) -> str:
        """Render ``prism.yaml`` plus ontology into an output string or path."""
