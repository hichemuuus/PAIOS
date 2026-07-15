"""Generate Veyron app icons at required sizes."""

from PIL import Image, ImageDraw
import os

ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "src-tauri", "icons")

def create_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = max(size // 16, 2)
    cx = cy = size // 2
    r = (size // 2) - pad
    # Glowing blue circle
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        fill=(30, 120, 220, 255),
    )
    # Inner subtle glow
    inner_r = r - max(size // 12, 1)
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        fill=(60, 150, 240, 80),
    )
    # White "V" shape
    v_points = [
        (size * 0.30, size * 0.30),
        (size * 0.30, size * 0.38),
        (size * 0.50, size * 0.72),
        (size * 0.70, size * 0.38),
        (size * 0.70, size * 0.30),
        (size * 0.50, size * 0.65),
    ]
    draw.polygon(v_points, fill=(255, 255, 255, 255))
    # Small accent dot (eyes)
    dot_r = max(size // 40, 1)
    draw.ellipse(
        [cx - dot_r * 3, cy - r * 0.6 - dot_r, cx - dot_r * 3 + dot_r * 2, cy - r * 0.6 + dot_r],
        fill=(255, 255, 255, 180),
    )
    return img


def create_ico(sizes=(32, 64, 128, 256)):
    """Create a Windows .ico file from multiple PNG-sized frames."""
    icons_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "src-tauri", "icons")
    imgs = [create_icon(s).resize((s, s), Image.LANCZOS) for s in sizes]
    first = imgs[0]
    ico_path = os.path.join(icons_dir, "icon.ico")
    first.save(ico_path, format="ICO", sizes=[(s, s) for s in sizes], append_images=imgs[1:])
    return ico_path


if __name__ == "__main__":
    os.makedirs(ICONS_DIR, exist_ok=True)
    # Generate PNG icons
    for size, name in [(32, "32x32.png"), (128, "128x128.png"), (256, "128x128@2x.png")]:
        img = create_icon(size)
        path = os.path.join(ICONS_DIR, name)
        img.save(path, "PNG")
        print(f"Created {path} ({size}x{size})")
    # Generate ICO for Windows
    ico_path = create_ico()
    print(f"Created {ico_path}")
    # Generate tray icon (16x16, simple)
    tray = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tray)
    draw.ellipse([0, 0, 15, 15], fill=(30, 120, 220, 255))
    draw.polygon([(4, 4), (4, 6), (8, 13), (12, 6), (12, 4), (8, 11)], fill=(255, 255, 255, 255))
    tray_path = os.path.join(ICONS_DIR, "tray-icon.png")
    tray.save(tray_path, "PNG")
    print(f"Created {tray_path} (16x16)")
    print("Done generating icons.")
