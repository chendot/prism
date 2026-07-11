"""Mermaid renderer for Prism Layer 3."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from html import escape
from itertools import count
import json
import logging
from math import ceil
from pathlib import Path
import re

from prism.core.models import Ontology
from prism.core.schema import Edge, EdgeDirection, Node, PrismDoc, RenderLane
from prism.core.validator import validate_prism_doc
from prism.ontologies.loader import load_ontology
from prism.render.base import Renderer
from prism.render.icons import ROLE_ICON_PATHS
from prism.render.theme import VisualTheme, load_theme


logger = logging.getLogger(__name__)
DAGRE_VERSION = "3.0.0"
DAGRE_VENDOR_PATH = Path(__file__).resolve().parent / "vendor" / "dagre.min.js"
DAGRE_RENDERER_PATH = Path(__file__).resolve().parent / "dagre_renderer.js"


class RenderError(RuntimeError):
    """Raised when a renderer cannot produce a valid canvas."""


@dataclass(frozen=True)
class LayoutConfig:
    top_margin: int = 32
    header_height: int = 104
    bottom_margin: int = 72
    lane_padding: int = 40
    node_gap: int = 56
    node_height: int = 64
    node_width: int = 280
    node_max_width: int = 340
    node_one_line_slack: int = 8
    node_width_ratio: float = 0.85
    fanout_curve_height: int = 80
    convergence_curve_height: int = 48
    label_gap_ratio: float = 0.5
    label_bg_padding_x: int = 4
    label_bg_padding_y: int = 2
    edge_label_bg_padding_x: int = 7
    edge_label_bg_padding_y: int = 4
    label_bg_opacity: float = 0.98
    arrowhead_size: int = 8
    canvas_width: int = 900
    title_font_weight: int = 700
    subtitle_opacity: float = 0.84
    edge_label_opacity: float = 0.94
    edge_opacity: float = 0.96
    feedback_edge_opacity: float = 0.38
    feedback_edge_width_scale: float = 0.72
    edge_label_font_size_offset: int = -1
    edge_port_gap: int = 12
    edge_track_gap: int = 12
    edge_route_margin: int = 40
    edge_outer_margin: int = 16
    node_route_clearance: int = 64
    node_column_gap: int = 40
    node_title_font_size: int = 15
    node_subtitle_font_size: int = 13
    edge_label_font_size: int = 12
    loop_font_size: int = 13
    watermark_font_size: int = 18
    icon_size: int = 16
    node_text_padding: int = 18
    node_vertical_padding: int = 14
    header_title_font_size: int = 26
    header_thesis_font_size: int = 14


class MermaidRenderer(Renderer):
    """Render a validated Prism document with a bundled dagre runtime."""

    def __init__(self, layout_config: LayoutConfig | None = None) -> None:
        self.layout_config = layout_config or LayoutConfig()

    def render(self, prism: PrismDoc, ontology: Ontology) -> str:
        """Return self-contained HTML that lays out and draws Prism with dagre."""

        validate_prism_doc(prism, ontology)
        theme = load_theme(prism.meta.visual_theme)
        payload = {
            "prism": prism.model_dump(mode="json", by_alias=True),
            "ontology": asdict(ontology),
            "theme": asdict(theme),
            "layout": asdict(self.layout_config),
            "icons": ROLE_ICON_PATHS,
            "dagre_version": DAGRE_VERSION,
        }
        payload_json = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).replace("<", "\\u003c")
        dagre_source = self._read_browser_asset(DAGRE_VENDOR_PATH)
        renderer_source = self._read_browser_asset(DAGRE_RENDERER_PATH)

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
      overflow-x: hidden;
      overflow-y: auto;
    }}
    main {{
      min-height: 100vh;
      display: grid;
      place-items: start center;
      box-sizing: border-box;
      padding: 24px 0;
    }}
    .diagram {{
      width: min({self.layout_config.canvas_width}px, 100vw);
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
    <section id="prism-root" class="diagram" data-layout-engine="dagre"></section>
  </main>
  <script>{dagre_source}</script>
  <script>{renderer_source}</script>
  <script id="prism-payload" type="application/json">{payload_json}</script>
  <script>
    PrismDagre.render(
      JSON.parse(document.getElementById("prism-payload").textContent),
      document.getElementById("prism-root")
    );
  </script>
</body>
</html>
"""

    def _read_browser_asset(self, path: Path) -> str:
        if not path.exists():
            raise RenderError(f"Missing bundled browser asset: {path}")
        return path.read_text(encoding="utf-8")

    def to_svg(
        self, prism: PrismDoc, ontology: Ontology, theme: VisualTheme | None = None
    ) -> str:
        """Render a mobile-friendly layered SVG diagram."""

        theme = theme or load_theme(prism.meta.visual_theme)
        config = self.layout_config
        layout = (
            self._layout_parallel_lanes(prism, ontology)
            if prism.render.template == "parallel_lanes"
            else self._layout_nodes(prism, ontology)
        )
        width = layout["width"]
        height = layout["height"]
        positions: dict[str, tuple[float, float, float, float]] = layout["positions"]  # type: ignore[assignment]
        node_by_id = {node.id: node for node in prism.nodes}
        edge_svg = (
            self._render_parallel_lanes_edges(prism, positions, layout, theme, ontology)
            if prism.render.template == "parallel_lanes"
            else self._render_svg_edges(prism, positions, ontology, theme)
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
            )
            for node_id in layout["order"]  # type: ignore[index]
        )

        return f"""<svg class="prism-svg" role="img" aria-label="{escape(prism.meta.title)}" width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad_neutral" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{theme.surface}" />
      <stop offset="100%" stop-color="{theme.background}" />
    </linearGradient>
    <linearGradient id="grad_positive" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{theme.accent_result}" />
      <stop offset="100%" stop-color="{theme.accent_result}" stop-opacity="0.82" />
    </linearGradient>
    <linearGradient id="grad_highlight" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{theme.accent_result}" />
      <stop offset="100%" stop-color="{theme.accent_result}" stop-opacity="0.82" />
    </linearGradient>
    <linearGradient id="grad_bar_primary" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{theme.accent_primary}" />
      <stop offset="100%" stop-color="{theme.accent_primary}" stop-opacity="0.2" />
    </linearGradient>
    <linearGradient id="grad_bar_result" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{theme.accent_result}" />
      <stop offset="100%" stop-color="{theme.accent_result}" stop-opacity="0.2" />
    </linearGradient>
    <linearGradient id="grad_bar_risk" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{theme.accent_risk}" />
      <stop offset="100%" stop-color="{theme.accent_risk}" stop-opacity="0.2" />
    </linearGradient>
    <filter id="glow_primary" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="{theme.glow_blur:g}" result="blur" />
      <feFlood flood-color="{theme.accent_primary}" flood-opacity="{theme.primary_glow_opacity:g}" result="glow-color" />
      <feComposite in="glow-color" in2="blur" operator="in" result="glow" />
      <feMerge><feMergeNode in="glow"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="glow_highlight" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="{theme.glow_blur:g}" result="blur" />
      <feFlood flood-color="{theme.accent_result}" flood-opacity="{theme.highlight_glow_opacity:g}" result="glow-color" />
      <feComposite in="glow-color" in2="blur" operator="in" result="glow" />
      <feMerge><feMergeNode in="glow"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <marker id="filled_triangle" markerWidth="{config.arrowhead_size}" markerHeight="{config.arrowhead_size}" refX="{config.arrowhead_size}" refY="{config.arrowhead_size / 2:.1f}" orient="auto" markerUnits="strokeWidth">
      <path d="M 0 0 L {config.arrowhead_size} {config.arrowhead_size / 2:.1f} L 0 {config.arrowhead_size} z" fill="{theme.accent_primary}" />
    </marker>
    <marker id="filled_triangle_large" markerWidth="{config.arrowhead_size * 1.4:.1f}" markerHeight="{config.arrowhead_size * 1.4:.1f}" refX="{config.arrowhead_size * 1.4:.1f}" refY="{config.arrowhead_size * 0.7:.1f}" orient="auto" markerUnits="strokeWidth">
      <path d="M 0 0 L {config.arrowhead_size * 1.4:.1f} {config.arrowhead_size * 0.7:.1f} L 0 {config.arrowhead_size * 1.4:.1f} z" fill="{theme.accent_primary}" />
    </marker>
    <marker id="open_triangle" markerWidth="{config.arrowhead_size}" markerHeight="{config.arrowhead_size}" refX="{config.arrowhead_size}" refY="{config.arrowhead_size / 2:.1f}" orient="auto" markerUnits="strokeWidth">
      <path d="M 0 0 L {config.arrowhead_size} {config.arrowhead_size / 2:.1f} L 0 {config.arrowhead_size}" fill="none" stroke="{theme.accent_primary}" />
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
        class_names: dict[tuple[str, str], str] = {}
        class_counter = count(1)

        for node in prism.nodes:
            node_label = self._node_label(node.label, node.sublabel)
            visual = ontology.role_visual(node.role)
            lines.append(self._mermaid_node(node, node_label, str(visual["shape"])))
            class_key = (node.role, node.status.value)
            class_name = class_names.setdefault(class_key, f"role{next(class_counter)}")
            lines.append(f"    class {node.id} {class_name}")

        for index, edge in enumerate(prism.edges):
            visual = ontology.edge_visual(edge.type)
            arrow = "---" if visual["arrow"] == "none" else self._arrow(edge.direction)
            label = f"|{self._escape_mermaid(edge.label)}|" if edge.label else ""
            lines.append(f"    {edge.from_} {arrow}{label} {edge.to}")
            edge_index = index
            style_bits = [
                f"stroke:{theme.accent_primary}",
                f"stroke-width:{visual['stroke_width']}px",
            ]
            if visual.get("stroke_dash") is not None:
                style_bits.append(f"stroke-dasharray:{visual['stroke_dash']}")
            lines.append(f"    linkStyle {edge_index} {','.join(style_bits)}")

        for (role, status), class_name in class_names.items():
            visual = ontology.role_visual(role)
            node = next(node for node in prism.nodes if node.role == role and node.status.value == status)
            fill, border = self._status_colors(node, theme)
            dash = visual.get("border_dash") if role == "risk" else None
            dash_style = f",stroke-dasharray:{dash}" if dash is not None else ""
            lines.append(
                f"    classDef {class_name} fill:{fill},stroke:{border},"
                f"stroke-width:{visual['border_width']}px,color:{theme.text_primary}{dash_style}"
            )

        if prism.render.highlight_nodes:
            for node_id in prism.render.highlight_nodes:
                lines.append(f"    style {node_id} stroke:{theme.accent_result}")

        return "\n".join(lines)

    def _mermaid_node(self, node: Node, label: str, shape: str) -> str:
        if shape == "round":
            return f'    {node.id}(["{label}"])'
        if shape == "double_border":
            return f'    {node.id}[["{label}"]]'
        return f'    {node.id}["{label}"]'

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
        ontology: Ontology | None = None,
    ) -> str:
        ontology = ontology or load_ontology(prism.meta.ontology)
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
                path = self._parallel_lane_edge_path(edge, positions)
                color = theme.accent_primary
                label_kind = "vertical"
            elif edge.from_ == shared_entry:
                path = self._parallel_entry_fan_path(edge, positions)
                color = theme.accent_secondary
                label_kind = "fan"
            elif edge.to == shared_convergence:
                path = self._parallel_convergence_fan_path(edge, positions)
                color = theme.accent_secondary
                label_kind = "fan"
            else:
                path = self._parallel_margin_edge_path(edge, positions, layout)
                color = theme.accent_secondary
                label_kind = "margin"
            endpoints = self._parallel_path_endpoints(path)
            if endpoints is None or self._drop_parallel_edge_path(edge, endpoints, positions, layout):
                continue
            if not self._source_endpoint_inside_node(edge, endpoints[0], positions):
                print(f"SKIPPED stray edge: {edge.from_} -> {edge.to}")
                continue

            visual = ontology.edge_visual(edge.type)
            dash = self._stroke_dash_attribute(visual.get("stroke_dash"))
            marker = self._marker_attribute(str(visual["arrow"]))
            label = self._parallel_edge_label(edge, positions, theme, label_kind)
            parts.append(
                f'<path d="{path}" data-edge-type="{escape(edge.type)}" fill="none" '
                f'stroke="{color}" stroke-width="{visual["stroke_width"]}"{dash}{marker} '
                f'opacity="{self.layout_config.edge_opacity:g}" />{label}'
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
        font_size = config.arrowhead_size + config.label_bg_padding_x + config.edge_label_font_size_offset
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
                    f'fill="{theme.text_secondary}" font-size="{font_size}" opacity="{config.edge_label_opacity:g}" '
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
        margin_x = self.layout_config.node_route_clearance
        top = 36
        bottom = 156
        node_height = 66
        max_per_row = 3
        x_gap = self.layout_config.node_column_gap
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
            node_by_id = {node.id: node for node in prism.nodes}
            for node_id, box in list(positions.items()):
                positions[node_id] = self._scale_layout_box(
                    box, node_by_id[node_id], ontology
                )
            self._ensure_min_horizontal_gap(
                positions, order, prism, ontology, width, margin_x, x_gap
            )

        return {"width": width, "height": height, "positions": positions, "order": order}

    def _layout_parallel_lanes(
        self, prism: PrismDoc, ontology: Ontology | None = None
    ) -> dict[str, object]:
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
        node_by_id = {node.id: node for node in prism.nodes}

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
                if ontology is not None:
                    positions[node_id] = self._scale_layout_box(
                        positions[node_id], node_by_id[node_id], ontology
                    )
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
            if ontology is not None:
                positions[shared_entry] = self._scale_layout_box(
                    positions[shared_entry], node_by_id[shared_entry], ontology
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
            if ontology is not None:
                positions[shared_convergence] = self._scale_layout_box(
                    positions[shared_convergence],
                    node_by_id[shared_convergence],
                    ontology,
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
        return x, y, x + width, y + height

    def _scale_layout_box(
        self,
        box: tuple[float, float, float, float],
        node: Node,
        ontology: Ontology,
    ) -> tuple[float, float, float, float]:
        x, y, width, height = box
        scale = float(ontology.role_visual(node.role).get("scale", 1.0))
        scaled_width = width * scale
        scaled_height = height * scale
        scaled_x = x + (width - scaled_width) / 2
        scaled_y = y + (height - scaled_height) / 2
        return scaled_x, scaled_y, scaled_width, scaled_height

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
        ontology: Ontology,
        theme: VisualTheme,
    ) -> str:
        path_parts = []
        label_parts = []
        visible_edges = [
            edge
            for edge in prism.edges
            if not (
                prism.render.show_loops
                and self._edge_represented_by_loop(edge, prism)
            )
        ]
        routes = self._plan_edge_routes(visible_edges, positions)
        occupied_labels: list[tuple[float, float, float, float]] = []
        for edge_index, edge in enumerate(visible_edges):
            if edge.from_ not in positions or edge.to not in positions:
                continue
            x1, y1, w1, h1 = positions[edge.from_]
            x2, y2, w2, _ = positions[edge.to]
            color = theme.accent_primary
            visual = ontology.edge_visual(edge.type)

            points = routes[edge_index]
            start_x, start_y = points[0]
            end_x, end_y = points[-1]
            if not self._source_endpoint_inside_node(edge, (start_x, start_y), positions):
                print(f"SKIPPED stray edge: {edge.from_} -> {edge.to}")
                continue
            path = self._polyline_path(points)
            dash = self._stroke_dash_attribute(visual.get("stroke_dash"))
            marker = self._marker_attribute(str(visual["arrow"]))

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
                route_points=points,
                positions=positions,
                occupied_labels=occupied_labels,
            )

            path_parts.append(
                f'<path d="{path}" data-edge-type="{escape(edge.type)}" fill="none" '
                f'stroke="{color}" stroke-width="{visual["stroke_width"]}"{dash}{marker} '
                f'opacity="{self.layout_config.edge_opacity:g}" />'
            )
            label_parts.append(label)
        return "".join(path_parts + label_parts)

    def _edge_represented_by_loop(self, edge: Edge, prism: PrismDoc) -> bool:
        """Avoid drawing a feedback relation twice when the loop panel shows it."""

        if edge.type != "feedback" and edge.direction != EdgeDirection.BACKWARD:
            return False
        for loop in prism.loops:
            if len(loop.nodes) < 2:
                continue
            adjacent_pairs = zip(loop.nodes, loop.nodes[1:] + loop.nodes[:1])
            if any(
                {edge.from_, edge.to} == {source, target}
                for source, target in adjacent_pairs
            ):
                return True
        return False

    def _plan_edge_routes(
        self,
        edges: list[Edge],
        positions: dict[str, tuple[float, float, float, float]],
    ) -> dict[int, list[tuple[float, float]]]:
        """Plan ports and tracks for the whole layered graph before drawing."""

        row_tops = sorted({box[1] for box in positions.values()})
        fan_offsets = self._edge_fan_offsets(edges, positions)
        gutter_offsets = self._edge_gutter_offsets(edges, positions, row_tops)
        margin_tracks = self._edge_margin_tracks(edges, positions, row_tops)
        center_tracks = self._edge_center_tracks(edges, positions, row_tops)
        routes: dict[int, list[tuple[float, float]]] = {}
        for edge_index, edge in enumerate(edges):
            if edge.from_ not in positions or edge.to not in positions:
                continue
            routes[edge_index] = self._edge_route_points(
                edge,
                edge_index,
                positions,
                row_tops,
                fan_offsets.get(edge_index, (0.0, 0.0)),
                margin_x=margin_tracks.get(edge_index),
                gutter_offsets=gutter_offsets.get(edge_index, (0.0, 0.0)),
                center_route_x=center_tracks.get(edge_index),
            )
        return routes

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

        source_groups: dict[tuple[str, str], list[int]] = {}
        target_groups: dict[tuple[str, str], list[int]] = {}
        for index, (source_key, target_key) in enumerate(zip(source_keys, target_keys)):
            if source_key is not None:
                source_groups.setdefault(source_key, []).append(index)
            if target_key is not None:
                target_groups.setdefault(target_key, []).append(index)

        source_offsets: dict[int, float] = {}
        target_offsets: dict[int, float] = {}
        for indexes in source_groups.values():
            indexes.sort(
                key=lambda index: (
                    positions[edges[index].to][0] + positions[edges[index].to][2] / 2,
                    positions[edges[index].to][1],
                    edges[index].to,
                )
            )
            source_id = edges[indexes[0]].from_
            usable_width = max(0.0, positions[source_id][2] - 32)
            gap = min(
                self.layout_config.edge_port_gap,
                usable_width / max(1, len(indexes) - 1),
            )
            for order, index in enumerate(indexes):
                source_offsets[index] = (order - (len(indexes) - 1) / 2) * gap
        for indexes in target_groups.values():
            indexes.sort(
                key=lambda index: (
                    positions[edges[index].from_][0]
                    + positions[edges[index].from_][2] / 2,
                    positions[edges[index].from_][1],
                    edges[index].from_,
                )
            )
            target_id = edges[indexes[0]].to
            usable_width = max(0.0, positions[target_id][2] - 32)
            gap = min(
                self.layout_config.edge_port_gap,
                usable_width / max(1, len(indexes) - 1),
            )
            for order, index in enumerate(indexes):
                target_offsets[index] = (order - (len(indexes) - 1) / 2) * gap

        return {
            index: (source_offsets.get(index, 0.0), target_offsets.get(index, 0.0))
            for index in range(len(edges))
            if source_keys[index] is not None and target_keys[index] is not None
        }

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

    def _edge_direction_and_rows(
        self,
        edge: Edge,
        positions: dict[str, tuple[float, float, float, float]],
        row_tops: list[float],
    ) -> tuple[int, int, int]:
        source_row = row_tops.index(positions[edge.from_][1])
        target_row = row_tops.index(positions[edge.to][1])
        direction = 1 if target_row >= source_row else -1
        if edge.direction == EdgeDirection.BACKWARD:
            direction = -1
        return source_row, target_row, direction

    def _edge_uses_margin(
        self,
        edge: Edge,
        positions: dict[str, tuple[float, float, float, float]],
        row_tops: list[float],
    ) -> bool:
        source_row, target_row, _direction = self._edge_direction_and_rows(
            edge, positions, row_tops
        )
        row_distance = abs(target_row - source_row)
        return (
            row_distance > 2
            or edge.type in {"influence", "risk", "feedback"}
            or edge.direction == EdgeDirection.BACKWARD
        )

    def _edge_gutter_offsets(
        self,
        edges: list[Edge],
        positions: dict[str, tuple[float, float, float, float]],
        row_tops: list[float],
    ) -> dict[int, tuple[float, float]]:
        """Allocate independent horizontal tracks inside each row gap."""

        endpoint_gaps: dict[tuple[int, str], int] = {}
        gap_members: dict[int, list[tuple[int, str]]] = {}
        for index, edge in enumerate(edges):
            if edge.from_ not in positions or edge.to not in positions:
                continue
            source_row, target_row, direction = self._edge_direction_and_rows(
                edge, positions, row_tops
            )
            source_gap = source_row if direction >= 0 else source_row - 1
            target_gap = target_row - 1 if direction >= 0 else target_row
            endpoint_gaps[(index, "source")] = source_gap
            endpoint_gaps[(index, "target")] = target_gap
            gap_members.setdefault(source_gap, []).append((index, "source"))
            if target_gap != source_gap:
                gap_members.setdefault(target_gap, []).append((index, "target"))

        endpoint_offsets: dict[tuple[int, str], float] = {}
        for gap, members in gap_members.items():
            unique_indexes = sorted(
                {index for index, _endpoint in members},
                key=lambda index: (
                    positions[edges[index].from_][0]
                    + positions[edges[index].from_][2] / 2,
                    positions[edges[index].to][0] + positions[edges[index].to][2] / 2,
                    edges[index].from_,
                    edges[index].to,
                ),
            )
            track_gap = self.layout_config.edge_track_gap
            if 0 <= gap < len(row_tops) - 1 and len(unique_indexes) > 1:
                upper_bottom = max(
                    y + height
                    for _x, y, _width, height in positions.values()
                    if y == row_tops[gap]
                )
                free_height = max(0.0, row_tops[gap + 1] - upper_bottom - 12)
                track_gap = min(
                    track_gap,
                    free_height / max(1, len(unique_indexes) - 1),
                )
            for order, index in enumerate(unique_indexes):
                offset = (order - (len(unique_indexes) - 1) / 2) * track_gap
                for endpoint in ("source", "target"):
                    if endpoint_gaps.get((index, endpoint)) == gap:
                        endpoint_offsets[(index, endpoint)] = offset

        offsets: dict[int, tuple[float, float]] = {}
        for index in range(len(edges)):
            source_offset = endpoint_offsets.get((index, "source"), 0.0)
            target_offset = endpoint_offsets.get((index, "target"), source_offset)
            edge = edges[index]
            if (
                endpoint_gaps.get((index, "source"))
                == endpoint_gaps.get((index, "target"))
                and (
                    edge.type == "feedback"
                    or edge.direction == EdgeDirection.BACKWARD
                )
            ):
                half_gap = self.layout_config.edge_track_gap / 2
                source_offset += half_gap
                target_offset -= half_gap
            offsets[index] = (source_offset, target_offset)
        return offsets

    def _edge_margin_tracks(
        self,
        edges: list[Edge],
        positions: dict[str, tuple[float, float, float, float]],
        row_tops: list[float],
    ) -> dict[int, float]:
        """Assign distinct side rails to long, risk, and feedback edges."""

        side_members: dict[str, list[int]] = {"left": [], "right": []}
        side_load = Counter({"left": 0, "right": 0})
        for index, edge in enumerate(edges):
            if (
                edge.from_ not in positions
                or edge.to not in positions
                or not self._edge_uses_margin(edge, positions, row_tops)
            ):
                continue
            start_center = positions[edge.from_][0] + positions[edge.from_][2] / 2
            end_center = positions[edge.to][0] + positions[edge.to][2] / 2
            if (
                edge.type in {"influence", "risk", "feedback"}
                or edge.direction == EdgeDirection.BACKWARD
            ):
                side = "right"
            elif end_center < start_center:
                side = "left"
            elif end_center > start_center:
                side = "right"
            else:
                side = "left" if side_load["left"] <= side_load["right"] else "right"
            side_members[side].append(index)
            side_load[side] += 1

        tracks: dict[int, float] = {}
        config = self.layout_config
        for side, indexes in side_members.items():
            indexes.sort(
                key=lambda index: (
                    0
                    if edges[index].type == "feedback"
                    or edges[index].direction == EdgeDirection.BACKWARD
                    else 1,
                    index,
                )
            )
            if side == "left":
                candidates = list(
                    range(
                        config.edge_route_margin,
                        config.edge_outer_margin - 1,
                        -config.edge_track_gap,
                    )
                )
                candidates.extend(
                    range(
                        config.edge_route_margin + config.edge_track_gap,
                        config.node_route_clearance,
                        config.edge_track_gap,
                    )
                )
            else:
                candidates = list(
                    range(
                        config.canvas_width - config.edge_route_margin,
                        config.canvas_width - config.edge_outer_margin + 1,
                        config.edge_track_gap,
                    )
                )
                candidates.extend(
                    range(
                        config.canvas_width - config.edge_route_margin - config.edge_track_gap,
                        config.canvas_width - config.node_route_clearance,
                        -config.edge_track_gap,
                    )
                )
            available = list(candidates)
            for index in indexes:
                edge = edges[index]
                is_feedback = (
                    edge.type == "feedback"
                    or edge.direction == EdgeDirection.BACKWARD
                )
                if not available:
                    tracks[index] = float(candidates[-1])
                    continue
                if is_feedback:
                    chosen = min(available) if side == "left" else max(available)
                else:
                    preferred = (
                        config.edge_route_margin
                        if side == "left"
                        else config.canvas_width - config.edge_route_margin
                    )
                    chosen = min(available, key=lambda candidate: abs(candidate - preferred))
                available.remove(chosen)
                tracks[index] = float(chosen)
        return tracks

    def _edge_center_tracks(
        self,
        edges: list[Edge],
        positions: dict[str, tuple[float, float, float, float]],
        row_tops: list[float],
    ) -> dict[int, float]:
        """Allocate distinct vertical tracks for multi-row non-margin edges."""

        groups: dict[tuple[int, int], list[int]] = {}
        for index, edge in enumerate(edges):
            if edge.from_ not in positions or edge.to not in positions:
                continue
            source_row, target_row, _direction = self._edge_direction_and_rows(
                edge, positions, row_tops
            )
            if (
                abs(target_row - source_row) <= 1
                or self._edge_uses_margin(edge, positions, row_tops)
            ):
                continue
            groups.setdefault(
                (min(source_row, target_row), max(source_row, target_row)), []
            ).append(index)

        tracks: dict[int, float] = {}
        occupied: list[tuple[float, int, int]] = []
        gap = self.layout_config.edge_track_gap
        for (lower_row, upper_row), indexes in sorted(
            groups.items(), key=lambda item: (-(item[0][1] - item[0][0]), item[0])
        ):
            indexes.sort(
                key=lambda index: (
                    positions[edges[index].from_][0]
                    + positions[edges[index].from_][2] / 2,
                    positions[edges[index].to][0] + positions[edges[index].to][2] / 2,
                    edges[index].from_,
                )
            )
            first = edges[indexes[0]]
            first_start = positions[first.from_][0] + positions[first.from_][2] / 2
            first_end = positions[first.to][0] + positions[first.to][2] / 2
            preferred = self._safe_center_route_x(
                positions,
                row_tops,
                lower_row,
                upper_row,
                first_start,
                first_end,
            )
            desired_tracks = [
                preferred + (order - (len(indexes) - 1) / 2) * gap
                for order in range(len(indexes))
            ]
            candidates = sorted(
                {
                    float(x)
                    for x in range(
                        self.layout_config.node_route_clearance,
                        self.layout_config.canvas_width
                        - self.layout_config.node_route_clearance
                        + 1,
                        max(4, gap // 2),
                    )
                },
                key=lambda x: abs(x - preferred),
            )
            for index, desired in zip(indexes, desired_tracks):
                ordered_candidates = [desired] + [
                    candidate
                    for candidate in candidates
                    if abs(candidate - desired) > 0.1
                ]
                chosen = next(
                    (
                        candidate
                        for candidate in ordered_candidates
                        if self._center_track_is_clear(
                            candidate,
                            lower_row,
                            upper_row,
                            positions,
                            row_tops,
                            occupied,
                        )
                    ),
                    preferred,
                )
                tracks[index] = chosen
                occupied.append((chosen, lower_row, upper_row))
        return tracks

    def _center_track_is_clear(
        self,
        candidate: float,
        lower_row: int,
        upper_row: int,
        positions: dict[str, tuple[float, float, float, float]],
        row_tops: list[float],
        occupied: list[tuple[float, int, int]],
    ) -> bool:
        clearance = 8
        blockers = [
            box
            for box in positions.values()
            if lower_row < row_tops.index(box[1]) < upper_row
        ]
        if any(
            x - clearance <= candidate <= x + width + clearance
            for x, _y, width, _height in blockers
        ):
            return False
        return all(
            upper_row <= used_lower
            or lower_row >= used_upper
            or abs(candidate - used_x) >= self.layout_config.edge_track_gap
            for used_x, used_lower, used_upper in occupied
        )

    def _edge_route_points(
        self,
        edge: Edge,
        edge_index: int,
        positions: dict[str, tuple[float, float, float, float]],
        row_tops: list[float],
        fan_offsets: tuple[float, float],
        *,
        margin_x: float | None = None,
        gutter_offsets: tuple[float, float] = (0.0, 0.0),
        center_route_x: float | None = None,
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

        source_gutter = (
            self._edge_gutter_y(row_tops, positions, source_row, direction)
            + gutter_offsets[0]
        )
        target_gutter = (
            self._edge_gutter_y(row_tops, positions, target_row, -direction)
            + gutter_offsets[1]
        )
        row_distance = abs(row_delta)
        use_margin = row_distance > 2 or edge.type in {"influence", "risk"}
        if edge.type == "feedback" or edge.direction == EdgeDirection.BACKWARD:
            use_margin = use_margin or row_distance > 0

        if use_margin:
            route_x = (
                margin_x
                if margin_x is not None
                else self._edge_margin_x(edge, edge_index, start[0], end[0])
            )
            return [
                start,
                (start[0], source_gutter),
                (route_x, source_gutter),
                (route_x, target_gutter),
                (end[0], target_gutter),
                end,
            ]

        route_x = (
            center_route_x
            if center_route_x is not None
            else self._safe_center_route_x(
                positions, row_tops, source_row, target_row, start[0], end[0]
            )
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
        *,
        route_points: list[tuple[float, float]] | None = None,
        positions: dict[str, tuple[float, float, float, float]] | None = None,
        occupied_labels: list[tuple[float, float, float, float]] | None = None,
    ) -> str:
        if not text:
            return ""

        canvas_width = 900
        min_x = 24
        right_margin = 12
        max_x = canvas_width - right_margin
        label_text = text
        font_size = 13 + self.layout_config.edge_label_font_size_offset
        estimated_width = self._estimate_text_width(label_text, font_size=font_size)
        raw_label_x = (start_x + end_x) / 2
        label_y = (start_y + end_y) / 2 - 8
        text_anchor = "end" if raw_label_x > 600 else "middle"

        collision_aware = route_points is not None and positions is not None
        label_box: tuple[float, float, float, float] | None = None
        if collision_aware:
            placement = self._edge_label_placement(
                route_points,
                estimated_width,
                font_size,
                positions,
                occupied_labels or [],
            )
            if placement is not None:
                label_x, label_y, text_anchor, label_box = placement
            else:
                collision_aware = False

        if not collision_aware and text_anchor == "end":
            label_x = min(raw_label_x, max_x)
            if label_x - estimated_width < min_x:
                label_x = min(max_x, min_x + estimated_width)
        elif not collision_aware:
            raw_label_x = (source_center_x + target_center_x) / 2
            half_width = estimated_width / 2
            if raw_label_x - half_width < min_x or raw_label_x + half_width > max_x:
                label_y = min(source_center_y, target_center_y) - 10
            label_x = raw_label_x
            if label_x + half_width > max_x:
                label_x = max_x - half_width - 0.1
            elif label_x - half_width < min_x:
                label_x = min_x + half_width

        if label_box is None:
            label_box = self._edge_label_box(
                label_x, label_y, estimated_width, font_size, text_anchor
            )
        if occupied_labels is not None:
            occupied_labels.append(label_box)

        rect_x, rect_top, rect_right, rect_bottom = label_box
        background = (
            f'<rect x="{rect_x:.1f}" y="{rect_top:.1f}" '
            f'width="{rect_right - rect_x:.1f}" height="{rect_bottom - rect_top:.1f}" '
            f'rx="2" fill="{theme.background}" opacity="0.92" />'
            if collision_aware
            else ""
        )

        return (
            f'{background}<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="{text_anchor}" '
            f'fill="{theme.text_secondary}" font-size="{font_size}" opacity="{self.layout_config.edge_label_opacity:g}" '
            f'font-family="ui-sans-serif, system-ui">{escape(label_text)}</text>'
        )

    def _edge_label_placement(
        self,
        points: list[tuple[float, float]],
        text_width: float,
        font_size: int,
        positions: dict[str, tuple[float, float, float, float]],
        occupied_labels: list[tuple[float, float, float, float]],
    ) -> tuple[float, float, str, tuple[float, float, float, float]] | None:
        candidates = []
        for start, end in zip(points, points[1:]):
            if abs(start[1] - end[1]) > 0.1:
                continue
            length = abs(end[0] - start[0])
            if length < text_width + 12:
                continue
            candidates.append((length, (start[0] + end[0]) / 2, start[1] - 8))

        for _length, raw_x, label_y in sorted(candidates, reverse=True):
            half_width = text_width / 2
            label_x = self._clamp(raw_x, 24 + half_width, 888 - half_width)
            box = self._edge_label_box(label_x, label_y, text_width, font_size, "middle")
            if self._box_overlaps_any(box, positions.values(), padding=4):
                continue
            if any(self._bounds_overlap(box, occupied, padding=4) for occupied in occupied_labels):
                continue
            return label_x, label_y, "middle", box
        return None

    def _edge_label_box(
        self,
        label_x: float,
        label_y: float,
        text_width: float,
        font_size: int,
        text_anchor: str,
    ) -> tuple[float, float, float, float]:
        if text_anchor == "end":
            left = label_x - text_width
            right = label_x
        else:
            left = label_x - text_width / 2
            right = label_x + text_width / 2
        return left - 4, label_y - font_size - 2, right + 4, label_y + 3

    def _box_overlaps_any(
        self,
        box: tuple[float, float, float, float],
        others: Iterable[tuple[float, float, float, float]],
        *,
        padding: float,
    ) -> bool:
        return any(self._boxes_overlap(box, other, padding=padding) for other in others)

    def _boxes_overlap(
        self,
        first: tuple[float, float, float, float],
        second: tuple[float, float, float, float],
        *,
        padding: float,
    ) -> bool:
        first_left, first_top, first_right, first_bottom = first
        second_x, second_y, second_width, second_height = second
        second_left = second_x - padding
        second_top = second_y - padding
        second_right = second_x + second_width + padding
        second_bottom = second_y + second_height + padding
        return (
            first_left < second_right
            and first_right > second_left
            and first_top < second_bottom
            and first_bottom > second_top
        )

    def _bounds_overlap(
        self,
        first: tuple[float, float, float, float],
        second: tuple[float, float, float, float],
        *,
        padding: float,
    ) -> bool:
        return (
            first[0] < second[2] + padding
            and first[2] > second[0] - padding
            and first[1] < second[3] + padding
            and first[3] > second[1] - padding
        )

    def _clamp(self, value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    def _render_svg_node(
        self,
        node: Node,
        box: tuple[float, float, float, float],
        ontology: Ontology,
        theme: VisualTheme,
    ) -> str:
        x, y, width, height = box
        visual = ontology.role_visual(node.role)
        fill, border = self._status_colors(node, theme)
        status = node.status.value
        text_color = (
            theme.background
            if status in {"positive", "highlight"}
            else theme.text_primary
        )
        border_width = float(visual["border_width"])
        radius = float(visual["radius"])
        border_dash = visual.get("border_dash") if node.role == "risk" else None
        logger.debug(
            "Resolved node visual: id=%s role=%s status=%s fill=%s border=%s border_dash=%s",
            node.id,
            node.role,
            status,
            fill,
            border,
            border_dash,
        )
        dash = self._stroke_dash_attribute(border_dash)
        glow_filter = ""
        if status == "highlight":
            glow_filter = ' filter="url(#glow_highlight)"'
        elif node.weight == "primary":
            glow_filter = ' filter="url(#glow_primary)"'
        icon_size = 16
        icon_text_gap = 8
        text_x = x + 18 + icon_size + icon_text_gap
        text_width = width - (text_x - x) - 10
        title_lines = self._wrap_text(node.label, max(4, int(text_width / 16)), 2)
        sublabel_lines = self._wrap_text(node.sublabel or "", max(6, int(text_width / 13)), 2)
        title_y = y + 28 if len(title_lines) == 1 else y + 23
        text_parts = []
        for index, line in enumerate(title_lines):
            text_parts.append(
                f'<text x="{text_x:.1f}" y="{title_y + index * 18:.1f}" '
                f'fill="{text_color}" font-size="15" font-weight="{self.layout_config.title_font_weight}" '
                f'font-family="ui-sans-serif, system-ui">{escape(line)}</text>'
            )
        sublabel_y = y + 51 if len(title_lines) == 1 else y + 56
        for index, line in enumerate(sublabel_lines[:1]):
            text_parts.append(
                f'<text x="{text_x:.1f}" y="{sublabel_y + index * 15:.1f}" '
                f'fill="{text_color}" font-size="13" font-weight="400" opacity="{self.layout_config.subtitle_opacity:g}" '
                f'font-family="ui-sans-serif, system-ui">{escape(line)}</text>'
            )

        shape_parts = [
            f'<rect class="node-shape node-shape-outer" x="{x:.1f}" y="{y:.1f}" '
            f'width="{width:.1f}" height="{height:.1f}" rx="{radius:g}" fill="{fill}" '
            f'stroke="{border}" stroke-width="{border_width:g}"{dash}{glow_filter} />'
        ]
        if visual["shape"] == "double_border":
            inner_gap = 2.0
            inner_border_width = border_width - 0.5
            shape_parts.append(
                f'<rect class="node-shape node-shape-inner" x="{x + inner_gap:.1f}" '
                f'y="{y + inner_gap:.1f}" width="{width - inner_gap * 2:.1f}" '
                f'height="{height - inner_gap * 2:.1f}" rx="{max(0.0, radius - inner_gap):g}" '
                f'fill="none" stroke="{border}" stroke-width="{inner_border_width:g}"{dash} />'
            )
        accent_bar = ""
        if bool(visual["accent_bar"]):
            bar_gradient = self._accent_bar_gradient(status)
            accent_radius = min(radius, height / 2)
            accent_bar = (
                f'<path class="prism-node-accent" '
                f'd="M {x + accent_radius:.1f} {y:.1f} '
                f'Q {x:.1f} {y:.1f} {x:.1f} {y + accent_radius:.1f} '
                f'V {y + height - accent_radius:.1f} '
                f'Q {x:.1f} {y + height:.1f} {x + accent_radius:.1f} {y + height:.1f}" '
                f'fill="none" stroke="url(#{bar_gradient})" '
                f'stroke-width="{theme.node_accent_bar_width}" stroke-linecap="round" />'
            )
        icon_color = text_color if status in {"positive", "highlight"} else border
        icon = self._render_svg_icon(
            node.role,
            x,
            y,
            height,
            icon_color,
            bool(visual["accent_bar"]),
            theme,
        )
        return (
            f'<g class="node" data-node-id="{escape(node.id)}" '
            f'data-role="{escape(node.role)}" data-status="{status}">'
            f'{"".join(shape_parts)}'
            f'{accent_bar}'
            f'{icon}'
            f'{"".join(text_parts)}'
            "</g>"
        )

    def _render_svg_icon(
        self,
        role: str,
        x: float,
        y: float,
        height: float,
        border: str,
        accent_bar: bool,
        theme: VisualTheme,
    ) -> str:
        path = ROLE_ICON_PATHS.get(role)
        if path is None:
            return ""
        icon_size = 16
        icon_x = x + 10
        if accent_bar:
            icon_x += theme.node_accent_bar_width + 8
        icon_y = y + height / 2 - icon_size / 2
        return (
            f'<rect class="prism-node-icon-badge" x="{icon_x - 6:.1f}" y="{icon_y - 6:.1f}" '
            f'width="{icon_size + 12}" height="{icon_size + 12}" rx="7" fill="{border}" '
            f'opacity="{theme.icon_badge_opacity:g}" />'
            f'<svg class="prism-node-icon" x="{icon_x:.1f}" y="{icon_y:.1f}" '
            f'width="{icon_size}" height="{icon_size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{border}" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{path}</svg>'
        )

    def _status_colors(self, node: Node, theme: VisualTheme) -> tuple[str, str]:
        if node.status.value == "positive":
            return "url(#grad_positive)", theme.accent_result
        if node.status.value == "highlight":
            return "url(#grad_highlight)", theme.accent_result
        if node.status.value == "negative":
            return theme.surface, theme.accent_risk
        return "url(#grad_neutral)", theme.accent_primary

    def _accent_bar_gradient(self, status: str) -> str:
        if status in {"positive", "highlight"}:
            return "grad_bar_result"
        if status == "negative":
            return "grad_bar_risk"
        return "grad_bar_primary"

    def _stroke_dash_attribute(self, stroke_dash: object) -> str:
        if stroke_dash is None:
            return ""
        return f' stroke-dasharray="{escape(str(stroke_dash))}"'

    def _marker_attribute(self, arrow: str) -> str:
        if arrow == "none":
            return ""
        return f' marker-end="url(#{escape(arrow)})"'

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
