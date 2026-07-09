from pathlib import Path
from typing import Any

from pytest import MonkeyPatch
from typer.testing import CliRunner

from prism import cli
from prism.compression.compressor import PlaceholderCompressor
from prism.core.models import Ontology
from prism.core.schema import PrismDoc


runner = CliRunner()


class FakeLLMCompressor:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def compress(
        self, topic: str, findings: dict[str, Any] | None, ontology: Ontology
    ) -> PrismDoc:
        prism = PlaceholderCompressor().compress(topic, findings, ontology)
        data = prism.model_dump(mode="json", by_alias=True)
        data["meta"]["subtitle"] = f"fake llm provider: {self.provider}"
        data["nodes"][0]["sublabel"] = "fake llm output"
        return PrismDoc.model_validate(data)


def test_run_uses_llm_compressor_by_default(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cli, "LLMCompressor", FakeLLMCompressor)

    result = runner.invoke(
        cli.app,
        [
            "run",
            "美债如何运作",
            "--skip-research",
            "--llm-provider",
            "test-provider",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    prism = PrismDoc.from_yaml(str(tmp_path / "prism.yaml"))
    assert prism.meta.subtitle == "fake llm provider: test-provider"
    assert prism.nodes[0].sublabel == "fake llm output"


def test_run_placeholder_flag_uses_placeholder_compressor(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    def fail_if_used(provider: str) -> FakeLLMCompressor:
        raise AssertionError("LLMCompressor should not be used with --placeholder")

    monkeypatch.setattr(cli, "LLMCompressor", fail_if_used)

    result = runner.invoke(
        cli.app,
        [
            "run",
            "美债如何运作",
            "--skip-research",
            "--placeholder",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    prism = PrismDoc.from_yaml(str(tmp_path / "prism.yaml"))
    assert prism.meta.subtitle == "Placeholder compression output"


def test_render_rejects_unimplemented_renderers_gracefully(tmp_path: Path) -> None:
    source = Path("examples/treasury.yaml").read_text(encoding="utf-8")

    for renderer_name in ("svg", "d3"):
        file = tmp_path / f"{renderer_name}_renderer.yaml"
        file.write_text(
            source.replace("renderer: mermaid", f"renderer: {renderer_name}"),
            encoding="utf-8",
        )

        result = runner.invoke(
            cli.app,
            ["render", str(file)],
        )

        assert result.exit_code != 0
        assert f"Renderer '{renderer_name}' is planned but not implemented yet." in result.output
