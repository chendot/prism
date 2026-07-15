import re

from prism.core.schema import Edge, PrismDoc
from prism.ontologies.loader import load_ontology
from prism.render.mermaid import MermaidRenderer
from prism.render.theme import load_theme


def test_mermaid_renderer_includes_styles_and_loops() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()
    html = renderer.render(prism, ontology)
    svg = renderer.to_svg(prism, ontology)

    assert 'data-layout-engine="dagre"' in html
    assert 'id="prism-payload" type="application/json"' in html
    assert '"dagre_version":"3.0.0"' in html
    assert 'PrismDagre.render(' in html
    assert '<script src=' not in html
    assert "var dagre=" in html
    assert "width: min(900px" in html
    assert "aspect-ratio: 3 / 4" not in html
    assert "height: auto" in html
    assert "overflow-x: hidden;" in html
    assert "overflow-y: auto;" in html
    assert "place-items: start center;" in html
    assert "美国财政部" in html
    assert "background: #1f1814" in html
    assert '<svg class="prism-svg"' in svg
    assert 'class="prism-node-accent"' in svg
    assert '<rect class="prism-node-accent"' not in svg
    assert '<path class="prism-node-accent"' in svg
    assert 'fill="#e5bc6a"' in svg
    assert 'stroke-width="1.5"' in svg
    assert 'stroke-width="2"' in svg
    assert " C " not in svg
    assert "chendot · prism" in svg
    assert "Feedback loops" in svg
    assert "利率-需求反馈" in svg
    assert '<section class="loops">' not in html


def test_browser_renderer_places_labels_and_wraps_node_text() -> None:
    prism = PrismDoc.from_yaml("examples/china-financial-market-framework.yaml")
    ontology = load_ontology("financial")

    html = MermaidRenderer().render(prism, ontology)

    assert "function wrapText(text, maxWidth, fontSize)" in html
    assert "estimateTextWidth(candidate, fontSize) > maxWidth" in html
    assert "function placeEdgeLabels(routedEdges, result, config)" in html
    assert "!nodeRects.some((nodeRect) => rectsOverlap(rect, nodeRect))" in html
    assert "!occupied.some((occupiedRect) => rectsOverlap(rect, occupiedRect))" in html
    assert "const middleY = (start.y + end.y) / 2;" in html
    assert "routeDeferredEdge(edge, normalized.nodes, normalized.width, payload.layout, index)" in html
    assert "function renderHeader(svg, payload, result)" in html
    assert "payload.prism.diagram.thesis || payload.prism.meta.subtitle" in html
    assert "payload.ontology.weights[node.weight]" in html
    assert 'class: "diagram-header"' in html
    assert "feedback_edge_opacity" in html
    assert "y: positioned.y + payload.layout.header_height" in html
    assert "marginy: config.top_margin" in html
    assert "const preferredWidth = iconAndPadding + contentWidth + config.node_one_line_slack;" in html
    assert "Math.min(config.node_max_width, Math.max(baseWidth, preferredWidth))" in html


def test_mermaid_source_keeps_node_ids() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    ontology = load_ontology("financial")
    mermaid = MermaidRenderer().to_mermaid(prism, ontology)

    assert 'treasury["美国财政部' in mermaid
    assert "class treasury" in mermaid


def test_node_weight_does_not_override_status_visual_mapping() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0]["weight"] = "primary"
    weighted = PrismDoc.model_validate(data)
    ontology = load_ontology("financial")

    svg = MermaidRenderer().to_svg(weighted, ontology)
    treasury_group = svg.split('data-node-id="treasury"', 1)[1].split("</g>", 1)[0]

    assert 'data-status="neutral"' in treasury_group
    assert 'fill="url(#grad_neutral)"' in treasury_group
    assert 'stroke="#e5bc6a"' in treasury_group


def test_muted_nodes_have_gradient_background_to_cover_edges() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-revenue.yaml")
    ontology = load_ontology("financial")

    svg = MermaidRenderer().to_svg(prism, ontology)
    redeem_fee_group = svg.split('data-node-id="redeem_fee"', 1)[1].split("</g>", 1)[0]

    assert 'fill="url(#grad_neutral)"' in redeem_fee_group


