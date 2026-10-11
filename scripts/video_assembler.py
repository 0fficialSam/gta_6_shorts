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


def draw_countdown_banner(img: Image.Image, t: float, days: int, theme: dict = None, prog_ratio: float = 0.0) -> Image.Image:
    """
    Renders a broadcast-grade GTA VI countdown header strip:
    - Left: Official-style 'GTA VI' gradient pill badge
    - Center: Prominent glowing remaining days counter + 'DAYS REMAINING'
    - Right: 'FALL 2026' launch window with live pulsing neon status dot
    - Bottom: Seamlessly integrated glowing neon progress bar
    """
    if theme is None:
        theme = DAILY_THEMES[0]

    h = 104
    bar = Image.new("RGBA", (WIDTH, h), (10, 8, 20, 235))
    d = ImageDraw.Draw(bar)

    # Top neon double accent line
    d.line([(0, 0), (WIDTH, 0)], fill=(*theme["primary"], 255), width=3)
    d.line([(0, 2), (WIDTH, 2)], fill=(*theme["bar_c2"], 160), width=1)

    # Left Pill Badge: "GTA VI"
    bw, bh = 144, 52
    bx, by = 40, (h - 4 - bh) // 2
    for gx in range(bw):
        gr = gx / bw
        col = (
            int(theme["primary"][0] * (1 - gr) + theme["bar_c1"][0] * gr),
            int(theme["primary"][1] * (1 - gr) + theme["bar_c1"][1] * gr),
            int(theme["primary"][2] * (1 - gr) + theme["bar_c1"][2] * gr),
            255
        )
        d.line([(bx + gx, by), (bx + gx, by + bh)], fill=col)
    d.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=12, outline=(255, 255, 255, 220), width=2)
    d.text((bx + bw // 2, by + bh // 2), "GTA VI", font=get_font(32, bold=True), fill=(255, 255, 255),
           anchor="mm", stroke_width=1, stroke_fill=(50, 0, 30))

    # Center Countdown Content
    cy = (h - 4) // 2
    font_num = get_font(58, bold=True)
    font_lbl = get_font(32, bold=True)
    font_tag = get_font(24, bold=True)

    if days > 0:
        num_str = str(days)
        lbl_str = "DAYS REMAINING"
        nw = d.textbbox((0, 0), num_str, font=font_num)[2]
        lw = d.textbbox((0, 0), lbl_str, font=font_lbl)[2]
        total_w = nw + 16 + lw
        center_x = 580
        sx = center_x - total_w // 2

        d.text((sx + nw // 2, cy), num_str, font=font_num, fill=theme["highlight"],
               stroke_width=3, stroke_fill=(0, 0, 0), anchor="mm")
        d.text((sx + nw + 16 + lw // 2, cy), lbl_str, font=font_lbl, fill=(255, 255, 255),
               stroke_width=2, stroke_fill=(0, 0, 0), anchor="mm")
    else:
        out_str = "GTA 6 IS OUT NOW!"
        d.text((580, cy), out_str, font=font_lbl, fill=theme["highlight"],
               stroke_width=3, stroke_fill=(0, 0, 0), anchor="mm")

    # Right Tag (Release Window & Live Indicator)
    tag_str = "FALL 2026"
    tw = d.textbbox((0, 0), tag_str, font=font_tag)[2]
    rx = WIDTH - 42
    d.text((rx - tw, cy), tag_str, font=font_tag, fill=(210, 220, 240),
           stroke_width=1, stroke_fill=(0, 0, 0), anchor="lm")
    dot_x = rx - tw - 18
    d.ellipse([(dot_x - 5, cy - 5), (dot_x + 5, cy + 5)], fill=(*theme["secondary"], 255))

    # Integrated progress bar at bottom of header strip (y = h - 5 to h)
    pw = int(WIDTH * min(max(prog_ratio, 0.0), 1.0))
    bar_y1, bar_y2 = h - 5, h
    d.rectangle([(0, bar_y1), (WIDTH, bar_y2)], fill=(25, 22, 35, 240))
    d.rectangle([(0, bar_y1), (pw, bar_y2)], fill=(*theme["progress_color"], 255))
    if 6 < pw < WIDTH - 6:
        d.ellipse([(pw - 5, bar_y1 - 2), (pw + 5, bar_y2 + 2)], fill=(255, 255, 255, 255))

    img.paste(bar, (0, 0), bar)
    return img


def draw_creator_footer(img: Image.Image, t: float, theme: dict = None, is_cta: bool = False,
                        handle: str = "@SamWithJoystick") -> Image.Image:
    """
    Renders the modern creator footer at the bottom of the short:
    - Normal state: Frosted glass bar with @SamWithJoystick branding & GTA 6 tagline
    - CTA state (last 7s): High-energy call to action to subscribe / follow
    """
    if theme is None:
        theme = DAILY_THEMES[0]

    font_handle = get_font(40, bold=True)
    font_sub = get_font(20, bold=True)

    if not is_cta:
        h = 96
        by = HEIGHT - h
        bar = Image.new("RGBA", (WIDTH, h), (10, 8, 20, 238))
        d = ImageDraw.Draw(bar)

        # Top double neon border line
        d.line([(0, 0), (WIDTH, 0)], fill=(*theme["secondary"], 255), width=2)
        d.line([(0, 2), (WIDTH, 2)], fill=(*theme["primary"], 140), width=1)

        # Creator handle: @SamWithJoystick
        d.text((WIDTH // 2, 34), handle, font=font_handle,
               fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0), anchor="mm")

        # Subtitle: DAILY GTA 6 NEWS • LEAKS • COUNTDOWN
        d.text((WIDTH // 2, 72), "DAILY GTA 6 NEWS  •  LEAKS  •  COUNTDOWN", font=font_sub,
               fill=theme["highlight"], stroke_width=1, stroke_fill=(0, 0, 0), anchor="mm")

        img.paste(bar, (0, by), bar)
    else:
        # CTA State (last 7s)
        h = 135
        by = HEIGHT - h
        pulse = 0.9 + 0.1 * math.sin(t * 5.0)
        bar = Image.new("RGBA", (WIDTH, h), (18, 10, 28, 245))
        d = ImageDraw.Draw(bar)

        c_pulse = tuple(min(255, int(c * pulse)) for c in theme["primary"])
        d.line([(0, 0), (WIDTH, 0)], fill=(*c_pulse, 255), width=3)
        d.line([(0, 3), (WIDTH, 3)], fill=(*theme["highlight"], 180), width=1)

        cta_font_lg = get_font(44, bold=True)
        cta_font_sm = get_font(26, bold=True)

        cta_title = f"SUBSCRIBE TO {handle}"
        d.text((WIDTH // 2, 42), cta_title, font=cta_font_lg,
               fill=(255, 255, 255), stroke_width=3, stroke_fill=(50, 0, 30), anchor="mm")

        d.text((WIDTH // 2, 94), "NEW GTA 6 SHORTS & LEAKS EVERY DAY!", font=cta_font_sm,
               fill=theme["highlight"], stroke_width=2, stroke_fill=(0, 0, 0), anchor="mm")

        img.paste(bar, (0, by), bar)

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


# ── DYNAMIC 4K IMAGE BACKGROUND ENGINE (KEN BURNS & DAILY VARIETY) ───────────
class DynamicImageBackgroundEngine:
    """
    Renders authentic 4K GTA 6 screenshots with cinematic camera motion:
    - Shuffles/curates scenes daily based on date & story so videos never look identical
    - Variable shot durations (2.6s - 3.4s) for an organic, human editing pace
    - Alternating Ken Burns camera motion (pan left/right, slow zoom-in, slow zoom-out)
    - Full 4K resolution clarity with subtle top/bottom contrast gradients
    """
    def __init__(self, image_paths: list, seed: str = None):
        self.images = []
        rng = random.Random(seed) if seed else random.Random()

        # Shuffle available 4K screenshots uniquely for each day / story
        shuffled_paths = list(image_paths)
        rng.shuffle(shuffled_paths)

        for p in shuffled_paths:
            try:
                im = Image.open(p).convert("RGB")
                iw, ih = im.size
                if ih > 2160:
                    scale = 2160 / ih
                    im = im.resize((int(iw * scale), 2160), Image.BILINEAR)
                self.images.append(im)
            except:
                pass

        if not self.images:
            self.images.append(Image.new("RGB", (WIDTH, HEIGHT), (20, 16, 36)))

        # Dynamic variable shot durations per scene
        n_shots = max(len(self.images), 1)
        self.shot_durs = [round(rng.uniform(2.7, 3.4), 2) for _ in range(n_shots)]
        self.patterns = [rng.randint(0, 3) for _ in range(n_shots)]

        # Pre-calculate cumulative transition timestamps
        self.shot_starts = [0.0]
        for d in self.shot_durs:
            self.shot_starts.append(round(self.shot_starts[-1] + d, 2))
        self.total_cycle = max(self.shot_starts[-1], 1.0)

        # Pre-render subtle top & bottom contrast gradient overlays
        self.top_grad = Image.new("RGBA", (WIDTH, 220), (0, 0, 0, 0))
        d_top = ImageDraw.Draw(self.top_grad)
        for y in range(220):
            a = int(140 * (1 - y / 220))
            d_top.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, a))

        self.bot_grad = Image.new("RGBA", (WIDTH, 260), (0, 0, 0, 0))
        d_bot = ImageDraw.Draw(self.bot_grad)
        for y in range(260):
            a = int(160 * (y / 260))
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
        shot_prog = min(max((cycle_t - shot_start) / cur_dur, 0.0), 1.0)

        src = self.images[shot_idx % len(self.images)]
        sw, sh = src.size

        target_aspect = WIDTH / HEIGHT  # 1080 / 1920 = 0.5625
        base_h = sh
        base_w = int(base_h * target_aspect)
        if base_w > sw:
            base_w = sw
            base_h = int(base_w / target_aspect)

        max_pan_x = max(sw - base_w, 0)
        pattern = self.patterns[shot_idx % len(self.patterns)]

        if pattern == 0:
            # Smooth pan left to right
            cx = int(max_pan_x * (0.2 + 0.6 * shot_prog))
            cy = (sh - base_h) // 2
            cw, ch = base_w, base_h
        elif pattern == 1:
            # Ken Burns slow zoom in
            zoom = 1.0 - 0.07 * shot_prog
            cw = int(base_w * zoom)
            ch = int(base_h * zoom)
            cx = (sw - cw) // 2
            cy = (sh - ch) // 2
        elif pattern == 2:
            # Smooth pan right to left
            cx = int(max_pan_x * (0.8 - 0.6 * shot_prog))
            cy = (sh - base_h) // 2
            cw, ch = base_w, base_h
        else:
            # Ken Burns slow zoom out
            zoom = 0.93 + 0.07 * shot_prog
            cw = int(base_w * zoom)
            ch = int(base_h * zoom)
            cx = (sw - cw) // 2
            cy = (sh - ch) // 2

        cx = max(0, min(cx, sw - cw))
        cy = max(0, min(cy, sh - ch))

        frame = src.crop((cx, cy, cx + cw, cy + ch))
        if frame.size != (WIDTH, HEIGHT):
            frame = frame.resize((WIDTH, HEIGHT), Image.BILINEAR)

        frame.paste(self.top_grad, (0, 0), self.top_grad)
        frame.paste(self.bot_grad, (0, HEIGHT - 260), self.bot_grad)
        return frame


def draw_hook_badge(img: Image.Image, story_title: str, t: float, max_dur: float = 3.6,
                    theme: dict = None) -> Image.Image:
    """
    Renders a punchy, translucent breaking news badge at the top of the video
    during the first 3.6 seconds to hook viewers without obscuring subtitles or gameplay.
    """
    if t >= max_dur:
        return img
    if theme is None:
        theme = DAILY_THEMES[0]

    alpha = 220 if t < (max_dur - 0.6) else int(220 * (max_dur - t) / 0.6)
    badge_h = 74
    badge_y = 118
    h_font = get_font(38, bold=True)

    clean_title = re.sub(r'#\w+', '', story_title).strip()
    if len(clean_title) > 40:
        clean_title = clean_title[:38].strip() + "..."
    title_upper = "BREAKING: " + clean_title.upper()

    d_test = ImageDraw.Draw(img)
    tb = d_test.textbbox((0, 0), title_upper, font=h_font)
    tw = tb[2] - tb[0]
    pad_x = 28
    badge_w = min(tw + pad_x * 2, WIDTH - 40)
    bx = (WIDTH - badge_w) // 2

    border_c = (*theme["badge_border"], alpha)
    badge = Image.new("RGBA", (badge_w, badge_h), (0, 0, 0, 0))
    d_b = ImageDraw.Draw(badge)
    d_b.rounded_rectangle([(0, 0), (badge_w, badge_h)], radius=16,
                          fill=(18, 12, 30, alpha), outline=border_c, width=2)
    img.paste(badge, (bx, badge_y), badge)

    d = ImageDraw.Draw(img)
    stroke_text(d, title_upper, WIDTH // 2, badge_y + badge_h // 2, h_font,
                fill=theme["badge_tag"], sfill=(0, 0, 0), sw=3, anchor="mm")
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
            imgs = list(Path("assets/backgrounds").glob("*.jpg")) + list(Path("assets/backgrounds").glob("*.png"))
            if imgs:
                bg_imgs = [str(p) for p in imgs]
                bg_source = "images"
                print(f"  BG: {len(bg_imgs)} downloaded image(s)")
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
        dynamic_img_engine = DynamicImageBackgroundEngine(bg_imgs, seed=daily_seed)
        print(f"  BG: dynamic 4K GTA 6 engine active ({len(dynamic_img_engine.images)} frames, daily shuffle & cuts)")

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

            # 2. Floating hook breaking news badge for first 3.6s
            img = draw_hook_badge(img, story_title, t, max_dur=3.6, theme=theme)

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
