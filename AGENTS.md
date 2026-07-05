# AGENTS.md

给 Codex 和其他 coding agent 的协作说明。项目契约以 `SPEC.md` 为准；这里不重复 spec，只记录工作方式。

## 工作前先确认

- 改 schema、validator、ontology、renderer 前先读 `SPEC.md`。
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
