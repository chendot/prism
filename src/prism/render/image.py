"""Raster image export for self-contained Prism HTML artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ImageExportError(RuntimeError):
    """Raised when a rendered HTML artifact cannot be exported as an image."""


@dataclass(frozen=True)
class ImageProfile:
    """A fixed publishing artboard."""

    width: int
    height: int


IMAGE_PROFILES: dict[str, ImageProfile] = {
    "xiaohongshu_card": ImageProfile(width=1080, height=1350),
    "x_card": ImageProfile(width=1200, height=675),
    "wechat_cover": ImageProfile(width=900, height=383),
}
DEFAULT_IMAGE_PROFILE = "xiaohongshu_card"


def export_html_to_png(
    html_path: Path,
    output_path: Path,
    target_format: str = DEFAULT_IMAGE_PROFILE,
) -> Path:
    """Screenshot a rendered Prism HTML artifact into a fixed PNG artboard.

    The browser consumes the same self-contained Dagre HTML that users open,
    keeping the publish image visually aligned with the production renderer.
    """

    profile = IMAGE_PROFILES.get(target_format)
    if profile is None:
        available = ", ".join(sorted(IMAGE_PROFILES))
        raise ImageExportError(
            f"Unknown image target format '{target_format}'. Available: {available}"
        )
    if not html_path.exists():
        raise ImageExportError(f"Rendered HTML does not exist: {html_path}")

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise ImageExportError(
            "Image export requires Playwright. Install project dependencies, then run "
            "'.venv/bin/python -m playwright install chromium'."
        ) from error

    output_path.parent.mkdir(parents=True, exist_ok=True)
    artboard_css = f"""
      html, body {{ margin: 0 !important; width: {profile.width}px; height: {profile.height}px; overflow: hidden !important; }}
      main {{ display: block !important; min-height: {profile.height}px !important; padding: 0 !important; }}
      .diagram {{ width: {profile.width}px !important; height: {profile.height}px !important; }}
      .prism-svg {{ display: block !important; width: 100% !important; height: 100% !important; }}
    """

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(
                    viewport={"width": profile.width, "height": profile.height},
                    device_scale_factor=1,
                )
                page.goto(html_path.resolve().as_uri(), wait_until="load")
                page.wait_for_selector("svg.prism-svg")
                page.add_style_tag(content=artboard_css)
                page.screenshot(path=str(output_path), type="png")
            finally:
                browser.close()
    except PlaywrightError as error:
        raise ImageExportError(
            "Unable to launch Chromium for image export. Run "
            "'.venv/bin/python -m playwright install chromium'."
        ) from error

    return output_path
