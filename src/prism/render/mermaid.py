"""Mermaid renderer for Prism Layer 3."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from html import escape
from itertools import count
import logging
from math import ceil
import re

from prism.core.models import Ontology
from prism.core.schema import Edge, EdgeDirection, Node, PrismDoc, RenderLane
from prism.core.validator import validate_prism_doc
from prism.render.base import Renderer
from prism.render.theme import VisualTheme, load_theme


logger = logging.getLogger(__name__)


class RenderError(RuntimeError):
    """Raised when a renderer cannot produce a valid canvas."""


@dataclass(frozen=True)
class LayoutConfig:
    top_margin: int = 32
    bottom_margin: int = 72
    lane_padding: int = 40
    node_gap: int = 56
    node_height: int = 64
    node_width_ratio: float = 0.85
    fanout_curve_height: int = 80
    convergence_curve_height: int = 48
    label_gap_ratio: float = 0.5
    label_bg_padding_x: int = 4
    label_bg_padding_y: int = 2
    arrowhead_size: int = 8
    canvas_width: int = 900


class MermaidRenderer(Renderer):
    """Render a validated Prism document to self-contained Mermaid HTML."""

    def __init__(self, layout_config: LayoutConfig | None = None) -> None:
        self.layout_config = layout_config or LayoutConfig()

    def render(self, prism: PrismDoc, ontology: Ontology) -> str:
        """Return an HTML document containing a Mermaid diagram."""

        validate_prism_doc(prism, ontology)
        theme = load_theme(prism.meta.visual_theme)
        diagram_svg = self.to_svg(prism, ontology, theme)

        return f"""<!doctype html>
<html lang="{escape(prism.meta.language.value)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(prism.meta.title)}</title>
  <style>
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: {theme.text_primary};
      background: {theme.background};
      min-height: 100vh;
      overflow: hidden;
      display: grid;
      place-items: center;
    }}
    main {{
      padding: 0;
    }}
    .diagram {{
      width: min(900px, 100vw);
      background: {theme.surface};
    }}
    .prism-svg {{
      display: block;
      width: 100%;
      height: auto;
      background: {theme.background};
    }}
  </style>
</head>
<body>
  <main>
    <section class="diagram">{diagram_svg}</section>
  </main>
</body>
</html>
"""

    def to_svg(
        self, prism: PrismDoc, ontology: Ontology, theme: VisualTheme | None = None
    ) -> str:
        """Render a mobile-friendly layered SVG diagram."""

        theme = theme or load_theme(prism.meta.visual_theme)
        config = self.layout_config
        layout = (
            self._layout_parallel_lanes(prism)
            if prism.render.template == "parallel_lanes"
            else self._layout_nodes(prism, ontology)
        )
        width = layout["width"]
        height = layout["height"]
        positions: dict[str, tuple[float, float, float, float]] = layout["positions"]  # type: ignore[assignment]
        node_by_id = {node.id: node for node in prism.nodes}
        emphasized_nodes = self._emphasized_nodes(prism)
        edge_svg = (
            self._render_parallel_lanes_edges(prism, positions, layout, theme)
            if prism.render.template == "parallel_lanes"
            else self._render_svg_edges(prism, positions, theme)
        )
        # Diagnostic finding from `prism render examples/stablecoin-interest-parallel-lanes.yaml`:
        # entry_node_top_y=32, canvas_height=784, max_content_bottom_y=712, bottom_margin=72.
        # The extra visible whitespace came from the HTML wrapper's fixed 3:4 aspect ratio,
        # not from the SVG canvas calculation.
        loops_svg = self._render_svg_loops(prism, theme) if prism.render.show_loops else ""
        lane_svg = (
            self._render_parallel_lane_guides(layout, theme)
            if prism.render.template == "parallel_lanes"
            else ""
        )
        node_svg = "".join(
            self._render_svg_node(
                node_by_id[node_id],
                positions[node_id],
                ontology,
                theme,
                node_id in emphasized_nodes,
            )
            for node_id in layout["order"]  # type: ignore[index]
        )

        return f"""<svg class="prism-svg" role="img" aria-label="{escape(prism.meta.title)}" width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arrow-primary" markerWidth="{config.arrowhead_size}" markerHeight="{config.arrowhead_size}" refX="{config.arrowhead_size}" refY="{config.arrowhead_size / 2:.1f}" orient="auto" markerUnits="strokeWidth">
      <path d="M 0 0 L {config.arrowhead_size} {config.arrowhead_size / 2:.1f} L 0 {config.arrowhead_size} z" fill="{theme.accent_primary}" />
    </marker>
    <marker id="arrow-secondary" markerWidth="{config.arrowhead_size}" markerHeight="{config.arrowhead_size}" refX="{config.arrowhead_size}" refY="{config.arrowhead_size / 2:.1f}" orient="auto" markerUnits="strokeWidth">
      <path d="M 0 0 L {config.arrowhead_size} {config.arrowhead_size / 2:.1f} L 0 {config.arrowhead_size} z" fill="{theme.accent_secondary}" />
    </marker>
    <marker id="arrow-risk" markerWidth="{config.arrowhead_size}" markerHeight="{config.arrowhead_size}" refX="{config.arrowhead_size}" refY="{config.arrowhead_size / 2:.1f}" orient="auto" markerUnits="strokeWidth">
      <path d="M 0 0 L {config.arrowhead_size} {config.arrowhead_size / 2:.1f} L 0 {config.arrowhead_size} z" fill="{theme.accent_risk}" />
    </marker>
  </defs>
  <rect width="{width}" height="{height}" fill="{theme.background}" />
  <!-- Dash diagnostic: grep found dasharray only on Mermaid link styles, lane dividers, and non-border edge paths. -->
  <rect x="0" y="0" width="{width}" height="{height}" rx="16" fill="none" stroke="{theme.surface_border}" stroke-width="1.5" />
  {lane_svg}
  <g class="edges">{edge_svg}</g>
  <g class="nodes">{node_svg}</g>
  {loops_svg}
  <text x="{width - config.arrowhead_size * 2}" y="{height - config.arrowhead_size * 2}" text-anchor="end" fill="{theme.watermark_color}" font-size="18" font-family="ui-sans-serif, system-ui">{escape(theme.watermark)}</text>
