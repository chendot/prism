# CLAUDE.md

Claude Code / Claude 类 coding agent 在本仓库工作时，请先遵守这份文件。

## 文档优先级

- `SPEC.md`：架构和数据契约，涉及 schema、ontology、layer 边界时以它为准。
- `README.md`：用户入口和常用命令，面向中文读者。
- `AGENTS.md`：通用 coding agent 协作规则。
- `CLAUDE.md`：Claude 专用执行约束，不重复定义项目 spec。

如果文档之间出现冲突，先保持代码不动，指出冲突并建议如何统一。

## Claude 工作约束

- 修改前先用 `rg`、`sed`、`git status --short` 了解现状。
- 不要把 ontology 中的 role 或 edge type 写死进 Pydantic schema。
- 不要让 Research、Compression、Render 三层共享隐藏状态。
- 不要把生成的 HTML、Mermaid、SVG 当作核心资产提交；核心资产是 `prism.yaml`。
- 不要扩大重构范围。优先做小而可验证的改动。
- 不要新增与 `README.md`、`SPEC.md`、`AGENTS.md` 重复的大段说明。

## 必跑检查

改代码后至少运行：

```bash
.venv/bin/python -m pytest
```

改 CLI、示例、renderer 或 ontology 后额外运行：

```bash
.venv/bin/prism validate examples/treasury.yaml
.venv/bin/prism render examples/treasury.yaml
```

若 `.venv` 不存在，再按 `README.md` 的快速开始安装依赖。

## 提交前

- 确认 `git diff --check` 通过。
- 确认 `git status --short` 只包含本次任务相关文件。
- 提交信息用英文祈使句或简短名词短语，例如 `Add Claude agent guidance`。
