from prism.core.schema import PrismDoc
from prism.ontologies.loader import load_ontology
from prism.render.mermaid import MermaidRenderer


def test_mermaid_renderer_includes_styles_and_loops() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    ontology = load_ontology("financial")
    html = MermaidRenderer().render(prism, ontology)

    assert "flowchart LR" in html
    assert "美国财政部" in html
    assert "fill:#DBEAFE" in html
    assert "stroke:#16A34A" in html
    assert "Feedback loops" in html
    assert "利率-需求反馈" in html


def test_mermaid_source_keeps_node_ids() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    ontology = load_ontology("financial")
    mermaid = MermaidRenderer().to_mermaid(prism, ontology)

    assert 'treasury["美国财政部' in mermaid
    assert "class treasury" in mermaid
