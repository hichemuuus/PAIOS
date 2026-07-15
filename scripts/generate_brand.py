"""Generate Veyron brand identity — SVG logo, PNG icons, favicon, tray icon, Windows ICO."""

from PIL import Image, ImageDraw, ImageFont
import os, math

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public")
ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "src-tauri", "icons")
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(ICONS_DIR, exist_ok=True)

# ── Colour palette ──────────────────────────────────────────────
GOLD       = (212, 168, 75)
GOLD_LIGHT = (232, 200, 120)
DARK       = (18, 18, 28)
DARK_SURF  = (28, 28, 42)
WHITE      = (245, 242, 237)
DIM        = (120, 115, 110)

def draw_veyron_mark(draw, cx, cy, size):
    """Draw the geometric V-mark centred at (cx, cy) with given size."""
    # The mark: two thick bars forming a V with a crisp cut
    t = max(size * 0.18, 2)        # bar thickness
    gap = size * 0.08              # gap between bars at top
    h = size * 0.85                # overall height
    w = size * 0.90                # overall width

    # Left bar (top-left to bottom-centre)
    x1 = cx - w / 2
    y1 = cy - h / 2 + gap
    x2 = cx
    y2 = cy + h / 2 - gap * 1.5

    # Right bar (top-right to bottom-centre, shorter tip for asymmetry)
    x3 = cx + w / 2
    y3 = cy - h / 2 + gap
    x4 = cx + t * 0.3
    y4 = cy + h / 2 - gap * 1.5

    left_pts = [
        (x1, y1),
        (x1 + t, y1 + t * 0.3),
        (x2 - t * 0.8, y2 - t * 0.3),
        (x2 - t * 0.3, y2),
        (x2 + t * 0.3, y2 - t * 0.2),
        (x3 - t, y3 + t * 0.3),
        (x3, y3 + gap),
        (x3 - t, y3 + t),
        (x2 + t * 0.5, y2 - t * 0.5),
        (x2 - t * 0.5, y2 + t * 0.2),
        (x1 + t * 0.3, y1 + t),
    ]

    # Draw gradient-like effect with gold
    draw.polygon(left_pts, fill=GOLD, outline=None)
    # Accent highlight on left bar
    hl = [
        (x1 + t * 0.15, y1 + t * 0.3),
        (x2 - t * 0.5, y2 - t * 0.3),
        (x2 - t * 0.6, y2 - t * 0.1),
        (x1 + t * 0.05, y1 + t * 0.6),
    ]
    draw.polygon(hl, fill=GOLD_LIGHT, outline=None)


def create_svg_logo(path, size=512):
    """Write an SVG version of the Veyron mark + wordmark."""
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
  <defs>
    <linearGradient id="v-gold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#e8c878"/>
      <stop offset="100%" stop-color="#d4a84b"/>
    </linearGradient>
  </defs>
  <rect width="{size}" height="{size}" rx="{size//6}" fill="#12121c"/>
  <!-- Geometric V-mark -->
  <path d="M {size*0.22} {size*0.35}
           L {size*0.30} {size*0.30}
           L {size*0.50} {size*0.72}
           L {size*0.70} {size*0.30}
           L {size*0.78} {size*0.35}
           L {size*0.52} {size*0.80}
           Z"
        fill="url(#v-gold)"/>
</svg>'''
    with open(path, "w") as f:
        f.write(svg)
    return path


def create_svg_favicon(path):
    """Simple V-mark favicon."""
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <defs>
    <linearGradient id="v-gold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#e8c878"/>
      <stop offset="100%" stop-color="#d4a84b"/>
    </linearGradient>
  </defs>
  <rect width="32" height="32" rx="6" fill="#12121c"/>
  <path d="M 7 11 L 10 9 L 16 23 L 22 9 L 25 11 L 17 26 Z" fill="url(#v-gold)"/>
</svg>'''
    with open(path, "w") as f:
        f.write(svg)
    return path