def test_same_layer_nodes_fit_within_canvas_margins() -> None:
    prism = PrismDoc.model_validate(
        {
            "meta": {
                "title": "Fit",
                "topic": "Fit",
                "ontology": "financial",
                "audience": "beginner",
                "language": "zh",
                "tags": [],
            },
            "diagram": {"type": "flow", "direction": "LR"},
            "nodes": [
                {
                    "id": "left_node",
                    "label": "很长的左侧节点标题",
                    "sublabel": "这是一段很长的节点说明文字，用来触发布局宽度上限",
                    "role": "asset",
                    "layer": 1,
                },
                {
                    "id": "right_node",
                    "label": "很长的右侧节点标题",
                    "sublabel": "这也是一段很长的节点说明文字，用来触发布局宽度上限",
                    "role": "asset",
                    "layer": 1,
                },
            ],
            "edges": [],
            "loops": [],
            "render": {"renderer": "mermaid"},
        }
    )
    renderer = MermaidRenderer()
    layout = renderer._layout_nodes(prism)
    positions = layout["positions"]
    same_layer = ["left_node", "right_node"]
    left = min(positions[node_id][0] for node_id in same_layer)
    right = max(positions[node_id][0] + positions[node_id][2] for node_id in same_layer)

    assert left >= 40
    assert right <= 860
    assert right - left <= 820


def test_svg_edges_render_before_nodes() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    ontology = load_ontology("financial")

    svg = MermaidRenderer().to_svg(prism, ontology)

    assert svg.index('<g class="edges">') < svg.index('<g class="nodes">')
    assert svg.index('<path d=') < svg.index('<g class="node"')


def test_scaled_same_row_nodes_keep_minimum_horizontal_gap() -> None:
    prism = PrismDoc.model_validate(
        {
            "meta": {
                "title": "Gap",
                "topic": "Gap",
                "ontology": "financial",
                "audience": "beginner",
                "language": "zh",
                "tags": [],
            },
            "diagram": {"type": "flow", "direction": "LR"},
            "nodes": [
                {
                    "id": "left_node",
                    "label": "左",
                    "role": "asset",
                    "layer": 1,
                    "weight": "primary",
                },
                {
                    "id": "right_node",
                    "label": "右",
                    "role": "asset",
                    "layer": 1,
                    "weight": "primary",
                },
            ],
            "edges": [],
            "loops": [],
            "render": {"renderer": "mermaid"},
        }
    )
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()
    layout = renderer._layout_nodes(prism, ontology)
    positions = layout["positions"]
    nodes = {node.id: node for node in prism.nodes}

    left_bounds = renderer._rendered_node_bounds(
        positions["left_node"], nodes["left_node"], ontology
    )
    right_bounds = renderer._rendered_node_bounds(
        positions["right_node"], nodes["right_node"], ontology
    )

    assert right_bounds[0] - left_bounds[1] >= 20


def test_stablecoin_revenue_nodes_do_not_overlap_or_exceed_canvas() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-revenue.yaml")
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()
    layout = renderer._layout_nodes(prism, ontology)
    positions = layout["positions"]
    nodes = {node.id: node for node in prism.nodes}
    rects: list[tuple[str, float, float, float, float]] = []

    for node_id, box in positions.items():
        left, top, right, bottom = renderer._rendered_node_box(box, nodes[node_id], ontology)
        rects.append((node_id, left, top, right, bottom))
        assert left >= 40
        assert right <= 860

    for index, first in enumerate(rects):
        for second in rects[index + 1 :]:
            x_gap = max(first[1], second[1]) - min(first[3], second[3])
            y_gap = max(first[2], second[2]) - min(first[4], second[4])
            assert x_gap >= 20 or y_gap >= 20


