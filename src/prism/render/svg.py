"""SVG renderer placeholder for Prism Layer 3."""

from __future__ import annotations

from prism.core.models import Ontology
from prism.core.schema import PrismDoc
from prism.render.base import Renderer


class SvgRenderer(Renderer):
    """Future deterministic SVG renderer."""

    def render(self, prism: PrismDoc, ontology: Ontology) -> str:
        """Render Prism to SVG.

        TODO: Implement layout and SVG generation without relying on Mermaid.
        """

        raise NotImplementedError("SVG renderer is planned but not implemented yet.")
