# AGENTS.md

给 Codex 和其他 coding agent 的协作说明。项目契约以 `SPEC.md` 为准；这里不重复 spec，只记录工作方式。

## Default behavior

- 不要默认扫描整个仓库，除非任务本身需要全局理解。
- 先阅读 `SPEC.md`、`README.md` 和本次任务直接相关的文件。
- 编辑前先说明预计会修改哪些文件。
- 优先使用最小 patch。
- 不要重构无关代码。
- 修改后只运行最窄相关检查；文档变更通常只需 `git diff --check`。
- 大改动拆成小 patch 或小提交。

## Project rules

- `SPEC.md` 是产品和架构契约。
- `README.md` 是面向用户的中文入口文档。
- 除非任务明确要求，不要改变既有项目结构。
- 改 schema、validator、ontology、renderer 前必须先读 `SPEC.md`。
- 不要把领域枚举写进 `src/prism/core/schema.py`。
- 不要让 renderer 依赖 research/compression 的内部状态。
- 不要把生成物当成核心资产；核心资产始终是 `prism.yaml`。

## 本地验证

优先使用已有虚拟环境：

```bash
.venv/bin/python -m pytest
.venv/bin/prism validate examples/treasury.yaml
.venv/bin/prism render examples/treasury.yaml
```

如果还没有安装依赖：

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## 修改对应测试

- schema 或 validator 变更：更新 `tests/test_schema.py`、`tests/test_validator.py`。
- Mermaid 输出变更：更新 `tests/test_render_mermaid.py`。
- ontology 变更：确认 `examples/treasury.yaml` 仍能 validate。

## 代码风格

- Python 3.11+。
- Pydantic v2。
- 类型注解优先。
- 占位实现要写清 TODO。
- 保持接口小而稳定，避免为了占位功能引入复杂抽象。

## 当前任务上下文

**Sprint 1：LLMCompressor to Valid Prism YAML**

目标：打通从"用户输入观点/文章"到"可渲染 prism.yaml"的完整链路。

验收标准：
- 输入 5 个真实主题，至少 4 个生成 valid prism.yaml
- Renderer 不报错
- 输出图肉眼可读
- warm_layered 风格保持一致

---

### LLMCompressor 实现规格

路径：`src/prism/compressors/llm_compressor.py`

**两步实现，不要合并成一步：**

**Step 1 — 判断解释结构**

```python
# 输入：topic: str, notes: str | None
# 输出：template_name: Literal["value_flow", "causal_chain", "layer_stack"]
```

System prompt 参考 `src/prism/compressors/prompts/system.md`。

判断规则（写进 prompt，不写进代码）：
- 利益分配 / 资金流 / 权力转移 / DeFi → value_flow
- 风险传导 / 市场周期 / 政策影响 / 因果链 → causal_chain
- 系统分层 / 软件架构 / 能力栈 → layer_stack

**Step 2 — 按 template 生成 prism.yaml**

```python
# 输入：topic, notes, template_name, ontology: Ontology
# 输出：PrismDoc（经过 validator 校验）
```

System prompt 动态构建，包含：
1. `src/prism/compressors/prompts/system.md`（通用规则）
2. `src/prism/compressors/prompts/prism_yaml_schema.md`（schema 约束）
3. 对应 template 的结构约束（从 `src/prism/templates/<name>.yaml` 读取）
4. ontology 的 roles 和 edge_types（控制合法词表）
5. 两个 few-shot 示例（`examples/treasury.yaml` + `examples/fed_rate_hike.yaml`）

**validate-retry 规则：**
- 调用 `validator.validate()` 校验输出
- 失败则将错误信息拼入下一轮 prompt，重试
- 最多 2 次重试，仍失败则抛出 `CompressionError` 并附原因

**模型：** `claude-sonnet-4-6`，Anthropic SDK

**不要删除 `PlaceholderCompressor`。**

---

### 当前最小文件结构

Sprint 1 只需要这些文件存在（其余不要提前创建）：

```text
src/prism/
  core/
    schema.py          # 已有
    validator.py       # 已有
  compressors/
    placeholder.py     # 已有，保留
    llm_compressor.py  # Sprint 1 主目标
    prompts/
      system.md
      prism_yaml_schema.md
      template_rules.md
  templates/
    value_flow.yaml    # Sprint 1
    causal_chain.yaml  # Sprint 1
    layer_stack.yaml   # Sprint 1
  themes/
    warm_layered.yaml  # Sprint 1
  renderers/
    svg.py             # 已有
  ontologies/
    financial.yaml     # 已有
```

Phase B（templates 扩展）、Phase C（platform renderer）、Phase D（research pipeline）在 Sprint 1 验收后再动。
