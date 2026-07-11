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

默认 CLI 生成物统一写入 `outputs/`：`compress` 生成 `prism.yaml`，`research` 生成 `findings.json`，`render` 按输入 YAML 的文件名生成 HTML，`run` 生成完整的三项产物。`examples/` 只存放可提交的成熟 YAML 模板和样例，不作为默认输出目录。

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
- `diagram.thesis` 可选。一句核心判断，供平台策略和读者快速识别图解的叙事中心。
- `nodes[].id` 必须是唯一的 lowercase snake_case。
- `nodes[].role` 只在 schema 中声明为字符串，合法值由 ontology 校验。
- `nodes[].weight` 只在 schema 中声明为字符串，合法值由 ontology 的 `weights` 块校验，默认 `secondary`。
- `nodes[].lane` 可选字段，字符串。仅在 `render.template == "parallel_lanes"` 时生效，用于将节点分配到某条并行泳道；其他 template 忽略该字段。合法值由 `render.lanes[].id` 校验（见下方 render 字段约束）。
- `edges[].type` 只在 schema 中声明为字符串，合法值由 ontology 校验。
- `edges[].from` 和 `edges[].to` 必须引用已有 node id。
- `loops[]` 用于保留反馈循环，即使某些 renderer 不能原生表达。
- `render.lanes` 可选字段，仅 `parallel_lanes` template 使用，结构为 `[{id, title, order}]`，定义泳道的数量、标题和排列顺序。其他 template 忽略该字段。

结构定义在 `src/prism/core/schema.py`，跨字段和 ontology 校验在 `src/prism/core/validator.py`。

**parallel_lanes 专属校验规则**（在 `core/validator.py` 中，仅当 `render.template == "parallel_lanes"` 时触发）：

- 每个 node 必须有非空 `lane` 值。
- 每个 node 的 `lane` 值必须出现在 `render.lanes[].id` 中；否则校验失败。
- `render.lanes` 至少包含 2 个泳道。
- 该规则不影响其他 template 的校验路径，属于 additive 检查。

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

### 内置 HTML Renderer（dagre）

当前内置 HTML renderer 的生产路径使用本地 vendored 的 `@dagrejs/dagre` 计算图布局：

- Python 负责读取并校验 `prism.yaml`，将 PrismDoc、ontology 视觉字段、visual theme、icons 与 `LayoutConfig` 序列化进 HTML。
- HTML 内嵌 dagre runtime 和 Prism SVG 绘制脚本，不依赖 CDN 或网络；输出文件可离线打开。
- `LayoutConfig` 是节点尺寸、间距、边距、字号与透明度的唯一配置来源；浏览器端只消费该 payload，不维护第二份布局常量。
- 浏览器端 dagre 负责节点与普通图层级布局；SVG 绘制继续消费 ontology 的 role/edge visual 字段和 theme 的颜色字段。
- `parallel_lanes` 使用 dagre compound graph（`setParent`）组织泳道节点，并按 `render.lanes[].order` 固定泳道从左到右的顺序。
- 泳道内部主流程使用正交直线；入口分流和终点汇聚使用平滑贝塞尔曲线；feedback 使用外侧虚线路由，避免参与主结构的 rank 计算。
- 生成页面允许纵向滚动、禁止横向溢出，避免高图在视口中被裁切。

新增 compressor：

```python
class Compressor(ABC):
    def compress(self, topic: str, findings: dict | None, ontology: Ontology) -> PrismDoc: ...
```

### LLMCompressor 内部工作流

`LLMCompressor` 的实现保持在 Compression 层内，不调用 Research。它按以下三步执行：

1. **Story Planning**：仅根据 `topic` 生成内存中的 `GraphPlan`，包含 `thesis`、`template`、选择理由和按叙事顺序排列的 3–6 个 `main_path` 概念。template 的选择以该计划为准，不再由关键词规则单独决定。
2. **Plan display**：在终端打印 GraphPlan 的 thesis、template（含理由）和 main path，供非阻断式人工扫读；GraphPlan 不落盘，不是 Prism 的 canonical 资产。
3. **YAML realization**：以锁定的 GraphPlan、topic、可选 findings 和 ontology 生成 `prism.yaml`。实现会将 `GraphPlan.thesis` 写入 `diagram.thesis`，确保计划与最终文档一致；随后沿用 validator 的最多两次修复重试。

