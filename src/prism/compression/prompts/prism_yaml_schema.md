prism.yaml 顶层字段固定为：

```yaml
meta: {}
diagram: {}
nodes: []
edges: []
loops: []
render: {}
```

meta 必填字段：
- title: str
- topic: str
- ontology: str
- template: value_flow | causal_chain | layer_stack | hierarchical_framework
- visual_theme: warm_layered
- audience: beginner | intermediate | expert
- language: zh | en | bilingual
- tags: list[str]

diagram 必填字段：
- type: flow | system | cycle | layer | comparison | timeline | decision_tree
- direction: TD | LR | BT | RL

diagram 可选字段：
- thesis: 一句核心判断；必须与给定 GraphPlan 的 thesis 保持一致
- groups: 层级框架容器列表；每项包含 id、title、kind、可选 parent 和 order
- hierarchy_view: overview | detail；hierarchical_framework 必填
- abstraction_level: 当前图所有节点共同的抽象海拔；hierarchical_framework 必填
- focus_group: 当前图的焦点 group id；hierarchical_framework 必填
- omitted_details: 主动省略、应进入后续子图的 1 到 5 个细节；hierarchical_framework 必填

nodes 每项必填：
- id: lowercase snake_case，唯一
- label: 短标签
- role: 必须来自 ontology.roles

nodes 可选：
- sublabel: 一句话解释
- layer: int，用于层级和传导顺序
- group: diagram.groups 中的合法 group id；hierarchical_framework 必填
- weight: ontology.weights 中的合法档位，默认 secondary；通常使用 primary、secondary、muted

edges 每项必填：
- from: 已存在 node id
- to: 已存在 node id
- type: 必须来自 ontology.edge_types
- direction: forward | backward | bidirectional

edges 可选：
- label: 短关系说明

loops 每项：
- id: lowercase snake_case
- label: 短标签
- nodes: 已存在 node id 列表
- polarity: positive | negative

render：
- style: default
- show_loops: true
- highlight_nodes: 已存在 node id 列表
- highlight_edges: []
- renderer: mermaid
