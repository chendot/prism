"""Runtime ontology loading for Prism.

Ontologies are the controlled vocabularies and visual mappings used by the
validator and renderers. They are intentionally separate from the Pydantic
schema so domains can be added without editing core models.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from prism.core.models import Ontology

ONTOLOGY_DIR = Path(__file__).resolve().parent


def list_ontologies() -> list[str]:
    """List ontology names available in the package."""

    return sorted(path.stem for path in ONTOLOGY_DIR.glob("*.yaml"))


def load_ontology(name: str) -> Ontology:
    """Load an ontology by name from ``src/prism/ontologies``."""

    path = ONTOLOGY_DIR / f"{name}.yaml"
    if not path.exists():
        available = ", ".join(list_ontologies()) or "none"
        raise FileNotFoundError(f"Unknown ontology '{name}'. Available: {available}")

    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    return Ontology(
        name=data["name"],
        description=data.get("description", ""),
        roles=data.get("roles", {}),
        edge_types=data.get("edge_types", {}),
        perspectives=data.get("perspectives", []),
    )
