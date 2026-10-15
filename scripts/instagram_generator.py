"""
=============================================================================
  GTA 6 AUTOMATION ENGINE — INSTAGRAM NEWS POST GENERATOR
  Creates professional 4:5 (1080x1350) Instagram news cards inspired by
  top gaming outlets (@thegamesgossip_, IGN, GameSpot, Rockstar Universe).
=============================================================================
"""

import os
import re
import math
import random
from datetime import datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from scripts.config import get_config
except ImportError:
    from config import get_config

# Import focal points & framing if available
try:
    from scripts.video_assembler import FOCAL_POINTS, detect_focal_point, get_font
except ImportError:
    FOCAL_POINTS = {}
    detect_focal_point = lambda img: (0.5, 0.45)
    def get_font(size: int, bold: bool = False):
        return get_ig_font(size, bold=bold)

@lru_cache(maxsize=64)
def get_ig_font(size: int, weight: str = None, bold: bool = None):
    """
    Loads unified typography from Windows system fonts:
    - 'black': Arial Black (ariblk.ttf) for ultra-punchy display headlines and hook badges.
    - 'bold': Arial Bold (arialbd.ttf) for cohesive editorial summary body text and badges.
    - 'medium': Segoe UI Semibold / Arial Bold for footer credit lines.
    - 'regular': Arial / Segoe UI for light copy.
    """
    if weight is None:
        if bold is False:
            weight = "regular"
        else:
            weight = "black"

    w_str = str(weight).lower()
    if w_str == "black":
        candidates = [
            "C:/Windows/Fonts/ariblk.ttf",
            "C:/Windows/Fonts/bahnschrift.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    elif w_str in ("bold", "semibold"):
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
    elif w_str == "medium":
        candidates = [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
    else:  # regular
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]

    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

# ── CANVAS CONSTANTS ───────────────────────────────────────────────────────────
IG_WIDTH = 1080
IG_HEIGHT = 1350  # 4:5 Instagram Portrait Feed Standard

# Keywords that should automatically get Electric Yellow highlight across any game
HIGHLIGHT_PATTERNS = [
    r'\b\d+\s*(?:MINUTES|MIN|HOURS|HOURS?|GB|FPS|DAYS?|WEEKS?|MONTHS?|YEARS?|K|P)\b',
    r'\b\$\d+[\w\.]*\b',
    r'\b(?:UNREAL\s*ENGINE\s*5|UE5|RAY\s*TRACING|DLSS\s*3|4K|60\s*FPS|120\s*FPS)\b',
    r'\b(?:ROCKSTAR\s*GAMES?|ROCKSTAR|PLAYSTATION|SONY|XBOX|NINTENDO|CD\s*PROJEKT\s*RED|FROM\s*SOFTWARE|BETHESDA|VALVE|STEAM)\b',
    r'\b(?:PC\s*VERSION|PC\s*RELEASE|PS5\s*PRO|PS5|XBOX\s*SERIES\s*X|SWITCH\s*2)\b',
    r'\b(?:LUCIA\s*(?:&|AND)\s*JASON|JASON\s*(?:&|AND)\s*LUCIA|LUCIA|JASON)\b',
    r'\b(?:GERALT|CIRL?|JIN\s*SAKAI|ATSUI?|ARTHUR\s*MORGAN|V|JOHNNY\s*SILVERHAND|DOOM\s*SLAYER)\b',
    r'\b(?:VICE\s*CITY|LEONIDA|NIGHT\s*CITY|THE\s*CONTINENT|ERDTREE)\b',
    r'\b(?:UNCENSORED|LEAKED?|CONFIRMED|DELAYED?|REVEALED?|CANCELLED?|ANNOUNCED?)\b',
    r'\b(?:RELEASE\s*DATE|FALL\s*2026|EARLY\s*2026|2025|2026|2027)\b',
    r'\b(?:MAP\s*SIZE|MAP\s*EXPANSION|BUDGET|GRAPHICS|COMBAT)\b',
    r'\b(?:MULTIPLAYER|CO-OP|CAMPAIGN|SINGLE\s*PLAYER|OPEN\s*WORLD)\b',
]


THEME_COLORS = {
    "vice": {
        "name": "Vice Neon",
        "highlight": (255, 230, 0),    # Electric Yellow
        "accent_hex": "#FFE600",
        "accent_rgb": (255, 230, 0),
        "glow_rgba": (255, 230, 0, 70),
        "hook": (255, 42, 109),        # Vice Pink
        "border": (0, 240, 255),       # Cyan
        "cat_fill": (255, 42, 109)
    },
    "sunset": {
        "name": "Miami Sunset",
        "highlight": (255, 183, 3),    # Warm Amber
        "accent_hex": "#FFB703",
        "accent_rgb": (255, 183, 3),
        "glow_rgba": (255, 183, 3, 70),
        "hook": (255, 107, 53),        # Sunset Orange
        "border": (157, 78, 221),      # Violet
        "cat_fill": (255, 107, 53)
    },
    "ocean": {
        "name": "Ocean Drive",
        "highlight": (254, 228, 64),   # Sun Yellow
        "accent_hex": "#FEE440",
        "accent_rgb": (254, 228, 64),
        "glow_rgba": (254, 228, 64, 70),
        "hook": (0, 245, 212),         # Aquamarine Teal
        "border": (0, 187, 249),       # Sky Blue
        "cat_fill": (0, 245, 212)
    },
    "gold": {
        "name": "Vice City Gold",
        "highlight": (255, 215, 0),    # Pure Gold
        "accent_hex": "#FFD700",
        "accent_rgb": (255, 215, 0),
        "glow_rgba": (255, 215, 0, 70),
        "hook": (217, 4, 41),          # Crimson
        "border": (255, 195, 0),       # Amber Gold
        "cat_fill": (217, 4, 41)
    }
}
THEME_PALETTES = THEME_COLORS


def find_highlight_spans(text: str, custom_keywords: list = None) -> list:
    """Finds (start, end) index spans for words that should be highlighted."""
    if not text:
        return []
    text = str(text)
    spans = []
    if custom_keywords is not None:
        if isinstance(custom_keywords, str):
            custom_keywords = [custom_keywords]
        # User explicitly specified keywords/chips from UI -> honor user choice 1:1!
        patterns = []
        for kw in custom_keywords:
            if kw is not None and str(kw).strip():
                k_clean = str(kw).strip().upper()
                pre = r'\b' if k_clean[0].isalnum() else r'(?<!\w)'
                post = r'\b' if k_clean[-1].isalnum() else r'(?!\w)'
                patterns.append(pre + re.escape(k_clean) + post)
    else:
        # CLI / Auto Mode fallback -> use automatic viral pattern heuristics
        patterns = list(HIGHLIGHT_PATTERNS)

    upper_text = text.upper()
    for pat in patterns:
        for m in re.finditer(pat, upper_text):
            spans.append((m.start(), m.end()))

    # Also highlight text wrapped in curly braces like {THIS}
    for m in re.finditer(r'\{([^}]+)\}', text):
        spans.append((m.start(), m.end()))

    # Merge overlapping spans
    if not spans:
        return []
    spans.sort(key=lambda s: s[0])
    merged = [spans[0]]
    for cur in spans[1:]:
        prev_s, prev_e = merged[-1]
        if cur[0] <= prev_e:
            merged[-1] = (prev_s, max(prev_e, cur[1]))
        else:
            merged.append(cur)
    return merged


def get_available_screenshots(base_dir: str = None) -> list:
    """Collects all 4K screenshots available in the assets directory, including game subfolders."""
    if not base_dir:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    shot_dir = os.path.join(base_dir, "assets", "backgrounds")
    if not os.path.exists(shot_dir):
        return []
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    shots = []
    for root, _, files in os.walk(shot_dir):
        for f in files:
            if os.path.splitext(f)[1].lower() in valid_exts:
                shots.append(os.path.join(root, f))
    return sorted(shots)


def pick_smart_background(headline: str, summary: str = "", game_title: str = "GTA VI", base_dir: str = None) -> str:
    """Intelligently matches script keywords to the most relevant 4K screenshot for ANY video game."""
    try:
        from scripts.game_image_fetcher import fetch_game_images_on_demand, find_best_matching_image
    except ImportError:
        from game_image_fetcher import fetch_game_images_on_demand, find_best_matching_image

    game_clean = (game_title or "GTA VI").strip()
    shots = fetch_game_images_on_demand(game_clean, target_count=16, base_dir=base_dir)
    if not shots:
        return None

    best = find_best_matching_image(shots, headline, summary, game_clean)
    if best and best.get("path") and os.path.exists(best["path"]):
        return best["path"]

    return shots[0]["path"] if shots else None


def crop_to_4_5(image: Image.Image, focal_x: float = 0.5, focal_y: float = 0.45) -> Image.Image:
    """Crops a widescreen image to 4:5 (1080x1350) centered around the focal point."""
    target_ratio = IG_WIDTH / IG_HEIGHT  # 0.8
    orig_w, orig_h = image.size
    orig_ratio = orig_w / orig_h

    if orig_ratio > target_ratio:
        # Image is wider than 4:5 -> crop horizontal width
        crop_h = orig_h
        crop_w = int(orig_h * target_ratio)
        ideal_cx = int(orig_w * focal_x)
        left = max(0, min(orig_w - crop_w, ideal_cx - crop_w // 2))
        top = 0
        right = left + crop_w
        bottom = crop_h
    else:
        # Image is taller than 4:5 -> crop vertical height
        crop_w = orig_w
        crop_h = int(orig_w / target_ratio)
        ideal_cy = int(orig_h * focal_y)
        left = 0
        top = max(0, min(orig_h - crop_h, ideal_cy - crop_h // 2))
        right = crop_w
        bottom = top + crop_h

    cropped = image.crop((left, top, right, bottom))
    return cropped.resize((IG_WIDTH, IG_HEIGHT), Image.Resampling.LANCZOS)


def create_gradient_vignette() -> Image.Image:
    """
    Creates a master cinematic gradient overlay:
    - Subtle top vignette (for top badges & creator handle).
    - Deep, rich bottom vignette (from y=480 down to 1350) ensuring 100% text contrast.
    """
    overlay = Image.new("RGBA", (IG_WIDTH, IG_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Top gradient (0 -> 240px, max alpha 160)
    for y in range(240):
        alpha = int(160 * ((240 - y) / 240.0) ** 1.3)
        draw.line([(0, y), (IG_WIDTH, y)], fill=(6, 8, 14, alpha))

    # Bottom gradient: start at y=480, smooth multi-stop fade to deep velvet black
    y_start = 480
    for y in range(y_start, IG_HEIGHT):
        progress = (y - y_start) / float(IG_HEIGHT - y_start)
        if progress < 0.38:
            alpha = int(255 * (0.65 * (progress / 0.38) ** 1.15))
        else:
            p2 = (progress - 0.38) / 0.62
            alpha = int(255 * (0.65 + 0.34 * (p2 ** 0.85)))
        alpha = max(0, min(252, alpha))
        draw.line([(0, y), (IG_WIDTH, y)], fill=(6, 8, 14, alpha))

    return overlay


def wrap_text_with_highlights(
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    custom_keywords: list = None
) -> list:
    """
    Wraps text into lines and tokenizes each word into (word, is_highlighted)
    while preserving natural spacing and line bounds.
    """
    # Clean text if wrapped in curly braces
    clean_text = text.replace("{", "").replace("}", "").strip()
    highlight_spans = find_highlight_spans(clean_text, custom_keywords)

    words = clean_text.split()
    tokens = []
    cursor = 0
    for w in words:
        w_start = clean_text.find(w, cursor)
        w_end = w_start + len(w)
        cursor = w_end

        # Check if word falls in any highlight span
        is_hl = any(not (w_end <= s or w_start >= e) for s, e in highlight_spans)
        tokens.append((w, is_hl))

    # Line wrapping by tokens
    dummy_img = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(dummy_img)
    space_w = d.textbbox((0, 0), " ", font=font)[2]

    lines = []
    current_line = []
    current_w = 0

    for token in tokens:
        word, is_hl = token
        bbox = d.textbbox((0, 0), word, font=font)
        word_w = bbox[2] - bbox[0]

        needed = word_w if not current_line else current_w + space_w + word_w
        if needed <= max_width:
            current_line.append(token)
            current_w = needed
        else:
            if current_line:
                lines.append(current_line)
            current_line = [token]
            current_w = word_w

    if current_line:
        lines.append(current_line)

    return lines


def draw_styled_headline(
    draw: ImageDraw.ImageDraw,
    lines: list,
    font: ImageFont.ImageFont,
    start_y: int,
    highlight_color: tuple = (255, 230, 0),  # Electric Yellow
    default_color: tuple = (255, 255, 255),  # Crisp White
    stroke_color: tuple = (0, 0, 0),
    stroke_width: int = 3,
    line_spacing: int = 16,
    align: str = "center"
) -> int:
    """Draws tokenized lines with per-word highlighting and returns bottom Y coordinate."""
    dummy_img = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(dummy_img)
    space_w = d.textbbox((0, 0), " ", font=font)[2]
    line_h = d.textbbox((0, 0), "Ag", font=font)[3]

    cur_y = start_y
    for line in lines:
        # Calculate total line width
        line_w = 0
        for i, (word, _) in enumerate(line):
            bbox = d.textbbox((0, 0), word, font=font)
            line_w += (bbox[2] - bbox[0])
            if i < len(line) - 1:
                line_w += space_w

        if align == "center":
            cur_x = (IG_WIDTH - line_w) // 2
        else:
            cur_x = 60  # Left margin

        for i, (word, is_hl) in enumerate(line):
            fill = highlight_color if is_hl else default_color
            bbox = d.textbbox((0, 0), word, font=font)
            word_w = bbox[2] - bbox[0]

            # Text shadow for extra depth
            draw.text(
                (cur_x + 3, cur_y + 3),
                word,
                font=font,
                fill=(0, 0, 0, 180),
                stroke_width=stroke_width,
                stroke_fill=(0, 0, 0, 200)
            )

            # Main text
            draw.text(
                (cur_x, cur_y),
                word,
                font=font,
                fill=fill,
                stroke_width=stroke_width,
                stroke_fill=stroke_color
            )

            cur_x += word_w + space_w

        cur_y += line_h + line_spacing

    return cur_y - line_spacing


def generate_instagram_post(
    headline: str,
    summary: str = "",
    game_title: str = "GTA VI",
    category: str = "LEAKS & RUMORS",
    hook_word: str = None,
    background_path: str = None,
    output_path: str = None,
    source_credit: str = "ROCKSTAR INTEL",
    creator_handle: str = None,
    custom_keywords: list = None,
    theme_name: str = "vice",
    focal_x: float = None,
    focal_y: float = None
) -> dict:
    """
    Generates a complete, ready-to-post 4:5 Instagram feed post image for ANY video game.
    Returns metadata including output file path, dimensions, and ready-to-copy caption.
    """
    cfg = get_config()
    if not creator_handle:
        creator_handle = cfg.get("branding", {}).get("creator_handle", "@SamWithJoystick")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    game_clean = (game_title or "GTA VI").strip().upper()

    t_cfg = THEME_COLORS.get((theme_name or "vice").lower(), THEME_COLORS["vice"])


    # 1. Select & crop background (smart semantic matching for ANY game)
    if not background_path or not os.path.exists(background_path):
        try:
            background_path = pick_smart_background(headline, summary, game_clean, base_dir)
        except Exception as e:
            print(f"Smart background selection error: {e}")

    base_canvas = None
    if background_path and os.path.exists(background_path):
        try:
            bg_img = Image.open(background_path).convert("RGB")
            # Check focal point
            fname = os.path.basename(background_path)
            fx, fy = None, None
            if focal_x is not None and focal_y is not None:
                try:
                    fx, fy = float(focal_x), float(focal_y)
                    if not (0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0):
                        fx, fy = None, None
                except (ValueError, TypeError):
                    fx, fy = None, None
            if fx is None or fy is None:
                if fname in FOCAL_POINTS:
                    fx, fy = FOCAL_POINTS[fname]
                else:
                    fx, fy = detect_focal_point(bg_img)
            base_canvas = crop_to_4_5(bg_img, fx, fy)
        except Exception as e:
            print(f"[instagram_generator] Warning loading background {background_path}: {e}")
            base_canvas = None

    if base_canvas is None:
        # Fallback dark gradient canvas
        base_canvas = Image.new("RGB", (IG_WIDTH, IG_HEIGHT), (15, 17, 24))

    # 2. Apply cinematic vignettes
    vignette = create_gradient_vignette()
    base_canvas.paste(vignette, (0, 0), vignette)

    draw = ImageDraw.Draw(base_canvas)

    # 3. TOP BRANDING: SYMMETRICAL TWIN CAPSULES (EXACT SAME FONT SIZE & EXACT SAME HEIGHT)
    bar_font = get_ig_font(20, bold=True)
    bar_h = 38
    bar_y1 = 54
    bar_y2 = bar_y1 + bar_h
    bar_cy = (bar_y1 + bar_y2) // 2
    pad_h = 18

    # Left Badge: Game Title [ ● GAME_TITLE ]
    game_tw = draw.textbbox((0, 0), game_clean, font=bar_font)[2]
    g_x1 = 54
    g_x2 = g_x1 + 16 + 10 + game_tw + pad_h

    draw.rounded_rectangle(
        [(g_x1, bar_y1), (g_x2, bar_y2)],
        radius=12,
        fill=(10, 12, 18, 220),
        outline=(255, 255, 255, 45),
        width=2
    )
    # Glowing Dot (Cyan or Theme Border)
    draw.ellipse([(g_x1 + 16 - 4, bar_cy - 4), (g_x1 + 16 + 4, bar_cy + 4)], fill=t_cfg["border"])
    draw.text((g_x1 + 16 + 10, bar_cy), game_clean, font=bar_font, fill=(255, 255, 255), anchor="lm")

    # Right Badge: Creator Watermark [ @CREATOR_HANDLE ] (EXACT SAME FONT, EXACT SAME HEIGHT)
    brand_text = creator_handle.upper()
    brand_tw = draw.textbbox((0, 0), brand_text, font=bar_font)[2]
    b_pill_x2 = IG_WIDTH - 54
    b_pill_x1 = b_pill_x2 - brand_tw - (pad_h * 2)

    draw.rounded_rectangle(
        [(b_pill_x1, bar_y1), (b_pill_x2, bar_y2)],
        radius=12,
        fill=(10, 12, 18, 220),
        outline=(255, 255, 255, 45),
        width=2
    )
    draw.text(((b_pill_x1 + b_pill_x2) // 2, bar_cy), brand_text, font=bar_font, fill=(255, 255, 255), anchor="mm")

    # 4. HOOK WORD (e.g., "CYBERLEAK", "CONFIRMED", "LEAKED", "REVEALED")
    if not hook_word:
        upper_hl = headline.upper()
        if "LEAK" in upper_hl:
            hook_word = "LEAKED"
        elif "CONFIRM" in upper_hl or "OFFICIAL" in upper_hl:
            hook_word = "CONFIRMED"
        elif "DELAY" in upper_hl:
            hook_word = "DELAYED?"
        elif "TRAILER 2" in upper_hl:
            hook_word = "TRAILER 2"
        elif "ROCKSTAR" in upper_hl:
            hook_word = "ROCKSTAR GAMES"
        elif "MAP" in upper_hl:
            hook_word = "MAP REVEAL"

    # 5. HEADLINE PREPARATION (ARIAL BLACK / MONTSERRAT 900)
    headline_clean = headline.strip().upper()
    if len(headline_clean) < 55:
        head_font_size = 48
        line_spacing = 10
    elif len(headline_clean) < 95:
        head_font_size = 42
        line_spacing = 10
    else:
        head_font_size = 36
        line_spacing = 8

    head_font = get_ig_font(head_font_size, bold=True)
    wrapped_lines = wrap_text_with_highlights(
        headline_clean,
        head_font,
        max_width=970,
        custom_keywords=custom_keywords
    )

    # 6. SUMMARY CONTEXT PREPARATION (ARIAL BOLD 24PT — CLEAN EDITORIAL WEIGHT)
    sum_lines = []
    if summary and summary.strip():
        sum_font = get_ig_font(24, weight="bold")
        words = summary.strip().split()
        cur_sl = []
        for w in words:
            test = " ".join(cur_sl + [w])
            if draw.textbbox((0, 0), test, font=sum_font)[2] <= 950:
                cur_sl.append(w)
            else:
                if cur_sl:
                    sum_lines.append(" ".join(cur_sl))
                cur_sl = [w]
            if len(sum_lines) >= 2:
                break
        if cur_sl and len(sum_lines) < 2:
            sum_lines.append(" ".join(cur_sl))

    # 7. UNIFIED VERTICAL STACK CALCULATION (PERFECT BREATHING ROOM!)
    hook_h = 36 if hook_word else 0
    hook_gap = 10 if hook_word else 0  # Tight, intentional 10px gap to headline
    headline_h = len(wrapped_lines) * (head_font_size + line_spacing)
    sum_gap = 22 if sum_lines else 0  # 22px clear breathing room between headline and summary
    sum_line_h = 34  # Comfortable editorial line height
    sum_h = (len(sum_lines) * sum_line_h) if sum_lines else 0
    footer_gap = 36  # Generous 36px breathing room between summary and footer credit!
    target_footer_y = 1295

    # Calculate stack start so footer has guaranteed clearance and text sits in lower third
    if sum_lines:
        target_summary_bottom = target_footer_y - footer_gap
        target_summary_start = target_summary_bottom - sum_h
        target_headline_bottom = target_summary_start - sum_gap
        target_headline_start = target_headline_bottom - headline_h
        target_hook_start = target_headline_start - hook_gap - hook_h
    else:
        target_headline_bottom = target_footer_y - 48
        target_headline_start = target_headline_bottom - headline_h
        target_hook_start = target_headline_start - hook_gap - hook_h

    # Ensure stack doesn't overlap top branding
    start_stack_y = max(740, target_hook_start if hook_word else target_headline_start)

    current_y = start_stack_y

    # A. Draw Hook Word (directly above headline)
    if hook_word:
        hook_font = get_ig_font(22, weight="black")
        hook_clean = hook_word.strip().upper()
        hook_w = draw.textbbox((0, 0), hook_clean, font=hook_font)[2]
        hk_pad_x = 18
        hk_x1 = (IG_WIDTH - hook_w) // 2 - hk_pad_x
        hk_x2 = hk_x1 + hook_w + (hk_pad_x * 2)
        hk_y1 = current_y
        hk_y2 = hk_y1 + hook_h

        draw.rounded_rectangle(
            [(hk_x1, hk_y1), (hk_x2, hk_y2)],
            radius=10,
            fill=(12, 14, 22),
            outline=t_cfg["hook"],
            width=2
        )
        draw.text(
            ((hk_x1 + hk_x2) // 2, (hk_y1 + hk_y2) // 2),
            hook_clean,
            font=hook_font,
            fill=t_cfg["hook"],
            anchor="mm"
        )
        current_y = hk_y2 + hook_gap  # Exactly 10px below hook badge!

    # B. Draw Headline (starts immediately at current_y)
    bottom_y = draw_styled_headline(
        draw=draw,
        lines=wrapped_lines,
        font=head_font,
        start_y=current_y,
        highlight_color=t_cfg["highlight"],
        default_color=(255, 255, 255),
        stroke_color=(0, 0, 0),
        stroke_width=2,
        line_spacing=line_spacing,
        align="center"
    )

    # C. Draw Summary (cleanly separated below headline)
    if sum_lines:
        sum_y = bottom_y + sum_gap
        for sline in sum_lines:
            s_w = draw.textbbox((0, 0), sline, font=sum_font)[2]
            s_x = (IG_WIDTH - s_w) // 2
            # Drop shadow
            draw.text((s_x + 2, sum_y + 2), sline, font=sum_font, fill=(0, 0, 0, 220), stroke_width=2, stroke_fill=(0, 0, 0))
            # Text
            draw.text((s_x, sum_y), sline, font=sum_font, fill=(230, 235, 245), stroke_width=1, stroke_fill=(0, 0, 0))
            sum_y += sum_line_h
        summary_end_y = sum_y
    else:
        summary_end_y = bottom_y

    # 8. FOOTER CREDIT BAR (SLEEK ARIAL BOLD 17PT — NEVER CROWDED)
    footer_font = get_ig_font(17, weight="bold")
    footer_text = f"VIA: {source_credit.upper()}  •  FOLLOW {creator_handle.upper()} FOR DAILY {game_clean} UPDATES"
    actual_footer_y = max(target_footer_y, summary_end_y + 26)
    draw.text((IG_WIDTH // 2, actual_footer_y), footer_text, font=footer_font, fill=(160, 170, 185), stroke_width=1, stroke_fill=(0, 0, 0), anchor="mm")

    # 8. SAVE IMAGE
    if not output_path:
        out_dir = os.path.join(base_dir, "output")
        os.makedirs(out_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug_clean = re.sub(r'[^a-zA-Z0-9]+', '_', game_clean.lower()).strip('_')
        output_path = os.path.join(out_dir, f"{slug_clean}_post_{timestamp}.png")

    base_canvas.save(output_path, "PNG", quality=95)

    # 9. GENERATE READY-TO-PASTE INSTAGRAM CAPTION
    game_tag = re.sub(r'[^a-zA-Z0-9]', '', game_clean.title())
    base_tags = [f"#{game_tag}", f"#{game_tag}News", "#GamingNews", "#GamingCommunity", "#Gamer", "#VideoGames"]

    g_lower = game_clean.lower()
    if "gta" in g_lower or "grand theft" in g_lower:
        base_tags.extend(["#GTA6", "#RockstarGames", "#ViceCity", "#GTA6Leaks"])
    elif "witcher" in g_lower:
        base_tags.extend(["#TheWitcher", "#Witcher4", "#CDProjektRed", "#GeraltOfRivia"])
    elif "cyberpunk" in g_lower:
        base_tags.extend(["#Cyberpunk2077", "#CDProjektRed", "#NightCity"])
    elif "ghost of" in g_lower or "yotei" in g_lower:
        base_tags.extend(["#GhostOfYotei", "#GhostOfTsushima", "#PlayStation", "#PS5"])
    elif "elden" in g_lower:
        base_tags.extend(["#EldenRing", "#FromSoftware", "#ShadowOfTheErdtree"])
    elif "wolverine" in g_lower:
        base_tags.extend(["#MarvelsWolverine", "#InsomniacGames", "#PlayStation5"])
    elif "black ops" in g_lower or "call of duty" in g_lower:
        base_tags.extend(["#CallOfDuty", "#BlackOps6", "#Activision"])
    elif "doom" in g_lower:
        base_tags.extend(["#DoomTheDarkAges", "#idSoftware", "#Bethesda"])

    caption = (
        f"🚨 BREAKING: {headline_clean.title()}!\n\n"
        f"{summary if summary else f'New details and reports have surfaced regarding {game_clean}. Here is the full breakdown.'}\n\n"
        f"Source: {source_credit}\n"
        f"Follow {creator_handle} for daily {game_clean} news & gaming updates.\n\n"
        f"What are your thoughts on this? Let us know in the comments below! 👇\n\n"
        f"{' '.join(base_tags)}"
    )

    return {
        "success": True,
        "image_path": output_path,
        "width": IG_WIDTH,
        "height": IG_HEIGHT,
        "caption": caption,
        "background_used": background_path,
        "headline": headline_clean,
        "category": category,
        "game_title": game_clean,
        "source": source_credit
    }


if __name__ == "__main__":
    test_headline = "CYBERLEAK CONFIRMS 25 MINUTES OF UNCENSORED GTA 6 GAMEPLAY FEATURING LUCIA & JASON"
    test_summary = "Internal development footage surfaces online showing realistic vehicle physics and new Vice City map details."
    res = generate_instagram_post(
        headline=test_headline,
        summary=test_summary,
        category="EXCLUSIVE LEAK",
        source_credit="ROCKSTAR INTEL"
    )
    print("Generated Instagram post successfully at:", res["image_path"])
    print("\n--- INSTAGRAM CAPTION ---\n")
    print(res["caption"].encode("ascii", "replace").decode("ascii"))
