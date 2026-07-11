# Prism

Prism 是一个「视觉解释系统」项目骨架：输入复杂主题，生成可复用、可版本控制的 `prism.yaml`，再由确定性渲染器输出图解。

它不是文生图工具。项目的核心资产是 `prism.yaml`，最终图片、HTML 或 Mermaid 代码都只是渲染结果。

## 快速开始

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

验证示例：

```bash
.venv/bin/prism validate examples/treasury.yaml
.venv/bin/prism render examples/treasury.yaml
```

渲染后会生成：

```text
outputs/treasury.html
```

`examples/` 只存放可提交的成熟 YAML 模板和样例；未指定 `--output` 的生成 YAML、HTML 和 research 结果统一写入 `outputs/`（该目录已被 Git 忽略）。如需指定文件名，可传入 `--output`。

## 常用命令

```bash
prism validate examples/treasury.yaml
prism render examples/treasury.yaml
prism render examples/treasury.yaml --output outputs/treasury-preview.html
prism compress "美债如何运作" --ontology financial
prism research "美债如何运作" --ontology financial
prism run "美债如何运作" --ontology financial --skip-research
prism ontologies
```

## 项目结构

```text
prism/
├── src/prism/
│   ├── core/          # prism.yaml schema、领域无关模型、validator
│   ├── research/      # Layer 1：可选研究层
│   ├── compression/   # Layer 2：topic/findings -> prism.yaml
│   ├── render/        # Layer 3：prism.yaml -> HTML/SVG/D3 等输出
│   ├── ontologies/    # 领域词表和视觉映射
│   └── cli.py
├── examples/
└── tests/
```

## 文档分工

- `README.md`：使用入口、命令和项目导航。
- `SPEC.md`：架构边界、数据契约和扩展契约。
- `AGENTS.md`：给 Codex/agent 的开发协作规则。

新增 ontology、renderer 或更改 `prism.yaml` 结构前，先看 `SPEC.md`。