def test_edge_label_x_positions_stay_inside_canvas() -> None:
    prism = PrismDoc.model_validate(
        {
            "meta": {
                "title": "Labels",
                "topic": "Labels",
                "ontology": "financial",
                "audience": "beginner",
                "language": "zh",
                "tags": [],
            },
            "diagram": {"type": "flow", "direction": "LR"},
            "nodes": [
                {"id": "source", "label": "来源", "role": "asset", "layer": 1},
                {"id": "target", "label": "目标", "role": "asset", "layer": 1},
            ],
            "edges": [
                {
                    "from": "target",
                    "to": "source",
                    "label": "这是一条很长的反馈边标签，应该通过移动位置保留完整文本",
                    "type": "feedback",
                    "direction": "forward",
                }
            ],
            "loops": [],
            "render": {"renderer": "mermaid"},
        }
    )
    ontology = load_ontology("financial")

    svg = MermaidRenderer().to_svg(prism, ontology)
    labels = [
        (float(x), anchor, text)
        for x, anchor, text in re.findall(
            r'<text x="([0-9.]+)" y="[^"]+" text-anchor="([^"]+)"'
            r' fill="#c6a878" font-size="12" opacity="0.94" font-family="ui-sans-serif, system-ui">'
            r'([^<>]+)</text>',
            svg,
        )
    ]

    assert labels
    assert all(x <= 888 for x, _anchor, _text in labels)
    assert any(
        text == "这是一条很长的反馈边标签，应该通过移动位置保留完整文本"
        for _x, _anchor, text in labels
    )


def test_adjacent_edge_waypoints_use_row_gutter() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-revenue.yaml")
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()
    layout = renderer._layout_nodes(prism, ontology)
    positions = layout["positions"]
    row_tops = sorted({box[1] for box in positions.values()})
    edge = next(edge for edge in prism.edges if edge.from_ == "users" and edge.to == "fiat_issuer")

    points = renderer._edge_route_points(edge, 0, positions, row_tops, (0, 0))

    assert points[1][1] == points[2][1]
    assert positions["users"][1] + positions["users"][3] < points[1][1] < positions["fiat_issuer"][1]


def test_long_distance_edge_routes_along_canvas_margin() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-revenue.yaml")
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()
    layout = renderer._layout_nodes(prism, ontology)
    positions = layout["positions"]
    row_tops = sorted({box[1] for box in positions.values()})
    edge = next(edge for edge in prism.edges if edge.from_ == "staking_yield" and edge.to == "users")

    points = renderer._edge_route_points(edge, 18, positions, row_tops, (0, 0))

    assert any(x in {40, 860} for x, _y in points[2:4])


def test_edges_from_same_side_are_fanned_out() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-revenue.yaml")
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()
    layout = renderer._layout_nodes(prism, ontology)
    positions = layout["positions"]
    row_tops = sorted({box[1] for box in positions.values()})
    offsets = renderer._edge_fan_offsets(prism.edges, positions)
    user_edge_indexes = [
        index
        for index, edge in enumerate(prism.edges)
        if edge.from_ == "users" and positions[edge.to][1] > positions[edge.from_][1]
    ]

    start_x_values = [
        renderer._edge_route_points(
            prism.edges[index], index, positions, row_tops, offsets[index]
        )[0][0]
        for index in user_edge_indexes
    ]

    assert len(start_x_values) >= 3
    assert len(set(start_x_values)) == len(start_x_values)
    assert sorted(start_x_values)[1] - sorted(start_x_values)[0] == 12


def test_route_planner_assigns_distinct_gutter_tracks() -> None:
    prism = PrismDoc.model_validate(
        {
            "meta": {
                "title": "Tracks",
                "topic": "Tracks",
                "ontology": "financial",
                "audience": "beginner",
                "language": "zh",
            },
            "diagram": {"type": "layer", "direction": "TD"},
            "nodes": [
                {"id": "source", "label": "来源", "role": "entry", "layer": 0},
                {"id": "left", "label": "左", "role": "asset", "layer": 1},
                {"id": "center", "label": "中", "role": "asset", "layer": 1},
                {"id": "right", "label": "右", "role": "asset", "layer": 1},
            ],
            "edges": [
                {"from": "source", "to": target, "type": "control", "direction": "forward"}
                for target in ("left", "center", "right")
            ],
            "render": {"renderer": "mermaid"},
        }
    )
    renderer = MermaidRenderer()
    positions = renderer._layout_nodes(prism, load_ontology("financial"))["positions"]
    routes = renderer._plan_edge_routes(prism.edges, positions)

    gutter_y_values = [routes[index][1][1] for index in range(3)]

    assert len(set(gutter_y_values)) == 3
    assert sorted(gutter_y_values)[1] - sorted(gutter_y_values)[0] == 12


