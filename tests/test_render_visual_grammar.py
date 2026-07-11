import logging
import re

import pytest

from prism.core.schema import PrismDoc
from prism.ontologies.loader import load_ontology
from prism.render.mermaid import LayoutConfig, MermaidRenderer
from prism.render.icons import ROLE_ICON_PATHS
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
    if visual["accent_bar"]:
        assert '<path class="prism-node-accent"' in group
        assert 'fill="none" stroke="url(#grad_bar_primary)"' in group
        outer = re.search(r'class="node-shape node-shape-outer" x="([\d.]+)" y="([\d.]+)"', group)
        assert outer is not None
        x, y = map(float, outer.groups())
        radius = float(visual["radius"])
        assert f'M {x + radius:.1f} {y:.1f} Q {x:.1f} {y:.1f} {x:.1f}' in group
        assert 'stroke-linecap="round"' in group


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

    assert 'fill="url(#grad_positive)"' in positive
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

    rendered_svg = renderer.to_svg(prism, ontology)
    positive = _node_group(rendered_svg, "positive_result")
    thesis = _node_group(rendered_svg, "core_thesis")
    unscaled = renderer._layout_nodes(prism)["positions"]["core_thesis"]
    scaled = renderer._layout_nodes(prism, ontology)["positions"]["core_thesis"]

    assert prism.nodes[0].status.value == "positive"
    assert prism.nodes[1].status.value == "highlight"
    assert theme.accent_result in rendered_svg
    assert 'fill="url(#grad_positive)"' in positive
    assert f'stroke="{theme.accent_result}"' in positive
    assert 'fill="url(#grad_highlight)"' in thesis
    assert f'stroke="{theme.accent_result}"' in thesis
    assert 'stroke-width="2"' in thesis
    assert "stroke-dasharray" not in thesis
    assert scaled[2] == pytest.approx(unscaled[2] * 1.15)
    assert scaled[3] == pytest.approx(unscaled[3] * 1.15)
    assert "status=positive fill=url(#grad_positive)" in caplog.text
    assert "status=highlight fill=url(#grad_highlight)" in caplog.text


def test_final_html_contains_visible_markers_and_positive_example_fills() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    ontology = load_ontology("financial")
    theme = load_theme("warm_layered")

    rendered_svg = MermaidRenderer().to_svg(prism, ontology)

    assert '<marker id="filled_triangle"' in rendered_svg
    assert '<marker id="filled_triangle_large"' in rendered_svg
    assert '<marker id="open_triangle"' in rendered_svg
    for node_id in ("reserve_yield", "lending_interest", "funding_income"):
        group = _node_group(rendered_svg, node_id)
        assert 'data-status="positive"' in group
        assert 'fill="url(#grad_positive)"' in group
        assert 'stroke="url(#grad_bar_result)"' in group
    for edge in prism.edges:
        visual = ontology.edge_visual(edge.type)
        edge_path = rendered_svg.split(
            f'data-edge-type="{edge.type}"', 1
        )[1].split("/>", 1)[0]
        if visual["arrow"] == "none":
            assert "marker-end" not in edge_path
        else:
            assert f'marker-end="url(#{visual["arrow"]})"' in edge_path


def test_final_svg_defines_node_and_accent_bar_gradients() -> None:
    ontology = load_ontology("financial")
    svg = MermaidRenderer().to_svg(_document(role="benefit", status="positive"), ontology)

    assert '<linearGradient id="grad_neutral"' in svg
    assert '<linearGradient id="grad_positive"' in svg
    assert '<linearGradient id="grad_highlight"' in svg
    assert 'stop-color="#2b211b"' in svg
    assert 'stop-color="#1f1814"' in svg
    assert 'stop-color="#ef805d"' in svg
    assert 'stop-opacity="0.82"' in svg
    assert '<linearGradient id="grad_bar_result"' in svg
    assert 'stop-opacity="0.2"' in svg


