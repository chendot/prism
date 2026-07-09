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
- `nodes[].weight` 只在 schema 中声明为字符串，合法值由 ontology 的 `weights` 块校验，默认 `secondary`。
- `edges[].type` 只在 schema 中声明为字符串，合法值由 ontology 校验。
- `edges[].from` 和 `edges[].to` 必须引用已有 node id。
- `loops[]` 用于保留反馈循环，即使某些 renderer 不能原生表达。

结构定义在 `src/prism/core/schema.py`，跨字段和 ontology 校验在 `src/prism/core/validator.py`。

## Ontology

每个领域一个 YAML 文件：

```text
src/prism/ontologies/<name>.yaml
```

必须包含：

```yaml
name: str
description: str
roles: {}
edge_types: {}
weights: {}
perspectives: []
```

`roles`、`edge_types` 和 `weights` 是领域受控词表，同时提供 renderer 可使用的视觉映射。核心 schema 不允许写死任何领域枚举。

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

## meta 字段扩展

`meta` 新增两个可选字段：

```yaml
meta:
  title: "稳定币真正挑战的是利息分配权"
  ontology: "crypto"
  template: "value_flow"       # 可选，指定解释结构模板
  visual_theme: "warm_layered" # 可选，指定视觉主题，默认 warm_layered
  target_format: "x_card"      # 可选，指定发布平台策略
```

`template` 字段由 LLMCompressor 在 Step 1 判断后写入，Compressor Step 2 读取它来约束生成结构。Renderer 不读 `template`。

`target_format` 字段由 Renderer 读取，决定信息密度和 layout 策略（见下方 Platform Strategy）。

---

## Template（解释结构模板）

模板不是视觉模板，而是"解释结构先验"——约束 Compressor 应该生成什么类型的节点和边关系。

路径：`src/prism/templates/<name>.yaml`

当前三个模板（Phase B 前不扩展）：

### value_flow

适用主题：利益分配、资金流向、权力转移、DeFi / 稳定币机制。

结构约束：
- 必须有 `participant` 类角色节点（参与方）
- 必须有 `flow` 类型边（资金 / 价值流动方向）
- 必须有至少一个 `benefit` 或 `cost` 节点（收益归属 / 成本承担）
- 推荐节点数：8–14

### causal_chain

适用主题：风险传导、市场周期、政策影响、AI 能力迁移。

结构约束：
- 节点按因果顺序排列，有明确的 `trigger` 起点节点
- 边类型以 `causes` / `amplifies` / `suppresses` 为主
- 必须有至少一个反馈 loop（自我强化或自我抑制）
- 推荐节点数：8–16

### layer_stack

适用主题：系统架构、能力分层、软件工程、内容生产流程。

结构约束：
- 节点按层级组织，有明确的 `layer` 属性
- 边以 `depends_on` / `abstracts` / `enables` 为主
- 同层节点不应有直接边（层内关系通过 ontology 的 `group` 字段描述）
- 推荐节点数：6–12

---

## Platform Strategy（平台发布策略）

`target_format` 不是尺寸参数，而是叙事密度策略。同一份 `prism.yaml` 在不同平台选择不同的节点子集和 layout。

### x_card

```text
叙事密度：低
核心要求：
  - 一个核心判断（来自 meta.title 或 diagram.thesis）
  - 一个视觉中心节点
  - 最多 6 个节点（Renderer 自动筛选 weight 最高的节点）
  - 标签文字极简，边 label 尽量省略
  - 优化转发：标题字号大，留白多
输出尺寸：1200×675 px
```

### xiaohongshu_card

```text
叙事密度：中
核心要求：
  - 单图，完整结构可见
  - 节点数量不限（但 Renderer 控制字号保证可读）
  - 保留所有 edge label
  - 左上角标题 + 右下角水印
输出尺寸：1080×1350 px
```

### xiaohongshu_carousel（Phase C 实现）

```text
叙事密度：高，分页展开
Page 1（hook）：meta.title + 最核心的 3 个节点
Page 2（mechanism）：完整结构图
Page 3（implication）：loops + 结论文字
输出尺寸：每页 1080×1350 px
```

### wechat_cover（Phase C 实现）

```text
叙事密度：极低
核心要求：标题视觉冲击优先，结构图简化到 3–5 节点
输出尺寸：900×383 px
```

---

## Visual Theme（视觉主题）

路径：`src/prism/themes/<name>.yaml`

当前锁定主题：`warm_layered`（不允许在未经人工确认的情况下修改）

```yaml
name: warm_layered
background: "#1c1612"
surface: "#221a0e"
surface_border: "#4a3318"
accent_primary: "#c9a96e"    # 琥珀金 — 政策层、主流向
accent_secondary: "#9b7a40"  # 暗金 — 中间传导层
accent_danger: "#e07b5a"     # 铜红 — 压力节点、输出层、反馈循环
text_primary: "#e8d5b0"
text_secondary: "#7a6040"
node_accent_bar_width: 3     # px，节点左侧彩色竖条
watermark: "chendot · prism"
watermark_color: "#302618"
```

Renderer 从 `meta.visual_theme` 读取主题名称，加载对应 YAML，不硬编码任何 hex 值。
