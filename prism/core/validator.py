"""Validation across Prism's schema and runtime ontologies."""

from __future__ import annotations

from pathlib import Path

from prism.core.models import Ontology
from prism.core.schema import PrismDoc
from prism.ontologies.loader import load_ontology


class PrismValidationError(ValueError):
    """Raised when a prism.yaml document violates graph or ontology rules."""


def validate_prism_doc(prism: PrismDoc, ontology: Ontology | None = None) -> PrismDoc:
    """Validate a Prism document before it enters Layer 3 rendering.

    Pydantic handles structural validation. This function validates runtime
    constraints: selected ontology, node references, role vocabulary, edge type
    vocabulary, and highlight/loop references.
    """

    ontology = ontology or load_ontology(prism.meta.ontology)
    if ontology.name != prism.meta.ontology:
        raise PrismValidationError(
            f"Document asks for ontology '{prism.meta.ontology}', got '{ontology.name}'"
        )

    node_ids = [node.id for node in prism.nodes]
    duplicate_ids = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
    if duplicate_ids:
        raise PrismValidationError(f"Duplicate node ids: {', '.join(duplicate_ids)}")

    node_id_set = set(node_ids)
    role_names = set(ontology.roles)
    edge_type_names = set(ontology.edge_types)

    invalid_roles = sorted({node.role for node in prism.nodes if node.role not in role_names})
    if invalid_roles:
        raise PrismValidationError(
            f"Unknown role(s) for ontology '{ontology.name}': {', '.join(invalid_roles)}"
        )

    for edge in prism.edges:
        if edge.from_ not in node_id_set:
            raise PrismValidationError(f"Edge references unknown from node '{edge.from_}'")
        if edge.to not in node_id_set:
            raise PrismValidationError(f"Edge references unknown to node '{edge.to}'")
        if edge.type not in edge_type_names:
            raise PrismValidationError(
                f"Unknown edge type '{edge.type}' for ontology '{ontology.name}'"
            )

    for loop in prism.loops:
        missing = sorted(set(loop.nodes) - node_id_set)
        if missing:
            raise PrismValidationError(
                f"Loop '{loop.id}' references unknown node(s): {', '.join(missing)}"
            )

    missing_highlights = sorted(set(prism.render.highlight_nodes) - node_id_set)
    if missing_highlights:
        raise PrismValidationError(
            f"highlight_nodes references unknown node(s): {', '.join(missing_highlights)}"
        )

    return prism


def validate_prism_file(path: str | Path) -> PrismDoc:
    """Load a prism.yaml file and validate it against its selected ontology."""

    prism = PrismDoc.from_yaml(str(path))
    return validate_prism_doc(prism)
