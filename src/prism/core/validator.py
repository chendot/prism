"""Validation across Prism's schema and runtime ontologies."""

from __future__ import annotations

import warnings
from pathlib import Path

from prism.core.models import Ontology
from prism.core.schema import Direction, EdgeDirection, HierarchyView, PrismDoc
from prism.ontologies.loader import load_ontology


class PrismValidationError(ValueError):
    """Raised when a prism.yaml document violates graph or ontology rules."""


_HIERARCHY_NODE_GUIDANCE: dict[str, tuple[int, int]] = {
    "wechat_cover": (3, 5),
    "x_card": (3, 6),
    "xiaohongshu_card": (5, 12),
    "xiaohongshu_carousel": (8, 20),
}


def _warn_hierarchy_density(prism: PrismDoc) -> None:
    target_format = prism.meta.target_format or "xiaohongshu_card"
    minimum, maximum = _HIERARCHY_NODE_GUIDANCE.get(target_format, (6, 15))
    node_count = len(prism.nodes)
    if minimum <= node_count <= maximum:
        return
    warnings.warn(
        "hierarchical_framework density guidance for "
        f"'{target_format}' is {minimum} to {maximum} visible nodes; found {node_count}. "
        "This is a cognitive-design warning, not a structural validation error.",
        UserWarning,
        stacklevel=3,
    )


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

    thesis_count = sum(node.role == "thesis" for node in prism.nodes)
    if thesis_count > 2:
        warnings.warn(
            f"Visual grammar recommends at most 2 thesis nodes; found {thesis_count}",
            UserWarning,
            stacklevel=2,
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
    if prism.render.template == "hierarchical_framework":
        _validate_hierarchical_framework(prism)

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


def _validate_hierarchical_framework(prism: PrismDoc) -> None:
    groups = prism.diagram.groups
    if len(groups) < 2:
        raise PrismValidationError(
            "hierarchical_framework requires at least 2 diagram.groups entries"
        )

    group_ids = [group.id for group in groups]
    duplicate_group_ids = sorted(
        {group_id for group_id in group_ids if group_ids.count(group_id) > 1}
    )
    if duplicate_group_ids:
        raise PrismValidationError(
            f"Duplicate diagram.groups id(s): {', '.join(duplicate_group_ids)}"
        )

    group_id_set = set(group_ids)
    group_by_id = {group.id: group for group in groups}
    invalid_parents = sorted(
        f"{group.id}:{group.parent}"
        for group in groups
        if group.parent is not None and group.parent not in group_id_set
    )
    if invalid_parents:
        raise PrismValidationError(
            "diagram.groups parent must reference an existing group. "
            f"Invalid parent(s): {', '.join(invalid_parents)}"
        )

    parent_by_group = {group.id: group.parent for group in groups}
    for group_id in group_ids:
        seen: set[str] = set()
        current: str | None = group_id
        depth = 0
        while current is not None:
            if current in seen:
                raise PrismValidationError(
                    f"diagram.groups contains a parent cycle involving '{current}'"
                )
            seen.add(current)
            current = parent_by_group.get(current)
            depth += 1
            if depth > 3:
                raise PrismValidationError(
                    "hierarchical_framework supports at most 3 nested group levels"
                )

    sibling_orders: dict[str | None, list[int]] = {}
    for group in groups:
        sibling_orders.setdefault(group.parent, []).append(group.order)
    duplicate_order_parents = sorted(
        parent or "root"
        for parent, orders in sibling_orders.items()
        if len(orders) != len(set(orders))
    )
    if duplicate_order_parents:
        raise PrismValidationError(
            "hierarchical_framework sibling group order must be unique under: "
            + ", ".join(duplicate_order_parents)
        )

    ungrouped_nodes = sorted(node.id for node in prism.nodes if not node.group)
    if ungrouped_nodes:
        raise PrismValidationError(
            "hierarchical_framework nodes must define group: " + ", ".join(ungrouped_nodes)
        )

    invalid_node_groups = sorted(
        f"{node.id}:{node.group}"
        for node in prism.nodes
        if node.group is not None and node.group not in group_id_set
    )
    if invalid_node_groups:
        raise PrismValidationError(
            "hierarchical_framework node group must match diagram.groups id. "
            f"Invalid node group(s): {', '.join(invalid_node_groups)}"
        )

    if prism.diagram.direction != Direction.TD:
        raise PrismValidationError("hierarchical_framework requires diagram.direction: TD")
    if prism.diagram.hierarchy_view is None:
        raise PrismValidationError("hierarchical_framework requires diagram.hierarchy_view")
    if not prism.diagram.abstraction_level or not prism.diagram.abstraction_level.strip():
        raise PrismValidationError("hierarchical_framework requires diagram.abstraction_level")
    if prism.diagram.focus_group not in group_id_set:
        raise PrismValidationError(
            "hierarchical_framework diagram.focus_group must reference diagram.groups"
        )
    if not 1 <= len(prism.diagram.omitted_details) <= 5:
        raise PrismValidationError(
            "hierarchical_framework diagram.omitted_details must contain 1 to 5 items"
        )

    _warn_hierarchy_density(prism)

    if prism.diagram.hierarchy_view == HierarchyView.OVERVIEW:
        focus_group = prism.diagram.focus_group
        direct_children = [group for group in groups if group.parent == focus_group]
        if not 3 <= len(direct_children) <= 7:
            raise PrismValidationError(
                "hierarchical_framework overview requires 3 to 7 direct child groups"
            )
        allowed_group_ids = {focus_group, *(group.id for group in direct_children)}
        unexpected_groups = sorted(group_id_set - allowed_group_ids)
        if unexpected_groups:
            raise PrismValidationError(
                "hierarchical_framework overview cannot expand grandchildren: "
                + ", ".join(unexpected_groups)
            )
        nodes_by_group = {
            group.id: [node for node in prism.nodes if node.group == group.id]
            for group in direct_children
        }
        invalid_child_counts = sorted(
            f"{group_id}:{len(nodes)}"
            for group_id, nodes in nodes_by_group.items()
            if not 1 <= len(nodes) <= 3
        )
        if invalid_child_counts:
            raise PrismValidationError(
                "hierarchical_framework overview requires 1 to 3 nodes per child group: "
                + ", ".join(invalid_child_counts)
            )
        invalid_primary_counts = sorted(
            f"{group_id}:{sum(node.weight == 'primary' for node in nodes)}"
            for group_id, nodes in nodes_by_group.items()
            if sum(node.weight == "primary" for node in nodes) != 1
        )
        if invalid_primary_counts:
            raise PrismValidationError(
                "hierarchical_framework overview requires exactly one primary summary node per child group: "
                + ", ".join(invalid_primary_counts)
            )
        focus_nodes = sorted(node.id for node in prism.nodes if node.group == focus_group)
        if focus_nodes:
            raise PrismValidationError(
                "hierarchical_framework overview focus group must not contain direct nodes: "
                + ", ".join(focus_nodes)
            )

    node_group_by_id = {node.id: node.group for node in prism.nodes}
    for edge in prism.edges:
        if edge.direction != EdgeDirection.FORWARD:
            raise PrismValidationError(
                "hierarchical_framework edges must use direction: forward"
            )
        source_group_id = node_group_by_id[edge.from_]
        target_group_id = node_group_by_id[edge.to]
        if source_group_id == target_group_id:
            continue
        source_group = group_by_id[source_group_id]
        target_group = group_by_id[target_group_id]
        if source_group.parent != target_group.parent:
            raise PrismValidationError(
                "hierarchical_framework cross-group edges must connect sibling groups: "
                f"{edge.from_}->{edge.to}"
            )
        if target_group.order - source_group.order != 1:
            raise PrismValidationError(
                "hierarchical_framework cross-group edges must point down to the next group: "
                f"{edge.from_}->{edge.to}"
            )


def validate_prism_file(path: str | Path) -> PrismDoc:
    """Load a prism.yaml file and validate it against its selected ontology."""

    prism = PrismDoc.from_yaml(str(path))
    return validate_prism_doc(prism)