</svg>"""

    def to_mermaid(
        self, prism: PrismDoc, ontology: Ontology, theme: VisualTheme | None = None
    ) -> str:
        """Render only Mermaid source for tests and alternate delivery."""

        theme = theme or load_theme(prism.meta.visual_theme)
        lines = [f"flowchart {prism.diagram.direction.value}"]
        class_names: dict[str, str] = {}
        class_counter = count(1)

        for node in prism.nodes:
            node_label = self._node_label(node.label, node.sublabel)
            lines.append(f"    {node.id}[\"{node_label}\"]")
            class_name = class_names.setdefault(node.role, f"role{next(class_counter)}")
            lines.append(f"    class {node.id} {class_name}")

        for index, edge in enumerate(prism.edges):
            arrow = self._arrow(edge.direction)
            label = f"|{self._escape_mermaid(edge.label)}|" if edge.label else ""
            lines.append(f"    {edge.from_} {arrow}{label} {edge.to}")
            style = ontology.edge_style(edge.type)
            edge_index = index
            color = self._edge_color(edge.type, theme)
            stroke_style = "stroke-dasharray: 5 5" if style.get("style") == "dashed" else ""
            style_bits = [f"stroke:{color}"]
            if stroke_style:
                style_bits.append(stroke_style)
            lines.append(f"    linkStyle {edge_index} {','.join(style_bits)}")

        for role, class_name in class_names.items():
            lines.append(
                f"    classDef {class_name} fill:{theme.surface},"
                f"stroke:{theme.surface_border},stroke-width:1.5px,color:{theme.text_primary}"
            )

        if prism.render.highlight_nodes:
            for node_id in prism.render.highlight_nodes:
                lines.append(f"    style {node_id} stroke:{theme.accent_result},stroke-width:3px")

        return "\n".join(lines)

    def _edge_color(self, edge_type: str, theme: VisualTheme) -> str:
        if edge_type == "feedback":
            return theme.accent_risk
        if edge_type in {"information", "authorization"}:
            return theme.accent_secondary
        return theme.accent_primary

    def _render_parallel_lane_guides(
        self, layout: dict[str, object], theme: VisualTheme
    ) -> str:
        guides: dict[str, object] = layout["lane_guides"]  # type: ignore[assignment]
        lanes: list[RenderLane] = guides["lanes"]  # type: ignore[assignment]
        margin_x = float(guides["margin_x"])
        lane_width = float(guides["lane_width"])
        header_y = float(guides["header_y"])
        divider_top = float(guides["divider_top"])
        divider_bottom = float(guides["divider_bottom"])
        config = self.layout_config
        parts: list[str] = []
        for index, lane in enumerate(lanes):
            center_x = margin_x + index * lane_width + lane_width / 2
            parts.append(
                f'<text x="{center_x:.1f}" y="{header_y:.1f}" text-anchor="middle" '
                f'fill="{theme.text_secondary}" font-size="{config.arrowhead_size + config.label_bg_padding_x}" font-weight="650" '
                f'letter-spacing="1" '
                f'font-family="ui-sans-serif, system-ui">{escape(lane.title)}</text>'
            )
            if index > 0:
                divider_x = margin_x + index * lane_width
                parts.append(
                    f'<path d="M {divider_x:.1f} {divider_top:.1f} '
                    f'L {divider_x:.1f} {divider_bottom:.1f}" fill="none" '
                    f'stroke="{theme.accent_secondary}" stroke-width="1.5" '
                    f'stroke-dasharray="7 9" opacity="0.6" />'
                )
        return f'<g class="parallel-lanes">{"".join(parts)}</g>'

    def _render_parallel_lanes_edges(
        self,
        prism: PrismDoc,
        positions: dict[str, tuple[float, float, float, float]],
        layout: dict[str, object],
        theme: VisualTheme,
    ) -> str:
        lane_by_node = {node.id: node.lane for node in prism.nodes}
        node_ids = {node.id for node in prism.nodes}
        shared_entry = layout.get("shared_entry")
        shared_convergence = layout.get("shared_convergence")
        parts: list[str] = []
        for edge in prism.edges:
            if not self._valid_parallel_edge(edge, node_ids, positions, layout):
                continue
            same_lane = lane_by_node.get(edge.from_) == lane_by_node.get(edge.to)
            if same_lane:
                path, dash = self._parallel_lane_edge_path(edge, positions), ""
                color = self._edge_color(edge.type, theme)
                label_kind = "vertical"
            elif edge.from_ == shared_entry:
                path, dash = self._parallel_entry_fan_path(edge, positions), ""
                color = theme.accent_secondary
                label_kind = "fan"
            elif edge.to == shared_convergence:
                path, dash = self._parallel_convergence_fan_path(edge, positions), ""
                color = theme.accent_secondary
                label_kind = "fan"
            else:
                path = self._parallel_margin_edge_path(edge, positions, layout)
                dash = ' stroke-dasharray="8 7"'
                color = theme.accent_secondary
                label_kind = "margin"
            endpoints = self._parallel_path_endpoints(path)
            if endpoints is None or self._drop_parallel_edge_path(edge, endpoints, positions, layout):
                continue
            if not self._source_endpoint_inside_node(edge, endpoints[0], positions):
                print(f"SKIPPED stray edge: {edge.from_} -> {edge.to}")
                continue

            marker = {
                theme.accent_secondary: "arrow-secondary",
                theme.accent_risk: "arrow-risk",
            }.get(color, "arrow-primary")
            label = self._parallel_edge_label(edge, positions, theme, label_kind)
            parts.append(
                f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.5"{dash} '
                f'marker-end="url(#{marker})" opacity="0.86" />{label}'
            )
        return "".join(parts)

    def _parallel_path_endpoints(
        self, path: str
    ) -> tuple[tuple[float, float], tuple[float, float]] | None:
        values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", path)]
        if len(values) < 4 or len(values) % 2:
            return None
        return (values[0], values[1]), (values[-2], values[-1])

    def _drop_parallel_edge_path(
        self,
        edge: Edge,
        endpoints: tuple[tuple[float, float], tuple[float, float]],
        positions: dict[str, tuple[float, float, float, float]],
        layout: dict[str, object],
    ) -> bool:
        source, target = endpoints
        if source == target:
            logger.warning(
                "Skipping zero-length parallel_lanes edge: %s -> %s",
                edge.from_,
                edge.to,
            )
            return True

        lane_guides: dict[str, object] = layout["lane_guides"]  # type: ignore[assignment]
        lane_left_boundary = float(lane_guides["margin_x"])
        if source[0] < lane_left_boundary and not self._x_intersects_any_node(source[0], positions):
            logger.warning(
                "Skipping stray left-margin parallel_lanes edge: %s -> %s",
                edge.from_,
                edge.to,
            )
            return True
        return False

    def _x_intersects_any_node(
        self,
        x_value: float,
        positions: dict[str, tuple[float, float, float, float]],
    ) -> bool:
        return any(x <= x_value <= x + width for x, _y, width, _height in positions.values())

    def _valid_parallel_edge(
        self,
        edge: Edge,
        node_ids: set[str],
        positions: dict[str, tuple[float, float, float, float]],
        layout: dict[str, object],
    ) -> bool:
        if edge.from_ not in node_ids or edge.to not in node_ids:
            logger.warning(
                "Skipping parallel_lanes edge with invalid node reference: %s -> %s",
                edge.from_,
                edge.to,
            )
            return False
        if edge.from_ not in positions or edge.to not in positions:
            logger.warning(
                "Skipping parallel_lanes edge without resolved coordinates: %s -> %s",
                edge.from_,
                edge.to,
            )
            return False

        canvas_width = float(layout["width"])
        canvas_height = float(layout["height"])
        for node_id in (edge.from_, edge.to):
            x, y, width, height = positions[node_id]
            if x < 0 or y < 0 or x + width > canvas_width or y + height > canvas_height:
                logger.warning(
                    "Skipping parallel_lanes edge with out-of-bounds coordinates: %s -> %s",
                    edge.from_,
                    edge.to,
                )
                return False
        return True

    def _parallel_lane_edge_path(
        self,
        edge: Edge,
        positions: dict[str, tuple[float, float, float, float]],
    ) -> str:
        x1, y1, w1, h1 = positions[edge.from_]
        x2, y2, w2, h2 = positions[edge.to]
        if y2 >= y1:
            start = (x1 + w1 / 2, y1 + h1)
            end = (x2 + w2 / 2, y2)
        else:
            start = (x1 + w1 / 2, y1)
            end = (x2 + w2 / 2, y2 + h2)
        mid_y = (start[1] + end[1]) / 2
        return self._polyline_path([start, (start[0], mid_y), (end[0], mid_y), end])

    def _parallel_entry_fan_path(
        self,
        edge: Edge,
        positions: dict[str, tuple[float, float, float, float]],
    ) -> str:
        x1, y1, w1, h1 = positions[edge.from_]
        x2, y2, w2, _h2 = positions[edge.to]
        start_x = x1 + w1 / 2
        start_y = y1 + h1
        end_x = x2 + w2 / 2
        end_y = y2
        control_y = start_y + min(
            self.layout_config.fanout_curve_height,
            max(0, (end_y - start_y) * self.layout_config.label_gap_ratio),
        )
        return (
            f"M {start_x:.1f} {start_y:.1f} "
            f"C {start_x:.1f} {control_y:.1f}, {end_x:.1f} {control_y:.1f}, "
            f"{end_x:.1f} {end_y:.1f}"
        )

    def _parallel_convergence_fan_path(
        self,
        edge: Edge,
        positions: dict[str, tuple[float, float, float, float]],
    ) -> str:
        x1, y1, w1, h1 = positions[edge.from_]
        x2, y2, w2, _h2 = positions[edge.to]
        start_x = x1 + w1 / 2
        start_y = y1 + h1
        end_x = x2 + w2 / 2
        end_y = y2
        control_y = end_y - min(
            self.layout_config.convergence_curve_height,
            max(0, (end_y - start_y) * self.layout_config.label_gap_ratio),
        )
        return (
            f"M {start_x:.1f} {start_y:.1f} "
            f"C {start_x:.1f} {control_y:.1f}, {end_x:.1f} {control_y:.1f}, "
            f"{end_x:.1f} {end_y:.1f}"
        )

    def _parallel_margin_edge_path(
        self,
        edge: Edge,
        positions: dict[str, tuple[float, float, float, float]],
        layout: dict[str, object],
    ) -> str:
        width = int(layout["width"])
        height = int(layout["height"])
        config = self.layout_config
        left_gutter = config.lane_padding
        right_gutter = width - config.lane_padding
        source_box = positions[edge.from_]
        target_box = positions[edge.to]
        source_center = (
            source_box[0] + source_box[2] / 2,
            source_box[1] + source_box[3] / 2,
        )
        target_center = (
            target_box[0] + target_box[2] / 2,
            target_box[1] + target_box[3] / 2,
        )
        source_gutter_x = (
            left_gutter
            if abs(source_center[0] - left_gutter) <= abs(source_center[0] - right_gutter)
            else right_gutter
        )
        target_gutter_x = (
            left_gutter
            if abs(target_center[0] - left_gutter) <= abs(target_center[0] - right_gutter)
            else right_gutter
        )
        source_anchor = self._parallel_safe_border_anchor(source_box, source_gutter_x)
        target_anchor = self._parallel_safe_border_anchor(target_box, target_gutter_x)
        route_y = height - config.bottom_margin / 2
        return self._polyline_path(
            [
                source_anchor,
                (source_gutter_x, source_anchor[1]),
                (source_gutter_x, route_y),
                (target_gutter_x, route_y),
                (target_gutter_x, target_anchor[1]),
                target_anchor,
            ]
        )

    def _parallel_safe_border_anchor(
        self,
        box: tuple[float, float, float, float],
        gutter_x: float,
    ) -> tuple[float, float]:
        x, y, width, height = box
        center_x = x + width / 2
        anchor_x = x if gutter_x <= center_x else x + width
        return anchor_x, y + height / 2

    def _parallel_edge_label(
        self,
        edge: Edge,
        positions: dict[str, tuple[float, float, float, float]],
        theme: VisualTheme,
        label_kind: str,
    ) -> str:
        if not edge.label:
            return ""
        x1, y1, w1, h1 = positions[edge.from_]
        x2, y2, w2, h2 = positions[edge.to]
        source_bottom = y1 + h1
        target_top = y2
        if label_kind == "vertical":
            label_x = self._clamp(
                (x1 + w1 / 2 + x2 + w2 / 2) / 2,
                self.layout_config.lane_padding,
                self.layout_config.canvas_width - self.layout_config.lane_padding,
            )
            if y2 >= y1:
                label_y = source_bottom + (target_top - source_bottom) * self.layout_config.label_gap_ratio
            else:
                label_y = y2 + h2 + (y1 - (y2 + h2)) * self.layout_config.label_gap_ratio
        elif label_kind == "fan":
            source_x = x1 + w1 / 2
            target_x = x2 + w2 / 2
            label_x = self._clamp(
                source_x + (target_x - source_x) * self.layout_config.label_gap_ratio,
                self.layout_config.lane_padding,
                self.layout_config.canvas_width - self.layout_config.lane_padding,
            )
            label_y = source_bottom + (target_top - source_bottom) * self.layout_config.label_gap_ratio
        else:
            label_x = self._clamp(
                (x1 + w1 / 2 + x2 + w2 / 2) / 2,
                self.layout_config.lane_padding,
                self.layout_config.canvas_width - self.layout_config.lane_padding,
            )
            label_y = (
                y1
                + h1 / 2
                + ((y2 + h2 / 2) - (y1 + h1 / 2)) * self.layout_config.label_gap_ratio
                - self.layout_config.arrowhead_size
            )
        return self._render_parallel_label_box(edge.label, label_x, label_y, positions, theme)

    def _render_parallel_label_box(
        self,
        text: str,
        label_x: float,
        label_y: float,
        positions: dict[str, tuple[float, float, float, float]],
        theme: VisualTheme,
    ) -> str:
        config = self.layout_config
        font_size = config.arrowhead_size + config.label_bg_padding_x
        padding_x = config.label_bg_padding_x
        padding_y = config.label_bg_padding_y
        estimated_width = self._estimate_text_width(text, font_size)
        box_width = estimated_width + padding_x * 2
        adjusted_y = label_y
        for _attempt in range(2):
            label_box = (
                label_x - box_width / 2,
                adjusted_y - font_size - padding_y,
                label_x + box_width / 2,
                adjusted_y + padding_y,
            )
            if not self._label_overlaps_nodes(label_box, positions):
                rect_x, rect_y, rect_right, rect_bottom = label_box
                return (
                    f'<rect x="{rect_x:.1f}" y="{rect_y:.1f}" '
                    f'width="{rect_right - rect_x:.1f}" height="{rect_bottom - rect_y:.1f}" '
                    f'fill="{theme.background}" />'
                    f'<text x="{label_x:.1f}" y="{adjusted_y:.1f}" text-anchor="middle" '
                    f'fill="{theme.text_secondary}" font-size="{font_size}" '
                    f'font-family="ui-sans-serif, system-ui">{escape(text)}</text>'
                )
            adjusted_y -= config.arrowhead_size + config.label_bg_padding_y * 2
        return ""

    def _label_overlaps_nodes(
        self,
        label_box: tuple[float, float, float, float],
        positions: dict[str, tuple[float, float, float, float]],
    ) -> bool:
        label_left, label_top, label_right, label_bottom = label_box
        for x, y, width, height in positions.values():
            tolerance = self.layout_config.label_bg_padding_x
            node_left = x - tolerance
            node_top = y - tolerance
            node_right = x + width + tolerance
            node_bottom = y + height + tolerance
            if (
                label_left < node_right
                and label_right > node_left
                and label_top < node_bottom
                and label_bottom > node_top
            ):
                return True
        return False

    def _layout_nodes(
        self, prism: PrismDoc, ontology: Ontology | None = None
    ) -> dict[str, object]:
        layers = self._topological_layers(prism)
        width = 900
        height = 1200
        margin_x = 40
        top = 36
        bottom = 156
        node_height = 66
        max_per_row = 3
        x_gap = 20
        y_gap = 20

        layer_heights = []
        for layer in layers:
            rows = ceil(len(layer) / max_per_row)
            layer_heights.append(rows * node_height + max(0, rows - 1) * y_gap)
        available_gap = height - top - bottom - sum(layer_heights)
        layer_gap = max(18, available_gap / max(1, len(layers) - 1))

        positions: dict[str, tuple[float, float, float, float]] = {}
        order: list[str] = []
        y = top

        for layer_index, layer in enumerate(layers):
            rows = [layer[index : index + max_per_row] for index in range(0, len(layer), max_per_row)]
            for row_index, row in enumerate(rows):
                cols = len(row)
                node_width = self._layer_node_width(
                    row, prism, width, margin_x, x_gap, max_per_row
                )
                row_width = cols * node_width + max(0, cols - 1) * x_gap
                x = (width - row_width) / 2
                for node_id in row:
                    positions[node_id] = (x, y, node_width, node_height)
                    order.append(node_id)
                    x += node_width + x_gap
                y += node_height
                if row_index < len(rows) - 1:
                    y += y_gap
            if layer_index < len(layers) - 1:
                y += layer_gap

        if ontology is not None:
            self._ensure_min_horizontal_gap(
                positions, order, prism, ontology, width, margin_x, x_gap
            )

        return {"width": width, "height": height, "positions": positions, "order": order}

    def _layout_parallel_lanes(self, prism: PrismDoc) -> dict[str, object]:
        config = self.layout_config
        width = config.canvas_width
        margin_x = config.lane_padding
        top = config.top_margin
        node_height = config.node_height
        node_gap = config.node_gap
        lanes = sorted(prism.render.lanes, key=lambda lane: (lane.order, lane.id))
        lane_count = max(1, len(lanes))
        lane_width = (width - 2 * margin_x) / lane_count
        node_width = lane_width * config.node_width_ratio
        lane_by_node = {node.id: node.lane for node in prism.nodes}
        node_ids = [node.id for node in prism.nodes]

        shared_entry = self._parallel_shared_entry(prism, lanes)
        shared_convergence = self._parallel_shared_convergence(prism, lanes)
        floating_nodes = {node_id for node_id in (shared_entry, shared_convergence) if node_id}
        lane_orders: dict[str, list[str]] = {}
        positions: dict[str, tuple[float, float, float, float]] = {}
        order: list[str] = []

        lane_top = top + (
            node_height + config.fanout_curve_height if shared_entry else 0
        )
        for lane_index, lane in enumerate(lanes):
            lane_nodes = [
                node_id
                for node_id in node_ids
                if lane_by_node[node_id] == lane.id and node_id not in floating_nodes
            ]
            lane_order = self._parallel_lane_topological_order(prism, lane_nodes)
            lane_orders[lane.id] = lane_order
            x = margin_x + lane_index * lane_width + (lane_width - node_width) / 2
            for row_index, node_id in enumerate(lane_order):
                y = lane_top + row_index * (node_height + node_gap)
                positions[node_id] = (x, y, node_width, node_height)
                order.append(node_id)

        lane_bottom = max(
            (box[1] + box[3] for node_id, box in positions.items() if node_id not in floating_nodes),
            default=lane_top,
        )
        if shared_entry:
            entry_width = node_width
            positions[shared_entry] = (
                (width - entry_width) / 2,
                config.top_margin,
                entry_width,
                node_height,
            )
            order.insert(0, shared_entry)
        if shared_convergence:
            convergence_width = node_width
            positions[shared_convergence] = (
                width / 2 - convergence_width / 2,
                lane_bottom + config.convergence_curve_height,
                convergence_width,
                node_height,
            )
            order.append(shared_convergence)

        max_content_bottom = max((y + h for _x, y, _w, h in positions.values()), default=lane_top)
        height = int(max_content_bottom + config.bottom_margin)
        try:
            assert height > max_content_bottom
        except AssertionError as exc:
            raise RenderError(
                "parallel_lanes canvas height must exceed content bottom"
            ) from exc
        lane_guides = {
            "lanes": lanes,
            "margin_x": margin_x,
            "lane_width": lane_width,
            "header_y": lane_top - config.fanout_curve_height / 2,
            "divider_top": lane_top - config.fanout_curve_height,
            "divider_bottom": max_content_bottom,
        }

        return {
            "width": width,
            "height": height,
            "positions": positions,
            "order": order,
            "lane_orders": lane_orders,
            "shared_entry": shared_entry,
            "shared_convergence": shared_convergence,
            "max_content_bottom": max_content_bottom,
            "lane_guides": lane_guides,
        }

    def _parallel_lane_topological_order(self, prism: PrismDoc, lane_nodes: list[str]) -> list[str]:
        lane_node_set = set(lane_nodes)
        outgoing = {node_id: [] for node_id in lane_nodes}
        indegree = {node_id: 0 for node_id in lane_nodes}
        for edge in prism.edges:
            if edge.from_ not in lane_node_set or edge.to not in lane_node_set:
                continue
            if edge.type == "feedback" or edge.direction == EdgeDirection.BACKWARD:
                continue
            outgoing[edge.from_].append(edge.to)
            indegree[edge.to] += 1

        ready = [node_id for node_id in lane_nodes if indegree[node_id] == 0]
        ordered: list[str] = []
        while ready:
            node_id = ready.pop(0)
            ordered.append(node_id)
            for target in outgoing[node_id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)

        ordered_set = set(ordered)
        ordered.extend(node_id for node_id in lane_nodes if node_id not in ordered_set)
        return ordered

    def _parallel_shared_entry(
        self,
        prism: PrismDoc,
        lanes: list[RenderLane],
    ) -> str | None:
        lane_ids = {lane.id for lane in lanes}
        lane_by_node = {node.id: node.lane for node in prism.nodes}
        for node in prism.nodes:
            target_lanes = {
                lane_by_node.get(edge.to)
                for edge in prism.edges
                if edge.from_ == node.id and edge.to != node.id
            }
            if target_lanes & lane_ids == lane_ids:
                return node.id
        return None

    def _parallel_shared_convergence(
        self,
        prism: PrismDoc,
        lanes: list[RenderLane],
    ) -> str | None:
        lane_ids = {lane.id for lane in lanes}
        lane_by_node = {node.id: node.lane for node in prism.nodes}
        for node in prism.nodes:
            source_lanes = {
                lane_by_node.get(edge.from_)
                for edge in prism.edges
                if edge.to == node.id and lane_by_node.get(edge.from_) != node.lane
            }
            if len(source_lanes & lane_ids) >= 2:
                return node.id
        return None

    def _ensure_min_horizontal_gap(
        self,
        positions: dict[str, tuple[float, float, float, float]],
        order: list[str],
        prism: PrismDoc,
        ontology: Ontology,
        canvas_width: int,
        margin_x: int,
        min_gap: int,
    ) -> None:
        node_by_id = {node.id: node for node in prism.nodes}
        rows: dict[float, list[str]] = {}
        for node_id in order:
            rows.setdefault(positions[node_id][1], []).append(node_id)

        for row in rows.values():
            row.sort(key=lambda node_id: positions[node_id][0])
            self._nudge_row_apart(row, positions, node_by_id, ontology, min_gap)

            row_left = min(
                self._rendered_node_bounds(positions[node_id], node_by_id[node_id], ontology)[0]
                for node_id in row
            )
            row_right = max(
                self._rendered_node_bounds(positions[node_id], node_by_id[node_id], ontology)[1]
                for node_id in row
            )
            if row_right > canvas_width - margin_x:
                self._shift_row(row, positions, canvas_width - margin_x - row_right)
                row_left = min(
                    self._rendered_node_bounds(positions[node_id], node_by_id[node_id], ontology)[0]
                    for node_id in row
                )
            if row_left < margin_x:
                self._shift_row(row, positions, margin_x - row_left)

    def _nudge_row_apart(
        self,
        row: list[str],
        positions: dict[str, tuple[float, float, float, float]],
        node_by_id: dict[str, Node],
        ontology: Ontology,
        min_gap: int,
    ) -> None:
        previous_right: float | None = None
        for node_id in row:
            left, right = self._rendered_node_bounds(
                positions[node_id], node_by_id[node_id], ontology
            )
            if previous_right is not None and left < previous_right + min_gap:
                shift = previous_right + min_gap - left
                self._shift_node(node_id, positions, shift)
                left, right = self._rendered_node_bounds(
                    positions[node_id], node_by_id[node_id], ontology
                )
            previous_right = right

    def _shift_row(
        self,
        row: list[str],
        positions: dict[str, tuple[float, float, float, float]],
        shift: float,
    ) -> None:
        for node_id in row:
            self._shift_node(node_id, positions, shift)

    def _shift_node(
        self,
        node_id: str,
        positions: dict[str, tuple[float, float, float, float]],
        shift: float,
    ) -> None:
        x, y, width, height = positions[node_id]
        positions[node_id] = (x + shift, y, width, height)

    def _rendered_node_bounds(
        self,
        box: tuple[float, float, float, float],
        node: Node,
        ontology: Ontology,
    ) -> tuple[float, float]:
        left, _top, right, _bottom = self._rendered_node_box(box, node, ontology)
        return left, right

    def _rendered_node_box(
        self,
        box: tuple[float, float, float, float],
        node: Node,
        ontology: Ontology,
    ) -> tuple[float, float, float, float]:
        x, y, width, height = box
        scale = min(1.0, float(ontology.weight_style(node.weight)["scale"]))
        scaled_width = width * scale
        scaled_height = height * scale
        scaled_x = x + (width - scaled_width) / 2
        scaled_y = y + (height - scaled_height) / 2
        return scaled_x, scaled_y, scaled_x + scaled_width, scaled_y + scaled_height

    def _layer_node_width(
        self,
        layer: list[str],
        prism: PrismDoc,
        canvas_width: int,
        margin_x: int,
        x_gap: int,
        max_per_row: int,
    ) -> float:
        node_by_id = {node.id: node for node in prism.nodes}
        max_cols = min(max_per_row, len(layer))
        available_width = canvas_width - 2 * margin_x - max(0, max_cols - 1) * x_gap
        max_allowed = available_width / max_cols
        longest = max(
            len(node_by_id[node_id].label) * 16 + len(node_by_id[node_id].sublabel or "") * 5
            for node_id in layer
        )
        desired = 178 + min(110, longest)
        return min(max_allowed, max(120, min(max_allowed, desired)))

    def _topological_layers(self, prism: PrismDoc) -> list[list[str]]:
        explicit_layers = [node.layer for node in prism.nodes if node.layer is not None]
        if explicit_layers:
            grouped_by_layer: dict[int, list[str]] = {}
            for node in prism.nodes:
                layer = node.layer if node.layer is not None else max(explicit_layers) + 1
                grouped_by_layer.setdefault(layer, []).append(node.id)
            return [grouped_by_layer[index] for index in sorted(grouped_by_layer)]

        node_ids = [node.id for node in prism.nodes]
        node_id_set = set(node_ids)
        outgoing = {node_id: [] for node_id in node_ids}
        indegree = {node_id: 0 for node_id in node_ids}

        for edge in prism.edges:
            if edge.type == "feedback" or edge.direction == EdgeDirection.BACKWARD:
                continue
            if edge.from_ not in node_id_set or edge.to not in node_id_set:
                continue
            outgoing[edge.from_].append(edge.to)
            indegree[edge.to] += 1

        ready = [node_id for node_id in node_ids if indegree[node_id] == 0]
        layer_index = {node_id: 0 for node_id in node_ids}
        seen: set[str] = set()

        while ready:
            node_id = ready.pop(0)
            seen.add(node_id)
            for target in outgoing[node_id]:
                layer_index[target] = max(layer_index[target], layer_index[node_id] + 1)
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)

        for node_id in node_ids:
            if node_id not in seen:
                predecessors = [
                    edge.from_
                    for edge in prism.edges
                    if edge.to == node_id and edge.from_ in layer_index and edge.type != "feedback"
                ]
                layer_index[node_id] = (
                    max(layer_index[predecessor] for predecessor in predecessors) + 1
                    if predecessors
                    else 0
                )

        grouped: dict[int, list[str]] = {}
        for node_id in node_ids:
            grouped.setdefault(layer_index[node_id], []).append(node_id)
        return [grouped[index] for index in sorted(grouped)]

    def _render_svg_edges(
        self,
        prism: PrismDoc,
        positions: dict[str, tuple[float, float, float, float]],
        theme: VisualTheme,
    ) -> str:
        parts = []
        edge_offsets = self._edge_fan_offsets(prism.edges, positions)
        row_tops = sorted({box[1] for box in positions.values()})
        for edge_index, edge in enumerate(prism.edges):
            if edge.from_ not in positions or edge.to not in positions:
                continue
            x1, y1, w1, h1 = positions[edge.from_]
            x2, y2, w2, _ = positions[edge.to]
            color = self._edge_color(edge.type, theme)
            marker = {
                theme.accent_secondary: "arrow-secondary",
                theme.accent_risk: "arrow-risk",
            }.get(color, "arrow-primary")

            points = self._edge_route_points(
                edge,
                edge_index,
                positions,
                row_tops,
                edge_offsets.get(edge_index, (0.0, 0.0)),
            )
            start_x, start_y = points[0]
            end_x, end_y = points[-1]
            if not self._source_endpoint_inside_node(edge, (start_x, start_y), positions):
                print(f"SKIPPED stray edge: {edge.from_} -> {edge.to}")
                continue
            path = self._polyline_path(points)
            if edge.type in {"feedback", "influence", "risk"} or y2 <= y1:
                dash = ' stroke-dasharray="8 7"'
            else:
                dash = ""

            label = self._render_edge_label(
                edge.label,
                start_x,
                start_y,
                end_x,
                end_y,
                x1 + w1 / 2,
                y1 + h1 / 2,
                x2 + w2 / 2,
                y2 + h1 / 2,
                theme,
            )

            parts.append(
                f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.5"{dash} '
                f'marker-end="url(#{marker})" opacity="0.86" />{label}'
            )
        return "".join(parts)

    def _source_endpoint_inside_node(
        self,
        edge: Edge,
        source_xy: tuple[float, float],
        positions: dict[str, tuple[float, float, float, float]],
    ) -> bool:
        # Edge diagnostic findings from the stablecoin parallel-lanes render:
        # every rendered source point was inside its source node; the visually suspicious
        # feedback edge was funding_income -> treasury_bills, source=(839.5, 448.0),
        # target=(60.5, 328.0), which lies on funding_income's right border.
        x, y, width, height = positions[edge.from_]
        source_x, source_y = source_xy
        return (
            x - 2 <= source_x <= x + width + 2
            and y - 2 <= source_y <= y + height + 2
        )

    def _edge_fan_offsets(
        self,
        edges: list[Edge],
        positions: dict[str, tuple[float, float, float, float]],
    ) -> dict[int, tuple[float, float]]:
        source_keys = []
        target_keys = []
        for edge in edges:
            if edge.from_ not in positions or edge.to not in positions:
                source_keys.append(None)
                target_keys.append(None)
                continue
            source_side, target_side = self._edge_sides(edge, positions)
            source_keys.append((edge.from_, source_side))
            target_keys.append((edge.to, target_side))

        source_counts = Counter(key for key in source_keys if key is not None)
        target_counts = Counter(key for key in target_keys if key is not None)
        source_seen: Counter[tuple[str, str]] = Counter()
        target_seen: Counter[tuple[str, str]] = Counter()
        offsets: dict[int, tuple[float, float]] = {}

        for index, (source_key, target_key) in enumerate(zip(source_keys, target_keys)):
            if source_key is None or target_key is None:
                continue
            source_index = source_seen[source_key]
            target_index = target_seen[target_key]
            source_seen[source_key] += 1
            target_seen[target_key] += 1
            source_offset = (source_index - (source_counts[source_key] - 1) / 2) * 12
            target_offset = (target_index - (target_counts[target_key] - 1) / 2) * 12
            offsets[index] = (source_offset, target_offset)

        return offsets

    def _edge_sides(
        self,
        edge: Edge,
        positions: dict[str, tuple[float, float, float, float]],
    ) -> tuple[str, str]:
        source_row = positions[edge.from_][1]
        target_row = positions[edge.to][1]
        if target_row < source_row or edge.direction == EdgeDirection.BACKWARD:
            return "top", "bottom"
        return "bottom", "top"

    def _edge_route_points(
        self,
        edge: Edge,
        edge_index: int,
        positions: dict[str, tuple[float, float, float, float]],
        row_tops: list[float],
        fan_offsets: tuple[float, float],
    ) -> list[tuple[float, float]]:
        x1, y1, w1, h1 = positions[edge.from_]
        x2, y2, w2, h2 = positions[edge.to]
        source_row = row_tops.index(y1)
        target_row = row_tops.index(y2)
        row_delta = target_row - source_row
        direction = 1 if row_delta >= 0 else -1
        if edge.direction == EdgeDirection.BACKWARD:
            direction = -1

        source_offset, target_offset = fan_offsets
        if direction >= 0:
            start = (x1 + w1 / 2 + source_offset, y1 + h1)
            end = (x2 + w2 / 2 + target_offset, y2)
        else:
            start = (x1 + w1 / 2 + source_offset, y1)
            end = (x2 + w2 / 2 + target_offset, y2 + h2)

        source_gutter = self._edge_gutter_y(row_tops, positions, source_row, direction)
        target_gutter = self._edge_gutter_y(row_tops, positions, target_row, -direction)
        row_distance = abs(row_delta)
        use_margin = row_distance > 2 or edge.type in {"influence", "risk"}
        if edge.type == "feedback" or edge.direction == EdgeDirection.BACKWARD:
            use_margin = use_margin or row_distance > 0

        if use_margin:
            route_x = self._edge_margin_x(edge, edge_index, start[0], end[0])
            return [
                start,
                (start[0], source_gutter),
                (route_x, source_gutter),
                (route_x, target_gutter),
                (end[0], target_gutter),
                end,
            ]

        route_x = self._safe_center_route_x(
            positions, row_tops, source_row, target_row, start[0], end[0]
        )
        if row_distance <= 1:
            shared_gutter = source_gutter
            return [start, (start[0], shared_gutter), (end[0], shared_gutter), end]

        return [
            start,
            (start[0], source_gutter),
            (route_x, source_gutter),
            (route_x, target_gutter),
            (end[0], target_gutter),
            end,
        ]

    def _edge_gutter_y(
        self,
        row_tops: list[float],
        positions: dict[str, tuple[float, float, float, float]],
        row_index: int,
        direction: int,
    ) -> float:
        row_height = max(height for _x, y, _w, height in positions.values() if y == row_tops[row_index])
        if direction >= 0:
            if row_index < len(row_tops) - 1:
                return (row_tops[row_index] + row_height + row_tops[row_index + 1]) / 2
            return row_tops[row_index] + row_height + 18
        if row_index > 0:
            prev_height = max(
                height for _x, y, _w, height in positions.values() if y == row_tops[row_index - 1]
            )
            return (row_tops[row_index - 1] + prev_height + row_tops[row_index]) / 2
        return max(18, row_tops[row_index] - 18)

    def _edge_margin_x(
        self,
        edge: Edge,
        edge_index: int,
        start_x: float,
        end_x: float,
    ) -> float:
        if edge.type in {"influence", "risk"}:
            return 860
        if end_x < start_x:
            return 40
        if edge_index % 2:
            return 40
        return 860

    def _safe_center_route_x(
        self,
        positions: dict[str, tuple[float, float, float, float]],
        row_tops: list[float],
        source_row: int,
        target_row: int,
        start_x: float,
        end_x: float,
    ) -> float:
        lower = min(source_row, target_row) + 1
        upper = max(source_row, target_row)
        blockers = [
            box
            for box in positions.values()
            if lower <= row_tops.index(box[1]) < upper
        ]
        candidates = [(start_x + end_x) / 2, 450, 310, 590, 170, 730]
        for candidate in candidates:
            if all(not (x - 8 <= candidate <= x + width + 8) for x, _y, width, _h in blockers):
                return self._clamp(candidate, 40, 860)
        return self._clamp((start_x + end_x) / 2, 40, 860)

    def _render_edge_label(
        self,
        text: str | None,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        source_center_x: float,
        source_center_y: float,
        target_center_x: float,
        target_center_y: float,
        theme: VisualTheme,
    ) -> str:
        if not text:
            return ""

        canvas_width = 900
        min_x = 24
        right_margin = 12
        max_x = canvas_width - right_margin
        label_text = text
        estimated_width = self._estimate_text_width(label_text, font_size=13)
        raw_label_x = (start_x + end_x) / 2
        label_y = (start_y + end_y) / 2 - 8
        text_anchor = "end" if raw_label_x > 600 else "middle"

        if text_anchor == "end":
            label_x = min(raw_label_x, max_x)
            if label_x - estimated_width < min_x:
                label_x = min(max_x, min_x + estimated_width)
        else:
            raw_label_x = (source_center_x + target_center_x) / 2
            half_width = estimated_width / 2
            if raw_label_x - half_width < min_x or raw_label_x + half_width > max_x:
                label_y = min(source_center_y, target_center_y) - 10
            label_x = raw_label_x
            if label_x + half_width > max_x:
                label_x = max_x - half_width - 0.1
            elif label_x - half_width < min_x:
                label_x = min_x + half_width

        return (
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="{text_anchor}" '
            f'fill="{theme.text_secondary}" font-size="13" '
            f'font-family="ui-sans-serif, system-ui">{escape(label_text)}</text>'
        )

    def _clamp(self, value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    def _render_svg_node(
        self,
        node: Node,
        box: tuple[float, float, float, float],
        ontology: Ontology,
        theme: VisualTheme,
        emphasized: bool,
    ) -> str:
        x, y, width, height = box
        weight_style = ontology.weight_style(node.weight)
        scale = min(1.0, float(weight_style["scale"]))
        fill = weight_style["fill"] if weight_style["fill"] != "none" else theme.background
        text_color = weight_style["text"]
        border = weight_style["border"]
        scaled_width = width * scale
        scaled_height = height * scale
        scaled_x = x + (width - scaled_width) / 2
        scaled_y = y + (height - scaled_height) / 2
        title_lines = self._wrap_text(node.label, max(4, int(scaled_width / 18)), 2)
        sublabel_lines = self._wrap_text(node.sublabel or "", max(6, int(scaled_width / 14)), 2)
        title_y = scaled_y + 28 if len(title_lines) == 1 else scaled_y + 23
        text_parts = []
        for index, line in enumerate(title_lines):
            text_parts.append(
                f'<text x="{scaled_x + 18:.1f}" y="{title_y + index * 18:.1f}" '
                f'fill="{text_color}" font-size="15" font-weight="650" '
                f'font-family="ui-sans-serif, system-ui">{escape(line)}</text>'
            )
        sublabel_y = scaled_y + 51 if len(title_lines) == 1 else scaled_y + 56
        for index, line in enumerate(sublabel_lines[:1]):
            text_parts.append(
                f'<text x="{scaled_x + 18:.1f}" y="{sublabel_y + index * 15:.1f}" '
                f'fill="{text_color}" font-size="13" opacity="0.78" '
                f'font-family="ui-sans-serif, system-ui">{escape(line)}</text>'
            )

        bar_width = theme.node_accent_bar_width + (2 if emphasized else 0)
        stroke_width = 2 if emphasized else 1
        return (
            f'<g class="node" data-node-id="{escape(node.id)}">'
            f'<rect x="{scaled_x:.1f}" y="{scaled_y:.1f}" width="{scaled_width:.1f}" '
            f'height="{scaled_height:.1f}" rx="8" fill="{fill}" stroke="{border}" '
            f'stroke-width="{stroke_width}" />'
            f'<rect class="prism-node-accent" x="{scaled_x:.1f}" y="{scaled_y:.1f}" '
            f'width="{bar_width}" height="{scaled_height:.1f}" rx="1" '
            f'fill="{border}" />'
            f'{"".join(text_parts)}'
            "</g>"
        )

    def _render_svg_loops(self, prism: PrismDoc, theme: VisualTheme) -> str:
        if not prism.loops:
            return ""
        loop_x = 48
        loop_y = 1048
        loop_width = 804
        loop_height = 96
        padding_x = 14
        title_y = loop_y + 22
        item_start_y = loop_y + 48
        item_gap = 16
        font_size = 12 if len(prism.loops) > 2 else 13
        max_items = min(len(prism.loops), max(1, (loop_height - 48) // item_gap))
        items = []
        for index, loop in enumerate(prism.loops[:max_items]):
            nodes = " -> ".join(loop.nodes)
            text = self._truncate_text(f"{loop.label} ({loop.polarity.value}): {nodes}", 68)
            if index == max_items - 1 and len(prism.loops) > max_items:
                text = self._truncate_text(f"{text} ...", 68)
            items.append(
                f'<text x="{loop_x + padding_x}" y="{item_start_y + index * item_gap}" '
                f'fill="{theme.text_secondary}" font-size="{font_size}" '
                f'font-family="ui-sans-serif, system-ui">{escape(text)}</text>'
            )
        return (
            f'<clipPath id="feedback-loops-clip">'
            f'<rect x="{loop_x}" y="{loop_y}" width="{loop_width}" height="{loop_height}" rx="10" />'
            f'</clipPath>'
            f'<g class="feedback-loops" clip-path="url(#feedback-loops-clip)">'
            f'<rect x="{loop_x}" y="{loop_y}" width="{loop_width}" height="{loop_height}" rx="10" '
            f'fill="{theme.background}" stroke="{theme.surface_border}" stroke-width="1" opacity="0.96" />'
            f'<text x="{loop_x + padding_x}" y="{title_y}" fill="{theme.text_primary}" font-size="13" '
            f'font-weight="650" font-family="ui-sans-serif, system-ui">Feedback loops</text>'
            f'{"".join(items)}'
            f'</g>'
        )

    def _polyline_path(self, points: list[tuple[float, float]]) -> str:
        start_x, start_y = points[0]
        segments = [f"M {start_x:.1f} {start_y:.1f}"]
        segments.extend(f"L {x:.1f} {y:.1f}" for x, y in points[1:])
        return " ".join(segments)

    def _emphasized_nodes(self, prism: PrismDoc) -> set[str]:
        node_ids = {node.id for node in prism.nodes}
        incoming = {node_id: 0 for node_id in node_ids}
        outgoing = {node_id: 0 for node_id in node_ids}
        for edge in prism.edges:
            if edge.type == "feedback" or edge.direction == EdgeDirection.BACKWARD:
                continue
            if edge.from_ in node_ids and edge.to in node_ids:
                outgoing[edge.from_] += 1
                incoming[edge.to] += 1

        starts = {node_id for node_id in node_ids if incoming[node_id] == 0 and outgoing[node_id] > 0}
        ends = {node_id for node_id in node_ids if outgoing[node_id] == 0 and incoming[node_id] > 0}
        return starts | ends

    def _wrap_text(self, text: str, max_chars: int, max_lines: int) -> list[str]:
        if not text:
            return []
        lines = [text[index : index + max_chars] for index in range(0, len(text), max_chars)]
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip("，。；：、 ") + "..."
        return lines

    def _truncate_text(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max(0, max_chars - 3)].rstrip("，。；：、 ") + "..."

    def _estimate_text_width(self, text: str, font_size: int) -> float:
        width = 0.0
        for char in text:
            width += font_size if ord(char) > 127 else font_size * 0.58
        return width

    def _arrow(self, direction: EdgeDirection) -> str:
        if direction == EdgeDirection.BACKWARD:
            return "<--"
        if direction == EdgeDirection.BIDIRECTIONAL:
            return "<-->"
        return "-->"

    def _node_label(self, label: str, sublabel: str | None) -> str:
        if not sublabel:
            return self._escape_mermaid(label)
        return f"{self._escape_mermaid(label)}<br/><small>{self._escape_mermaid(sublabel)}</small>"

    def _escape_mermaid(self, value: str) -> str:
        return value.replace('"', "#quot;")
