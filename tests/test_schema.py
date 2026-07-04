from prism.core.schema import PrismDoc


def test_schema_loads_treasury_example() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")

    assert prism.meta.ontology == "financial"
    assert prism.diagram.direction == "LR"
    assert prism.nodes[0].id == "treasury"
    assert prism.edges[0].from_ == "treasury"


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
