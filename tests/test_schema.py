import pytest
from pydantic import ValidationError

from prism.core.schema import PrismDoc


def test_schema_loads_treasury_example() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")

    assert prism.meta.ontology == "financial"
    assert prism.diagram.direction == "LR"
    assert prism.nodes[0].id == "treasury"
    assert prism.edges[0].from_ == "treasury"


def test_schema_accepts_optional_diagram_thesis() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["diagram"]["thesis"] = "利息收益的归属决定了激励分配。"

    validated = PrismDoc.model_validate(data)

    assert validated.diagram.thesis == "利息收益的归属决定了激励分配。"


def test_schema_rejects_non_snake_case_node_id() -> None:
    data = {
        "meta": {
            "title": "Bad",
            "topic": "Bad",
            "ontology": "financial",
            "audience": "beginner",
            "language": "en",
            "tags": [],
        },
        "diagram": {"type": "flow", "direction": "LR"},
        "nodes": [{"id": "BadNode", "label": "Bad", "role": "issuer"}],
        "edges": [],
        "loops": [],
        "render": {
            "style": "default",
            "show_loops": True,
            "highlight_nodes": [],
            "highlight_edges": [],
            "renderer": "mermaid",
        },
    }

    try:
        PrismDoc.model_validate(data)
    except ValueError as exc:
        assert "snake_case" in str(exc)
    else:
        raise AssertionError("Expected schema validation to fail")


def test_schema_defaults_node_weight_to_secondary_without_enum_validation() -> None:
    data = {
        "meta": {
            "title": "Weighted",
            "topic": "Weighted",
            "ontology": "financial",
            "audience": "beginner",
            "language": "en",
            "tags": [],
        },
        "diagram": {"type": "flow", "direction": "LR"},
        "nodes": [
            {"id": "normal_node", "label": "Normal", "role": "asset"},
            {"id": "custom_node", "label": "Custom", "role": "asset", "weight": "custom"},
        ],
        "edges": [],
        "loops": [],
        "render": {
            "style": "default",
            "show_loops": True,
            "highlight_nodes": [],
            "highlight_edges": [],
            "renderer": "mermaid",
        },
    }

    prism = PrismDoc.model_validate(data)

    assert prism.nodes[0].weight == "secondary"
    assert prism.nodes[1].weight == "custom"


def test_schema_accepts_parallel_lane_fields() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")

    assert prism.render.template == "parallel_lanes"
    assert prism.nodes[0].lane == "collateral_lending"
    assert [lane.id for lane in prism.render.lanes] == [
        "fiat_reserve",
        "collateral_lending",
        "delta_hedge",
    ]


@pytest.mark.parametrize("status", ["neutral", "positive", "negative", "highlight"])
def test_schema_accepts_valid_node_status(status: str) -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0]["status"] = status

    validated = PrismDoc.model_validate(data)

    assert validated.nodes[0].status.value == status


def test_schema_rejects_invalid_node_status() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0]["status"] = "urgent"

    with pytest.raises(ValidationError, match="neutral|positive|negative|highlight"):
        PrismDoc.model_validate(data)


def test_schema_defaults_missing_node_status_to_neutral() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0].pop("status")

    validated = PrismDoc.model_validate(data)

    assert validated.nodes[0].status.value == "neutral"
