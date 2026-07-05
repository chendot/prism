"""Mermaid renderer for Prism Layer 3."""

from __future__ import annotations

from html import escape
from itertools import count

from prism.core.models import Ontology
from prism.core.schema import EdgeDirection, PrismDoc
from prism.core.validator import validate_prism_doc
from prism.render.base import Renderer


class MermaidRenderer(Renderer):
    """Render a validated Prism document to self-contained Mermaid HTML."""

    def render(self, prism: PrismDoc, ontology: Ontology) -> str:
        """Return an HTML document containing a Mermaid diagram."""

        validate_prism_doc(prism, ontology)
        mermaid = self.to_mermaid(prism, ontology)
        loops_html = self._render_loops(prism) if prism.render.show_loops else ""
        subtitle = f"<p>{escape(prism.meta.subtitle)}</p>" if prism.meta.subtitle else ""

        return f"""<!doctype html>
<html lang="{escape(prism.meta.language.value)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(prism.meta.title)}</title>
  <script type="module">
    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
    mermaid.initialize({{ startOnLoad: true, theme: "base" }});
  </script>
  <style>
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #111827;
      background: #ffffff;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      line-height: 1.2;
    }}
    p {{
      margin: 0 0 24px;
      color: #4B5563;
    }}
    .mermaid {{
      border: 1px solid #E5E7EB;
      border-radius: 8px;
      padding: 20px;
      overflow-x: auto;
      background: #FAFAFA;
    }}
    .loops {{
      margin-top: 24px;
      border-top: 1px solid #E5E7EB;
      padding-top: 16px;
    }}
    .loops h2 {{
      margin: 0 0 8px;
      font-size: 18px;
    }}
    .loops li {{
      margin: 6px 0;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{escape(prism.meta.title)}</h1>
    {subtitle}
    <pre class="mermaid">
{escape(mermaid)}
    </pre>
    {loops_html}
  </main>
</body>
</html>
"""

    def to_mermaid(self, prism: PrismDoc, ontology: Ontology) -> str:
        """Render only Mermaid source for tests and alternate delivery."""

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
            color = style.get("color", "#6B7280")
            stroke_style = "stroke-dasharray: 5 5" if style.get("style") == "dashed" else ""
            style_bits = [f"stroke:{color}"]
            if stroke_style:
                style_bits.append(stroke_style)
            lines.append(f"    linkStyle {edge_index} {','.join(style_bits)}")

        for role, class_name in class_names.items():
            style = ontology.role_style(role)
            fill = style.get("fill", "#FFFFFF")
            stroke = style.get("stroke", "#9CA3AF")
            lines.append(f"    classDef {class_name} fill:{fill},stroke:{stroke},stroke-width:1.5px")

        if prism.render.highlight_nodes:
            for node_id in prism.render.highlight_nodes:
                lines.append(f"    style {node_id} stroke:#111827,stroke-width:3px")

        return "\n".join(lines)

    def _render_loops(self, prism: PrismDoc) -> str:
        """Render loop metadata Mermaid cannot reliably express."""

        if not prism.loops:
            return ""
        items = []
        for loop in prism.loops:
            nodes = " -> ".join(escape(node_id) for node_id in loop.nodes)
            items.append(
                f"<li><strong>{escape(loop.label)}</strong> "
                f"({escape(loop.polarity.value)}): {nodes}</li>"
            )
        return f'<section class="loops"><h2>Feedback loops</h2><ul>{"".join(items)}</ul></section>'

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
