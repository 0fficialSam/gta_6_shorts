"""
GTA 6 Video Assembler - High-Performance Streaming Pipeline
===========================================================
- ZERO per-frame disk I/O (no temp JPEGs)
- Direct memory-to-FFmpeg rawvideo pipe (< 30s render time)
- Single-pass continuous video background decoding with infinite loop & auto-cropping
- Hardware-accelerated encoding auto-detection (NVENC -> Windows Media Foundation -> libx264 ultrafast)
- Pre-cached procedural Vice City graphics & font rendering
"""
import json, os, sys, re, glob, subprocess, shutil, time, math, hashlib, random
from datetime import datetime, date as _date
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

try:
    from scripts.config import get_target_launch_date, get_video_settings, get_creator_handle
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.config import get_target_launch_date, get_video_settings, get_creator_handle

_vid_cfg = get_video_settings()
WIDTH, HEIGHT, FPS = _vid_cfg.get("width", 1080), _vid_cfg.get("height", 1920), _vid_cfg.get("fps", 30)

# ── COUNTDOWN CONFIG ───────────────────────────────────────────────────────────
COUNTDOWN_PHRASES = [
    "{n} DAYS UNTIL GTA 6 DROPS!",
    "GTA 6 IN {n} DAYS — ARE YOU READY?",
    "ONLY {n} DAYS LEFT. GET HYPED.",
    "{n} DAYS TO THE BIGGEST GAME EVER.",
    "T-MINUS {n} DAYS TO GTA 6!",
    "THE WAIT IS ALMOST OVER — {n} DAYS",
    "{n} MORE DAYS. ROCKSTAR IS COMING.",
    "GTA 6 LAUNCHES IN {n} DAYS!",
    "JUST {n} DAYS UNTIL GTA 6. INSANE.",
    "{n} DAYS LEFT. YOUR BODY IS READY?",
]


def get_days_left() -> int:
    today = _date.today()
    delta = get_target_launch_date() - today
    return delta.days


def get_countdown_text(days: int) -> str:
    if days <= 0:
        return "GTA 6 IS OUT NOW — GET IT!"
    # Seed by date for consistent daily phrase
    seed_str = str(_date.today())
    seed_val = sum(ord(c) for c in seed_str)
    phrase = COUNTDOWN_PHRASES[seed_val % len(COUNTDOWN_PHRASES)]
    return phrase.replace("{n}", str(days))


# ── FONT CACHE ─────────────────────────────────────────────────────────────────
@lru_cache(maxsize=64)
def get_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf"  if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/verdanab.ttf" if bold else "C:/Windows/Fonts/verdana.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                pass
    return ImageFont.load_default()


def stroke_text(draw, text, x, y, font, fill=(255, 255, 255), sfill=(0, 0, 0), sw=3, anchor="mm"):
    draw.text((x, y), text, font=font, fill=fill, stroke_width=sw, stroke_fill=sfill, anchor=anchor)



def wrap_draw(draw, text, cx, cy, font, fill=(255, 255, 255), sfill=(0, 0, 0), sw=3, max_w=960, lsp=14):
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))

    lh = draw.textbbox((0, 0), "Ag", font=font)[3] + lsp
    sy = cy - (lh * len(lines)) // 2
    for i, line in enumerate(lines):
        stroke_text(draw, line, cx, sy + i * lh, font, fill, sfill, sw, "mm")


# ── KINETIC WORD-LEVEL SUBTITLE ENGINE ─────────────────────────────────────────
def prepare_kinetic_chunks(subtitles_timing: list, raw_script: str, audio_dur: float, cover_dur: float = 0.0) -> list:
    """
    Transforms speech-timed sentences into punchy 2-3 word kinetic chunks
    with exact per-word start and end timestamps.
    """
    usable_dur = max(audio_dur - cover_dur, 1.0)
    entries = []

    if subtitles_timing:
        entries = subtitles_timing
    else:
        raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', raw_script) if s.strip()]
        if not raw_sentences:
            raw_sentences = [raw_script[:80]]
        total_chars = max(sum(len(s) for s in raw_sentences), 1)
        cur_t = 0.0
        for s in raw_sentences:
            dur = (len(s) / total_chars) * usable_dur
            entries.append({
                "text": s,
                "start": round(cur_t, 3),
                "end": round(cur_t + dur, 3),
                "duration": round(dur, 3)
            })
            cur_t += dur

    chunks = []
    font = get_font(74, bold=True)
    temp_img = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(temp_img)

    for entry in entries:
        words = entry["text"].strip().split()
        if not words:
            continue
        sum_chars = max(sum(len(w) for w in words), 1)
        s_start = entry["start"]
        s_end = entry["end"]
        s_dur = max(s_end - s_start, 0.1)

        wt = []
        cur_w_t = s_start
        for w in words:
            w_dur = (len(w) / sum_chars) * s_dur
            wt.append({
                "w": w,
                "s": round(cur_w_t, 3),
                "e": round(cur_w_t + w_dur, 3)
            })
            cur_w_t += w_dur

        current_chunk = []
        for item in wt:
            test_chunk = current_chunk + [item]
            test_text = " ".join(x["w"] for x in test_chunk).upper()
            test_w = d.textbbox((0, 0), test_text, font=font)[2]

            if len(current_chunk) >= 3 or (current_chunk and test_w > 880):
                chunks.append({
                    "words": current_chunk,
                    "s": current_chunk[0]["s"],
                    "e": current_chunk[-1]["e"]
                })
                current_chunk = [item]
            else:
                current_chunk.append(item)

        if current_chunk:
            chunks.append({
                "words": current_chunk,
                "s": current_chunk[0]["s"],
                "e": current_chunk[-1]["e"]
            })

    return chunks


def get_active_chunk(chunks: list, elapsed_t: float):
    if not chunks:
        return None
    if elapsed_t < chunks[0]["s"]:
        return chunks[0]
    # Clean fade out after speech ends so CTA banner is unobstructed
    if elapsed_t > chunks[-1]["e"] + 0.6:
        return None

    for c in chunks:
        if c["s"] <= elapsed_t < c["e"]:
            return c

    for c in reversed(chunks):
        if elapsed_t >= c["s"]:
            return c

    return chunks[0]