def test_route_planner_assigns_distinct_multirow_center_tracks() -> None:
    prism = PrismDoc.model_validate(
        {
            "meta": {
                "title": "Center tracks",
                "topic": "Center tracks",
                "ontology": "financial",
                "audience": "beginner",
                "language": "zh",
            },
            "diagram": {"type": "layer", "direction": "TD"},
            "nodes": [
                {"id": "left_source", "label": "左来源", "role": "entry", "layer": 0},
                {"id": "right_source", "label": "右来源", "role": "entry", "layer": 0},
                {"id": "left_blocker", "label": "左中间", "role": "asset", "layer": 1},
                {"id": "right_blocker", "label": "右中间", "role": "asset", "layer": 1},
                {"id": "target", "label": "目标", "role": "asset", "layer": 2},
            ],
            "edges": [
                {"from": source, "to": "target", "type": "control", "direction": "forward"}
                for source in ("left_source", "right_source")
            ],
            "render": {"renderer": "mermaid"},
        }
    )
    renderer = MermaidRenderer()
    positions = renderer._layout_nodes(prism, load_ontology("financial"))["positions"]
    routes = renderer._plan_edge_routes(prism.edges, positions)
    center_x_values = [routes[index][2][0] for index in range(2)]

    assert len(set(center_x_values)) == 2
    assert abs(center_x_values[0] - center_x_values[1]) >= 12


def test_route_planner_assigns_distinct_side_rails() -> None:
    prism = PrismDoc.model_validate(
        {
            "meta": {
                "title": "Rails",
                "topic": "Rails",
                "ontology": "financial",
                "audience": "beginner",
                "language": "zh",
            },
            "diagram": {"type": "layer", "direction": "TD"},
            "nodes": [
                {"id": "source", "label": "来源", "role": "entry", "layer": 0},
                {"id": "step_one", "label": "一", "role": "flow_step", "layer": 1},
                {"id": "step_two", "label": "二", "role": "flow_step", "layer": 2},
                {"id": "target_one", "label": "目标一", "role": "asset", "layer": 3},
                {"id": "target_two", "label": "目标二", "role": "asset", "layer": 4},
            ],
            "edges": [
                {"from": "source", "to": "target_one", "type": "control", "direction": "forward"},
                {"from": "source", "to": "target_two", "type": "control", "direction": "forward"},
            ],
            "render": {"renderer": "mermaid"},
        }
    )
    renderer = MermaidRenderer()
    positions = renderer._layout_nodes(prism, load_ontology("financial"))["positions"]
    routes = renderer._plan_edge_routes(prism.edges, positions)
    rail_x_values = [routes[index][2][0] for index in range(2)]

    assert len(set(rail_x_values)) == 2
    assert all(x <= 40 or x >= 860 for x in rail_x_values)


def test_adjacent_feedback_uses_separate_outbound_and_return_tracks() -> None:
    prism = PrismDoc.model_validate(
        {
            "meta": {
                "title": "Feedback",
                "topic": "Feedback",
                "ontology": "financial",
                "audience": "beginner",
                "language": "zh",
            },
            "diagram": {"type": "layer", "direction": "TD"},
            "nodes": [
                {"id": "generate", "label": "生成", "role": "flow_step", "layer": 0},
                {"id": "validate", "label": "验证", "role": "protocol", "layer": 1},
            ],
            "edges": [
                {"from": "generate", "to": "validate", "type": "flow", "direction": "forward"},
                {"from": "validate", "to": "generate", "type": "feedback", "direction": "backward"},
            ],
            "render": {"renderer": "mermaid"},
        }
    )
    renderer = MermaidRenderer()
    positions = renderer._layout_nodes(prism, load_ontology("financial"))["positions"]
    feedback_route = renderer._plan_edge_routes(prism.edges, positions)[1]

    assert feedback_route[1][1] != feedback_route[3][1]
    assert feedback_route[2][0] >= 860
    assert feedback_route[2][0] == feedback_route[3][0]


