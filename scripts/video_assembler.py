"""
GTA 6 Video Assembler - High-Performance Streaming Pipeline
===========================================================
- ZERO per-frame disk I/O (no temp JPEGs)
- Direct memory-to-FFmpeg rawvideo pipe (< 30s render time)
- Single-pass continuous video background decoding with infinite loop & auto-cropping
- Hardware-accelerated encoding auto-detection (NVENC -> Windows Media Foundation -> libx264 ultrafast)
- Pre-cached procedural Vice City graphics & font rendering
"""
import json, os, sys, re, glob, subprocess, shutil, time, math
from datetime import datetime, date as _date
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

try:
    from scripts.config import get_target_launch_date, get_video_settings
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.config import get_target_launch_date, get_video_settings

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
@lru_cache(maxsize=32)
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
def prepare_kinetic_chunks(subtitles_timing: list, raw_script: str, audio_dur: float, cover_dur: float = 2.0) -> list:
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
    font = get_font(70, bold=True)
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

            if len(current_chunk) >= 3 or (current_chunk and test_w > 900):
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
    if elapsed_t >= chunks[-1]["e"]:
        return chunks[-1]

    for c in chunks:
        if c["s"] <= elapsed_t < c["e"]:
            return c

    for c in reversed(chunks):
        if elapsed_t >= c["s"]:
            return c

    return chunks[0]


