"""D3 renderer placeholder for Prism Layer 3."""

from __future__ import annotations

from prism.core.models import Ontology
from prism.core.schema import PrismDoc
from prism.render.base import Renderer


class D3Renderer(Renderer):
    """Future interactive D3 renderer."""

    def render(self, prism: PrismDoc, ontology: Ontology) -> str:
        """Render Prism to an interactive D3 artifact.

        TODO: Implement JSON export plus a browser runtime for D3.
        """

        raise NotImplementedError("D3 renderer is planned but not implemented yet.")
