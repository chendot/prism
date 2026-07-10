import logging

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


def test_yaml_statuses_resolve_positive_and_solid_highlight(tmp_path, caplog) -> None:
    path = tmp_path / "status-visuals.yaml"
    path.write_text(
        """meta:
  title: Status visuals
  topic: Status visuals
  ontology: financial
  audience: expert
  language: en
diagram:
  type: flow
  direction: LR
nodes:
  - id: positive_result
    label: Positive result
    role: benefit
    status: positive
  - id: core_thesis
    label: Core thesis
    role: thesis
    status: highlight
edges:
  - from: positive_result
    to: core_thesis
    type: benefit_flow
    direction: forward
""",
        encoding="utf-8",
    )
    ontology = load_ontology("financial")
    theme = load_theme("warm_layered")
    renderer = MermaidRenderer()
    prism = PrismDoc.from_yaml(str(path))
    caplog.set_level(logging.DEBUG, logger="prism.render.mermaid")

    rendered_html = renderer.render(prism, ontology)
    positive = _node_group(rendered_html, "positive_result")
    thesis = _node_group(rendered_html, "core_thesis")
    unscaled = renderer._layout_nodes(prism)["positions"]["core_thesis"]
    scaled = renderer._layout_nodes(prism, ontology)["positions"]["core_thesis"]

    assert prism.nodes[0].status.value == "positive"
    assert prism.nodes[1].status.value == "highlight"
    assert theme.accent_result in rendered_html
    assert f'fill="{theme.accent_result}"' in positive
    assert f'stroke="{theme.accent_result}"' in positive
    assert f'fill="{theme.accent_result}"' in thesis
    assert f'stroke="{theme.accent_result}"' in thesis
    assert 'stroke-width="2"' in thesis
    assert "stroke-dasharray" not in thesis
    assert scaled[2] == pytest.approx(unscaled[2] * 1.15)
    assert scaled[3] == pytest.approx(unscaled[3] * 1.15)
    assert "status=positive fill=#e07b5a" in caplog.text
    assert "status=highlight fill=#e07b5a" in caplog.text


def test_final_html_contains_visible_markers_and_positive_example_fills() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    ontology = load_ontology("financial")
    theme = load_theme("warm_layered")

    rendered_html = MermaidRenderer().render(prism, ontology)

    assert '<marker id="filled_triangle"' in rendered_html
    assert '<marker id="filled_triangle_large"' in rendered_html
    assert '<marker id="open_triangle"' in rendered_html
    for node_id in ("reserve_yield", "lending_interest", "funding_income"):
        group = _node_group(rendered_html, node_id)
        assert 'data-status="positive"' in group
        assert f'fill="{theme.accent_result}"' in group
    for edge in prism.edges:
        visual = ontology.edge_visual(edge.type)
        edge_path = rendered_html.split(
            f'data-edge-type="{edge.type}"', 1
        )[1].split("/>", 1)[0]
        if visual["arrow"] == "none":
            assert "marker-end" not in edge_path
        else:
            assert f'marker-end="url(#{visual["arrow"]})"' in edge_path


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
        assert f'marker-end="url(#{visual["arrow"]})"' in edge_path
