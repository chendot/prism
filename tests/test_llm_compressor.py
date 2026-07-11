from prism.compression.llm_compressor import LLMCompressor
from prism.ontologies.loader import load_ontology


class FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return next(self.responses)


def test_compressor_uses_graph_plan_and_exposes_it(capsys) -> None:
    graph_plan = """\
thesis: 加息通过融资成本与资产价格共同压低需求。
template: causal_chain
reason: 主题核心是政策冲击的多步传导。
main_path:
  - 政策利率上调
  - 短端利率上升
  - 融资成本提高
  - 总需求放缓
  - 通胀压力回落
"""
    prism_yaml = """\
meta:
  title: 美联储加息传导
  audience: beginner
  language: zh
  tags: [fed]
diagram:
  type: flow
  direction: LR
  thesis: 模型写错的判断。
nodes:
  - id: policy_rate
    label: 政策利率上调
    role: regulator
  - id: short_rates
    label: 短端利率上升
    role: market
  - id: borrowing_cost
    label: 融资成本提高
    role: risk
  - id: demand
    label: 总需求放缓
    role: market
  - id: inflation
    label: 通胀压力回落
    role: risk
edges:
  - from: policy_rate
    to: short_rates
    type: causal
    direction: forward
  - from: short_rates
    to: borrowing_cost
    type: causal
    direction: forward
  - from: borrowing_cost
    to: demand
    type: causal
    direction: forward
  - from: demand
    to: inflation
    type: causal
    direction: forward
loops: []
render:
  renderer: mermaid
"""
    compressor = LLMCompressor()
    fake_client = FakeClient([graph_plan, prism_yaml])
    compressor.client = fake_client

    prism = compressor.compress("美联储加息如何传导", None, load_ontology("financial"))

    output = capsys.readouterr().out
    assert "GraphPlan" in output
    assert "template: causal_chain" in output
    assert "政策利率上调 → 短端利率上升" in output
    assert prism.meta.template == "causal_chain"
    assert prism.diagram.thesis == "加息通过融资成本与资产价格共同压低需求。"
    assert "锁定的 GraphPlan" in fake_client.prompts[1]
