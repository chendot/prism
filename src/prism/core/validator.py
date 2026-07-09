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
    weight_names = set(ontology.weights)

    invalid_roles = sorted({node.role for node in prism.nodes if node.role not in role_names})
    if invalid_roles:
        raise PrismValidationError(
            f"Unknown role(s) for ontology '{ontology.name}': {', '.join(invalid_roles)}"
        )

    invalid_weights = sorted(
        {node.weight for node in prism.nodes if node.weight not in weight_names}
    )
    if invalid_weights:
        available = ", ".join(sorted(weight_names)) or "none"
        raise PrismValidationError(
            f"Unknown node weight(s) for ontology '{ontology.name}': "
            f"{', '.join(invalid_weights)}. Available weights: {available}"
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

    if prism.render.template == "parallel_lanes":
        _validate_parallel_lanes(prism)

    return prism


def _validate_parallel_lanes(prism: PrismDoc) -> None:
    lanes = prism.render.lanes
    if len(lanes) < 2:
        raise PrismValidationError("parallel_lanes requires at least 2 render.lanes entries")

    lane_ids = [lane.id for lane in lanes]
    duplicate_lane_ids = sorted(
        {lane_id for lane_id in lane_ids if lane_ids.count(lane_id) > 1}
    )
    if duplicate_lane_ids:
        raise PrismValidationError(f"Duplicate render.lanes id(s): {', '.join(duplicate_lane_ids)}")

    lane_id_set = set(lane_ids)
    missing_lane_nodes = sorted(node.id for node in prism.nodes if not node.lane)
    if missing_lane_nodes:
        raise PrismValidationError(
            "parallel_lanes nodes must define lane: " + ", ".join(missing_lane_nodes)
        )

    invalid_lane_nodes = sorted(
        f"{node.id}:{node.lane}"
        for node in prism.nodes
        if node.lane is not None and node.lane not in lane_id_set
    )
    if invalid_lane_nodes:
        available = ", ".join(sorted(lane_id_set))
        raise PrismValidationError(
            "parallel_lanes node lane must match render.lanes id. "
            f"Invalid node lane(s): {', '.join(invalid_lane_nodes)}. "
            f"Available lanes: {available}"
        )


def validate_prism_file(path: str | Path) -> PrismDoc:
    """Load a prism.yaml file and validate it against its selected ontology."""

    prism = PrismDoc.from_yaml(str(path))
    return validate_prism_doc(prism)
