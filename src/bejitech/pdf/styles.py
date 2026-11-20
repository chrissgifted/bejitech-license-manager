"""Shared colours and helpers for generated PDFs."""
from __future__ import annotations

import colorsys
import hashlib
from pathlib import Path

from reportlab.lib import colors

BRAND = colors.HexColor("#1F4E9B")
INK = colors.HexColor("#1D2433")
MUTED = colors.HexColor("#5B6475")
LINE = colors.HexColor("#D9DEE7")
SOFT = colors.HexColor("#F4F6FA")

_PALETTE = ["#1F4E9B", "#0F6E6E", "#2E6B30", "#6B2D5C", "#B5501C", "#3F3F9E", "#7A2E2E", "#0B6A8F"]


def fallback_accent(seed: str) -> colors.Color:
    idx = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(_PALETTE)
    return colors.HexColor(_PALETTE[idx])


def accent_from_logo(logo: Path | None, seed: str) -> colors.Color:
    """Pick the dominant saturated colour of the product logo, so each note matches its product."""
    if not logo or not Path(logo).exists():
        return fallback_accent(seed)
    try:
        from PIL import Image

        with Image.open(logo) as img:
            img = img.convert("RGBA").resize((64, 64))
            buckets: dict[tuple[int, int, int], int] = {}
            pixels = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
            for r, g, b, a in pixels:
                if a < 128:
                    continue
                h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
                if s < 0.35 or l < 0.15 or l > 0.85:
                    continue
                key = (r // 32, g // 32, b // 32)
                buckets[key] = buckets.get(key, 0) + 1
            if not buckets:
                return fallback_accent(seed)
            r, g, b = max(buckets, key=buckets.get)
            # darken slightly so white text stays readable
            h, l, s = colorsys.rgb_to_hls((r * 32 + 16) / 255, (g * 32 + 16) / 255, (b * 32 + 16) / 255)
            r2, g2, b2 = colorsys.hls_to_rgb(h, min(l, 0.42), s)
            return colors.Color(r2, g2, b2)
    except Exception:  # noqa: BLE001 - any image problem → fallback colour
        return fallback_accent(seed)


def tint(c: colors.Color, amount: float = 0.9) -> colors.Color:
    return colors.Color(c.red + (1 - c.red) * amount, c.green + (1 - c.green) * amount,
                        c.blue + (1 - c.blue) * amount)


def initials(name: str) -> str:
    words = [w for w in name.replace("-", " ").split() if w[:1].isalnum()]
    return "".join(w[0] for w in words[:2]).upper() or "?"
