# Roadmap

本文档记录 Prism 的阶段性计划、暂缓事项及其触发条件。区别于 `SPEC.md`（稳定契约）和 `VISUAL_GRAMMAR.md`（视觉规范），这里存放"决定做什么、决定暂时不做什么、以及为什么"的过程性记录。

---

## 进行中 / 刚完成

- [x] Sprint 1：LLMCompressor 两步压缩流程
- [x] warm_layered 视觉主题
- [x] value_flow / causal_chain / layer_stack 三个 template
- [x] parallel_lanes template（新增，含 LayoutConfig 重构 + 冒烟测试）
- [x] Visual Grammar v0.2：role→shape、status→color 解耦，edge_type→stroke 映射
- [x] Visual polish PR 1：节点/竖条纵向渐变（[截图](examples/screenshots/pr1.png)）
- [x] Visual polish PR 2：highlight thesis glow 与文字层级（[截图](examples/screenshots/pr2.png)）
- [x] Visual polish PR 3：role 语义图标（Lucide MIT path， [截图](examples/screenshots/pr3.png)）
- [ ] **发布第一张图**（稳定币利息分配，小红书）—— 当前最高优先级，未完成前不再扩展新功能

---

## 计划中（有明确时机）

### Phase C：target_format 升级为叙事策略

x_card（节点筛选逻辑）、xiaohongshu_carousel（三页分页）。SPEC.md 已定义接口，等 Phase B 稳定后启动。

### layer_stack 模板真实主题验证

目前只在 acceptance 阶段跑过，未在真实发布场景验证。

明确不采纳：**按泳道切换主色调**（图 2 参考图里蓝/绿/紫分泳道）。理由：warm_layered 单一暖棕色系是 chendot 品牌辨识度的核心资产，之前人工评审已明确认可这一点；彩虹配色是当下 AI 生成信息图的通用审美，会削弱而非强化品牌区分度。

---

## 暂缓（附触发条件，未来重新评估时直接看这里）

- **Role 重构为 Actor/Object/Process/Outcome/Decision + subtype 分层**
  提出者：外部反馈（Visual Grammar 讨论）
  暂缓理由：目前只有 1 个 ontology（financial）在运行，尚无跨领域语义冲突的真实案例支撑重构方向；现在做等于为假设的通用性预付架构成本，与"compress, don't expand"原则冲突
  触发条件：**某个 role 在第 3 个不同领域的 ontology 里出现语义冲突或强行复用**（例如给 AI/政策类主题写 ontology 时，发现现有 8 个 role 明显不够表达）

- **拆分独立的 Narrative 层**（Ontology → Narrative → Visual Grammar → Theme → Renderer 五层架构）
  提出者：外部反馈（Visual Grammar 讨论）
  暂缓理由：现有 `template` 字段（value_flow/causal_chain/parallel_lanes）已经在承担"哪些先说、哪些后说"的职责，尚无证据表明它不够用
  触发条件：**出现一个主题，其叙事顺序无法用现有 template 的结构约束表达**（即需要独立于结构类型之外的"讲述顺序"控制）

- **研究层（Research engine）**
  暂缓理由：本项目原则中"Research layer is frozen until a concrete knowledge gap triggers its need"
  触发条件：出现一个主题，LLMCompressor 在没有额外研究输入的情况下无法生成合格的 prism.yaml

---

## 明确不做

- **文生图模型作为生产链路的一环**（即便美化效果好看）。理由：deterministic rendering 是 Prism 的核心原则，文生图会引入不可控的文字错误（已在图 2 参考图中发现"购买发行"被错误生成为"购实发行"）、不可复现、不可版本控制。GPT 美化图仅可作为 Visual Grammar 迭代的视觉参考，不进入正式渲染链路。
- **按泳道切换主色调**（见上方 v0.3 说明）。
