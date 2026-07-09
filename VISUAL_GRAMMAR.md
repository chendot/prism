# Visual Grammar (草案 v0.2)

v0.2 变更（相对 v0.1）：
- 拆分 role 与颜色的耦合：role 只决定 shape/border/radius/scale；颜色改由新增的正交字段 `status` 决定
- Lane 背景改为 role 驱动，废弃 v0.1 中"按泳道内序号推断层级"的方案
- Role 词表本身暂不做 Actor/Object/Process 式的大重构——保留现有 8 个 role，待跑满本次发布 + 至少 2 个新领域主题后再评估是否需要拆分 subtype 层。理由：当前尚无跨领域数据支撑重构方向，过早抽象等于为假设的通用性预付成本，与 SPEC.md "compress, don't expand" 原则冲突。

本文档定义 Prism 的视觉语法契约：节点角色、边类型、权重如何映射到具体的视觉样式。目标是让读者不读文字，仅凭形状/颜色/线型就能判断节点和关系的语义类型。

一旦确认，本文档的映射表将写入对应 ontology 文件的 `roles` / `edge_types` 块（视觉字段），并成为 renderer 消费的 canonical 依据。**不在 renderer 里硬编码任何一条映射规则** —— renderer 只负责"读字段、按规则画"，规则本身全部来自 ontology + theme。

---

## 1. Role → Shape 映射（v0.2：仅形状/描边/缩放，不含颜色）

角色（role）是节点在叙事结构中的功能位置，不是节点的具体内容。跨领域（financial / tech / policy）应尽量复用同一套角色词表，减少每个 ontology 重新发明形状语言。

**颜色不在这张表里** —— role 只回答"这是什么形状的节点"，颜色由第 1.5 节的 `status` 字段独立决定。这是 v0.2 相对 v0.1 最核心的修正：v0.1 把 benefit/thesis 直接绑定橙色，导致同一 role 在不同语境下需要不同颜色时（例如"收益"变成"负收益"）无法表达。

| Role | 含义 | Shape | 视觉细节（形状/描边/缩放，无颜色） | 出现示例 |
|---|---|---|---|---|
| `entry` | 叙事起点 / 用户 / 触发者 | `round` | 圆角 16px（远大于普通节点的 8px），无 accent bar | 稳定币用户、监管约束(trigger) |
| `asset` | 资产、资源、底层存量 | `rect` | 标准矩形，8px 圆角（当前默认样式） | 短期国债、超额抵押品、法币储备 |
| `protocol` | 机构 / 协议 / 中介角色 | `double_border` | 双描边（外描边 1.5px + 内描边间隔 2px），矩形 | 抵押协议、收益发行方、法币发行方 |
| `flow_step` | 中间传导环节，无特殊语义 | `rect` | 标准矩形（同 asset） | 借款人、永续空头、Delta中性仓位 |
| `benefit` | 收益产出 | `rect` | 标准矩形；描边 1.5px（比默认略粗，强调"这是结果类节点"） | 储备收益、借贷利息、资金费收益 |
| `owner` | 收益最终归属方 | `rect` | 标准矩形，描边 2px | 发行方留存、存入者分成、对冲运营方 |
| `thesis` | 全图核心结论 / 最终问题 | `rect` | 比普通节点宽 20%、高 15%；描边 2px；每图建议 0–1 个（软校验，不强制） | 利息分配权 |
| `risk` | 风险 / 负反馈 | `rect` | 描边 2px，虚线描边以区分"风险"与"结果"两类强调节点 | 系统性风险、清算罚款 |

---

## 1.5 Status → Color 映射（新增，v0.2 核心改动）

`status` 是与 `role` 正交的字段，只回答"这个节点当前是正向、负向，还是需要高亮"，不涉及形状。同一个 role 在不同图里可以有不同 status。

| Status | 含义 | 颜色 |
|---|---|---|
| `neutral`（默认） | 常规节点，无特殊强调 | 深棕 `surface`（主题默认背景色） |
| `positive` | 正向结果 / 收益 / 增长 | 珊瑚橙 `accent_danger`（沿用现有色值，语义上代表"值得注意的产出"，命名待 theme 层重新考虑，见下方待办） |
| `negative` | 负向结果 / 成本 / 风险 | 珊瑚橙描边，深棕填充（与 positive 用同一色但"填充 vs 描边"区分方向，不新增色值） |
| `highlight` | 需要视觉汇聚的核心节点（配合 role=thesis 使用） | 珊瑚橙填充 + scale 1.15（scale 由 role=thesis 决定，highlight 只决定颜色本身） |