def test_risk_edge_prefers_right_margin_route() -> None:
    prism = PrismDoc.model_validate(
        {
            "meta": {
                "title": "Risk",
                "topic": "Risk",
                "ontology": "financial",
                "audience": "beginner",
                "language": "zh",
                "tags": [],
            },
            "diagram": {"type": "flow", "direction": "LR"},
            "nodes": [
                {"id": "source", "label": "来源", "role": "asset", "layer": 1},
                {"id": "target", "label": "目标", "role": "asset", "layer": 4},
            ],
            "edges": [
                {
                    "from": "source",
                    "to": "target",
                    "label": "风险传导",
                    "type": "risk",
                    "direction": "forward",
                }
            ],
            "loops": [],
            "render": {"renderer": "mermaid"},
        }
    )
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()
    layout = renderer._layout_nodes(prism, ontology)
    positions = layout["positions"]
    row_tops = sorted({box[1] for box in positions.values()})

    points = renderer._edge_route_points(prism.edges[0], 0, positions, row_tops, (0, 0))

    assert points[2][0] == 860
    assert points[3][0] == 860


def test_right_edge_label_uses_end_anchor_and_keeps_right_margin() -> None:
    renderer = MermaidRenderer()
    visual_theme = load_theme("warm_layered")
    label = renderer._render_edge_label(
        "非常长的右侧边缘标签应该完整保留",
        890,
        100,
        930,
        180,
        850,
        100,
        880,
        180,
        visual_theme,
    )

    match = re.search(
        r'<text x="([0-9.]+)" y="[^"]+" text-anchor="([^"]+)"[^>]*>([^<>]+)</text>',
        label,
    )

    assert match is not None
    assert float(match.group(1)) <= 888
    assert match.group(2) == "end"
    assert match.group(3) == "非常长的右侧边缘标签应该完整保留"


def test_centered_edge_label_shifts_left_without_truncating() -> None:
    renderer = MermaidRenderer()
    visual_theme = load_theme("warm_layered")
    text = "right edge label stays complete"
    label = renderer._render_edge_label(
        text,
        760,
        100,
        840,
        180,
        690,
        100,
        770,
        180,
        visual_theme,
    )
    label_x = float(re.search(r'x="([0-9.]+)"', label).group(1))
    label_text = re.search(r">([^<>]+)</text>", label).group(1)

    assert 'text-anchor="end"' in label
    assert label_x <= 888
    assert label_text == text
    assert label_x <= 800


def test_middle_edge_label_shifts_left_without_truncating() -> None:
    renderer = MermaidRenderer()
    visual_theme = load_theme("warm_layered")
    text = "a somewhat longer right side edge label"
    label = renderer._render_edge_label(
        text,
        420,
        100,
        650,
        180,
        760,
        100,
        790,
        180,
        visual_theme,
    )
    label_x = float(re.search(r'x="([0-9.]+)"', label).group(1))
    label_text = re.search(r">([^<>]+)</text>", label).group(1)
    estimated_width = renderer._estimate_text_width(label_text, font_size=12)

    assert 'text-anchor="middle"' in label
    assert label_x + estimated_width / 2 <= 888
    assert label_x < 775
    assert label_text == text


def test_right_edge_label_accounts_for_estimated_text_width() -> None:
    renderer = MermaidRenderer()
    theme = renderer.to_svg(
        PrismDoc.model_validate(
            {
                "meta": {
                    "title": "Label",
                    "topic": "Label",
                    "ontology": "financial",
                    "audience": "beginner",
                    "language": "zh",
                    "tags": [],
                },
                "diagram": {"type": "flow", "direction": "LR"},
                "nodes": [{"id": "node", "label": "节点", "role": "asset"}],
                "edges": [],
                "loops": [],
                "render": {"renderer": "mermaid"},
            }
        ),
        load_ontology("financial"),
    )
    assert '<svg class="prism-svg"' in theme

    visual_theme = load_theme("warm_layered")
    label = renderer._render_edge_label(
        "非常长的右侧边缘标签",
        850,
        100,
        900,
        100,
        300,
        100,
        500,
        100,
        visual_theme,
    )
    label_x = float(re.search(r'x="([0-9.]+)"', label).group(1))
    label_text = re.search(r">([^<>]+)</text>", label).group(1)
    estimated_width = renderer._estimate_text_width(label_text, font_size=13)

    assert label_x <= 888
    assert 'text-anchor="end"' in label
    assert label_text == "非常长的右侧边缘标签"


