"""Placeholder compressor for Prism Layer 2."""

from __future__ import annotations

from typing import Any

from prism.compression.base import Compressor
from prism.core.models import Ontology
from prism.core.schema import Diagram, Meta, Node, PrismDoc, RenderConfig
from prism.core.validator import validate_prism_doc


class PlaceholderCompressor(Compressor):
    """Minimal compressor that creates a valid stub PrismDoc.

    TODO: Replace this with an LLM or deterministic compression implementation.
    The important contract is already present: output must validate before it
    can be rendered.
    """

    def compress(
        self, topic: str, findings: dict[str, Any] | None, ontology: Ontology
    ) -> PrismDoc:
        """Create a tiny valid PrismDoc from a topic and optional findings."""

        first_role = next(iter(ontology.roles), "component")
        prism = PrismDoc(
            meta=Meta(
                title=topic,
                subtitle="Placeholder compression output",
                topic=topic,
                ontology=ontology.name,
                audience="beginner",
                language="zh",
                tags=["placeholder"],
            ),
            diagram=Diagram(type="flow", direction="LR"),
            nodes=[
                Node(
                    id="topic",
                    label=topic,
                    sublabel="TODO: replace with compressed structure",
                    role=first_role,
                )
            ],
            edges=[],
            loops=[],
            render=RenderConfig(renderer="mermaid"),
        )
        return validate_prism_doc(prism, ontology)
