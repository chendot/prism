import pytest

from prism.core.schema import PrismDoc
from prism.ontologies.loader import load_ontology
from prism.render.mermaid import MermaidRenderer
from prism.render.theme import load_theme


def _document(
    *,
    role: str = "asset",
    status: str = "neutral",
    edge_type: str | None = None,
) -> PrismDoc:
    nodes = [{"id": "source", "label": "Source", "role": role, "status": status}]
    edges = []
    if edge_type is not None:
        nodes.append({"id": "target", "label": "Target", "role": "asset"})
        edges.append(
            {
                "from": "source",
                "to": "target",
                "type": edge_type,
                "direction": "forward",
            }
        )
    return PrismDoc.model_validate(
        {
            "meta": {
                "title": "Visual grammar",
                "topic": "Visual grammar",
                "ontology": "financial",
                "audience": "expert",
                "language": "en",
            },
            "diagram": {"type": "flow", "direction": "LR"},
            "nodes": nodes,
            "edges": edges,
        }
    )


def _node_group(svg: str, node_id: str = "source") -> str:
    return svg.split(f'data-node-id="{node_id}"', 1)[1].split("</g>", 1)[0]


@pytest.mark.parametrize("role", list(load_ontology("financial").roles))
def test_each_role_renders_its_ontology_shape(role: str) -> None:
    ontology = load_ontology("financial")
    visual = ontology.role_visual(role)
    svg = MermaidRenderer().to_svg(_document(role=role), ontology)
    group = _node_group(svg)

    rect_count = group.count('class="node-shape')
    assert rect_count == (2 if visual["shape"] == "double_border" else 1)
    assert f'rx="{visual["radius"]}"' in group
    assert f'stroke-width="{visual["border_width"]:g}"' in group
    assert ('class="prism-node-accent"' in group) is bool(visual["accent_bar"])


def test_round_and_double_border_shapes_have_required_geometry() -> None:
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()

    round_group = _node_group(renderer.to_svg(_document(role="entry"), ontology))
    double_group = _node_group(renderer.to_svg(_document(role="protocol"), ontology))

    assert 'rx="16"' in round_group
    assert 'class="node-shape node-shape-outer"' in double_group
    assert 'class="node-shape node-shape-inner"' in double_group


def test_status_colors_come_from_theme() -> None:
    ontology = load_ontology("financial")
    theme = load_theme("warm_layered")
    renderer = MermaidRenderer()

    positive = _node_group(renderer.to_svg(_document(status="positive"), ontology))
    negative = _node_group(
        renderer.to_svg(_document(role="risk", status="negative"), ontology)
    )

    assert f'fill="{theme.accent_result}"' in positive
    assert f'stroke="{theme.accent_result}"' in positive
    assert f'fill="{theme.surface}"' in negative
    assert f'stroke="{theme.accent_risk}"' in negative
    assert 'stroke-dasharray="4,3"' in negative


def test_highlight_role_scale_is_applied_during_layout() -> None:
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()
    prism = _document(role="thesis", status="highlight")

    unscaled = renderer._layout_nodes(prism)["positions"]["source"]
    scaled = renderer._layout_nodes(prism, ontology)["positions"]["source"]

    assert scaled[2] == pytest.approx(unscaled[2] * ontology.role_visual("thesis")["scale"])
    assert scaled[3] == pytest.approx(unscaled[3] * ontology.role_visual("thesis")["scale"])


@pytest.mark.parametrize("edge_type", list(load_ontology("financial").edge_types))
def test_each_edge_type_renders_ontology_stroke(edge_type: str) -> None:
    ontology = load_ontology("financial")
    visual = ontology.edge_visual(edge_type)
    svg = MermaidRenderer().to_svg(_document(edge_type=edge_type), ontology)
    edge_path = svg.split(f'data-edge-type="{edge_type}"', 1)[1].split("/>", 1)[0]

    assert f'stroke-width="{visual["stroke_width"]}"' in edge_path
    if visual["stroke_dash"] is None:
        assert "stroke-dasharray" not in edge_path
    else:
        assert f'stroke-dasharray="{visual["stroke_dash"]}"' in edge_path

    if visual["arrow"] == "none":
        assert "marker-end" not in edge_path
    else:
        assert f'marker-end="url(#arrow-{visual["arrow"]})"' in edge_path