def test_feedback_loops_render_inside_svg_surface() -> None:
    prism = PrismDoc.from_yaml("examples/fed_rate_hike.yaml")
    ontology = load_ontology("financial")

    svg = MermaidRenderer().to_svg(prism, ontology)
    loop_rect = re.search(
        r'<rect x="48" y="([0-9]+)" width="804" height="([0-9]+)" rx="10" '
        r'fill="#1f1814"',
        svg,
    )

    assert 'class="feedback-loops"' in svg
    assert 'clip-path="url(#feedback-loops-clip)"' in svg
    assert loop_rect is not None
    assert int(loop_rect.group(1)) + int(loop_rect.group(2)) <= 1200
    assert 'fill="#ffffff"' not in svg


def test_feedback_edge_is_not_drawn_twice_when_loop_panel_is_visible() -> None:
    prism = PrismDoc.from_yaml("examples/fed_rate_hike.yaml")
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()

    with_loop_panel = renderer.to_svg(prism, ontology)
    data = prism.model_dump(mode="json", by_alias=True)
    data["render"]["show_loops"] = False
    without_loop_panel = renderer.to_svg(PrismDoc.model_validate(data), ontology)

    assert 'data-edge-type="feedback"' not in with_loop_panel
    assert 'data-edge-type="feedback"' in without_loop_panel


def test_feedback_loops_truncate_when_too_many_items() -> None:
    prism = PrismDoc.from_yaml("examples/fed_rate_hike.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["loops"] = [
        {
            "id": f"policy_inflation_loop_{index}",
            "label": "很长的政策通胀反馈循环说明",
            "nodes": ["fed", "short_rates", "borrowers", "demand", "inflation"],
            "polarity": "negative",
        }
        for index in range(6)
    ]
    crowded = PrismDoc.model_validate(data)
    ontology = load_ontology("financial")

    svg = MermaidRenderer().to_svg(crowded, ontology)
    loop_text_y_values = [
        int(value)
        for value in re.findall(
                r'<text x="62" y="([0-9]+)" fill="#c6a878" font-size="12"',
            svg,
        )
    ]

    assert loop_text_y_values
    assert max(loop_text_y_values) <= 1144
    assert "..." in svg


def test_parallel_lanes_layout_stacks_nodes_by_lane() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    renderer = MermaidRenderer()
    layout = renderer._layout_parallel_lanes(prism)
    positions = layout["positions"]

    assert layout["shared_entry"] == "stablecoin_users"
    assert layout["shared_convergence"] == "interest_allocation"
    assert positions["cash_reserve"][0] < positions["lending_pool"][0] < positions["hedge_collateral"][0]
    assert positions["cash_reserve"][0] == positions["treasury_bills"][0]
    assert positions["lending_pool"][0] == positions["borrowers"][0]
    assert positions["hedge_collateral"][0] == positions["short_perps"][0]
    assert positions["stablecoin_users"][1] < positions["cash_reserve"][1]
    assert positions["interest_allocation"][1] > positions["issuer_capture"][1]
    convergence_x, _y, convergence_width, _height = positions["interest_allocation"]
    assert convergence_x + convergence_width / 2 == layout["width"] / 2
    assert positions["stablecoin_users"][1] == renderer.layout_config.top_margin
    assert positions["treasury_bills"][1] - (
        positions["cash_reserve"][1] + positions["cash_reserve"][3]
    ) == 56


def test_parallel_lanes_height_follows_content_bottom() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    renderer = MermaidRenderer()
    layout = renderer._layout_parallel_lanes(prism)
    positions = layout["positions"]
    assert layout["height"] == int(
        layout["max_content_bottom"] + renderer.layout_config.bottom_margin
    )
    assert layout["height"] < 1200


