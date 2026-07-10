"""Inline, stroke-based SVG paths for Prism node roles.

The path data is adapted from Lucide icons (MIT License).
"""

from __future__ import annotations


ROLE_ICON_PATHS: dict[str, str] = {
    "entry": '<path d="M18 20a6 6 0 0 0-12 0M12 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />',
    "asset": '<path d="M12 2C7.58 2 4 3.79 4 6s3.58 4 8 4 8-1.79 8-4-3.58-4-8-4ZM4 6v6c0 2.21 3.58 4 8 4s8-1.79 8-4V6M4 12v6c0 2.21 3.58 4 8 4s8-1.79 8-4v-6" />',
    "protocol": '<path d="M6 22V4h12v18M2 22h20M10 8h4M10 12h4M10 16h4" />',
    "flow_step": '<path d="M8 12h8M12 8l4 4-4 4M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />',
    "benefit": '<path d="m3 17 6-6 4 4 8-8M14 7h7v7" />',
    "owner": '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2M16 12h5v4h-5a2 2 0 0 1 0-4Z" />',
    "thesis": '<path d="m2 4 3 12h14l3-12-5 4-5-6-5 6-5-4ZM5 20h14" />',
    "risk": '<path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3ZM12 9v4M12 17h.01" />',
    # Existing financial roles reuse the nearest semantic icon.
    "issuer": '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2M16 12h5v4h-5a2 2 0 0 1 0-4Z" />',
    "buyer": '<path d="M18 20a6 6 0 0 0-12 0M12 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />',
    "regulator": '<path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3ZM12 9v4M12 17h.01" />',
    "constraint": '<path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3ZM12 9v4M12 17h.01" />',
    "intermediary": '<path d="M6 22V4h12v18M2 22h20M10 8h4M10 12h4M10 16h4" />',
    "market": '<path d="M8 12h8M12 8l4 4-4 4M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />',
}
