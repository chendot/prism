import warnings

import pytest

from prism.core.schema import PrismDoc
from prism.core.validator import PrismValidationError, validate_prism_doc, validate_prism_file


def test_validator_accepts_treasury_example() -> None:
    prism = validate_prism_file("examples/treasury.yaml")

    assert len(prism.nodes) == 7


def test_validator_rejects_role_not_in_ontology() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0]["role"] = "not_a_financial_role"
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="Unknown role"):
        validate_prism_doc(invalid)


@pytest.mark.parametrize("weight", ["high", "normal"])
def test_validator_rejects_weight_not_in_ontology(weight: str) -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0]["weight"] = weight
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="Available weights: muted, primary, secondary"):
        validate_prism_doc(invalid)


def test_validator_rejects_unknown_edge_node() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["edges"][0]["to"] = "missing_node"
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="unknown to node"):
        validate_prism_doc(invalid)


def test_validator_accepts_parallel_lanes_example() -> None:
    prism = validate_prism_file("examples/stablecoin-interest-parallel-lanes.yaml")

    assert prism.render.template == "parallel_lanes"


def test_validator_accepts_hierarchical_framework_example() -> None:
    prism = validate_prism_file("examples/prism-hierarchical-framework.yaml")

    assert len(prism.diagram.groups) == 4


def test_validator_rejects_hierarchical_group_cycle() -> None:
    prism = PrismDoc.from_yaml("examples/prism-hierarchical-framework.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["diagram"]["groups"][0]["parent"] = "story_layer"
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="parent cycle"):
        validate_prism_doc(invalid)


def test_validator_requires_hierarchical_node_groups() -> None:
    prism = PrismDoc.from_yaml("examples/prism-hierarchical-framework.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0]["group"] = None
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="must define group"):
        validate_prism_doc(invalid)


def test_validator_rejects_hierarchical_backward_edge() -> None:
    prism = PrismDoc.from_yaml("examples/prism-hierarchical-framework.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["edges"][0]["direction"] = "backward"
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="direction: forward"):
        validate_prism_doc(invalid)


def test_validator_rejects_hierarchical_cross_layer_jump() -> None:
    prism = PrismDoc.from_yaml("examples/prism-hierarchical-framework.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    edge = next(item for item in data["edges"] if item["from"] == "story_planning")
    edge["to"] = "dagre_layout"
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="next group"):
        validate_prism_doc(invalid)


def test_validator_warns_about_hierarchical_cognitive_overload() -> None:
    prism = PrismDoc.from_yaml("examples/prism-hierarchical-framework.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    base_node = data["nodes"][0]
    for index in range(6):
        data["nodes"].append(
            {**base_node, "id": f"extra_component_{index}", "label": f"Extra {index}"}
        )
    invalid = PrismDoc.model_validate(data)

    with pytest.warns(UserWarning, match="5 to 12 visible nodes; found 13"):
        validate_prism_doc(invalid)


def test_validator_accepts_hierarchical_overview_with_one_primary_per_group() -> None:
    prism = PrismDoc.from_yaml("examples/prism-hierarchical-framework.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["diagram"]["hierarchy_view"] = "overview"
    data["meta"]["target_format"] = "x_card"
    summary_node_ids = {"story_planning", "prism_schema", "dagre_layout"}
    data["nodes"] = [
        node for node in data["nodes"] if node["id"] in summary_node_ids
    ]
    for node in data["nodes"]:
        node["weight"] = "primary"
    data["edges"] = []
    data["render"]["highlight_nodes"] = ["prism_schema"]

    validate_prism_doc(PrismDoc.model_validate(data))


def test_validator_rejects_hierarchical_overview_with_more_than_two_supporting_nodes() -> None:
    prism = PrismDoc.from_yaml("examples/prism-hierarchical-framework.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["diagram"]["hierarchy_view"] = "overview"
    summary_node_ids = {
        "topic_discussion",
        "story_planning",
        "prism_schema",
        "dagre_layout",
    }
    data["nodes"] = [
        node for node in data["nodes"] if node["id"] in summary_node_ids
    ]
    for node in data["nodes"]:
        if node["id"] in {"story_planning", "prism_schema", "dagre_layout"}:
            node["weight"] = "primary"
    supporting = next(node for node in data["nodes"] if node["id"] == "topic_discussion")
    data["nodes"].append(
        {**supporting, "id": "story_context", "label": "Story Context"}
    )
    data["nodes"].append(
        {**supporting, "id": "story_scope", "label": "Story Scope"}
    )
    data["edges"] = []

    with pytest.raises(PrismValidationError, match="1 to 3 nodes"):
        validate_prism_doc(PrismDoc.model_validate(data))


def test_validator_requires_node_lanes_only_for_parallel_lanes() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0].pop("lane")
    invalid_parallel = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="must define lane"):
        validate_prism_doc(invalid_parallel)

    data["render"]["template"] = "value_flow"
    non_parallel = PrismDoc.model_validate(data)

    validate_prism_doc(non_parallel)


def test_validator_rejects_unknown_parallel_lane() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0]["lane"] = "missing_lane"
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="must match render.lanes id"):
        validate_prism_doc(invalid)


@pytest.mark.parametrize("thesis_count", [2, 3])
def test_validator_warns_only_above_thesis_soft_limit(thesis_count: int) -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    for node in data["nodes"][:thesis_count]:
        node["role"] = "thesis"
    candidate = PrismDoc.model_validate(data)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validated = validate_prism_doc(candidate)

    assert validated is candidate
    thesis_warnings = [warning for warning in caught if "thesis nodes" in str(warning.message)]
    assert len(thesis_warnings) == (1 if thesis_count == 3 else 0)
