"""Converte a arte oficial existente em ícones Windows de várias resoluções."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
image = Image.open(ROOT / "assets/brand/Icon-100.jpg").convert("RGBA")
image = image.resize((256, 256), Image.Resampling.LANCZOS)
image.save(ROOT / "assets/brand/companion.png")
image.save(ROOT / "assets/brand/companion.ico", sizes=[(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
print("Created companion.png and companion.ico from the project brand artwork.")