**待办（不阻塞本次发布，留给 theme 层重构时处理）**：主题里 `accent_danger` 这个命名本身就带有"危险"语义，但现在拿它同时表达 positive 和 highlight，命名和语义已经不匹配。建议下次动 theme.yaml 时把它拆成 `accent_result`（结果类节点通用色）+ 保留 `accent_danger` 只给纯风险描边用。这次不动，因为改 theme 需要人工确认（SPEC.md 里锁定了 warm_layered 不可未经确认修改）。



---

## 2. Edge Type → Stroke Style 映射

| Edge Type | 含义 | Stroke | 箭头 | 出现示例 |
|---|---|---|---|---|
| `flow` | 资金 / 资产流动 | 实线，1.2px | 实心三角 | 存入法币、放出资金 |
| `benefit_flow` | 收益流向（flow 的子类，视觉更强调） | 实线，2px（比 flow 粗） | 实心三角，稍大 | 收益归发行方、收益归运营方 |
| `control` | 约束 / 监管 / 影响关系，非资金流 | 虚线 `4,4`，1px | 空心三角 | 约束储备披露、监管约束 |
| `depends` | 结构性依赖，非因果 | 点线 `1,3`，1px | 无箭头或细箭头 | layer_stack 的 depends_on |
| `causes` | 因果链（causal_chain 专用） | 实线，1.2px | 实心三角 | Fed 加息 → 传导路径 |

**决策要点**：
- 现有截图里"约束储备披露""挤兑反馈"这类长距离虚线，语义上是 `control`，应统一用虚线，目前 renderer 里的虚线判断逻辑需要核对是否已经按 edge_type 分类，还是单纯按"跨泳道/跨层"这种拓扑位置判断的（如果是后者，需要改成按语义字段判断，这是本次改动的核心）。

---

## 3. Weight → 视觉权重映射（在现有基础上补全，不是新概念）

| Weight | Scale | 描边 | 透明度 |
|---|---|---|---|
| `high` | 1.0（默认，不额外放大——放大交给 role=thesis 专属） | 1.5px | 100% |
| `normal` | 1.0 | 1px | 100% |
| `low` | 0.95 | 1px | 75% |

**决策要点**：
- 原本 `weight:high` 承担了"珊瑚橙填充 + 放大"的双重职责。拆分后，颜色职责交给 `role`（benefit/thesis 自带珊瑚橙），`weight` 只负责描边粗细和透明度这类次一级的强调。避免同一视觉效果被两套字段同时控制、互相打架。

---

## 4. Lane 分层背景（parallel_lanes 专用，v0.2：role 驱动，不再按序号推断）

v0.1 曾提议按"泳道内第几个节点"自动推断资产层/收益层/归属层，v0.2 采纳反馈意见废弃这个方案——原因：不同泳道长度不一致时（例如稳定币图里法币储备只有 3 层，另外两条有 4 层），按序号推断会直接错位。renderer 不应该猜测语义，只应该消费明确字段。

改为直接按 `role` 分层，规则固定、不依赖节点在泳道中的位置：

| Role | 背景处理 |
|---|---|
| `entry` / `asset` / `protocol` / `flow_step` | 无背景（透明），视为"过程层" |
| `benefit` | 所在整行加 `accent_primary` 5% 透明度横向色带 |
| `owner` | 所在整行加 `accent_secondary` 5% 透明度横向色带 |
| `thesis` / `risk` | 无独立色带（本身已用 scale/描边强调，不需要再叠加背景） |

这样即使某条泳道节点数量和其他泳道不同，色带也总是跟着 role 走，不会因为长度差异而错位。

---

## 需要你确认的问题（v0.2，已比 v0.1 减少）

1. `status` 字段的四个取值（neutral/positive/negative/highlight）够用吗？还是需要更细（比如区分"轻微负向"和"严重负向"）？我倾向先用这四个，不够再加。
2. `thesis` 每图 0–1 个，够用吗？
3. `accent_danger` 命名和语义不匹配的问题，是现在顺手改 theme.yaml，还是留到下次专门动 theme 的时候一起处理？我建议留到下次——这次改动已经涉及 schema + renderer，不建议同一批次再动被锁定的 theme 文件。
4. Role 词表本次不重构（保留 8 个），但反馈提出的 Actor/Object/Process/Outcome/Decision 拆分方向本身是否认可，作为"未来触发条件"记录下来？比如"当某个 role 在第 3 个不同领域的 ontology 里出现语义冲突时，才启动重构"——需要你定这个触发条件，还是先不写，到时候再说？

## 本次不做，明确记录原因的事项

- **不新增 Narrative 独立层**：现有 `template` 字段已经承担了"哪些先说、哪些后说"的职责，在没有证据表明 template 不够用之前，不拆分成独立的 Narrative 层。
- **不重构 Role 为 Actor/Object/Process/Outcome/Decision + subtype**：当前只有 1 个 ontology（financial），跨领域冲突尚未发生，重构时机未到。参考 SPEC.md "compress, don't expand" 原则。
