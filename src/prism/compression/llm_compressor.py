"""Local-agent-backed compressor for Prism Layer 2."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
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
        """Classify the explanation template, generate YAML, then validate it."""

        notes = self._notes_from_findings(findings)
        template_name = self.choose_template(topic, notes)
        return self.generate_yaml(topic, notes, template_name, ontology)

    def choose_template(self, topic: str, notes: str | None) -> TemplateName:
        """Step 1: ask the local agent which explanation structure best fits."""

        prompt = "\n\n".join(
            [
                self._read_prompt("system.md"),
                "你现在只做解释结构判断。",
                "判断规则：",
                "- 利益分配 / 资金流 / 权力转移 / DeFi -> value_flow",
                "- 风险传导 / 市场周期 / 政策影响 / 因果链 -> causal_chain",
                "- 系统分层 / 软件架构 / 能力栈 -> layer_stack",
                "只输出一个模板名：value_flow、causal_chain 或 layer_stack。",
                self._topic_prompt(topic, notes),
            ]
        )
        template_name = self._extract_template_name(self.client.complete(prompt))
        if template_name not in VALID_TEMPLATES:
            raise CompressionError(f"Local agent returned unknown template: {template_name}")
        return template_name  # type: ignore[return-value]

    def generate_yaml(
        self,
        topic: str,
        notes: str | None,
        template_name: TemplateName,
        ontology: Ontology,
    ) -> PrismDoc:
        """Step 2: generate a Prism YAML document and retry validation failures."""

        system_prompt = self._build_generation_prompt(template_name, ontology)
        user_prompt = self._generation_user_prompt(topic, notes)
        retry_context = ""
        last_yaml = ""
        last_error = ""

        for attempt in range(MAX_RETRIES + 1):
            prompt = "\n\n".join(
                part for part in [system_prompt, user_prompt, retry_context] if part
            )
            raw_yaml = self._strip_yaml_fence(self.client.complete(prompt))
            last_yaml = raw_yaml

            try:
                doc_dict = yaml.safe_load(raw_yaml)
                if not isinstance(doc_dict, dict):
                    raise CompressionError("LLM output is not a YAML mapping.")
                doc_dict.setdefault("meta", {})
                doc_dict["meta"]["topic"] = topic
                doc_dict["meta"]["ontology"] = ontology.name
                doc_dict["meta"]["template"] = template_name
                doc_dict["meta"].setdefault("visual_theme", "warm_layered")
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
            f"Template: {template_name}\n"
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

    def _generation_user_prompt(self, topic: str, notes: str | None) -> str:
        return "\n\n".join(
            [
                "请根据 topic 和 notes 生成完整 prism.yaml。",
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

    def _strip_yaml_fence(self, text: str) -> str:
        match = re.search(r"```(?:yaml|yml)?\s*(.*?)```", text, flags=re.DOTALL)
        return (match.group(1) if match else text).strip()
