"""Placeholder research engine for Layer 1."""

from __future__ import annotations

from typing import Any

from prism.core.models import Ontology
from prism.research.base import ResearchEngine
from prism.research.interview import generate_questions


class PlaceholderResearchEngine(ResearchEngine):
    """Create findings scaffolds without calling retrieval or LLM APIs."""

    def research(self, topic: str, ontology: Ontology) -> dict[str, Any]:
        """Return perspective questions and empty extracted findings."""

        return {
            "topic": topic,
            "ontology": ontology.name,
            "questions": generate_questions(topic, ontology),
            "entities": [],
            "relations": [],
        }