def draw_kinetic_caption(img: Image.Image, chunk: dict, elapsed_t: float) -> Image.Image:
    words = chunk["words"]
    font = get_font(70, bold=True)
    d = ImageDraw.Draw(img)

    words_upper = [w["w"].upper() for w in words]
    full_text = " ".join(words_upper)
    bbox = d.textbbox((0, 0), full_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    cy = 1300
    pad_x = 32
    pad_y = 16
    pill_w = tw + pad_x * 2
    pill_h = th + pad_y * 2
    bx = (WIDTH - pill_w) // 2
    by = cy - th // 2 - pad_y

    pill = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle([(0, 0), (pill_w, pill_h)], radius=22, fill=(0, 0, 0, 200))
    img.paste(pill, (bx, by), pill)

    d = ImageDraw.Draw(img)
    cur_x = bx + pad_x
    top_y = by + pad_y

    for w_info in words:
        w_text = w_info["w"].upper()
        is_active = w_info["s"] <= elapsed_t < w_info["e"]
        fill_col = (255, 230, 0) if is_active else (255, 255, 255)

        d.text((cur_x, top_y), w_text, font=font, fill=fill_col,
               stroke_width=5, stroke_fill=(0, 0, 0), anchor="lt")

        cur_x += d.textbbox((0, 0), w_text + " ", font=font)[2]

    return img


# ── PRE-RENDERED COUNTDOWN BANNER BASE ─────────────────────────────────────────
_COUNTDOWN_BAR_BASE = None

def get_countdown_bar_base():
    global _COUNTDOWN_BAR_BASE
    if _COUNTDOWN_BAR_BASE is None:
        bar = Image.new("RGB", (WIDTH, 90))
        d = ImageDraw.Draw(bar)
        for x in range(0, WIDTH, 2):
            ratio = abs(x - WIDTH // 2) / (WIDTH // 2)
            r = int(180 + (1 - ratio) * 60)
            g = int(30 + (1 - ratio) * 20)
            d.rectangle([(x, 0), (x + 2, 90)], fill=(min(r, 255), min(g, 255), 0))
        _COUNTDOWN_BAR_BASE = bar
    return _COUNTDOWN_BAR_BASE


def draw_countdown_banner(img: Image.Image, t: float, days: int) -> Image.Image:
    pulse = 0.85 + 0.15 * math.sin(t * 3.0)
    bar_base = get_countdown_bar_base()
    bar = ImageEnhance.Brightness(bar_base).enhance(pulse)
    img.paste(bar, (0, 0))

    d = ImageDraw.Draw(img)
    glow_c = int(255 * pulse)
    d.rectangle([(0, 87), (WIDTH, 90)], fill=(glow_c, glow_c // 2, 0))

    text = get_countdown_text(days)
    num_str = str(days) if days > 0 else ""
    bar_h = 90

    if num_str and num_str in text:
        parts = text.split(num_str, 1)
        font_sm = get_font(32, bold=True)
        font_num = get_font(62, bold=True)
        font_sf = get_font(32, bold=True)

        pre_w = d.textbbox((0, 0), parts[0], font=font_sm)[2] if parts[0] else 0
        num_w = d.textbbox((0, 0), num_str, font=font_num)[2]
        suf_w = d.textbbox((0, 0), parts[1], font=font_sf)[2] if parts[1] else 0
        total_w = pre_w + num_w + suf_w
        start_x = (WIDTH - total_w) // 2
        cy = bar_h // 2

        if parts[0]:
            stroke_text(d, parts[0], start_x + pre_w // 2, cy,
                        font_sm, (255, 255, 255), (0, 0, 0), 2, "mm")
        num_x = start_x + pre_w + num_w // 2
        stroke_text(d, num_str, num_x, cy,
                    font_num, (255, 230, 0), (120, 60, 0), 3, "mm")
        if parts[1]:
            suf_x = start_x + pre_w + num_w + suf_w // 2
            stroke_text(d, parts[1], suf_x, cy,
                        font_sf, (255, 255, 255), (0, 0, 0), 2, "mm")
    else:
        stroke_text(d, text, WIDTH // 2, bar_h // 2,
                    get_font(40, bold=True), (255, 230, 0), (0, 0, 0), 3, "mm")

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


# ── STATIC IMAGE LOADER & CACHE ────────────────────────────────────────────────
def load_image_bg(path: str) -> Image.Image:
    try:
        img = Image.open(path).convert("RGB")
        iw, ih = img.size
        scale = max(WIDTH / iw, HEIGHT / ih)
        nw, nh = int(iw * scale) + 1, int(ih * scale) + 1
        img = img.resize((nw, nh), Image.LANCZOS)
        x0 = (nw - WIDTH) // 2
        y0 = (nh - HEIGHT) // 2
        img = img.crop((x0, y0, x0 + WIDTH, y0 + HEIGHT))
        img = ImageEnhance.Brightness(img).enhance(0.75)
        img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
        return img
    except:
        return None


# ── GTA 6 LOGO CACHE ───────────────────────────────────────────────────────────
_gta6_logo_cache = None

def load_gta6_logo(size: tuple = (480, 200)) -> Image.Image:
    global _gta6_logo_cache
    if _gta6_logo_cache is not None:
        return _gta6_logo_cache
    logo_paths = [
        "assets/gta6_logo.png",
        "assets/gta6_logo.jpg",
        "assets/gta6logo.png",
        "assets/logo.png",
    ]
    for path in logo_paths:
        if os.path.exists(path):
            try:
                logo = Image.open(path).convert("RGBA")
                logo.thumbnail(size, Image.LANCZOS)
                _gta6_logo_cache = logo
                return logo
            except:
                pass
    return None


# ── STATIC COVER CARD BUILDER ──────────────────────────────────────────────────
def build_cover_base(story_title: str, days_left: int) -> Image.Image:
    logo_paths = [
        "assets/gta6_logo.png", "assets/gta6_logo.jpg",
        "assets/gta6logo.png",  "assets/logo.png",
    ]
    img = None
    for lp in logo_paths:
        if os.path.exists(lp):
            try:
                raw = Image.open(lp).convert("RGB")
                if raw.size != (WIDTH, HEIGHT):
                    raw = raw.resize((WIDTH, HEIGHT), Image.LANCZOS)
                img = raw
                break
            except:
                pass
    if img is None:
        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))

    launch_str = get_target_launch_date().strftime("%B %d, %Y").upper()
    if days_left > 0:
        days_str = f"{days_left} DAYS LEFT"
    elif days_left == 0:
        days_str = "LAUNCHES TODAY!!"
    else:
        days_str = "OUT NOW!"

    # Zone 1 overlay (Date & Days Left)
    zone1_top = 180
    zone1_bot = 460
    zone1_w = WIDTH
    zone1_h = zone1_bot - zone1_top
    zone1_ov = Image.new("RGBA", (zone1_w, zone1_h), (0, 0, 0, 160))
    img.paste(zone1_ov, (0, zone1_top), zone1_ov)

    d = ImageDraw.Draw(img)
    stroke_text(d, "RELEASING", WIDTH // 2, zone1_top + 52,
                get_font(38, True), (160, 160, 160), (0, 0, 0), 2, "mm")
    stroke_text(d, launch_str, WIDTH // 2, zone1_top + 145,
                get_font(58, True), (255, 255, 255), (0, 0, 0), 3, "mm")
    stroke_text(d, days_str, WIDTH // 2, zone1_top + 270,
                get_font(96, True), (255, 225, 0), (120, 60, 0), 5, "mm")

    # Zone 2 overlay (Headline)
    zone2_top = 1350
    zone2_bot = HEIGHT - 20
    h_font = get_font(53, True)
    max_w = WIDTH - 80
    words = story_title.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if d.textbbox((0, 0), test, font=h_font)[2] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    if len(lines) > 4:
        lines = lines[:3]
        lines[-1] = lines[-1][:40] + "..."

    lh = d.textbbox((0, 0), "Ag", font=h_font)[3] + 8
    txt_h = lh * len(lines)
    pad = 20
    box_y0 = zone2_top
    box_y1 = min(box_y0 + txt_h + pad * 2, zone2_bot)
    box_h = box_y1 - box_y0

    hl_ov = Image.new("RGBA", (WIDTH, box_h), (0, 0, 0, 185))
    img.paste(hl_ov, (0, box_y0), hl_ov)

    d = ImageDraw.Draw(img)
    sy = box_y0 + pad
    for line in lines:
        stroke_text(d, line, WIDTH // 2, sy + lh // 2,
                    h_font, (220, 220, 200), (0, 0, 0), 2, "mm")
        sy += lh

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
            ffmpeg, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ], capture_output=True, text=True, timeout=15)
        return min(float(r.stdout.strip()), 58.0)
    except:
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

    COVER_DUR = 2.0
    tps = max(0.1, (audio_dur - COVER_DUR) / max(len(sentences), 1))
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
    print(f"  Kinetic Subtitles: {len(kinetic_chunks)} animated chunks ready")



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

    # 4. Initialize resources
    bg_reader = None
    if bg_source == "clip" and clip_path:
        bg_reader = VideoClipStreamReader(ffmpeg, clip_path, WIDTH, HEIGHT, FPS)

    cached_bg_images = []
    if bg_source == "images" and bg_imgs:
        cached_bg_images = [load_image_bg(p) for p in bg_imgs if os.path.exists(p)]
        cached_bg_images = [im for im in cached_bg_images if im is not None]

    proc_engine = ProceduralBackgroundEngine() if bg_source == "generate" or not (bg_reader or cached_bg_images) else None
    cover_base = build_cover_base(story_title, days_left)

    print(f"  Rendering stream directly to FFmpeg...")
    start_time = time.time()

    try:
        for i in range(total_frames):
            t = i / FPS

            if t < COVER_DUR:
                # Cover card
                frame_img = cover_base.copy()
                frame_img = draw_countdown_banner(frame_img, t, days_left)
            else:
                # Main body frame
                clip_t = t - COVER_DUR
                img = None

                if bg_reader:
                    img = bg_reader.read_frame()

                if img is None and cached_bg_images:
                    img_idx = int(clip_t // 8) % len(cached_bg_images)
                    img = cached_bg_images[img_idx].copy()

                if img is None and proc_engine:
                    img = proc_engine.get_frame(clip_t)

                if img is None:
                    img = Image.new("RGB", (WIDTH, HEIGHT), (15, 12, 28))

                d = ImageDraw.Draw(img)

                # Countdown banner
                img = draw_countdown_banner(img, t, days_left)
                d = ImageDraw.Draw(img)

                # Progress bar
                prog = int(WIDTH * (t / audio_dur))
                d.rectangle([(0, 93), (prog, 100)], fill=(255, 200, 0))
                d.rectangle([(prog, 93), (WIDTH, 100)], fill=(30, 30, 30))

                # Dynamic Kinetic Subtitles (2-3 words with active word highlight)
                active_chunk = get_active_chunk(kinetic_chunks, clip_t)
                if active_chunk:
                    img = draw_kinetic_caption(img, active_chunk, clip_t)
                    d = ImageDraw.Draw(img)


                # Footer
                show_cta = t >= audio_dur - 8
                if show_cta:
                    d.rectangle([(0, HEIGHT - 140), (WIDTH, HEIGHT)], fill=(220, 0, 0))
                    stroke_text(d, "FOLLOW FOR DAILY GTA 6 NEWS!",
                                WIDTH // 2, HEIGHT - 70,
                                get_font(44, True), (255, 255, 255), (100, 0, 0), 2, "mm")
                else:
                    d.rectangle([(0, HEIGHT - 80), (WIDTH, HEIGHT)], fill=(0, 0, 0))
                    stroke_text(d, "GTA6 DAILY  |  LIKE & FOLLOW  |  2026",
                                WIDTH // 2, HEIGHT - 40,
                                get_font(28), (130, 130, 130), (0, 0, 0), 1, "mm")

                frame_img = img

            pipe_out.stdin.write(frame_img.tobytes())

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
