"""Rebuild local image derivatives with Pillow; never overwrite original assets."""
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/optimized"
CAPTURES = {
    "pipeline": "03_Pipeline_iPad_2048x2732.png",
    "dashboard": "01_Dashboard_iPhone_1290x2796.png",
    "contacts": "02_Contacts_iPhone_1290x2796.png",
    "calendrier": "06_Calendrier_iPhone_1290x2796.png",
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with Image.open(ROOT / "splash-icon.png") as logo:
        for size, name in [(48, "favicon-48"), (84, "logo-84"), (126, "logo-126")]:
            logo.resize((size, size), Image.Resampling.LANCZOS).save(
                OUT / f"{name}.png", optimize=True
            )
    for name, source in CAPTURES.items():
        with Image.open(ROOT / "capture" / source) as original:
            for width in (480, 800):
                height = round(original.height * width / original.width)
                original.resize((width, height), Image.Resampling.LANCZOS).save(
                    OUT / f"{name}-{width}.webp", lossless=True, method=6
                )
    # Reuse the existing product visual without cropping or inventing UI.
    with Image.open(ROOT / "app-hero.png") as original:
        preview = ImageOps.contain(original.convert("RGB"), (1200, 630), Image.Resampling.LANCZOS)
        social = Image.new("RGB", (1200, 630), "#10112f")
        social.paste(preview, ((1200 - preview.width) // 2, (630 - preview.height) // 2))
        social.save(OUT / "flownova-social.jpg", quality=92, subsampling=0, optimize=True)
    for path in sorted(OUT.iterdir()):
        with Image.open(path) as img:
            img.verify()
        print(f"{path.relative_to(ROOT)}: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
