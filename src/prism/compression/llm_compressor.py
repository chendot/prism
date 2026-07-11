"""Local-agent-backed compressor for Prism Layer 2."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from prism.compression.base import Compressor
from prism.core.models import Ontology
from prism.core.schema import PrismDoc
from prism.core.validator import PrismValidationError, validate_prism_doc

TemplateName = Literal["value_flow", "causal_chain", "layer_stack"]
ProviderName = Literal["codex", "claude-cowork"]

MAX_RETRIES = 2
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
EXAMPLE_PATHS = [
    PROJECT_ROOT / "examples" / "treasury.yaml",
    PROJECT_ROOT / "examples" / "fed_rate_hike.yaml",
]
VALID_TEMPLATES: tuple[TemplateName, ...] = ("value_flow", "causal_chain", "layer_stack")
VALID_PROVIDERS: tuple[ProviderName, ...] = ("codex", "claude-cowork")


class CompressionError(RuntimeError):
    """Raised when LLM compression cannot produce a valid PrismDoc."""


@dataclass(frozen=True)
class GraphPlan:
    """Short-lived narrative plan used only inside the compression layer."""

    thesis: str
    template: TemplateName
    reason: str
    main_path: tuple[str, ...]

    def display(self) -> str:
        """Return a compact, human-scannable terminal summary."""

        return "\n".join(
            [
                "GraphPlan",
                f"  thesis: {self.thesis}",
                f"  template: {self.template} ({self.reason})",
                f"  main_path: {' → '.join(self.main_path)}",
            ]
        )


@dataclass(frozen=True)
class LocalAgentClient:
    """Invoke a local agent CLI without API credentials.

    The default commands intentionally stay small. If a local install needs
    extra flags, set PRISM_LLM_CODEX_COMMAND or PRISM_LLM_CLAUDE_COWORK_COMMAND.
    Commands may include ``{prompt}``; otherwise the prompt is sent on stdin.
    """

    provider: ProviderName

    def complete(self, prompt: str) -> str:
        command = self._command()
        command_text = " ".join(command)
        if "{prompt}" in command_text:
            command = [part.replace("{prompt}", prompt) for part in command]
            stdin = None
        else:
            stdin = prompt

        self._debug(
            "starting provider subprocess "
            f"command={command!r} stdin={'yes' if stdin is not None else 'no'} "
            f"prompt_chars={len(prompt)}"
        )

        try:
            result = subprocess.run(
                command,
                input=stdin,
                text=True,
                capture_output=True,
                check=False,
                cwd=PROJECT_ROOT,
            )
        except FileNotFoundError as error:
            raise CompressionError(
                f"Local LLM provider command not found for '{self.provider}': {command[0]}"
            ) from error

        self._debug(
            "provider subprocess completed "
            f"returncode={result.returncode} stdout_chars={len(result.stdout)} "
            f"stderr_chars={len(result.stderr)}"
        )
        if result.stderr.strip():
            self._debug(f"provider stderr preview={result.stderr.strip()[:500]!r}")
        if result.stdout.strip():
            self._debug(f"provider stdout preview={result.stdout.strip()[:500]!r}")

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            detail = stderr or stdout or f"exit code {result.returncode}"
            raise CompressionError(
                f"Local LLM provider '{self.provider}' failed: {detail}"
            )

        output = result.stdout.strip()
        if not output:
            raise CompressionError(f"Local LLM provider '{self.provider}' returned no output.")
        return output

    def _debug(self, message: str) -> None:
        if os.environ.get("PRISM_LLM_DEBUG") == "1":
            print(f"[prism llm] {message}", file=sys.stderr, flush=True)

    def _command(self) -> list[str]:
        env_name = {
            "codex": "PRISM_LLM_CODEX_COMMAND",
            "claude-cowork": "PRISM_LLM_CLAUDE_COWORK_COMMAND",
        }[self.provider]
        configured = os.environ.get(env_name)
        if configured:
            return shlex.split(configured)
        if self.provider == "codex":
            return ["codex", "exec", "-"]
        return ["claude", "cowork"]


class LLMCompressor(Compressor):
    """Compress a topic into a validated PrismDoc with a local agent."""

    def __init__(self, provider: str | ProviderName = "codex") -> None:
        if provider not in VALID_PROVIDERS:
            available = ", ".join(VALID_PROVIDERS)
            raise CompressionError(f"Unknown LLM provider '{provider}'. Available: {available}")
        self.client = LocalAgentClient(provider)  # type: ignore[arg-type]

    def compress(
        self, topic: str, findings: dict[str, Any] | None, ontology: Ontology
    ) -> PrismDoc:
        """Plan the story, expose the plan, then generate validated YAML."""

        notes = self._notes_from_findings(findings)
        graph_plan = self.plan_story(topic)
        print(graph_plan.display())
        return self.generate_yaml(topic, notes, graph_plan, ontology)

    def plan_story(self, topic: str) -> GraphPlan:
        """Step 1: choose an explanation structure from a concise story plan."""

        prompt = "\n\n".join(
            [
                self._read_prompt("system.md"),
                "你现在只做 Story Planning，不生成 prism.yaml。",
                "根据 topic 和 notes 形成一个可解释的图解计划。",
                "模板含义：",
                "- value_flow：利益分配、资金流、权力转移、DeFi。",
                "- causal_chain：风险传导、市场周期、政策影响、因果链。",
                "- layer_stack：系统分层、软件架构、能力栈。",
                "只输出 YAML mapping，且只能包含以下字段：",
                "thesis: 一句可检验的核心判断",
                "template: value_flow | causal_chain | layer_stack",
                "reason: 一句说明为何该结构最适合",
                "main_path: 3 到 6 个关键概念组成的列表，按叙事顺序排列",
                self._topic_prompt(topic, None),
            ]
        )
        return self._parse_graph_plan(self._complete("GraphPlan", prompt))

    def choose_template(self, topic: str, notes: str | None) -> TemplateName:
        """Compatibility helper; template selection now comes from GraphPlan."""

        return self.plan_story(topic).template

    def generate_yaml(
        self,
        topic: str,
        notes: str | None,
        graph_plan: GraphPlan,
        ontology: Ontology,
    ) -> PrismDoc:
        """Step 3: realize a GraphPlan as YAML and retry validation failures."""

        system_prompt = self._build_generation_prompt(graph_plan.template, ontology)
        user_prompt = self._generation_user_prompt(topic, notes, graph_plan)
        retry_context = ""
        last_yaml = ""
        last_error = ""

        for attempt in range(MAX_RETRIES + 1):
            prompt = "\n\n".join(
                part for part in [system_prompt, user_prompt, retry_context] if part
            )
            raw_yaml = self._strip_yaml_fence(self._complete("YAML", prompt))
            last_yaml = raw_yaml

            try:
                doc_dict = yaml.safe_load(raw_yaml)
                if not isinstance(doc_dict, dict):
                    raise CompressionError("LLM output is not a YAML mapping.")
                doc_dict.setdefault("meta", {})
                doc_dict.setdefault("diagram", {})
                doc_dict["meta"]["topic"] = topic
                doc_dict["meta"]["ontology"] = ontology.name
                doc_dict["meta"]["template"] = graph_plan.template
                doc_dict["meta"].setdefault("visual_theme", "warm_layered")
                doc_dict["diagram"]["thesis"] = graph_plan.thesis
                prism = PrismDoc.model_validate(doc_dict)
                return validate_prism_doc(prism, ontology)
            except (
                CompressionError,
                TypeError,
                yaml.YAMLError,
                ValidationError,
                PrismValidationError,
            ) as error:
                last_error = str(error)
                if attempt == MAX_RETRIES:
                    break
                retry_context = "\n\n".join(
                    [
                        "上一次输出没有通过 Prism validator。请只输出修正后的完整 YAML。",
                        f"validator 错误：\n{last_error}",
                        f"上一次 YAML：\n{raw_yaml}",
                    ]
                )

        raise CompressionError(
            "Local agent compression failed after validation retries.\n"
            f"Template: {graph_plan.template}\n"
            f"Validation error:\n{last_error}\n"
            f"Last YAML:\n{last_yaml}"
        )

    def _build_generation_prompt(self, template_name: TemplateName, ontology: Ontology) -> str:
        template_rules = self._read_template(template_name)
        ontology_prompt = self._ontology_prompt(ontology)
        examples = self._examples_prompt()
        return "\n\n".join(
            [
                self._read_prompt("system.md"),
                self._read_prompt("prism_yaml_schema.md"),
                self._read_prompt("template_rules.md"),
                f"当前选择模板：{template_name}",
                "当前模板 YAML 约束：",
                template_rules,
                ontology_prompt,
                examples,
            ]
        )

    def _ontology_prompt(self, ontology: Ontology) -> str:
        role_lines = [
            f"- {name}: {metadata.get('label_zh', name)}"
            for name, metadata in ontology.roles.items()
        ]
        edge_type_lines = [
            f"- {name}: {metadata.get('label_zh', name)}"
            for name, metadata in ontology.edge_types.items()
        ]
        weight_lines = [
            f"- {name}: scale={metadata.get('scale')}, fill={metadata.get('fill')}, "
            f"text={metadata.get('text')}, border={metadata.get('border')}, "
            f"opacity={metadata.get('opacity')}"
            for name, metadata in ontology.weights.items()
        ]
        return "\n".join(
            [
                f"Ontology: {ontology.name}",
                ontology.description,
                "",
                "合法 node.role，只能从这里选择：",
                *role_lines,
                "",
                "合法 edge.type，只能从这里选择：",
                *edge_type_lines,
                "",
                "合法 node.weight，只能从这里选择；未标注默认 secondary：",
                *weight_lines,
            ]
        )

    def _examples_prompt(self) -> str:
        parts = []
        for path in EXAMPLE_PATHS:
            if not path.exists():
                raise CompressionError(f"Missing few-shot example file: {path}")
            parts.append(f"Few-shot example: {path.name}\n{path.read_text(encoding='utf-8')}")
        return "\n\n".join(parts)

    def _generation_user_prompt(
        self, topic: str, notes: str | None, graph_plan: GraphPlan
    ) -> str:
        return "\n\n".join(
            [
                "请根据 topic、notes 和锁定的 GraphPlan 生成完整 prism.yaml。",
                "不得重新选择 template、改变 thesis 或改变 main_path 的叙事顺序。",
                "把 GraphPlan.thesis 原样写入 diagram.thesis。",
                "GraphPlan：",
                graph_plan.display(),
                self._topic_prompt(topic, notes),
                "输出要求：只输出 YAML，不要 markdown 代码块，不要解释文字。",
            ]
        )

    def _topic_prompt(self, topic: str, notes: str | None) -> str:
        return f"topic: {topic}\nnotes: {notes or '无'}"

    def _notes_from_findings(self, findings: dict[str, Any] | None) -> str | None:
        if not findings:
            return None
        return json.dumps(findings, ensure_ascii=False, indent=2, default=str)

    def _complete(self, step: str, prompt: str) -> str:
        """Invoke the provider while exposing step boundaries in debug mode."""

        if os.environ.get("PRISM_LLM_DEBUG") == "1":
            print(
                f"[prism llm] {step} request started (prompt_chars={len(prompt)})",
                file=sys.stderr,
                flush=True,
            )
        output = self.client.complete(prompt)
        if os.environ.get("PRISM_LLM_DEBUG") == "1":
            print(
                f"[prism llm] {step} response received (output_chars={len(output)})",
                file=sys.stderr,
                flush=True,
            )
        return output

    def _read_prompt(self, filename: str) -> str:
        path = PROMPT_DIR / filename
        if not path.exists():
            raise CompressionError(f"Missing prompt file: {path}")
        return path.read_text(encoding="utf-8").strip()

    def _read_template(self, template_name: TemplateName) -> str:
        path = TEMPLATE_DIR / f"{template_name}.yaml"
        if not path.exists():
            raise CompressionError(f"Missing template file: {path}")
        return path.read_text(encoding="utf-8").strip()

    def _extract_template_name(self, text: str) -> str:
        for template_name in VALID_TEMPLATES:
            if re.search(rf"\b{re.escape(template_name)}\b", text):
                return template_name
        return text.strip().strip("`")

    def _parse_graph_plan(self, text: str) -> GraphPlan:
        """Parse and minimally validate the LLM's transient story plan."""

        try:
            data = yaml.safe_load(self._strip_yaml_fence(text))
        except yaml.YAMLError as error:
            raise CompressionError(f"GraphPlan is not valid YAML: {error}") from error
        if not isinstance(data, dict):
            raise CompressionError("GraphPlan must be a YAML mapping.")

        thesis = data.get("thesis")
        template = data.get("template")
        reason = data.get("reason")
        main_path = data.get("main_path")
        if not isinstance(thesis, str) or not thesis.strip():
            raise CompressionError("GraphPlan requires a non-empty thesis.")
        if template not in VALID_TEMPLATES:
            raise CompressionError(f"GraphPlan returned unknown template: {template}")
        if not isinstance(reason, str) or not reason.strip():
            raise CompressionError("GraphPlan requires a non-empty reason.")
        if (
            not isinstance(main_path, list)
            or not 3 <= len(main_path) <= 6
            or not all(isinstance(item, str) and item.strip() for item in main_path)
        ):
            raise CompressionError("GraphPlan main_path must contain 3 to 6 non-empty strings.")

        return GraphPlan(
            thesis=thesis.strip(),
            template=template,
            reason=reason.strip(),
            main_path=tuple(item.strip() for item in main_path),
        )

    def _strip_yaml_fence(self, text: str) -> str:
        match = re.search(r"```(?:yaml|yml)?\s*(.*?)```", text, flags=re.DOTALL)
        return (match.group(1) if match else text).strip()
