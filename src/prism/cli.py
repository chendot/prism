"""Command line entry point for Prism's three-layer workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from prism.compression.compressor import PlaceholderCompressor
from prism.compression.llm_compressor import LLMCompressor
from prism.core.schema import PrismDoc, RendererName
from prism.core.validator import validate_prism_file
from prism.ontologies.loader import list_ontologies, load_ontology
from prism.render.base import Renderer
from prism.render.image import DEFAULT_IMAGE_PROFILE, ImageExportError, export_html_to_png
from prism.render.mermaid import MermaidRenderer
from prism.research.engine import PlaceholderResearchEngine

app = typer.Typer(help="Prism visual explanation system.")
DEFAULT_OUTPUT_DIR = Path("outputs")


def get_renderer(name: RendererName) -> Renderer:
    """Return the renderer implementation for a Prism renderer name."""

    if name == RendererName.MERMAID:
        return MermaidRenderer()
    if name == RendererName.SVG:
        raise typer.BadParameter("Renderer 'svg' is planned but not implemented yet.")
    if name == RendererName.D3:
        raise typer.BadParameter("Renderer 'd3' is planned but not implemented yet.")
    raise typer.BadParameter(f"Unknown renderer: {name}")


def write_text(path: Path, content: str) -> Path:
    """Write UTF-8 text and return the path for command feedback."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@app.command()
def validate(file: Path) -> None:
    """Validate a prism.yaml file against schema and ontology."""

    prism = validate_prism_file(file)
    typer.echo(f"OK: {file} ({len(prism.nodes)} nodes, {len(prism.edges)} edges)")


@app.command()
def render(
    file: Path,
    output: Path | None = typer.Option(None, "--output", "-o"),
    image_output: Path | None = typer.Option(None, "--image-output"),
    target_format: str | None = typer.Option(None, "--target-format"),
    no_image: bool = typer.Option(False, "--no-image"),
) -> None:
    """Run Layer 3 only: prism.yaml to render output."""

    prism = validate_prism_file(file)
    ontology = load_ontology(prism.meta.ontology)
    renderer = get_renderer(prism.render.renderer)
    content = renderer.render(prism, ontology)

    if output is None:
        suffix = ".html" if prism.render.renderer == RendererName.MERMAID else ".out"
        output = DEFAULT_OUTPUT_DIR / f"{file.stem}{suffix}"
    write_text(output, content)
    typer.echo(f"Rendered: {output}")
    if not no_image:
        image_path = image_output or output.with_suffix(".png")
        image_profile = target_format or prism.meta.target_format or DEFAULT_IMAGE_PROFILE
        _export_image(output, image_path, image_profile)


@app.command()
def compress(
    topic: str,
    ontology: str = typer.Option("financial", "--ontology"),
    llm_provider: str = typer.Option("codex", "--llm-provider"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Run Layer 2 only: topic to validated prism.yaml."""

    loaded_ontology = load_ontology(ontology)
    prism = LLMCompressor(provider=llm_provider).compress(topic, None, loaded_ontology)
    output = output or DEFAULT_OUTPUT_DIR / "prism.yaml"
    write_text(output, prism.to_yaml())
    typer.echo(f"Wrote: {output}")


@app.command()
def research(
    topic: str,
    ontology: str = typer.Option("financial", "--ontology"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Run optional Layer 1 only: topic to findings.json."""

    loaded_ontology = load_ontology(ontology)
    findings = PlaceholderResearchEngine().research(topic, loaded_ontology)
    output = output or DEFAULT_OUTPUT_DIR / "findings.json"
    write_text(output, json.dumps(findings, ensure_ascii=False, indent=2))
    typer.echo(f"Wrote: {output}")


@app.command()
def run(
    topic: str,
    ontology: str = typer.Option("financial", "--ontology"),
    llm_provider: str = typer.Option("codex", "--llm-provider"),
    skip_research: bool = typer.Option(False, "--skip-research"),
    placeholder: bool = typer.Option(False, "--placeholder"),
    output_dir: Path = typer.Option(DEFAULT_OUTPUT_DIR, "--output-dir"),
    target_format: str | None = typer.Option(None, "--target-format"),
    no_image: bool = typer.Option(False, "--no-image"),
) -> None:
    """Run research, compression, and render as one workflow."""

    loaded_ontology = load_ontology(ontology)
    findings: dict[str, Any] | None = None
    if not skip_research:
        findings = PlaceholderResearchEngine().research(topic, loaded_ontology)
        write_text(output_dir / "findings.json", json.dumps(findings, ensure_ascii=False, indent=2))

    compressor = (
        PlaceholderCompressor()
        if placeholder
        else LLMCompressor(provider=llm_provider)
    )
    prism = compressor.compress(topic, findings, loaded_ontology)
    yaml_path = write_text(output_dir / "prism.yaml", prism.to_yaml())

    renderer = get_renderer(prism.render.renderer)
    html = renderer.render(prism, loaded_ontology)
    render_path = write_text(output_dir / "prism.html", html)
    typer.echo(f"Wrote: {yaml_path}")
    typer.echo(f"Rendered: {render_path}")
    if not no_image:
        image_profile = target_format or prism.meta.target_format or DEFAULT_IMAGE_PROFILE
        _export_image(render_path, output_dir / "prism.png", image_profile)


def _export_image(html_path: Path, image_path: Path, target_format: str) -> None:
    try:
        export_html_to_png(html_path, image_path, target_format)
    except ImageExportError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(f"Image: {image_path} ({target_format})")


@app.command("ontologies")
def ontologies_command() -> None:
    """List available ontology plugins."""

    for name in list_ontologies():
        typer.echo(name)


if __name__ == "__main__":
    app()
