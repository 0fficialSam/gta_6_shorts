"""
GTA 6 Video Assembler - FIXED
- Much brighter background (0.75 brightness instead of 0.4)
- NO vignette (was causing dark centre effect)
- Clean subtitle box at bottom only
"""
import json, os, sys, re, glob, subprocess, shutil, tempfile, random, math
import numpy as np
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

WIDTH, HEIGHT, FPS = 1080, 1920, 30

# ── COUNTDOWN CONFIG ───────────────────────────────────────────────────────────
from datetime import date as _date
GTA6_LAUNCH_DATE = _date(2026, 11, 19)   # Nov 19 2026 — update if Rockstar confirms date

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
    delta = GTA6_LAUNCH_DATE - today
    return delta.days   # Can be negative (already launched)

def get_countdown_text(days: int) -> str:
    if days <= 0:
        return "GTA 6 IS OUT NOW — GET IT!"
    random.seed(str(_date.today()))   # Same phrase all day, changes daily
    phrase = random.choice(COUNTDOWN_PHRASES)
    random.seed()
    return phrase.replace("{n}", str(days))

def draw_countdown_banner(img: Image.Image, t: float, days: int) -> Image.Image:
    """
    Draw eye-catching animated countdown banner at top of frame.
    Pulses gently to draw attention. Always visible throughout video.
    """
    d = ImageDraw.Draw(img)
    pulse = 0.85 + 0.15 * math.sin(t * 3.0)   # subtle pulse animation

    # ── Background bar ──────────────────────────────────────────
    # Gradient-like effect: dark left, orange center, dark right
    bar_h = 90
    bar_y = 0
    for x in range(0, WIDTH, 2):
        ratio = abs(x - WIDTH//2) / (WIDTH//2)
        r = int((180 + (1-ratio)*60) * pulse)
        g = int((30  + (1-ratio)*20) * pulse)
        b = int(0)
        d.rectangle([(x, bar_y),(x+2, bar_y+bar_h)],
                    fill=(min(r,255), min(g,255), b))

    # ── Glowing border line at bottom of bar ──────────────────
    glow_c = int(255 * pulse)
    d.rectangle([(0, bar_h-3),(WIDTH, bar_h)], fill=(glow_c, glow_c//2, 0))

    # ── Countdown number (BIG, left-center) ───────────────────
    text   = get_countdown_text(days)

    # If it has a number, make the number pop larger
    num_str = str(days) if days > 0 else ""
    if num_str and num_str in text:
        parts = text.split(num_str, 1)
        # Draw prefix
        px = 30
        font_sm  = get_font(32, bold=True)
        font_num = get_font(62, bold=True)
        font_sf  = get_font(32, bold=True)

        # Measure all parts
        pre_w  = d.textbbox((0,0), parts[0], font=font_sm)[2]  if parts[0]  else 0
        num_w  = d.textbbox((0,0), num_str,  font=font_num)[2]
        suf_w  = d.textbbox((0,0), parts[1], font=font_sf)[2]   if parts[1] else 0
        total_w = pre_w + num_w + suf_w
        start_x = (WIDTH - total_w) // 2
        cy = bar_h // 2

        # Draw prefix text
        if parts[0]:
            stroke_text(d, parts[0], start_x + pre_w//2, cy,
                        font_sm, (255,255,255),(0,0,0), 2, "mm")
        # Draw number — bright yellow, larger
        num_x = start_x + pre_w + num_w//2
        stroke_text(d, num_str, num_x, cy,
                    font_num, (255,230,0),(120,60,0), 3, "mm")
        # Draw suffix
        if parts[1]:
            suf_x = start_x + pre_w + num_w + suf_w//2
            stroke_text(d, parts[1], suf_x, cy,
                        font_sf, (255,255,255),(0,0,0), 2, "mm")
    else:
        # No number (launched already)
        stroke_text(d, text, WIDTH//2, bar_h//2,
                    get_font(40, bold=True),(255,230,0),(0,0,0),3,"mm")

    return img


# ── FONTS ──────────────────────────────────────────────────────────────────────
def get_font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf"  if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/verdanab.ttf" if bold else "C:/Windows/Fonts/verdana.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

# ── TEXT ───────────────────────────────────────────────────────────────────────
def stroke_text(draw, text, x, y, font, fill=(255,255,255), sfill=(0,0,0), sw=3, anchor="mm"):
    for dx in range(-sw, sw+1):
        for dy in range(-sw, sw+1):
            if dx or dy:
                draw.text((x+dx, y+dy), text, font=font, fill=sfill, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)

def wrap_draw(draw, text, cx, cy, font, fill=(255,255,255), sfill=(0,0,0), sw=3, max_w=960, lsp=14):
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if draw.textbbox((0,0), test, font=font)[2] <= max_w: cur.append(w)
        else:
            if cur: lines.append(" ".join(cur))
            cur = [w]
    if cur: lines.append(" ".join(cur))
    lh = draw.textbbox((0,0), "Ag", font=font)[3] + lsp
    sy = cy - (lh * len(lines)) // 2
    for i, line in enumerate(lines):
        stroke_text(draw, line, cx, sy+i*lh, font, fill, sfill, sw, "mm")

# ── BACKGROUND ─────────────────────────────────────────────────────────────────
def generate_gta_background(t: float) -> Image.Image:
    """Bright vibrant GTA6 / Vice City night scene - NO dark vignette."""
    img = Image.new("RGB", (WIDTH, HEIGHT))
    d   = ImageDraw.Draw(img)

    # Sky: deep blue-purple gradient (top) to dark teal (horizon)
    pulse = 0.5 + 0.5 * math.sin(t * 0.25)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        if ratio < 0.55:
            # Sky
            r = int(15  + ratio * 30)
            g = int(10  + ratio * 20)
            b = int(60  + ratio * 80 + pulse * 15)
        else:
            # Ground / road
            ratio2 = (ratio - 0.55) / 0.45
            r = int(8  + ratio2 * 15)
            g = int(8  + ratio2 * 10)
            b = int(20 + ratio2 * 25)
        d.line([(0,y),(WIDTH,y)], fill=(min(r,255), min(g,255), min(b,255)))

    # Stars
    random.seed(1337)
    for _ in range(120):
        sx = random.randint(0, WIDTH)
        sy = random.randint(0, int(HEIGHT*0.45))
        blink = 0.4 + 0.6 * abs(math.sin(t * random.uniform(0.5,2.0) + sx))
        sc = int(180 * blink)
        d.ellipse([(sx-1,sy-1),(sx+1,sy+1)], fill=(sc,sc,min(sc+30,255)))

    # City skyline silhouette
    random.seed(42)
    horizon = int(HEIGHT * 0.55)
    x = -20
    while x < WIDTH + 20:
        bw = random.randint(55, 130)
        bh = random.randint(160, 750)
        btop = horizon - bh
        # Building — dark but NOT black (slight blue tint for city feel)
        bc = (18, 16, 35)
        d.rectangle([(x, btop),(x+bw, horizon)], fill=bc)
        # Lit windows — bright & vibrant
        random.seed(x * 13)
        wcolors = [(255,230,130),(180,240,255),(255,180,80),(200,255,180),(255,120,200)]
        for wy in range(btop+8, horizon-8, 22):
            for wx in range(x+6, x+bw-6, 16):
                if random.random() < 0.4:
                    wc = random.choice(wcolors)
                    flicker = abs(math.sin(t*1.8 + wx*0.4 + wy*0.2))
                    if flicker > 0.2:
                        brightness = int(180 + flicker*75)
                        wc2 = tuple(min(255, int(c * brightness/255)) for c in wc)
                        d.rectangle([(wx,wy),(wx+9,wy+14)], fill=wc2)
        x += bw + random.randint(3, 18)

    # Neon signs on buildings (GTA6 Vice City style)
    neon_signs = [
        (120,  int(HEIGHT*0.38), (255, 50,150), "VICE"),
        (480,  int(HEIGHT*0.32), (50, 220,255), "CITY"),
        (820,  int(HEIGHT*0.40), (255,160,  0), "CLUB"),
        (280,  int(HEIGHT*0.42), (180,  0,255), "24/7"),
        (670,  int(HEIGHT*0.35), (0,  255,150), "BAR"),
    ]
    for nx, ny, nc, txt in neon_signs:
        glow_alpha = int(160 + 80 * abs(math.sin(t*1.2 + nx*0.01)))
        font_neon = get_font(38, bold=True)
        # Glow halo
        for spread in range(8, 0, -2):
            gc = tuple(max(0, c - spread*15) for c in nc)
            stroke_text(d, txt, nx, ny, font_neon, fill=gc, sfill=gc, sw=spread, anchor="mm")
        stroke_text(d, txt, nx, ny, font_neon, fill=(255,255,255), sfill=nc, sw=2, anchor="mm")

    # Road
    road_top = horizon
    d.rectangle([(0,road_top),(WIDTH,HEIGHT)], fill=(12,10,22))

    # Road lane markings (perspective)
    vp = (WIDTH//2, road_top)
    for lane_offset in [-380,-190,0,190,380]:
        bx = vp[0] + lane_offset
        ex = vp[0] + lane_offset*5
        d.line([vp, (ex,HEIGHT)], fill=(50,48,70), width=3)

    # Neon ground reflections (bright puddles/wet road)
    refl_colors = [(255,50,150),(50,220,255),(255,160,0),(180,0,255)]
    for i, rc in enumerate(refl_colors):
        rx = int(WIDTH * (0.12 + i*0.22))
        ry = int(HEIGHT * 0.72)
        glow = 0.5 + 0.5 * abs(math.sin(t*1.5 + i*1.3))
        for g in range(6,0,-1):
            gc = tuple(int(c*(g/6)*glow) for c in rc)
            d.ellipse([(rx-g*18, ry-g*8),(rx+g*18, ry+g*8)], fill=gc)

    # Moving car headlights
    for car_i in range(3):
        speed = 200 + car_i * 80
        cx = int((t * speed + car_i * 350) % (WIDTH + 200)) - 100
        cy = int(HEIGHT * (0.65 + car_i * 0.06))
        beam_len = 120 - car_i*25
        # Headlight beams
        d.polygon([(cx,cy),(cx-20,cy+beam_len),(cx+20,cy+beam_len)], fill=(255,255,200,100))
        d.ellipse([(cx-12,cy-6),(cx+12,cy+6)], fill=(255,255,220))
        # Tail light glow
        d.ellipse([(cx-18,cy-4),(cx-6,cy+4)], fill=(200,0,0))
        d.ellipse([(cx+6, cy-4),(cx+18,cy+4)], fill=(200,0,0))

    return img


def load_image_bg(path: str) -> Image.Image:
    """Load image, crop to 9:16, keep it BRIGHT (0.75 brightness)."""
    try:
        img = Image.open(path).convert("RGB")
        iw, ih = img.size
        scale = max(WIDTH/iw, HEIGHT/ih)
        nw, nh = int(iw*scale)+1, int(ih*scale)+1
        img = img.resize((nw, nh), Image.LANCZOS)
        x0 = (nw-WIDTH)//2
        y0 = (nh-HEIGHT)//2
        img = img.crop((x0, y0, x0+WIDTH, y0+HEIGHT))
        # BRIGHT — was 0.4 before (too dark), now 0.75
        img = ImageEnhance.Brightness(img).enhance(0.75)
        # Very slight blur only
        img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
        return img
    except:
        return None


def extract_video_frame(ffmpeg, clip_path: str, t: float) -> Image.Image:
    """Extract frame from video clip at time t."""
    try:
        # Get clip duration
        r = subprocess.run([
            ffmpeg, "-v","error","-show_entries","format=duration",
            "-of","default=noprint_wrappers=1:nokey=1", clip_path
        ], capture_output=True, text=True, timeout=8)
        clip_dur = float(r.stdout.strip()) if r.stdout.strip() else 30.0

        seek = t % max(clip_dur, 1.0)
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        subprocess.run([
            ffmpeg, "-y", "-ss", f"{seek:.3f}", "-i", clip_path,
            "-vframes","1","-q:v","2", tmp.name
        ], capture_output=True, timeout=8)
        img = load_image_bg(tmp.name)
        os.unlink(tmp.name)
        return img
    except Exception as e:
        return None


# ── DARK STRIP ONLY AT BOTTOM (not centre vignette!) ─────────────────────────
def add_bottom_gradient(img: Image.Image, start_y: int) -> Image.Image:
    """Add dark gradient ONLY at bottom where subtitles go. No centre darkening."""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    d = ImageDraw.Draw(overlay)
    # Fade from transparent to dark only in bottom portion
    for y in range(start_y, HEIGHT):
        ratio = (y - start_y) / (HEIGHT - start_y)
        alpha = int(210 * ratio)
        d.line([(0,y),(WIDTH,y)], fill=(0,0,0,alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

# ── GTA 6 LOGO ─────────────────────────────────────────────────────────────────
_gta6_logo_cache = None

def load_gta6_logo(size: tuple = (480, 200)) -> Image.Image:
    """Load user-provided GTA 6 logo from assets/gta6_logo.png"""
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
                print(f"  Loaded GTA 6 logo: {path} ({logo.size})")
                return logo
            except Exception as e:
                print(f"  Logo load failed ({path}): {e}")
    return None


def draw_logo_section(img: Image.Image, days_left: int, launch_date) -> Image.Image:
    """
    Draw GTA 6 logo + release date + X days left
    shown in the middle section of the title card frame.
    """
    logo = load_gta6_logo(size=(700, 280))
    d = ImageDraw.Draw(img)

    center_y = HEIGHT // 2 - 60

    if logo:
        # Paste logo centred
        lx = (WIDTH - logo.width) // 2
        ly = center_y - logo.height // 2 - 40
        if logo.mode == "RGBA":
            img.paste(logo, (lx, ly), logo)
        else:
            img.paste(logo, (lx, ly))
        text_y = ly + logo.height + 30
    else:
        # Fallback: draw text GTA 6 logo
        stroke_text(d, "GTA 6", WIDTH//2, center_y - 80,
                    get_font(200, True), (255, 107, 0), (0, 0, 0), 9, "mm")
        text_y = center_y + 130

    # Release date line
    date_str = launch_date.strftime("%B %d, %Y").upper()
    stroke_text(d, f"RELEASES  {date_str}", WIDTH//2, text_y,
                get_font(36, True), (200, 200, 200), (0, 0, 0), 2, "mm")

    # Days left — BIG and bold
    if days_left > 0:
        days_text = f"{days_left} DAYS LEFT"
    elif days_left == 0:
        days_text = "LAUNCHES TODAY!!"
    else:
        days_text = "OUT NOW — GET IT!"

    # Glowing pill background behind days left
    days_font = get_font(72, True)
    bbox = d.textbbox((0, 0), days_text, font=days_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pill_x0 = WIDTH//2 - tw//2 - 30
    pill_y0 = text_y + 55
    pill_x1 = WIDTH//2 + tw//2 + 30
    pill_y1 = pill_y0 + th + 24

    # Draw pill
    pill = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle(
        [(pill_x0, pill_y0), (pill_x1, pill_y1)],
        radius=20, fill=(220, 0, 0, 220)
    )
    img = Image.alpha_composite(img.convert("RGBA"), pill).convert("RGB")
    d = ImageDraw.Draw(img)

    stroke_text(d, days_text, WIDTH//2, pill_y0 + (pill_y1-pill_y0)//2,
                days_font, (255, 230, 0), (100, 0, 0), 3, "mm")

    return img


# ── FRAME BUILDER ──────────────────────────────────────────────────────────────
def build_frame(t, total, bg_source, bg_imgs, clip_path, ffmpeg_path,
                story_title, sentences, title_dur, tps, story_source, story_date,
                days_left=0):

    # ── FIRST 3 SECONDS: full-frame logo image as cover ─────────────────────────
    COVER_DUR = 2.0
    if t < COVER_DUR:
        # Load logo as full 1080x1920 background
        logo_paths = [
            "assets/gta6_logo.png", "assets/gta6_logo.jpg",
            "assets/gta6logo.png",  "assets/logo.png",
        ]
        img = None
        for lp in logo_paths:
            if os.path.exists(lp):
                try:
                    raw = Image.open(lp).convert("RGB")
                    # Fit to exact frame size
                    if raw.size != (WIDTH, HEIGHT):
                        raw = raw.resize((WIDTH, HEIGHT), Image.LANCZOS)
                    img = raw
                    break
                except: pass
        if img is None:
            img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))

        # ── Countdown banner at very top (90px) ──────────────────
        img = draw_countdown_banner(img, t, days_left)
        d = ImageDraw.Draw(img)

        launch_str = GTA6_LAUNCH_DATE.strftime("%B %d, %Y").upper()
        if days_left > 0:
            days_str = f"{days_left} DAYS LEFT"
        elif days_left == 0:
            days_str = "LAUNCHES TODAY!!"
        else:
            days_str = "OUT NOW!"

        # ── ZONE 1: Release date + days left (between banner and logo) ──
        # Logo sits roughly in the middle of the frame.
        # We place date/days in the gap between banner (y=90) and logo top (~y=480)
        zone1_top = 180    # just below countdown banner
        zone1_bot = 460    # above where logo starts

        zone1_ov = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
        ImageDraw.Draw(zone1_ov).rectangle(
            [(0, zone1_top),(WIDTH, zone1_bot)], fill=(0,0,0,160))
        img = Image.alpha_composite(img.convert("RGBA"), zone1_ov).convert("RGB")
        d = ImageDraw.Draw(img)

        # "RELEASING" small label
        stroke_text(d, "RELEASING", WIDTH//2, zone1_top + 52,
                    get_font(38, True), (160,160,160),(0,0,0), 2, "mm")

        # Release date — large white
        stroke_text(d, launch_str, WIDTH//2, zone1_top + 145,
                    get_font(58, True), (255,255,255),(0,0,0), 3, "mm")

        # Days left — BIG yellow
        stroke_text(d, days_str, WIDTH//2, zone1_top + 270,
                    get_font(96, True), (255,225,0),(120,60,0), 5, "mm")

        # ── ZONE 2: News headline below logo with word wrap ─────────────
        # Logo ends roughly at y=1100, so headline goes from ~1120 onwards
        zone2_top = 1350
        zone2_bot = HEIGHT - 20

        short = story_title  # full title, we word-wrap it

        # Measure wrapped lines
        h_font = get_font(53, True)
        max_w  = WIDTH - 80
        words  = short.split()
        lines, cur = [], []
        for w in words:
            test = " ".join(cur + [w])
            if d.textbbox((0,0), test, font=h_font)[2] <= max_w:
                cur.append(w)
            else:
                if cur: lines.append(" ".join(cur))
                cur = [w]
        if cur: lines.append(" ".join(cur))
        # Cap at 4 lines
        if len(lines) > 4:
            lines = lines[:3]
            lines[-1] = lines[-1][:40] + "..."

        lh      = d.textbbox((0,0), "Ag", font=h_font)[3] + 8
        txt_h   = lh * len(lines)
        pad     = 20
        box_y0  = zone2_top
        box_y1  = min(box_y0 + txt_h + pad*2, zone2_bot)

        # Translucent box behind headline
        hl_ov = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
        ImageDraw.Draw(hl_ov).rectangle(
            [(0, box_y0),(WIDTH, box_y1)], fill=(0,0,0,185))
        img = Image.alpha_composite(img.convert("RGBA"), hl_ov).convert("RGB")
        d = ImageDraw.Draw(img)

        # Draw each line centred
        sy = box_y0 + pad
        for line in lines:
            stroke_text(d, line, WIDTH//2, sy + lh//2,
                        h_font, (220,220,200),(0,0,0), 2, "mm")
            sy += lh

        return img   # ← exit early, no video background needed

    # ── FROM 3s ONWARDS: video/image background + subtitle overlay ────────────
    # Offset time so clip starts from 0 when cover ends
    clip_t = t - COVER_DUR

    img = None
    if bg_source == "clip" and clip_path:
        img = extract_video_frame(ffmpeg_path, clip_path, clip_t)
    elif bg_source == "images" and bg_imgs:
        idx = int(clip_t // 8) % len(bg_imgs)
        img = load_image_bg(bg_imgs[idx])

    if img is None:
        img = generate_gta_background(clip_t)

    # ── Subtitle overlay logic (t >= COVER_DUR) ──────────────────────────────
    if True:   # always subtitle mode after cover

        # ── SUBTITLE FRAME ──
        elapsed = t - COVER_DUR
        idx = min(int(elapsed / tps), len(sentences)-1)
        sentence = sentences[idx]
        show_cta = t >= total - 8

        d = ImageDraw.Draw(img)

        # ── Countdown banner at top ──────────────────────────────
        img = draw_countdown_banner(img, t, days_left)
        d = ImageDraw.Draw(img)

        # ── Progress bar just below banner ───────────────────────
        prog = int(WIDTH * (t / total))
        d.rectangle([(0, 93), (prog, 100)], fill=(255, 200, 0))
        d.rectangle([(prog, 93), (WIDTH, 100)], fill=(30, 30, 30))

        # ── Sentence dots ─────────────────────────────────────────
        total_s = len(sentences)
        dw = min(16, 800 // max(total_s, 1))
        ds = WIDTH // 2 - (total_s * (dw + 5)) // 2
        for si in range(total_s):
            col = (255, 200, 0) if si == idx else (60, 60, 60)
            d.rectangle([(ds + si*(dw+5), 105), (ds + si*(dw+5) + dw, 113)], fill=col)

        # ── Translucent dark box behind subtitle text ─────────────
        sub_font = get_font(54, True)
        margin   = 50
        max_w    = WIDTH - margin * 2

        # Word-wrap to measure real height
        words = sentence.split()
        lines, cur = [], []
        for w in words:
            test = " ".join(cur + [w])
            if d.textbbox((0,0), test, font=sub_font)[2] <= max_w:
                cur.append(w)
            else:
                if cur: lines.append(" ".join(cur))
                cur = [w]
        if cur: lines.append(" ".join(cur))

        lh       = d.textbbox((0,0), "Ag", font=sub_font)[3] + 12
        box_h    = lh * len(lines) + 44
        box_y0   = HEIGHT - 180 - box_h
        box_y1   = HEIGHT - 160
        box_x0   = margin - 20
        box_x1   = WIDTH - margin + 20

        # Draw translucent rounded rect
        sub_ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        ImageDraw.Draw(sub_ov).rounded_rectangle(
            [(box_x0, box_y0), (box_x1, box_y1)],
            radius=18, fill=(0, 0, 0, 195)
        )
        img = Image.alpha_composite(img.convert("RGBA"), sub_ov).convert("RGB")
        d   = ImageDraw.Draw(img)

        # Draw subtitle text centred in box
        text_cy = (box_y0 + box_y1) // 2
        wrap_draw(d, sentence, WIDTH//2, text_cy, sub_font,
                  (255, 255, 255), (0, 0, 0), 3, max_w)

        # ── CTA or footer bar ─────────────────────────────────────
        if show_cta:
            d.rectangle([(0, HEIGHT-140), (WIDTH, HEIGHT)], fill=(220, 0, 0))
            stroke_text(d, "FOLLOW FOR DAILY GTA 6 NEWS!",
                        WIDTH//2, HEIGHT-70,
                        get_font(44, True), (255,255,255), (100,0,0), 2, "mm")
        else:
            d.rectangle([(0, HEIGHT-80), (WIDTH, HEIGHT)], fill=(0, 0, 0))
            stroke_text(d, "GTA6 DAILY  |  LIKE & FOLLOW  |  2026",
                        WIDTH//2, HEIGHT-40,
                        get_font(28), (130,130,130), (0,0,0), 1, "mm")

    return img


# ── FFMPEG ─────────────────────────────────────────────────────────────────────
def find_ffmpeg():
    for cmd in ["ffmpeg","ffmpeg.exe"]:
        if shutil.which(cmd): return cmd
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.exists(p): return p
    except: pass
    return None


def get_audio_duration(ffmpeg, audio_path):
    try:
        r = subprocess.run([ffmpeg,"-v","error","-show_entries","format=duration",
                            "-of","default=noprint_wrappers=1:nokey=1",audio_path],
                           capture_output=True,text=True,timeout=15)
        return min(float(r.stdout.strip()), 58.0)   # YouTube Shorts max = 60s, leave 2s buffer
    except: return 90.0


# ── MAIN ───────────────────────────────────────────────────────────────────────
def assemble_video(script_data: dict, audio_path: str, clip_override: str = None) -> str:
    print("Assembling GTA 6 Short...")

    # Audio
    if not os.path.exists(audio_path):
        alt = audio_path.replace(".mp3",".wav") if ".mp3" in audio_path else audio_path.replace(".wav",".mp3")
        if os.path.exists(alt): audio_path = alt
        else: print(f"ERROR: Audio not found: {audio_path}"); sys.exit(1)

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("ERROR: ffmpeg not found. Run: pip install imageio[ffmpeg]"); sys.exit(1)

    # Resolve background source
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
            imgs = list(Path("assets/backgrounds").glob("*.jpg")) + \
                   list(Path("assets/backgrounds").glob("*.png"))
            if imgs:
                bg_imgs = [str(p) for p in imgs]
                bg_source = "images"
                print(f"  BG: {len(bg_imgs)} downloaded image(s)")
            else:
                print("  BG: attempting image download...")
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
                    print(f"  BG: download failed ({e}) — using generated scene")
                    bg_source = "generate"

    if bg_source == "generate":
        print("  BG: auto-generating Vice City night scene")

    audio_dur = get_audio_duration(ffmpeg, audio_path)
    print(f"  Audio: {audio_dur:.1f}s | {WIDTH}x{HEIGHT} @ {FPS}fps")

    raw = script_data.get("script","GTA 6 news!")
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', raw) if s.strip()]
    if not sentences: sentences = [raw[:80]]

    COVER_DUR = 2.0   # First 3 seconds = logo cover card
    tps = (audio_dur - COVER_DUR) / max(len(sentences), 1)
    TITLE_DUR = COVER_DUR   # kept for compatibility
    story_title  = script_data.get("story",{}).get("title","GTA 6 Update")
    story_source = script_data.get("story",{}).get("source","GTA6 Daily")
    story_date   = script_data.get("story",{}).get("date", datetime.now().strftime("%b %Y"))

    total_frames = int(audio_dur * FPS)
    days_left    = get_days_left()
    print(f"  Countdown: {days_left} days until GTA 6 | Audio duration: {audio_dur:.1f}s")
    tmpdir = tempfile.mkdtemp(prefix="gta6_")
    print(f"  Rendering {total_frames} frames...")

    for i in range(total_frames):
        t = i / FPS
        frame_img = build_frame(
            t, audio_dur, bg_source, bg_imgs, clip_path, ffmpeg,
            story_title, sentences, TITLE_DUR, tps, story_source, story_date,
            days_left=days_left
        )
        frame_img.save(os.path.join(tmpdir, f"frame_{i:06d}.jpg"), quality=93)
        if i % (FPS*5) == 0:
            pct = int(100*i/total_frames)
            print(f"  {'#'*(pct//5)}{'.'*(20-pct//5)} {pct}%", end="\r")

    print(f"\n  Encoding...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = f"output/gta6_short_{timestamp}.mp4"
    os.makedirs("output", exist_ok=True)

    result = subprocess.run([
        ffmpeg,"-y",
        "-framerate",str(FPS),
        "-i", os.path.join(tmpdir,"frame_%06d.jpg"),
        "-i", audio_path,
        "-c:v","libx264","-preset","fast","-crf","20",
        "-c:a","aac","-b:a","128k",
        "-shortest","-movflags","+faststart","-pix_fmt","yuv420p",
        output_path
    ], capture_output=True, text=True)

    shutil.rmtree(tmpdir, ignore_errors=True)

    if result.returncode != 0:
        print(f"FFmpeg error:\n{result.stderr[-1500:]}"); sys.exit(1)

    size_mb = os.path.getsize(output_path)/(1024*1024)
    print(f"\n  Done: {output_path}  ({size_mb:.1f} MB)")
    return output_path


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open("assets/current_script.json", encoding="utf-8") as f:
        script_data = json.load(f)
    audio = "assets/voiceover.mp3" if os.path.exists("assets/voiceover.mp3") else "assets/voiceover.wav"
    clip  = sys.argv[1] if len(sys.argv) > 1 else None
    assemble_video(script_data, audio, clip_override=clip)