def test_parallel_lanes_render_guides_and_margin_feedback_route() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    ontology = load_ontology("financial")
    renderer = MermaidRenderer()
    layout = renderer._layout_parallel_lanes(prism)
    positions = layout["positions"]
    feedback_edge = next(edge for edge in prism.edges if edge.from_ == "funding_income")

    svg = renderer.to_svg(prism, ontology)
    feedback_path = renderer._parallel_margin_edge_path(feedback_edge, positions, layout)

    assert "法币储备" in svg
    assert "抵押借贷" in svg
    assert "Delta 对冲" in svg
    assert (
        f'<rect x="0" y="0" width="{layout["width"]}" height="{layout["height"]}"'
        in svg
        and 'rx="16" fill="none" stroke="#6f522e" stroke-width="1.5"'
        in svg
    )
    assert 'stroke-dasharray' not in svg.split('<rect x="0" y="0"', 1)[1].split("/>", 1)[0]
    assert 'x="884" y="' in svg
    assert f'y="{int(layout["height"]) - 16}"' in svg
    assert "chendot · prism" in svg
    assert 'class="parallel-lanes"' in svg
    assert 'stroke="#c9934f" stroke-width="1.5" stroke-dasharray="7 9" opacity="0.6"' in svg
    assert 'font-size="12" font-weight="650" letter-spacing="1"' in svg
    assert 'data-edge-type="feedback"' in svg
    assert 'stroke-dasharray="4,4"' in svg
    assert '<rect x="' in svg
    assert 'fill="none" /><text' in svg
    assert "L 40.0" in feedback_path or "L 860.0" in feedback_path
    assert "L 450.0" not in feedback_path

    points = [
        (float(x), float(y))
        for x, y in re.findall(r"[ML] ([0-9.]+) ([0-9.]+)", feedback_path)
    ]
    assert points[0][0] not in {40.0, 860.0}
    assert points[-1][0] not in {40.0, 860.0}
    assert not renderer._drop_parallel_edge_path(
        feedback_edge,
        renderer._parallel_path_endpoints(feedback_path),
        positions,
        layout,
    )


def test_parallel_lanes_vertical_edge_label_uses_gap_midpoint() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    theme = load_theme("warm_layered")
    renderer = MermaidRenderer()
    layout = renderer._layout_parallel_lanes(prism)
    positions = layout["positions"]
    edge = next(edge for edge in prism.edges if edge.from_ == "cash_reserve")
    source = positions[edge.from_]
    target = positions[edge.to]
    expected_y = (source[1] + source[3] + target[1]) / 2

    label = renderer._parallel_edge_label(edge, positions, theme, "vertical")

    assert f'y="{expected_y:.1f}"' in label
    assert 'fill="none"' in label


def test_parallel_lanes_skips_invalid_edges_with_warning(caplog) -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    theme = load_theme("warm_layered")
    renderer = MermaidRenderer()
    layout = renderer._layout_parallel_lanes(prism)
    positions = layout["positions"]
    invalid_edge = Edge.model_validate(
        {
            "from": "missing_source",
            "to": "cash_reserve",
            "label": "bad",
            "type": "feedback",
            "direction": "forward",
        }
    )

    caplog.set_level("WARNING", logger="prism.render.mermaid")
    svg = renderer._render_parallel_lanes_edges(
        PrismDoc.model_validate(
            {
                **prism.model_dump(mode="json", by_alias=True),
                "edges": [invalid_edge.model_dump(mode="json", by_alias=True)],
            }
        ),
        positions,
        layout,
        theme,
    )

    assert svg == ""
    assert "invalid node reference" in caplog.text


def test_parallel_lanes_drops_zero_length_and_stray_left_paths(caplog) -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    renderer = MermaidRenderer()
    layout = renderer._layout_parallel_lanes(prism)
    positions = layout["positions"]
    edge = prism.edges[0]

    caplog.set_level("WARNING", logger="prism.render.mermaid")

    assert renderer._drop_parallel_edge_path(edge, ((39.0, 120.0), (90.0, 120.0)), positions, layout)
    assert renderer._drop_parallel_edge_path(edge, ((80.0, 120.0), (80.0, 120.0)), positions, layout)
    assert "stray left-margin" in caplog.text
    assert "zero-length" in caplog.text