本地 provider 调用默认通过独立子进程执行：Story Planning 与 YAML realization 各一次。设置 `PRISM_LLM_DEBUG=1` 时，Compressor 会向 stderr 输出阶段边界、命令、返回码以及 stdout/stderr 的长度和预览，供排查 provider 启动或输出问题。

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

`template` 字段由 LLMCompressor 的 Story Planning 选定后写入。YAML realization 读取锁定的 GraphPlan 来约束生成结构；Renderer 不读 `template`。

`target_format` 是 Renderer 的平台密度策略契约（见下方 Platform Strategy）。当前 dagre renderer 先保留完整结构，尚未实现按 `target_format` 筛选节点或切换平台尺寸的分支。

---

## Template（解释结构模板）

模板不是视觉模板，而是"解释结构先验"——约束 Compressor 应该生成什么类型的节点和边关系。

路径：`src/prism/templates/<name>.yaml`

当前四个模板（Phase B 前不再扩展）：

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

### parallel_lanes

适用主题：多条并行价值路径的对比结构——同一入口分流出多种机制，各自独立产生收益并流向不同归属方（例如：稳定币多种生息模式对比、多种融资渠道对比、多路径风险敞口对比）。当主题的核心叙事是"几种做法/几条路径的横向对比"而非单一链条或网络时，优先选择此模板而非 `value_flow`。

结构约束：
- 每个节点必须有 `lane` 属性，标明所属并行路径
- 必须有一个共享的入口节点（`entry` 角色），其出边分别指向各条泳道的第一个节点
- 每条泳道内部的边应构成一条独立的纵向链条，泳道内节点数建议 3–5
- 允许存在跨泳道边，但仅限两类：入口分流（entry fan-out）与终点汇聚（多条泳道流向同一个下游节点，如"系统性风险"）；不允许在泳道中段随意添加跨泳道边
- 泳道数量建议 2–4 条；超过 4 条应考虑拆分为多图或改用 `value_flow`
- 推荐节点总数：10–18（含入口和汇聚节点）
- `render.lanes` 必须与实际使用的 `lane` 值一一对应，顺序决定视觉排列顺序（左到右）

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

**parallel_lanes 与 target_format 的关系**：`x_card`（最多 6 节点）与 `parallel_lanes`（推荐 10–18 节点）在密度上冲突，Renderer 遇到该组合时应回退为按 weight 筛选后合并为单列展示，不强行保留泳道结构。`xiaohongshu_card` 和 `xiaohongshu_carousel` 的 Page 2 是 `parallel_lanes` 的主要使用场景。

---

## Visual Theme（视觉主题）

路径：`src/prism/themes/<name>.yaml`

当前锁定主题：`warm_layered`（不允许在未经人工确认的情况下修改）

```yaml
name: warm_layered
background: "#1f1814"
surface: "#2b211b"
surface_border: "#6f522e"
accent_primary: "#e5bc6a"    # 琥珀金 — 主流程与普通描边
accent_secondary: "#c9934f"  # 暗金 — 跨泳道与次级关系
accent_result: "#ef805d"     # 珊瑚橙 — 正向结果、高亮、核心判断
accent_risk: "#ff8b68"       # 浅珊瑚 — 风险、负向节点的边框
text_primary: "#f7e6c4"
text_secondary: "#c6a878"
node_accent_bar_width: 3     # px，节点左侧彩色竖条
watermark: "chendot · prism"
watermark_color: "#6a5135"
```

Renderer 从 `meta.visual_theme` 读取主题名称，加载对应 YAML，不硬编码任何 hex 值。

`parallel_lanes` 的泳道标题文字沿用本主题的 `text_secondary`；泳道框与分隔视觉使用 `accent_secondary`、60% opacity、1.5px stroke-width。入口分流与底部汇聚使用曲线表达共享入口/终点，颜色与线型仍由对应 edge type 的 ontology visual 字段决定；跨泳道 feedback 使用 `accent_secondary` 的外侧虚线，不新增主题色值。

## Visual Grammar（视觉语法）

节点 role、edge type、status 到具体视觉样式（形状/描边/颜色/缩放）的映射规则定义在 `VISUAL_GRAMMAR.md`。

核心约束：
- `role` 只决定 shape / border / radius / scale，不决定颜色
- `status` 只决定颜色，与 `role` 正交
- Renderer 不得硬编码任何一条映射规则，必须从 ontology 的视觉字段读取

`VISUAL_GRAMMAR.md` 达成共识后视为定版，后续修改需人工确认（约束级别与 Visual Theme 一致）。
