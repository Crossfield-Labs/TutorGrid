from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


ICON_SIZES = [256, 128, 64, 48, 32, 16]
PADDING_RATIO = 0.14


def build_square_icon(source: Path, target_size: int = 512) -> Image.Image:
    image = Image.open(source).convert("RGBA")
    canvas = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))

    usable = int(target_size * (1.0 - PADDING_RATIO * 2))
    scale = min(usable / image.width, usable / image.height)
    resized = image.resize(
        (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
        Image.Resampling.LANCZOS,
    )

    offset = (
        (target_size - resized.width) // 2,
        (target_size - resized.height) // 2,
    )
    canvas.alpha_composite(resized, offset)
    return canvas


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: prepare_icons.py <source_png> <target_ico> <target_favicon_png>")

    source = Path(sys.argv[1]).resolve()
    target_ico = Path(sys.argv[2]).resolve()
    target_favicon = Path(sys.argv[3]).resolve()

    if not source.exists():
        print(f"[icons] Source icon not found: {source}")
        return 0

    square_icon = build_square_icon(source)
    target_ico.parent.mkdir(parents=True, exist_ok=True)
    target_favicon.parent.mkdir(parents=True, exist_ok=True)

    square_icon.save(target_ico, format="ICO", sizes=[(size, size) for size in ICON_SIZES])
    square_icon.resize((256, 256), Image.Resampling.LANCZOS).save(target_favicon, format="PNG")

    print(f"[icons] Prepared {target_ico} and {target_favicon}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