def create_png_icons():
    """Generate PNG icons at all required sizes."""
    sizes = [(32, "32x32.png"), (128, "128x128.png"), (256, "128x128@2x.png"),
             (16, "tray-icon.png"), (64, "favicon-64.png"), (192, "favicon-192.png")]

    outputs = []
    for size, name in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        pad = max(size // 12, 1)
        # Dark rounded-square background
        r = (size - 2 * pad)
        draw_rounded_rect(draw, pad, pad, pad + r, pad + r, max(size // 6, 2), (18, 18, 28, 255))
        # V-mark
        draw_veyron_mark(draw, size // 2, size // 2, size * 0.7)
        path = os.path.join(ICONS_DIR, name)
        img.save(path, "PNG")
        outputs.append(path)
        # Also copy favicon-64 and favicon-192 to public/
        if "favicon" in name:
            pub_path = os.path.join(ASSETS_DIR, name)
            img.save(pub_path, "PNG")
            outputs.append(pub_path)
    return outputs


def create_png_splash(size=(800, 600)):
    """Generate a splash screen with Veyron mark."""
    img = Image.new("RGBA", size, DARK + (255,))
    draw = ImageDraw.Draw(img)
    # Centre mark
    mark_size = min(size) * 0.25
    draw_veyron_mark(draw, size[0] // 2, size[1] // 2 - 20, mark_size)
    return img


def create_welcome_illustration(size=(600, 400)):
    """Generate a welcome illustration — abstract geometric composition."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size[0] // 2, size[1] // 2
    # Abstract glow circles
    for r, alpha in [(180, 8), (120, 15), (70, 25)]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD + (alpha,))
    # Central V-mark
    draw_veyron_mark(draw, cx, cy, min(size) * 0.25)
    # Small accent dots
    for angle in [30, 90, 150, 210, 270, 330]:
        rad = math.radians(angle)
        dx = int(math.cos(rad) * 140)
        dy = int(math.sin(rad) * 140)
        dr = 3
        draw.ellipse([cx + dx - dr, cy + dy - dr, cx + dx + dr, cy + dy + dr],
                     fill=GOLD_LIGHT + (40,))
    return img


def create_empty_state(size=(400, 300)):
    """Generate an empty state illustration."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size[0] // 2, size[1] // 2
    # Subtle circle
    draw.ellipse([cx - 80, cy - 80, cx + 80, cy + 80], fill=GOLD + (10,))
    # Small V-mark
    draw_veyron_mark(draw, cx, cy, 60)
    return img


def draw_rounded_rect(draw, x1, y1, x2, y2, r, fill):
    """Draw a rounded rectangle."""
    draw.rounded_rectangle([x1, y1, x2, y2], radius=r, fill=fill)


def create_ico():
    """Create Windows .ico file."""
    sizes = [(32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    imgs = []
    for w, h in sizes:
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        pad = max(w // 16, 1)
        r = max(w // 6, 2)
        draw_rounded_rect(draw, pad, pad, w - pad, h - pad, r, DARK + (255,))
        draw_veyron_mark(draw, w // 2, h // 2, w * 0.65)
        imgs.append(img)
    ico_path = os.path.join(ICONS_DIR, "icon.ico")
    imgs[0].save(ico_path, format="ICO", sizes=[(w, h) for w, h in sizes],
                 append_images=imgs[1:])
    return ico_path


if __name__ == "__main__":
    # SVG
    logo_svg = create_svg_logo(os.path.join(ASSETS_DIR, "veyron-logo.svg"))
    fav_svg = create_svg_favicon(os.path.join(ASSETS_DIR, "favicon.svg"))
    print(f"SVG logo: {logo_svg}")
    print(f"SVG favicon: {fav_svg}")

    # PNG icons
    pngs = create_png_icons()
    for p in pngs:
        print(f"PNG icon: {p}")

    # ICO
    ico = create_ico()
    print(f"ICO: {ico}")

    # Splash / welcome / empty-state
    splash = create_png_splash()
    splash_path = os.path.join(ASSETS_DIR, "veyron-splash.png")
    splash.save(splash_path, "PNG")
    print(f"Splash: {splash_path}")

    welcome = create_welcome_illustration()
    welcome_path = os.path.join(ASSETS_DIR, "veyron-welcome.png")
    welcome.save(welcome_path, "PNG")
    print(f"Welcome: {welcome_path}")

    empty = create_empty_state()
    empty_path = os.path.join(ASSETS_DIR, "veyron-empty.png")
    empty.save(empty_path, "PNG")
    print(f"Empty state: {empty_path}")

    print("\nAll assets generated.")
