"""Visual theme loading for renderers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

THEME_DIR = Path(__file__).resolve().parents[1] / "themes"
DEFAULT_THEME = "warm_layered"


@dataclass(frozen=True)
class VisualTheme:
    """Renderer-facing visual theme values."""

    name: str
    background: str
    surface: str
    surface_border: str
    accent_primary: str
    accent_secondary: str
    accent_result: str
    accent_risk: str
    text_primary: str
    text_secondary: str
    node_accent_bar_width: int
    icon_badge_opacity: float
    primary_glow_opacity: float
    highlight_glow_opacity: float
    glow_blur: float
    watermark: str
    watermark_color: str


def load_theme(name: str | None) -> VisualTheme:
    """Load a visual theme by name from ``src/prism/themes``."""

    theme_name = name or DEFAULT_THEME
    path = THEME_DIR / f"{theme_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown visual theme '{theme_name}' at {path}")

    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return VisualTheme(
        name=data["name"],
        background=data["background"],
        surface=data["surface"],
        surface_border=data["surface_border"],
        accent_primary=data["accent_primary"],
        accent_secondary=data["accent_secondary"],
        accent_result=data["accent_result"],
        accent_risk=data["accent_risk"],
        text_primary=data["text_primary"],
        text_secondary=data["text_secondary"],
        node_accent_bar_width=int(data["node_accent_bar_width"]),
        icon_badge_opacity=float(data["icon_badge_opacity"]),
        primary_glow_opacity=float(data["primary_glow_opacity"]),
        highlight_glow_opacity=float(data["highlight_glow_opacity"]),
        glow_blur=float(data["glow_blur"]),
        watermark=data["watermark"],
        watermark_color=data["watermark_color"],
    )
