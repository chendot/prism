# Prism Spec

本文档只定义 Prism 必须遵守的架构和数据契约；使用方法放在 `README.md`，开发协作规则放在 `AGENTS.md`。

## 核心原则

`prism.yaml` 是 Prism 的唯一核心资产。

```text
复杂主题 -> prism.yaml -> deterministic renderer -> 图解
```

图片、HTML、SVG、D3 页面、Mermaid 代码都是派生产物，不应成为系统间传递的 canonical 格式。

## 层边界

Prism 分为三个物理隔离层：

| Layer | 输入 | 输出 | 约束 |
| --- | --- | --- | --- |
| Research | topic + ontology | `findings.json` | 可选，可跳过 |
| Compression | topic + optional findings + ontology | `prism.yaml` | 输出必须通过 validator |
| Render | validated `prism.yaml` + ontology | html/svg/d3/etc. | 不读取研究/压缩内部状态 |

层间通信只能通过文件或显式数据对象完成，不共享隐藏状态。

## prism.yaml

顶层字段固定为：

```yaml
meta: {}
diagram: {}
nodes: []
edges: []
loops: []
render: {}
```

关键约束：

- `meta.ontology` 指定运行时 ontology。
- `nodes[].id` 必须是唯一的 lowercase snake_case。
- `nodes[].role` 只在 schema 中声明为字符串，合法值由 ontology 校验。
- `edges[].type` 只在 schema 中声明为字符串，合法值由 ontology 校验。
- `edges[].from` 和 `edges[].to` 必须引用已有 node id。
- `loops[]` 用于保留反馈循环，即使某些 renderer 不能原生表达。

结构定义在 `prism/core/schema.py`，跨字段和 ontology 校验在 `prism/core/validator.py`。

## Ontology

每个领域一个 YAML 文件：

```text
prism/ontologies/<name>.yaml
```

必须包含：

```yaml
name: str
description: str
roles: {}
edge_types: {}
perspectives: []
```

`roles` 和 `edge_types` 是领域受控词表，同时提供 renderer 可使用的视觉映射。核心 schema 不允许写死任何领域枚举。

## 扩展接口

新增 renderer：

```python
class Renderer(ABC):
    def render(self, prism: PrismDoc, ontology: Ontology) -> str: ...
```

新增 compressor：

```python
class Compressor(ABC):
    def compress(self, topic: str, findings: dict | None, ontology: Ontology) -> PrismDoc: ...
```

新增 research engine：

```python
class ResearchEngine(ABC):
    def research(self, topic: str, ontology: Ontology) -> dict: ...
```

所有实现都必须保持所在层的输入/输出边界。
