"""Perspective helpers for optional Layer 1 research."""

from __future__ import annotations

from prism.core.models import Ontology


def perspectives_for(ontology: Ontology) -> list[dict[str, str]]:
    """Return predefined research perspectives from an ontology."""

    return ontology.perspectives
