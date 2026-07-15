"""Pydantic contract for prism.yaml documents.

The schema is intentionally domain-neutral. Role names and edge type names are
validated later against the runtime ontology selected by ``meta.ontology``.
"""

from __future__ import annotations

from enum import StrEnum

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Audience(StrEnum):
    """Supported audience levels for explanation design."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class Language(StrEnum):
    """Supported output languages."""

    ZH = "zh"
    EN = "en"
    BILINGUAL = "bilingual"


class DiagramType(StrEnum):
    """High-level diagram families understood by Prism."""

    FLOW = "flow"
    SYSTEM = "system"
    CYCLE = "cycle"
    LAYER = "layer"
    COMPARISON = "comparison"
    TIMELINE = "timeline"
    DECISION_TREE = "decision_tree"


class HierarchyView(StrEnum):
    """Cognitive scope for a hierarchical framework diagram."""

    OVERVIEW = "overview"
    DETAIL = "detail"


class Direction(StrEnum):
    """Diagram layout direction."""

    TD = "TD"
    LR = "LR"
    BT = "BT"
    RL = "RL"


class EdgeDirection(StrEnum):
    """Logical direction of a relationship."""

    FORWARD = "forward"
    BACKWARD = "backward"
    BIDIRECTIONAL = "bidirectional"


class NodeStatus(StrEnum):
    """Semantic node status used by themes to resolve colors."""

    NEUTRAL = "neutral"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    HIGHLIGHT = "highlight"


class LoopPolarity(StrEnum):
    """Feedback loop polarity."""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class RendererName(StrEnum):
    """Built-in renderer identifiers."""

    MERMAID = "mermaid"
    SVG = "svg"
    D3 = "d3"


class PrismBaseModel(BaseModel):
    """Base model with strict-ish config for the Prism contract."""

    model_config = ConfigDict(extra="forbid")


class Meta(PrismBaseModel):
    """Document metadata and ontology selection."""

    title: str
    subtitle: str | None = None
    topic: str
    ontology: str
    template: str | None = None
    visual_theme: str | None = "warm_layered"
    target_format: str | None = None
    audience: Audience
    language: Language
    tags: list[str] = Field(default_factory=list)


class DiagramGroup(PrismBaseModel):
    """A semantic container used by hierarchical framework diagrams."""

    id: str
    title: str
    kind: str = "group"
    parent: str | None = None
    order: int = 0

    @field_validator("id")
    @classmethod
    def validate_snake_case_id(cls, value: str) -> str:
        if not value.replace("_", "").isalnum() or value.lower() != value:
            raise ValueError("group id must be lowercase snake_case")
        if value.startswith("_") or value.endswith("_") or "__" in value:
            raise ValueError("group id must be lowercase snake_case")
        return value


class Diagram(PrismBaseModel):
    """Diagram-level rendering intent."""

    type: DiagramType
    direction: Direction
    thesis: str | None = None
    groups: list[DiagramGroup] = Field(default_factory=list)
    hierarchy_view: HierarchyView | None = None
    abstraction_level: str | None = None
    focus_group: str | None = None
    omitted_details: list[str] = Field(default_factory=list)


class Node(PrismBaseModel):
    """A domain entity in the visual explanation graph."""

    id: str
    label: str
    sublabel: str | None = None
    role: str
    layer: int | None = None
    lane: str | None = None
    group: str | None = None
    weight: str = "secondary"
    status: NodeStatus = NodeStatus.NEUTRAL

    @field_validator("id")
    @classmethod
    def validate_snake_case_id(cls, value: str) -> str:
        """Keep node ids portable across renderers and version control diffs."""

        if not value.replace("_", "").isalnum() or value.lower() != value:
            raise ValueError("node id must be lowercase snake_case")
        if value.startswith("_") or value.endswith("_") or "__" in value:
            raise ValueError("node id must be lowercase snake_case")
        return value


class Edge(PrismBaseModel):
    """A typed relationship between two nodes."""

    from_: str = Field(alias="from")
    to: str
    label: str | None = None
    type: str
    direction: EdgeDirection


class Loop(PrismBaseModel):
    """A feedback loop preserved even when a renderer cannot draw it natively."""

    id: str
    label: str
    nodes: list[str]
    polarity: LoopPolarity


class RenderLane(PrismBaseModel):
    """A visual lane definition for parallel-lane render templates."""

    id: str
    title: str
    order: int


class RenderConfig(PrismBaseModel):
    """Renderer preferences carried by the portable document."""

    template: str | None = None
    style: str = "default"
    show_loops: bool = True
    lanes: list[RenderLane] = Field(default_factory=list)
    highlight_nodes: list[str] = Field(default_factory=list)
    highlight_edges: list[str] = Field(default_factory=list)
    renderer: RendererName = RendererName.MERMAID


class PrismDoc(PrismBaseModel):
    """Complete prism.yaml document passed from Layer 2 to Layer 3."""

    meta: Meta
    diagram: Diagram
    nodes: list[Node]
    edges: list[Edge]
    loops: list[Loop] = Field(default_factory=list)
    render: RenderConfig = Field(default_factory=RenderConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "PrismDoc":
        """Load and structurally validate a prism.yaml file."""

        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return cls.model_validate(data)

    def to_yaml(self) -> str:
        """Serialize a Prism document to stable YAML."""

        data = self.model_dump(mode="json", by_alias=True)
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