def draw_kinetic_caption(img: Image.Image, chunk: dict, elapsed_t: float,
                         highlight_color: tuple = (255, 230, 0)) -> Image.Image:
    words = chunk["words"]
    font = get_font(74, bold=True)
    d = ImageDraw.Draw(img)

    words_upper = [w["w"].upper() for w in words]
    full_text = " ".join(words_upper)
    bbox = d.textbbox((0, 0), full_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    cy = 1260
    pad_x = 34
    pad_y = 18
    pill_w = tw + pad_x * 2
    pill_h = th + pad_y * 2
    bx = (WIDTH - pill_w) // 2
    by = cy - th // 2 - pad_y

    pill = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle([(0, 0), (pill_w, pill_h)], radius=24, fill=(0, 0, 0, 205))
    img.paste(pill, (bx, by), pill)

    d = ImageDraw.Draw(img)
    cur_x = bx + pad_x
    top_y = by + pad_y

    for i, w_info in enumerate(words):
        w_text = w_info["w"].upper()
        # Word is active if elapsed_t is within its window, or keep last word highlighted until chunk changes
        is_active = (w_info["s"] <= elapsed_t < w_info["e"]) or (i == len(words) - 1 and elapsed_t >= w_info["s"])
        fill_col = highlight_color if is_active else (255, 255, 255)

        d.text((cur_x, top_y), w_text, font=font, fill=fill_col,
               stroke_width=5, stroke_fill=(0, 0, 0), anchor="lt")

        cur_x += d.textbbox((0, 0), w_text + " ", font=font)[2]

    return img


# ── DAILY VICE CITY THEME ENGINE ──────────────────────────────────────────────
DAILY_THEMES = [
    {
        "name": "Vice Neon",
        "primary": (255, 20, 147),      # Hot Magenta
        "secondary": (0, 240, 255),     # Electric Cyan
        "highlight": (255, 230, 0),     # Electric Yellow
        "bar_c1": (220, 15, 120),
        "bar_c2": (0, 200, 240),
        "badge_border": (255, 20, 147),
        "badge_tag": (255, 235, 100),
        "progress_color": (255, 20, 147),
    },
    {
        "name": "Miami Sunset",
        "primary": (255, 90, 0),        # Sunset Red-Orange
        "secondary": (255, 200, 0),     # Amber Gold
        "highlight": (255, 230, 0),     # Bright Yellow
        "bar_c1": (210, 40, 0),
        "bar_c2": (255, 180, 0),
        "badge_border": (255, 100, 0),
        "badge_tag": (255, 220, 50),
        "progress_color": (255, 150, 0),
    },
    {
        "name": "Ocean Drive",
        "primary": (0, 220, 215),       # Tropical Turquoise
        "secondary": (255, 60, 130),    # Flamingo Coral
        "highlight": (220, 255, 0),     # Electric Lime
        "bar_c1": (10, 70, 180),
        "bar_c2": (0, 220, 215),
        "badge_border": (0, 220, 215),
        "badge_tag": (255, 80, 150),
        "progress_color": (0, 220, 215),
    },
    {
        "name": "Vice City Gold",
        "primary": (255, 215, 0),       # Luxury Gold
        "secondary": (150, 30, 210),    # Royal Violet
        "highlight": (255, 235, 80),    # Golden Yellow
        "bar_c1": (120, 15, 170),
        "bar_c2": (255, 200, 0),
        "badge_border": (255, 215, 0),
        "badge_tag": (255, 235, 100),
        "progress_color": (255, 210, 0),
    },
]

def get_daily_theme(seed: str = None) -> dict:
    if not seed:
        seed = datetime.now().strftime("%Y-%m-%d")
    idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(DAILY_THEMES)
    return DAILY_THEMES[idx]


_COUNTDOWN_HUD_CACHE = {}

def get_countdown_hud_pill(days: int, theme: dict) -> tuple:
    """Pre-renders the static micro HUD status pill once per video."""
    pill_w = 680
    pill_h = 44
    pill_x = (WIDTH - pill_w) // 2
    pill_y = 18

    pill = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    dp = ImageDraw.Draw(pill)
    # Glassmorphism dark fill with subtle frosted outline
    dp.rounded_rectangle([(0, 0), (pill_w, pill_h)], radius=22,
                         fill=(10, 8, 18, 200), outline=(255, 255, 255, 55), width=1)

    # Left: GTA VI gradient badge
    gw, gh = 86, 30
    gx, gy = 8, (pill_h - gh) // 2
    for x in range(gw):
        r = x / gw
        col = (
            int(theme["primary"][0] * (1 - r) + theme["bar_c1"][0] * r),
            int(theme["primary"][1] * (1 - r) + theme["bar_c1"][1] * r),
            int(theme["primary"][2] * (1 - r) + theme["bar_c1"][2] * r),
            255
        )
        dp.line([(gx + x, gy), (gx + x, gy + gh)], fill=col)
    dp.rounded_rectangle([(gx, gy), (gx + gw, gy + gh)], radius=8, outline=(255, 255, 255, 120), width=1)
    dp.text((gx + gw // 2, gy + gh // 2), "GTA VI", font=get_font(20, bold=True), fill=(255, 255, 255), anchor="mm")

    # Center: Glowing status dot + remaining days counter
    dot_x = gx + gw + 22
    dot_y = pill_h // 2
    dp.ellipse([(dot_x - 4, dot_y - 4), (dot_x + 4, dot_y + 4)], fill=(*theme["highlight"], 255))
    count_str = f"{days} DAYS TO LAUNCH" if days > 0 else "GTA 6 IS OUT NOW!"
    dp.text((dot_x + 14, dot_y), count_str, font=get_font(22, bold=True), fill=theme["highlight"], anchor="lm")

    # Right: Launch Window
    dp.text((pill_w - 20, dot_y), "FALL 2026", font=get_font(20, bold=True), fill=(200, 210, 230), anchor="rm")

    return (pill, pill_x, pill_y)


def draw_countdown_banner(img: Image.Image, t: float, days: int, theme: dict = None, prog_ratio: float = 0.0) -> Image.Image:
    """
    Renders the modern, open 2026 Short-form HUD header:
    - Razor-thin 4px edge progress bar at y=0..4
    - Sleek floating micro HUD pill at y=18 ([ GTA VI ]  ● 38 DAYS TO LAUNCH   FALL 2026)
    - Zero heavy rectangular box containers, leaving the video full-bleed and breathable.
    """
    if theme is None:
        theme = DAILY_THEMES[0]

    d = ImageDraw.Draw(img)

    # 1. Razor-thin top edge progress bar (y = 0..4)
    pw = int(WIDTH * min(max(prog_ratio, 0.0), 1.0))
    d.rectangle([(0, 0), (WIDTH, 4)], fill=(20, 20, 30, 200))
    d.rectangle([(0, 0), (pw, 4)], fill=(*theme["progress_color"], 255))
    if 4 < pw < WIDTH - 4:
        d.ellipse([(pw - 4, 0), (pw + 4, 4)], fill=(255, 255, 255, 255))

    # 2. Sleek floating micro HUD pill (pre-rendered & cached)
    cache_key = (days, theme.get("name", ""))
    if cache_key not in _COUNTDOWN_HUD_CACHE:
        _COUNTDOWN_HUD_CACHE[cache_key] = get_countdown_hud_pill(days, theme)

    pill, px, py = _COUNTDOWN_HUD_CACHE[cache_key]
    img.paste(pill, (px, py), pill)
    return img


_CREATOR_PILL_CACHE = {}

def get_creator_pill(handle: str, theme: dict) -> tuple:
    """Pre-renders the floating creator glass chip once per video."""
    chip_w = 520
    chip_h = 46
    chip_x = (WIDTH - chip_w) // 2
    chip_y = HEIGHT - 84

    chip = Image.new("RGBA", (chip_w, chip_h), (0, 0, 0, 0))
    dc = ImageDraw.Draw(chip)
    dc.rounded_rectangle([(0, 0), (chip_w, chip_h)], radius=23,
                         fill=(10, 8, 18, 195), outline=(255, 255, 255, 45), width=1)
    # Accent dot
    dc.ellipse([(20, chip_h // 2 - 4), (28, chip_h // 2 + 4)], fill=(*theme["highlight"], 255))
    # Creator handle
    dc.text((38, chip_h // 2), handle, font=get_font(23, bold=True), fill=(255, 255, 255), anchor="lm")
    # GTA 6 tagline
    dc.text((chip_w - 20, chip_h // 2), "DAILY GTA 6 UPDATES", font=get_font(19, bold=True),
            fill=theme["highlight"], anchor="rm")

    return (chip, chip_x, chip_y)


def draw_creator_footer(img: Image.Image, t: float, theme: dict = None, is_cta: bool = False,
                        handle: str = "@SamWithJoystick") -> Image.Image:
    """
    Renders the modern floating creator HUD at the bottom of the short:
    - Normal state: Sleek floating frosted glass chip ([ ● @SamWithJoystick  DAILY GTA 6 UPDATES ])
    - CTA state (last 7s): High-energy floating glowing pill ([ SUBSCRIBE TO @SamWithJoystick ])
    - Zero full-width rectangular slabs, leaving video full-bleed to the bottom edge.
    """
    if theme is None:
        theme = DAILY_THEMES[0]

    if not is_cta:
        cache_key = (handle, theme.get("name", ""))
        if cache_key not in _CREATOR_PILL_CACHE:
            _CREATOR_PILL_CACHE[cache_key] = get_creator_pill(handle, theme)

        chip, cx, cy = _CREATOR_PILL_CACHE[cache_key]
        img.paste(chip, (cx, cy), chip)
    else:
        # CTA State (last 7s): Floating glowing pulse capsule
        cta_w = 640
        cta_h = 76
        cta_x = (WIDTH - cta_w) // 2
        cta_y = HEIGHT - 110

        pulse = 0.9 + 0.1 * math.sin(t * 5.0)
        border_alpha = min(255, int(220 * pulse))

        cta = Image.new("RGBA", (cta_w, cta_h), (0, 0, 0, 0))
        dcta = ImageDraw.Draw(cta)
        dcta.rounded_rectangle([(0, 0), (cta_w, cta_h)], radius=26,
                               fill=(220, 20, 60, 240), outline=(255, 255, 255, border_alpha), width=2)
        dcta.text((cta_w // 2, 28), f"SUBSCRIBE TO {handle}", font=get_font(32, bold=True),
                  fill=(255, 255, 255), stroke_width=2, stroke_fill=(50, 0, 30), anchor="mm")
        dcta.text((cta_w // 2, 56), "DAILY GTA 6 NEWS & LEAKS", font=get_font(20, bold=True),
                  fill=theme["highlight"], stroke_width=1, stroke_fill=(0, 0, 0), anchor="mm")
        img.paste(cta, (cta_x, cta_y), cta)

    return img


# ── PROCEDURAL VICE CITY BACKGROUND ENGINE ─────────────────────────────────────
class ProceduralBackgroundEngine:
    """Pre-generates the static skyline base once, only animates dynamic elements."""
    def __init__(self):
        self.base = Image.new("RGB", (WIDTH, HEIGHT))
        d = ImageDraw.Draw(self.base)

        # Sky gradient
        for y in range(0, int(HEIGHT * 0.55), 4):
            ratio = y / HEIGHT
            r = int(15 + ratio * 30)
            g = int(10 + ratio * 20)
            b = int(60 + ratio * 80)
            d.rectangle([(0, y), (WIDTH, y + 4)], fill=(min(r, 255), min(g, 255), min(b, 255)))

        # Road
        horizon = int(HEIGHT * 0.55)
        d.rectangle([(0, horizon), (WIDTH, HEIGHT)], fill=(12, 10, 22))

        # Stars
        import random as _r
        _r.seed(1337)
        for _ in range(120):
            sx = _r.randint(0, WIDTH)
            sy = _r.randint(0, int(HEIGHT * 0.45))
            d.ellipse([(sx - 1, sy - 1), (sx + 1, sy + 1)], fill=(200, 200, 240))

        # City skyline
        _r.seed(42)
        x = -20
        while x < WIDTH + 20:
            bw = _r.randint(55, 130)
            bh = _r.randint(160, 750)
            btop = horizon - bh
            bc = (18, 16, 35)
            d.rectangle([(x, btop), (x + bw, horizon)], fill=bc)
            # Lit windows
            wcolors = [(255, 230, 130), (180, 240, 255), (255, 180, 80), (200, 255, 180), (255, 120, 200)]
            for wy in range(btop + 8, horizon - 8, 22):
                for wx in range(x + 6, x + bw - 6, 16):
                    if _r.random() < 0.4:
                        wc = _r.choice(wcolors)
                        d.rectangle([(wx, wy), (wx + 9, wy + 14)], fill=wc)
            x += bw + _r.randint(3, 18)

        # Road perspective markings
        vp = (WIDTH // 2, horizon)
        for lane_offset in [-380, -190, 0, 190, 380]:
            bx = vp[0] + lane_offset
            ex = vp[0] + lane_offset * 5
            d.line([vp, (ex, HEIGHT)], fill=(50, 48, 70), width=3)

        self.neon_signs = [
            (120, int(HEIGHT * 0.38), (255, 50, 150), "VICE"),
            (480, int(HEIGHT * 0.32), (50, 220, 255), "CITY"),
            (820, int(HEIGHT * 0.40), (255, 160, 0), "CLUB"),
            (280, int(HEIGHT * 0.42), (180, 0, 255), "24/7"),
            (670, int(HEIGHT * 0.35), (0, 255, 150), "BAR"),
        ]

    def get_frame(self, t: float) -> Image.Image:
        img = self.base.copy()
        d = ImageDraw.Draw(img)

        # Neon signs
        font_neon = get_font(38, bold=True)
        for nx, ny, nc, txt in self.neon_signs:
            stroke_text(d, txt, nx, ny, font_neon, fill=(255, 255, 255), sfill=nc, sw=3, anchor="mm")

        # Neon road reflections
        refl_colors = [(255, 50, 150), (50, 220, 255), (255, 160, 0), (180, 0, 255)]
        for i, rc in enumerate(refl_colors):
            rx = int(WIDTH * (0.12 + i * 0.22))
            ry = int(HEIGHT * 0.72)
            glow = 0.5 + 0.5 * abs(math.sin(t * 1.5 + i * 1.3))
            gc = tuple(int(c * 0.5 * glow) for c in rc)
            d.ellipse([(rx - 36, ry - 16), (rx + 36, ry + 16)], fill=gc)

        # Moving car headlights
        for car_i in range(3):
            speed = 200 + car_i * 80
            cx = int((t * speed + car_i * 350) % (WIDTH + 200)) - 100
            cy = int(HEIGHT * (0.65 + car_i * 0.06))
            beam_len = 120 - car_i * 25
            d.polygon([(cx, cy), (cx - 20, cy + beam_len), (cx + 20, cy + beam_len)], fill=(255, 255, 200))
            d.ellipse([(cx - 12, cy - 6), (cx + 12, cy + 6)], fill=(255, 255, 220))
            d.ellipse([(cx - 18, cy - 4), (cx - 6, cy + 4)], fill=(200, 0, 0))
            d.ellipse([(cx + 6, cy - 4), (cx + 18, cy + 4)], fill=(200, 0, 0))

        return img


# ── STREAMING VIDEO CLIP READER ────────────────────────────────────────────────
class VideoClipStreamReader:
    """
    Reads video frames sequentially using a single persistent FFmpeg pipe.
    Seamlessly loops clip indefinitely and automatically crops/scales to 1080x1920.
    """
    def __init__(self, ffmpeg_path: str, clip_path: str, width: int = WIDTH, height: int = HEIGHT, fps: int = FPS):
        self.ffmpeg_path = ffmpeg_path
        self.clip_path = clip_path
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_size = width * height * 3
        self.process = None
        self._start_stream()

    def _start_stream(self):
        cmd = [
            self.ffmpeg_path,
            "-v", "error",
            "-stream_loop", "-1",
            "-i", self.clip_path,
            "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,crop={self.width}:{self.height}",
            "-r", str(self.fps),
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-"
        ]
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=self.frame_size * 4
        )

    def read_frame(self) -> Image.Image:
        if not self.process:
            return None
        raw = self.process.stdout.read(self.frame_size)
        if len(raw) < self.frame_size:
            return None
        return Image.frombytes("RGB", (self.width, self.height), raw)

    def close(self):
        if self.process:
            try:
                self.process.kill()
                self.process.wait(timeout=1)
            except:
                pass
            self.process = None


# ── GTA 6 TRAILER & OFFICIAL STILLS FOCAL POINTS (CALIBRATED CENTERING) ────────
FOCAL_POINTS = {
    # ── GTA 6 TRAILER 1 SCREENSHOTS (34) ──
    "gta6_trailer_01.jpg": (0.45, 0.55),  # Highway sunset panorama
    "gta6_trailer_02.jpg": (0.40, 0.50),  # Prison fence sunset
    "gta6_trailer_03.jpg": (0.28, 0.45),  # Lucia looking out prison window (left)
    "gta6_trailer_04.jpg": (0.42, 0.45),  # Prison counselor & Lucia discussion (left)
    "gta6_trailer_05.jpg": (0.50, 0.45),  # Lucia orange jumpsuit interview
    "gta6_trailer_06.jpg": (0.58, 0.48),  # Catamaran yacht & swimming dolphins
    "gta6_trailer_07.jpg": (0.50, 0.50),  # Vice Beach crowded coastline
    "gta6_trailer_08.jpg": (0.50, 0.45),  # Vice City skyline title card
    "gta6_trailer_09.jpg": (0.45, 0.50),  # Skyscrapers & palm trees low angle
    "gta6_trailer_10.jpg": (0.25, 0.55),  # Airboat skimming swamp at golden hour (left)
    "gta6_trailer_11.jpg": (0.50, 0.50),  # Flamingos taking flight over wetlands
    "gta6_trailer_12.jpg": (0.30, 0.55),  # Trio of beachgoers walking forward (left)
    "gta6_trailer_13.jpg": (0.52, 0.60),  # Speedboat in foreground, container ship in bay
    "gta6_trailer_14.jpg": (0.65, 0.55),  # Speedboat catching air over ocean wake (right)
    "gta6_trailer_15.jpg": (0.35, 0.55),  # Girl driving convertible under neon highway sign (left)
    "gta6_trailer_16.jpg": (0.28, 0.52),  # Iconic girl dancing in yellow dress on convertible (left)
    "gta6_trailer_17.jpg": (0.72, 0.60),  # Slammed emerald green lowrider sedan (right)
    "gta6_trailer_18.jpg": (0.50, 0.55),  # Pink lowrider donk street gathering
    "gta6_trailer_19.jpg": (0.50, 0.50),  # Vice City nightclub packed dance floor
    "gta6_trailer_20.jpg": (0.52, 0.45),  # Two street characters fist bumping up close
    "gta6_trailer_21.jpg": (0.50, 0.50),  # Night aerial cityscape & highway grid
    "gta6_trailer_22.jpg": (0.50, 0.55),  # Ocean Drive neon supercars cruising
    "gta6_trailer_23.jpg": (0.42, 0.45),  # DJ stage performance in nightclub (center-left)
    "gta6_trailer_24.jpg": (0.50, 0.45),  # Overseas highway bridges & seaplane
    "gta6_trailer_25.jpg": (0.50, 0.45),  # Bikini influencer on luxury rooftop pool
    "gta6_trailer_26.jpg": (0.50, 0.50),  # Massive VICE letters silhouette at sunset
    "gta6_trailer_27.jpg": (0.50, 0.50),  # Social media yacht party live stream
    "gta6_trailer_28.jpg": (0.40, 0.55),  # Florida man pulling alligator from swimming pool (left)
    "gta6_trailer_29.jpg": (0.42, 0.55),  # Social clip car roof dancer
    "gta6_trailer_30.jpg": (0.48, 0.50),  # Drone night view of intersection smoke burnout
    "gta6_trailer_31.jpg": (0.50, 0.50),  # Neon live stream dancers on mobile UI
    "gta6_trailer_32.jpg": (0.58, 0.55),  # Convenience store alligator crawling inside (right)
    "gta6_trailer_33.jpg": (0.60, 0.50),  # Police bodycam tactical room entry (right)
    "gta6_trailer_34.jpg": (0.55, 0.50),  # Police officer battering door

    # ── JASON & LUCIA DUO STILLS (11) ──
    "Jason_and_Lucia_01.jpg": (0.50, 0.45),  # Intimate close-up portrait of Lucia and Jason
    "Jason_and_Lucia_02.jpg": (0.42, 0.50),  # Heist vault breach with tactical gear
    "Jason_and_Lucia_03.jpg": (0.44, 0.50),  # Cruising in classic convertible smiling
    "Jason_and_Lucia_04.jpg": (0.45, 0.50),  # Jewelry heist action with shattered glass
    "Jason_and_Lucia_05.jpg": (0.50, 0.50),  # Store entrance standoff with hostages
    "Jason_and_Lucia_06.jpg": (0.55, 0.45),  # Hiding behind cover with handguns ready
    "Jason_and_Lucia_07.jpg": (0.45, 0.45),  # Low angle neon street showdown
    "Jason_and_Lucia_08.jpg": (0.52, 0.45),  # Walking into fiery explosion with duffel bags
    "Jason_and_Lucia_09.jpg": (0.55, 0.45),  # Motorcycle getaway chase with police behind
    "Jason_and_Lucia_10.jpg": (0.35, 0.45),  # Rooftop lounge party (Lucia on left)
    "Jason_and_Lucia_12.jpg": (0.48, 0.45),  # Dark alley weapon check before heist

    # ── JASON DUVAL STILLS (4) ──
    "Jason_Duval_01.jpg": (0.68, 0.45),      # Jason on green racing motorcycle (right)
    "Jason_Duval_02.jpg": (0.32, 0.45),      # Jason driving vehicle close-up (left)
    "Jason_Duval_04.jpg": (0.32, 0.45),      # Jason in floral shirt outside neon hotel (left)
    "Jason_Duval_09.jpg": (0.68, 0.45),      # Gun chamber action with Jason in background (right)

    # ── LUCIA CAMINOS STILLS (9) ──
    "Lucia_Caminos_01.jpg": (0.52, 0.45),    # Lucia boxing gym workout hitting heavy bag
    "Lucia_Caminos_02.jpg": (0.50, 0.45),    # Lucia lounging at luxury pool with cocktail
    "Lucia_Caminos_03.jpg": (0.35, 0.45),    # Lucia on motorcycle outside neon Liquor Bar (left)
    "Lucia_Caminos_05.jpg": (0.55, 0.45),    # Lucia handcuffed in orange prison lineup
    "Lucia_Caminos_06.jpg": (0.50, 0.45),    # Lucia in club dress on crowded dancefloor
    "Lucia_Caminos_07.jpg": (0.50, 0.45),    # Lucia gripping steering wheel in high-speed pursuit
    "Lucia_Caminos_08.jpg": (0.58, 0.45),    # Lucia carrying pink duffel bag past check-cashing store
    "Lucia_Caminos_09.jpg": (0.50, 0.45),    # Lucia sitting in gym hoodie resting between sets
    "Lucia_Caminos_10.jpg": (0.52, 0.45),    # Lucia looking in rearview mirror during sunset drive

    # ── LEONIDA LOCATIONS & DISTRICTS (19) ──
    "Ambrosia_01.jpg": (0.40, 0.55),         # Biker gang cruising down rural highway
    "Ambrosia_02.jpg": (0.50, 0.50),         # Night industrial refinery and distant city glow
    "Ambrosia_04.jpg": (0.50, 0.50),         # Golden hour power transmission towers
    "Cal_Hampton_04.jpg": (0.52, 0.45),      # Two guys walking through neighborhood plaza
    "Grassrivers_02.jpg": (0.50, 0.55),      # Stilt houses and waterways in the Everglades
    "Grassrivers_04.jpg": (0.38, 0.55),      # Mud-splattered 4x4 truck navigating wetlands
    "Grassrivers_05.jpg": (0.50, 0.50),      # Panoramic riverfront village and lush mangroves
    "Leonida_Keys_01.jpg": (0.52, 0.50),     # Overseas highway curving across turquoise reef
    "Leonida_Keys_05.jpg": (0.55, 0.50),     # Sandbar boat party with yachts and swimmers
    "Mount_Kalaga_National_Park_02.jpg": (0.45, 0.45), # Search helicopter over mountainous wilderness
    "Mount_Kalaga_National_Park_04.jpg": (0.58, 0.50), # Winding gorge highway between red rock cliffs
    "Port_Gellhorn_01.jpg": (0.50, 0.50),    # Starlet Motel vintage neon sign at night
    "Port_Gellhorn_04.jpg": (0.45, 0.50),    # Delights nightclub roadside marquee sign
    "Port_Gellhorn_06.jpg": (0.50, 0.50),    # Port Gellhorn town panorama at dusk
    "Vice_City_03.jpg": (0.50, 0.50),        # Urban basketball courts and palm-lined avenues
    "Vice_City_08.jpg": (0.50, 0.50),        # Boardwalk carnival with glowing Ferris wheel
    "Vice_City_09.jpg": (0.45, 0.55),        # Wynwood-style street art and classic muscle car
    "Vice_City_10.jpg": (0.50, 0.50),        # Downtown high-rises and luxury yacht marina
    "Vice_City_11.jpg": (0.52, 0.50),        # Sunset towers with police helicopter patrol

    # ── ULTIMATE EDITION & SPECIAL ASSETS (21) ──
    "ULTIMATE_EDITION_01.jpg": (0.50, 0.45), # Key art poster of Lucia and Jason
    "ULTIMATE_EDITION_02.jpg": (0.42, 0.45), # Duo posing on green vintage roadster
    "ULTIMATE_EDITION_GOODTIME_GEAR_01.jpg": (0.45, 0.45), # Vice City Goodtime retro t-shirts
    "ULTIMATE_EDITION_GROTTI_CHEETAH_01.jpg": (0.48, 0.55), # White Grotti Cheetah classic supercar
    "ULTIMATE_EDITION_RIDEOUT_CUSTOMS_03.jpg": (0.52, 0.55), # Yellow muscle car on hydraulic lifts
    "ULTIMATE_EDITION_SAFEHOUSE_VEHICLES_01.jpg": (0.52, 0.50), # Stilt beach house with sports coupe
    "ULTIMATE_EDITION_SAFEHOUSE_VEHICLES_03.jpg": (0.45, 0.55), # Sunset kayak on coastal bay
    "ULTIMATE_EDITION_SARAS_SALON_03.jpg": (0.42, 0.48), # Lucia inside Sara's Salon
    "ULTIMATE_EDITION_SQUALO_01.jpg": (0.48, 0.60), # Modern Squalo speedboat at neon waterfront
    "ULTIMATE_EDITION_SQUALO_03.jpg": (0.55, 0.55), # Dolphin breaching next to speedboat deck
    "ULTIMATE_EDITION_STOCK_305_04.jpg": (0.50, 0.45), # Record store cashier counter
    "ULTIMATE_EDITION_VAPID_GANADO_RETRO_BUILD_01.jpg": (0.52, 0.55), # Yellow Vapid Ganado retro ute
    "ULTIMATE_EDITION_VICE_CITY_STYLE_01.jpg": (0.50, 0.45), # Luxury poolside patio styling
    "ULTIMATE_EDITION_VICE_CITY_STYLE_04.jpg": (0.50, 0.45), # Jason in tropical silk shirt on balcony
    "ULTIMATE_EDITION_VICE_CITY_STYLE_05.jpg": (0.50, 0.45), # Lucia posing by bridge structure
    "VINTAGE_VICE_CITY_PACK_01.jpg": (0.44, 0.45), # Ocean View Hotel entrance in 80s suits
    "VINTAGE_VICE_CITY_PACK_02.jpg": (0.48, 0.45), # Industrial dockland vintage muscle car
    "VINTAGE_VICE_CITY_PACK_EXCLUSIVE_LOOKS_01.jpg": (0.52, 0.45), # Neon nightclub slow dance
    "VINTAGE_VICE_CITY_PACK_EXCLUSIVE_LOOKS_04.jpg": (0.50, 0.45), # Retro lounge cocktail portrait
    "VINTAGE_VICE_CITY_PACK_VAPID_STANIER_02.jpg": (0.45, 0.50), # Classic yellow cruiser interior
    "VINTAGE_VICE_CITY_WEAPON_PATTERN_01.jpg": (0.50, 0.55), # Custom skin weapons with cash on car seat
}


# ── WIDE FOREGROUND SHOTS (SMART PILLARBOX BLUR CANDIDATES) ───────────────────
# Shots where subjects or vehicles stretch across the widescreen frame.
# Instead of aggressive 9:16 cropping cutting off the foreground, these render in
# Hybrid Mode with a full 16:9 card and ambient blurred background fill.
WIDE_SHOTS = {
    # Special Promo & Character Stills with wide horizontal staging
    "ULTIMATE_EDITION_STOCK_305_04.jpg",       # Lucia leaning on record store counter
    "ULTIMATE_EDITION_VICE_CITY_STYLE_05.jpg",  # Lucia posing wide by bridge railing
    "ULTIMATE_EDITION_VICE_CITY_STYLE_01.jpg",  # Poolside lounge duo
    "ULTIMATE_EDITION_02.jpg",                  # Duo sitting on wide roadster
    "ULTIMATE_EDITION_GROTTI_CHEETAH_01.jpg",   # Grotti Cheetah supercar across widescreen
    "ULTIMATE_EDITION_VAPID_GANADO_RETRO_BUILD_01.jpg", # Yellow ute truck
    "ULTIMATE_EDITION_RIDEOUT_CUSTOMS_03.jpg",  # Muscle car on hydraulic lift
    "ULTIMATE_EDITION_SAFEHOUSE_VEHICLES_01.jpg", # Stilt beach house + sports coupe
    "ULTIMATE_EDITION_SAFEHOUSE_VEHICLES_03.jpg", # Sunset kayak bay
    "ULTIMATE_EDITION_SQUALO_01.jpg",           # Squalo speedboat wide
    "ULTIMATE_EDITION_SQUALO_03.jpg",           # Speedboat & leaping dolphin
    "ULTIMATE_EDITION_GOODTIME_GEAR_01.jpg",    # Retro clothing display
    "VINTAGE_VICE_CITY_PACK_02.jpg",            # Industrial dockland muscle car
    "VINTAGE_VICE_CITY_PACK_VAPID_STANIER_02.jpg", # Classic taxi cruiser interior
    "VINTAGE_VICE_CITY_WEAPON_PATTERN_01.jpg",  # Weapons & cash spread on seat
    "Cal_Hampton_04.jpg",                       # Two guys walking side-by-side
    "Grassrivers_04.jpg",                       # 4x4 mud truck navigating swamp
    "Jason_Duval_01.jpg",                       # Jason leaning against car
    "Jason_and_Lucia_04.jpg",                   # Duo in car interior
    "Jason_and_Lucia_08.jpg",                   # Duo lounging/dining

    # Authentic Trailer 1 Shots with wide staging
    "gta6_trailer_04.jpg",                      # Prison counselor & Lucia across table
    "gta6_trailer_12.jpg",                      # Beachgoers trio walking across sand
    "gta6_trailer_17.jpg",                      # Emerald green lowrider sedan across screen
    "gta6_trailer_18.jpg",                      # Pink lowrider street gathering
    "gta6_trailer_20.jpg",                      # Mud racing trucks & spectators
    "gta6_trailer_22.jpg",                      # Dirt bikes and quad ATV pack
    "gta6_trailer_25.jpg",                      # Alligator entering convenience store
    "gta6_trailer_29.jpg",                      # Jason and Lucia driving convertible
    "gta6_trailer_32.jpg",                      # Convenience store CCTV panorama
}


def detect_focal_point(img: Image.Image) -> tuple:
    """
    Fast visual saliency fallback for any custom or new image:
    Finds center of visual energy / high-frequency detail in the 16:9 canvas,
    avoiding sky, bottom letterboxes, and watermarks.
    """
    try:
        import numpy as np
        small = img.convert("L").resize((320, 180))
        edges = small.filter(ImageFilter.FIND_EDGES)
        arr = np.array(edges, dtype=float)
        h, w = arr.shape
        mask = np.zeros_like(arr)
        mask[int(h * 0.15):int(h * 0.85), int(w * 0.05):int(w * 0.95)] = 1.0
        mask[int(h * 0.75):, int(w * 0.7):] = 0.0
        weighted = arr * mask
        col_sums = weighted.sum(axis=0)
        smoothed_x = np.convolve(col_sums, np.ones(25) / 25, mode="same")
        peak_x = float(np.argmax(smoothed_x)) / w
        row_sums = weighted.sum(axis=1)
        smoothed_y = np.convolve(row_sums, np.ones(25) / 25, mode="same")
        peak_y = float(np.argmax(smoothed_y)) / h
        return (max(0.20, min(peak_x, 0.80)), max(0.35, min(peak_y, 0.65)))
    except Exception:
        return (0.50, 0.50)


# ── DYNAMIC 4K IMAGE BACKGROUND ENGINE (KEN BURNS & DAILY VARIETY) ───────────
class DynamicImageBackgroundEngine:
    """
    Renders authentic 4K GTA 6 screenshots with cinematic camera motion:
    - Hybrid Framing Mode:
        * Portrait / character close-ups -> Full-screen 9:16 crop with subject-anchored tracking
        * Wide foreground shots (counters, vehicles, duos) -> Smart Pillarbox Blur so 100% of the scene is visible
    - Smart story-aware shot curation across all 98 4K assets (characters, world, vehicles)
    - Organic shot durations (3.8s - 4.6s) giving ample breathing room for visual storytelling
    - 4 Subject-anchored camera patterns: Hero Push-In, Hero Pull-Back, Foreground Reveal Sweep, Tracking Drift
    - Ultra-fast startup & render: pre-blurs background proxies once in <0.2s for >30 FPS render speed
    """
    def __init__(self, image_paths: list, seed: str = None, story_text: str = "", max_shots: int = 16):
        self.images = []
        self.focal_points = []
        self.is_wide = []
        self.blurred_bgs = []
        rng = random.Random(seed) if seed else random.Random()

        # Story-aware shot curation from the 98-image library
        shuffled = list(image_paths)
        rng.shuffle(shuffled)

        selected_paths = []
        seen = set()
        text_lower = (story_text or "").lower()

        def add_matching(keyword_predicate, limit=4):
            added = 0
            for p in shuffled:
                fname = os.path.basename(p).lower()
                if p not in seen and keyword_predicate(fname):
                    selected_paths.append(p)
                    seen.add(p)
                    added += 1
                    if added >= limit:
                        break

        # Priority 1: Match scenes to story topic
        if any(w in text_lower for w in ["lucia", "female", "protagonist", "woman", "girl"]):
            add_matching(lambda f: "lucia" in f, 4)
        if "jason" in text_lower:
            add_matching(lambda f: "jason" in f, 4)
        if any(w in text_lower for w in ["car", "vehicle", "drive", "race", "speed", "custom"]):
            add_matching(lambda f: any(k in f for k in ["car", "cheetah", "ganado", "stanier", "squalo", "customs", "trailer_17", "trailer_18", "trailer_22"]), 4)
        if any(w in text_lower for w in ["map", "city", "location", "world", "lake", "swamp", "beach", "vice"]):
            add_matching(lambda f: any(k in f for k in ["vice", "keys", "kalaga", "gellhorn", "grassrivers", "ambrosia", "trailer_01", "trailer_07", "trailer_10"]), 4)
        if any(w in text_lower for w in ["heist", "robbery", "crime", "police", "cop", "bodycam", "prison"]):
            add_matching(lambda f: any(k in f for k in ["heist", "prison", "caminos_05", "trailer_02", "trailer_03", "trailer_04", "trailer_05", "trailer_33", "trailer_34"]), 4)

        # Priority 2: Fill remaining scenes with a diverse mix from shuffled pool
        for p in shuffled:
            if p not in seen:
                selected_paths.append(p)
                seen.add(p)
                if len(selected_paths) >= max_shots:
                    break

        # Weave selected shots so matching scenes are spread evenly
        rng.shuffle(selected_paths)

        # Load and prepare shots with Hybrid Framing support
        for p in selected_paths:
            try:
                fname = os.path.basename(p)
                fname_lower = fname.lower()
                wide_flag = (
                    fname in WIDE_SHOTS
                    or "_wide" in fname_lower
                    or "_blur" in fname_lower
                )

                im = Image.open(p).convert("RGB")
                iw, ih = im.size

                if wide_flag:
                    # Smart Pillarbox Blur: Pre-calculate blurred dark backdrop
                    bg_small = im.resize((270, 480), Image.BILINEAR).filter(ImageFilter.GaussianBlur(14))
                    bg_full = bg_small.resize((WIDTH, HEIGHT), Image.BILINEAR)
                    bg_dark = Image.eval(bg_full, lambda c: int(c * 0.38)).convert("RGBA")

                    # Pre-scale foreground proxy for blazing ~35 FPS compositing
                    target_aspect = iw / ih if ih > 0 else 16 / 9
                    base_fg_h = int(WIDTH / target_aspect)
                    im_proxy = im.resize((int(WIDTH * 1.08), int(base_fg_h * 1.08)), Image.BILINEAR)

                    self.images.append(im_proxy)
                    self.focal_points.append((0.50, 0.50))
                    self.is_wide.append(True)
                    self.blurred_bgs.append(bg_dark)
                else:
                    # Full-screen 9:16 Crop: Scale down massive 4K to height 2160
                    if ih > 2160:
                        scale = 2160 / ih
                        im = im.resize((int(iw * scale), 2160), Image.BILINEAR)

                    if fname in FOCAL_POINTS:
                        focal = FOCAL_POINTS[fname]
                    else:
                        m_fx = re.search(r'_fx([0-1]\.?\d*)', fname_lower)
                        if m_fx:
                            try:
                                focal = (float(m_fx.group(1)), 0.50)
                            except:
                                focal = detect_focal_point(im)
                        elif "_left" in fname_lower:
                            focal = (0.28, 0.50)
                        elif "_right" in fname_lower:
                            focal = (0.72, 0.50)
                        elif "_center" in fname_lower:
                            focal = (0.50, 0.50)
                        else:
                            focal = detect_focal_point(im)

                    self.images.append(im)
                    self.focal_points.append(focal)
                    self.is_wide.append(False)
                    self.blurred_bgs.append(None)
            except Exception:
                pass

        if not self.images:
            self.images.append(Image.new("RGB", (WIDTH, HEIGHT), (20, 16, 36)))
            self.focal_points.append((0.50, 0.50))
            self.is_wide.append(False)
            self.blurred_bgs.append(None)

        # Pre-render drop shadow base for wide pillarbox cards
        self.shadow_pad = 16
        base_w, base_h = WIDTH, 608
        self.shadow_base = Image.new("RGBA", (base_w + self.shadow_pad * 2, base_h + self.shadow_pad * 2), (0, 0, 0, 0))
        d_sh = ImageDraw.Draw(self.shadow_base)
        d_sh.rounded_rectangle(
            [(self.shadow_pad, self.shadow_pad), (base_w + self.shadow_pad, base_h + self.shadow_pad)],
            radius=10, fill=(0, 0, 0, 180)
        )
        self.shadow_base = self.shadow_base.filter(ImageFilter.GaussianBlur(10))

        # Organic variable shot durations (3.8s - 4.6s) to let foreground action breathe
        n_shots = max(len(self.images), 1)
        self.shot_durs = [round(rng.uniform(3.8, 4.6), 2) for _ in range(n_shots)]
        self.patterns = [rng.randint(0, 3) for _ in range(n_shots)]

        # Pre-calculate cumulative transition timestamps
        self.shot_starts = [0.0]
        for d in self.shot_durs:
            self.shot_starts.append(round(self.shot_starts[-1] + d, 2))
        self.total_cycle = max(self.shot_starts[-1], 1.0)

        # Pre-render subtle top & bottom contrast gradient vignettes
        self.top_grad = Image.new("RGBA", (WIDTH, 330), (0, 0, 0, 0))
        d_top = ImageDraw.Draw(self.top_grad)
        for y in range(330):
            ratio = 1.0 - (y / 330)
            a = int(195 * (ratio ** 1.8))
            d_top.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, a))

        self.bot_grad = Image.new("RGBA", (WIDTH, 220), (0, 0, 0, 0))
        d_bot = ImageDraw.Draw(self.bot_grad)
        for y in range(220):
            ratio = y / 220
            a = int(160 * (ratio ** 1.8))
            d_bot.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, a))

    def get_frame(self, t: float) -> Image.Image:
        cycle_t = t % self.total_cycle
        shot_idx = 0
        for i, s_t in enumerate(self.shot_starts[:-1]):
            if cycle_t >= s_t:
                shot_idx = i
            else:
                break

        shot_start = self.shot_starts[shot_idx]
        cur_dur = max(self.shot_durs[shot_idx], 0.1)
        raw_prog = min(max((cycle_t - shot_start) / cur_dur, 0.0), 1.0)
        # Smooth sinusoidal ease in/out for camera movement
        smooth_prog = 0.5 - 0.5 * math.cos(raw_prog * math.pi)

        idx = shot_idx % len(self.images)
        src = self.images[idx]
        is_wide = self.is_wide[idx]
        pattern = self.patterns[shot_idx % len(self.patterns)]

        if is_wide:
            bg_dark = self.blurred_bgs[idx]
            # Smooth cinematic Ken Burns float on the 16:9 card
            if pattern in (0, 2):
                zoom = 1.00 + 0.04 * smooth_prog
            else:
                zoom = 1.04 - 0.04 * smooth_prog

            base_w = WIDTH
            base_h = 608
            fg_w = int(base_w * zoom)
            fg_h = int(base_h * zoom)

            fg_scaled = src.resize((fg_w, fg_h), Image.BILINEAR)

            frame = bg_dark.copy()
            pos_x = (WIDTH - fg_w) // 2
            pos_y = 570 - int((fg_h - base_h) // 2)

            s_w = fg_w + self.shadow_pad * 2
            s_h = fg_h + self.shadow_pad * 2
            sh_scaled = self.shadow_base.resize((s_w, s_h), Image.BILINEAR)

            frame.paste(sh_scaled, (pos_x - self.shadow_pad, pos_y - self.shadow_pad), sh_scaled)
            frame.paste(fg_scaled, (pos_x, pos_y))
            out_frame = frame.convert("RGB")
            out_frame.paste(self.top_grad, (0, 0), self.top_grad)
            out_frame.paste(self.bot_grad, (0, HEIGHT - 220), self.bot_grad)
            return out_frame

        # Full-screen 9:16 Subject-Anchored Framing
        fx, fy = self.focal_points[idx]
        sw, sh = src.size

        target_aspect = WIDTH / HEIGHT  # 1080 / 1920 = 0.5625
        base_h = sh
        base_w = int(base_h * target_aspect)
        if base_w > sw:
            base_w = sw
            base_h = int(base_w / target_aspect)

        max_pan_x = max(sw - base_w, 0)
        max_pan_y = max(sh - base_h, 0)
        anchor_x = max(0, min(int(fx * sw - base_w / 2), max_pan_x))
        anchor_y = max(0, min(int(fy * sh - base_h / 2), max_pan_y))

        if pattern == 0:
            # Hero Subject Push-In (smooth Ken Burns zoom into subject)
            zoom = 1.0 - 0.09 * smooth_prog
            cw = int(base_w * zoom)
            ch = int(base_h * zoom)
            cx = int(fx * sw - cw / 2)
            cy = int(fy * sh - ch / 2)
        elif pattern == 1:
            # Hero Subject Pull-Back (starts on subject, smoothly reveals surroundings)
            zoom = 0.91 + 0.09 * smooth_prog
            cw = int(base_w * zoom)
            ch = int(base_h * zoom)
            cx = int(fx * sw - cw / 2)
            cy = int(fy * sh - ch / 2)
        elif pattern == 2:
            # Foreground Reveal Sweep (sweeps directly onto foreground subject)
            zoom = 0.96 - 0.04 * smooth_prog
            cw = int(base_w * zoom)
            ch = int(base_h * zoom)
            if anchor_x <= max_pan_x * 0.5:
                start_cx = min(anchor_x + 160, sw - cw)
            else:
                start_cx = max(anchor_x - 160, 0)
            cx = int(start_cx + (anchor_x - start_cx) * smooth_prog)
            cy = int(fy * sh - ch / 2)
        else:
            # Subject Tracking Drift (gentle drift across action while keeping subject in frame)
            zoom = 0.94
            cw = int(base_w * zoom)
            ch = int(base_h * zoom)
            drift_offset = 120 if anchor_x < max_pan_x / 2 else -120
            cx = int(anchor_x + drift_offset * smooth_prog)
            cy = int(fy * sh - ch / 2)

        cx = max(0, min(cx, sw - cw))
        cy = max(0, min(cy, sh - ch))

        frame = src.crop((cx, cy, cx + cw, cy + ch))
        if frame.size != (WIDTH, HEIGHT):
            frame = frame.resize((WIDTH, HEIGHT), Image.BILINEAR)

        frame.paste(self.top_grad, (0, 0), self.top_grad)
        frame.paste(self.bot_grad, (0, HEIGHT - 220), self.bot_grad)
        return frame


# ── ATTENTION-GRABBING BIG BREAKING NEWS ENGINE (ZERO BOXES) ───────────────────
_BREAKING_BADGE_CACHE = {}

def balance_wrap_headline(text: str, font, max_w: int = 940) -> list:
    """
    Splits headline text into 1 or 2 visually balanced lines,
    preventing awkward orphan words on line 2.
    """
    dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    words = text.split()
    if not words:
        return [text]

    # If fits on 1 line
    if dummy.textbbox((0, 0), text, font=font)[2] <= max_w:
        return [text]

    best_split = None
    min_diff = float("inf")

    for i in range(1, len(words)):
        l1 = " ".join(words[:i])
        l2 = " ".join(words[i:])
        w1 = dummy.textbbox((0, 0), l1, font=font)[2]
        w2 = dummy.textbbox((0, 0), l2, font=font)[2]
        if w1 <= max_w and w2 <= max_w:
            diff = abs(w1 - w2)
            if diff < min_diff:
                min_diff = diff
                best_split = [l1, l2]

    return best_split


def create_breaking_badge_overlay(story_title: str, theme: dict) -> tuple:
    """
    Renders open, high-impact big typography for the breaking headline:
    - Glowing '● BREAKING NEWS' crimson capsule tag to hook viewers instantly
    - Large bold headline (size 44-48) with balanced 2-line wrapping
    - Line 1 in crisp white, Line 2 highlighted in vibrant theme color (e.g. Electric Yellow)
    - Heavy 5px black stroke for 100% legibility without any boxed container
    - Pre-rendered once per video for 0ms per-frame overhead
    """
    clean = re.sub(r'#\w+', '', story_title).strip().upper()
    clean = re.sub(r'\s+', ' ', clean).replace('—', '-').replace('–', '-')

    dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    max_text_w = WIDTH - 100  # 980px safe width inside 1080px canvas

    font_chosen = None
    lines_chosen = None
    line_h_chosen = 56

    for f_size, l_h in [(48, 56), (44, 52), (40, 48), (36, 44)]:
        font = get_font(f_size, bold=True)
        split = balance_wrap_headline(clean, font, max_w=max_text_w)
        if split:
            font_chosen = font
            lines_chosen = split
            line_h_chosen = l_h
            break

    if not lines_chosen:
        font_chosen = get_font(34, bold=True)
        line_h_chosen = 42
        words = clean.split()
        lines_chosen = [" ".join(words[:len(words)//2]), " ".join(words[len(words)//2:])]

    # Pre-render full top breaking news element
    tag_str = "● BREAKING NEWS"
    font_tag = get_font(26, bold=True)
    tw_tag = dummy.textbbox((0, 0), tag_str, font=font_tag)[2]
    tag_pw = tw_tag + 36
    tag_ph = 38
    tag_px = (WIDTH - tag_pw) // 2
    tag_py = 66

    text_sy = tag_py + tag_ph + 10
    total_h = text_sy + len(lines_chosen) * line_h_chosen + 20

    overlay = Image.new("RGBA", (WIDTH, total_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # 1. Glowing crimson red capsule tag: ● BREAKING NEWS
    d.rounded_rectangle(
        [(tag_px, tag_py), (tag_px + tag_pw, tag_py + tag_ph)],
        radius=13,
        fill=(225, 20, 60, 245),
        outline=(255, 255, 255, 180),
        width=1
    )
    d.text(
        (WIDTH // 2, tag_py + tag_ph // 2),
        tag_str,
        font=font_tag,
        fill=(255, 255, 255),
        anchor="mm",
        stroke_width=1,
        stroke_fill=(60, 0, 10)
    )

    # 2. Big bold headline typography with dynamic highlight
    for i, line in enumerate(lines_chosen):
        col = (255, 255, 255) if (i == 0 or len(lines_chosen) == 1) else theme["highlight"]
        stroke_text(
            d, line, WIDTH // 2, text_sy + i * line_h_chosen + line_h_chosen // 2, font_chosen,
            fill=col, sfill=(0, 0, 0), sw=5, anchor="mm"
        )

    return (overlay, 0, 0)


def draw_hook_badge(img: Image.Image, story_title: str, t: float = 0.0, max_dur: float = None,
                    theme: dict = None) -> Image.Image:
    """
    Renders the open floating breaking news headline throughout the video.
    """
    if max_dur is not None and t >= max_dur:
        return img
    if theme is None:
        theme = DAILY_THEMES[0]

    cache_key = (story_title, theme.get("name", ""))
    if cache_key not in _BREAKING_BADGE_CACHE:
        _BREAKING_BADGE_CACHE[cache_key] = create_breaking_badge_overlay(story_title, theme)

    badge, bx, by = _BREAKING_BADGE_CACHE[cache_key]
    img.paste(badge, (bx, by), badge)
    return img


# ── HARDWARE ACCELERATION DETECTION ────────────────────────────────────────────
def get_best_encoder(ffmpeg_path: str):
    """
    Auto-detect the fastest available H.264 encoder.
    Tests NVENC -> Windows Media Foundation -> libx264.
    """
    candidates = [
        ("h264_nvenc", ["-preset", "p4", "-cq", "21"]),
        ("h264_mf",    ["-b:v", "8M"]),
        ("libx264",    ["-preset", "ultrafast", "-crf", "20"]),
    ]
    for enc, args in candidates:
        try:
            r = subprocess.run(
                [ffmpeg_path, "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.05",
                 "-c:v", enc, *args, "-f", "null", "-"],
                capture_output=True, timeout=3
            )
            if r.returncode == 0:
                return enc, args
        except:
            pass
    return "libx264", ["-preset", "ultrafast", "-crf", "20"]


def find_ffmpeg():
    for cmd in ["ffmpeg", "ffmpeg.exe"]:
        if shutil.which(cmd):
            return cmd
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.exists(p):
            return p
    except:
        pass
    return None


def get_audio_duration(ffmpeg, audio_path):
    try:
        r = subprocess.run([
            ffmpeg, "-i", audio_path, "-f", "null", "-"
        ], capture_output=True, text=True, timeout=15)
        for line in r.stderr.splitlines():
            if "Duration:" in line:
                m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", line)
                if m:
                    h, mn, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
                    dur = h * 3600 + mn * 60 + s
                    return min(round(dur, 2), 58.0)
    except Exception as e:
        pass
    return 58.0


# ── MAIN VIDEO ASSEMBLER ───────────────────────────────────────────────────────
def assemble_video(script_data: dict, audio_path: str, clip_override: str = None) -> str:
    print("Assembling GTA 6 Short...")

    if not os.path.exists(audio_path):
        alt = audio_path.replace(".mp3", ".wav") if ".mp3" in audio_path else audio_path.replace(".wav", ".mp3")
        if os.path.exists(alt):
            audio_path = alt
        else:
            print(f"ERROR: Audio not found: {audio_path}")
            sys.exit(1)

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("ERROR: ffmpeg not found. Run: pip install imageio-ffmpeg")
        sys.exit(1)

    # 1. Resolve background source
    clip_path, bg_imgs, bg_source = None, [], "generate"
    if clip_override and os.path.exists(clip_override):
        clip_path, bg_source = clip_override, "clip"
        print(f"  BG: your clip -> {clip_path}")
    else:
        clips = glob.glob("assets/clips/*.mp4") + glob.glob("assets/clips/*.mov")
        if clips:
            clip_path, bg_source = clips[0], "clip"
            print(f"  BG: clip from assets/clips/ -> {clip_path}")
        else:
            extensions = ["*.jpg", "*.jpeg", "*.png", "*.webp"]
            imgs = []
            for ext in extensions:
                imgs.extend(Path("assets/backgrounds").glob(ext))
            if imgs:
                bg_imgs = [str(p) for p in imgs]
                bg_source = "images"
                print(f"  BG: {len(bg_imgs)} background image(s)")
            else:
                try:
                    from scripts.background_fetcher import fetch_backgrounds
                    fetch_backgrounds()
                    imgs = list(Path("assets/backgrounds").glob("*.jpg"))
                    if imgs:
                        bg_imgs = [str(p) for p in imgs]
                        bg_source = "images"
                        print(f"  BG: downloaded {len(bg_imgs)} images")
                    else:
                        bg_source = "generate"
                except Exception as e:
                    print(f"  BG: fallback to procedural scene ({e})")
                    bg_source = "generate"

    if bg_source == "generate":
        print("  BG: procedural Vice City night scene")

    # 2. Timing and Script structure
    audio_dur = get_audio_duration(ffmpeg, audio_path)
    total_frames = int(audio_dur * FPS)
    days_left = get_days_left()
    print(f"  Audio: {audio_dur:.1f}s | {WIDTH}x{HEIGHT} @ {FPS}fps ({total_frames} frames)")
    print(f"  Countdown: {days_left} days until GTA 6")

    raw = script_data.get("script", "GTA 6 news!")
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', raw) if s.strip()]
    if not sentences:
        sentences = [raw[:80]]

    COVER_DUR = 0.0
    story_title = script_data.get("story", {}).get("title", "GTA 6 Update")

    subtitles_timing = script_data.get("subtitles_timing")
    if not subtitles_timing and os.path.exists("assets/subtitles_timing.json"):
        try:
            with open("assets/subtitles_timing.json", "r", encoding="utf-8") as f:
                subtitles_timing = json.load(f)
        except:
            subtitles_timing = None

    if subtitles_timing:
        print(f"  Subtitles: using {len(subtitles_timing)} speech-synchronized timestamps")

    kinetic_chunks = prepare_kinetic_chunks(subtitles_timing, raw, audio_dur, COVER_DUR)
    print(f"  Kinetic Subtitles: {len(kinetic_chunks)} animated chunks ready (1:1 speech-synced)")

    # 3. Setup video encoder & destination
    encoder, enc_args = get_best_encoder(ffmpeg)
    print(f"  Encoder: {encoder} ({' '.join(enc_args)})")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = f"output/gta6_short_{timestamp}.mp4"
    os.makedirs("output", exist_ok=True)

    cmd_out = [
        ffmpeg, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",               # Stdin raw bytes
        "-i", audio_path,        # Voice audio
        "-c:v", encoder,
        *enc_args,
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        output_path
    ]

    pipe_out = subprocess.Popen(
        cmd_out,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )

    # 4. Initialize resources & daily aesthetic theme
    daily_seed = f"{datetime.now().strftime('%Y-%m-%d')}_{story_title}"
    theme = get_daily_theme(daily_seed)
    creator_handle = get_creator_handle()
    print(f"  Daily Visual Theme: {theme['name']}")
    print(f"  Creator Branding: {creator_handle}")

    bg_reader = None
    if bg_source == "clip" and clip_path:
        bg_reader = VideoClipStreamReader(ffmpeg, clip_path, WIDTH, HEIGHT, FPS)

    dynamic_img_engine = None
    if bg_source == "images" and bg_imgs:
        dynamic_img_engine = DynamicImageBackgroundEngine(bg_imgs, seed=daily_seed, story_text=raw)
        print(f"  BG: dynamic 4K GTA 6 engine active ({len(dynamic_img_engine.images)} curated scenes from {len(bg_imgs)} library, daily shuffle & cuts)")

    proc_engine = ProceduralBackgroundEngine() if bg_source == "generate" or not (bg_reader or dynamic_img_engine) else None

    print(f"  Rendering stream directly to FFmpeg...")
    start_time = time.time()

    try:
        for i in range(total_frames):
            t = i / FPS
            img = None

            if bg_reader:
                img = bg_reader.read_frame()

            if img is None and dynamic_img_engine:
                img = dynamic_img_engine.get_frame(t)

            if img is None and proc_engine:
                img = proc_engine.get_frame(t)

            if img is None:
                img = Image.new("RGB", (WIDTH, HEIGHT), (15, 12, 28))

            # 1. Countdown banner (top y=0..104 with integrated progress bar)
            prog_ratio = t / max(audio_dur, 0.1)
            img = draw_countdown_banner(img, t, days_left, theme=theme, prog_ratio=prog_ratio)

            # 2. Broadcast multiline breaking news badge (visible throughout the entire video)
            img = draw_hook_badge(img, story_title, t, theme=theme)

            # 3. Dynamic Kinetic Subtitles (2-3 words with active word highlight) at exact speech time t
            active_chunk = get_active_chunk(kinetic_chunks, t)
            if active_chunk:
                img = draw_kinetic_caption(img, active_chunk, t, highlight_color=theme["highlight"])

            # 4. Creator branding footer (@SamWithJoystick) & end CTA
            show_cta = t >= audio_dur - 7.0
            img = draw_creator_footer(img, t, theme=theme, is_cta=show_cta, handle=creator_handle)

            pipe_out.stdin.write(img.tobytes())

            if (i % (FPS * 2) == 0) or (i == total_frames - 1):
                pct = int(100 * (i + 1) / total_frames)
                elapsed = time.time() - start_time
                fps_render = (i + 1) / max(elapsed, 0.001)
                eta = (total_frames - (i + 1)) / max(fps_render, 0.001)
                bar = '#' * (pct // 5) + '.' * (20 - pct // 5)
                print(f"  [{bar}] {pct}% | {fps_render:.1f} fps | ETA: {eta:.0f}s", end="\r", flush=True)

    finally:
        if bg_reader:
            bg_reader.close()
        if pipe_out and pipe_out.stdin:
            try:
                pipe_out.stdin.close()
            except:
                pass

    _, stderr_err = pipe_out.communicate()
    total_time = time.time() - start_time

    if pipe_out.returncode != 0:
        print(f"\nFFmpeg error:\n{stderr_err.decode(errors='replace')[-1500:]}")
        sys.exit(1)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n  Done in {total_time:.1f}s ({total_frames / max(total_time, 0.1):.1f} fps)! Output: {output_path} ({size_mb:.1f} MB)")
    return output_path


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open("assets/current_script.json", encoding="utf-8") as f:
        script_data = json.load(f)
    audio = "assets/voiceover.mp3" if os.path.exists("assets/voiceover.mp3") else "assets/voiceover.wav"
    clip = sys.argv[1] if len(sys.argv) > 1 else None
    assemble_video(script_data, audio, clip_override=clip)
