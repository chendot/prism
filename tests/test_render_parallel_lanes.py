import re
from pathlib import Path

from prism.core.schema import PrismDoc
from prism.ontologies.loader import load_ontology
from prism.render.mermaid import MermaidRenderer


def _parallel_lane_examples() -> list[Path]:
    examples = []
    for path in sorted(Path("examples").glob("*.yaml")):
        prism = PrismDoc.from_yaml(str(path))
        if prism.render.template == "parallel_lanes":
            examples.append(path)
    return examples


def _edge_paths(svg: str) -> list[str]:
    edge_group = svg.split('<g class="edges">', 1)[1].split("</g>", 1)[0]
    return re.findall(r'<path d="([^"]+)"', edge_group)


def _label_rects(svg: str) -> list[tuple[float, float, float, float]]:
    edge_group = svg.split('<g class="edges">', 1)[1].split("</g>", 1)[0]
    rects = []
    for x, y, width, height in re.findall(
        r'<rect x="([0-9.]+)" y="([0-9.]+)" width="([0-9.]+)" '
        r'height="([0-9.]+)" fill="#1c1612"',
        edge_group,
    ):
        left = float(x)
        top = float(y)
        rects.append((left, top, left + float(width), top + float(height)))
    return rects


def test_parallel_lanes_examples_render_without_geometry_regressions() -> None:
    examples = _parallel_lane_examples()
    assert examples

    renderer = MermaidRenderer()
    config = renderer.layout_config

    for path in examples:
        prism = PrismDoc.from_yaml(str(path))
        ontology = load_ontology(prism.meta.ontology)
        layout = renderer._layout_parallel_lanes(prism)
        positions = layout["positions"]
        canvas_width = float(layout["width"])
        canvas_height = float(layout["height"])

        assert canvas_width > 0
        assert canvas_height > 0

        for node_id, (x, y, width, height) in positions.items():
            assert x >= 0, f"{path}: {node_id} extends left"
            assert y >= 0, f"{path}: {node_id} extends above canvas"
            assert x + width <= canvas_width, f"{path}: {node_id} extends right"
            assert y + height <= canvas_height, f"{path}: {node_id} extends below canvas"

        content_bottom = float(layout["max_content_bottom"])
        assert canvas_height > content_bottom
        assert abs(canvas_height - (content_bottom + config.bottom_margin)) <= 2

        node_ids = {node.id for node in prism.nodes}
        for edge in prism.edges:
            assert renderer._valid_parallel_edge(edge, node_ids, positions, layout), (
                f"{path}: unresolved edge {edge.from_}->{edge.to}"
            )

        svg = renderer.to_svg(prism, ontology)
        for rect in _label_rects(svg):
            assert not renderer._label_overlaps_nodes(rect, positions), (
                f"{path}: edge label intersects a node"
            )

        paths = _edge_paths(svg)
        assert paths
        for edge_path in paths:
            endpoints = renderer._parallel_path_endpoints(edge_path)
            assert endpoints is not None, f"{path}: edge has unresolved endpoints"
            assert endpoints[0] != endpoints[1], f"{path}: edge has zero length"