def test_primary_and_highlight_nodes_use_distinct_accent_glows() -> None:
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()
    highlight = _node_group(renderer.to_svg(_document(role="thesis", status="highlight"), ontology))
    primary_data = _document(role="asset").model_dump(mode="json", by_alias=True)
    primary_data["nodes"][0]["weight"] = "primary"
    primary = _node_group(renderer.to_svg(PrismDoc.model_validate(primary_data), ontology))
    neutral = _node_group(renderer.to_svg(_document(role="asset"), ontology))
    svg = renderer.to_svg(_document(role="thesis", status="highlight"), ontology)

    assert '<filter id="glow_primary"' in svg
    assert '<filter id="glow_highlight"' in svg
    assert '<feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="blur" />' in svg
    assert 'flood-color="#e5bc6a" flood-opacity="0.28"' in svg
    assert 'flood-color="#ef805d" flood-opacity="0.48"' in svg
    assert 'class="node-shape node-shape-outer"' in highlight
    assert 'filter="url(#glow_highlight)"' in highlight
    assert 'filter="url(#glow_primary)"' in primary
    assert 'filter="url(#glow_' not in neutral
    assert 'fill="#1f1814" font-size="15"' in highlight
    assert 'stroke="#1f1814"' in highlight
    assert 'fill="#f7e6c4" font-size="15"' in neutral


def test_typography_hierarchy_uses_layout_config() -> None:
    config = LayoutConfig()
    assert config.title_font_weight == 700
    assert config.subtitle_opacity == 0.84
    assert config.edge_label_opacity == 0.94
    assert config.edge_opacity == 0.96
    assert config.edge_label_font_size_offset == -1

    data = _document().model_dump(mode="json", by_alias=True)
    data["nodes"][0]["sublabel"] = "Secondary detail"
    data["edges"] = [
        {"from": "source", "to": "target", "type": "flow", "direction": "forward", "label": "Flow"}
    ]
    data["nodes"].append({"id": "target", "label": "Target", "role": "asset"})
    prism = PrismDoc.model_validate(data)
    svg = MermaidRenderer().to_svg(prism, load_ontology("financial"))
    source = _node_group(svg)
    edge_label = MermaidRenderer()._render_edge_label(
        "Flow", 100, 100, 200, 200, 100, 100, 200, 200, load_theme("warm_layered")
    )

    assert 'font-weight="700"' in source
    assert 'font-weight="400" opacity="0.84"' in source
    assert 'font-size="12" opacity="0.94"' in edge_label


@pytest.mark.parametrize("role", list(load_ontology("financial").roles))
def test_each_role_renders_an_inline_icon_inside_node_bounds(role: str) -> None:
    ontology = load_ontology("financial")
    svg = MermaidRenderer().to_svg(_document(role=role), ontology)
    group = _node_group(svg)

    outer = re.search(
        r'class="node-shape node-shape-outer" x="([0-9.]+)" y="([0-9.]+)" '
        r'width="([0-9.]+)" height="([0-9.]+)"',
        group,
    )
    icon = re.search(
        r'<svg class="prism-node-icon" x="([0-9.]+)" y="([0-9.]+)" '
        r'width="16" height="16"[^>]*>(<path d="[^"]+" />)</svg>',
        group,
    )

    assert outer is not None
    assert icon is not None
    assert 'class="prism-node-icon-badge"' in group
    assert 'width="28" height="28" rx="7"' in group
    assert 'opacity="0.12"' in group
    assert ROLE_ICON_PATHS[role] in group
    node_x, node_y, node_width, node_height = map(float, outer.groups())
    icon_x, icon_y = map(float, icon.groups()[:2])
    assert node_x < icon_x < icon_x + 16 < node_x + node_width
    assert node_y < icon_y < icon_y + 16 < node_y + node_height

    title_x = float(re.search(r'<text x="([0-9.]+)"', group).group(1))
    assert title_x > icon_x + 16


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
