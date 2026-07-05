"""Compressor interface for Layer 2.

Compressors turn a topic and optional findings into a validated ``PrismDoc``.
They are replaceable so future LLM-backed or rules-backed compressors can share
the same contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from prism.core.models import Ontology
from prism.core.schema import PrismDoc


class Compressor(ABC):
    """Abstract base class for topic/findings to prism.yaml compression."""

    @abstractmethod
    def compress(
        self, topic: str, findings: dict[str, Any] | None, ontology: Ontology
    ) -> PrismDoc:
        """Convert a topic plus optional research findings into a PrismDoc."""
