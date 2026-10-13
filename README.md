# 🎮 Universal Gaming Content Studio & Shorts Automation Engine
### 100% Free · Studio Quality · Runs Locally on Windows · Zero Monthly Fees ($0.00)
### Engineered for `@SamWithJoystick` · YouTube Shorts (9:16) & Instagram Posts (4:5)

An automated, high-retention creator studio and video production engine that crafts and publishes viral short-form content covering **GTA 6 and ALL major video game franchises** (leaks, rumors, launch countdowns, and breaking news).

---

## ⚡ What Makes This Studio Next-Gen

- 🖥️ **Studio Pro 3-Zone Web App (`http://127.0.0.1:8000`)**:
  - **Left Icon Dock**: Fast navigation between `Create` (Editor), `News Feed`, `4K Asset Vault`, `Production Archive`, and `Shortcuts & Settings`.
  - **Hero Stage**: Fixed aspect-ratio live preview container (`4:5 Instagram` card & `9:16 Short` video player) with real-time DOM WYSIWYG rendering.
  - **Right Control Dock**: Focused top-to-bottom creation flow: `[⚡ Auto-Scrape Fresh Story]` → `[News Headline & Interactive Word Chips]` → `[1-Click Generate]`.
- 📸 **Instagram 4:5 News Post Generator**:
  - High-impact 1080×1350 portrait cards inspired by `@thegamesgossip_`.
  - Heavyweight **Arial Black** uppercase display headlines with real-time **Electric Yellow (`#FFE600`)** keyword highlights.
  - **Symmetrical Twin Top Capsules**: Game Name (`[ ● GAME ]`) and Creator Watermark (`[ @SamWithJoystick ]`) rendered at identical heights and typography.
  - **Deep Velvet Scrim**: Multi-stop cubic dark gradient guaranteeing 100% legibility over any bright background.
  - **Automated Social Captions**: Auto-formats breaking news emojis, summary breakdown, attribution, handle, and targeted hashtags.
- 🎬 **YouTube Shorts 9:16 Video Engine**:
  - **Blazing-Fast Render (<60s)**: Direct memory-to-FFmpeg `stdin` pipe with automatic GPU hardware acceleration (`h264_nvenc` / `h264_mf` / `libx264 ultrafast`).
  - **Hyper-Realistic Neural Voice**: Microsoft conversational neural voice (`en-US-BrianMultilingualNeural` at `+4%` natural human pacing).
  - **Broadcast Vocal Mastering**: Shure SM7B mastering chain (180 Hz chest warmth, 650 Hz de-box, 3.8 kHz de-harsh, 10 kHz acoustic air, transparent soft-knee leveler).
  - **Dynamic Sidechain BGM Ducking**: FFmpeg `sidechaincompress` smoothly ducks background music under spoken dialogue and swells during pauses.
  - **Kinetic Word Subtitles**: 2–3 words-at-a-time synchronized captions with electric yellow highlights (`#FFE600`) and rounded dark pill backdrops.
  - **4-Track Royalty-Free Studio Beats**: Rotating 80s outrun synthwave, phonk trap, heist suspense, and Miami funk tracks.
- 🌐 **Universal Multi-Game Support**:
  - Not locked to GTA 6! Supports **ANY video game** on-demand (*Ghost of Yōtei*, *Marvel's Wolverine*, *The Witcher 4*, *Cyberpunk 2077*, *Elden Ring*, *Black Ops 6*, etc.).
  - **Multi-Source Screenshot Scraper**: Fetches official publisher screenshots & 4K wallpapers via Steam Store API, Wallhaven 4K/8K API, and direct scrapers ($0.00 cost).
  - **Multi-Game News Engine**: Dynamic Google News RSS and gaming outlets per franchise with intelligent relevance filtering.
- ⚡ **Instant <200ms Load Times (98% Thumbnail Optimization)**:
  - Built-in progressive JPEG thumbnail engine (`assets/thumbs/`, 480×270, ~20 KB per image) reducing 220 MB of raw 4K wallpapers down to 4.7 MB.
  - Native `loading="lazy"` across asset strips and the 4K vault for zero DOM freeze.
- 📦 **Interactive Production Archive**:
  - Output vault grid with instant hover actions: `View` (inspect), `Reuse` (load into stage to adapt), `Download` (save file), and `Delete` (safely purge via API).
- ⌨️ **Keyboard Shortcuts & `localStorage` Memory**:
  - Full keyboard shortcuts (<kbd>G</kbd>, <kbd>D</kbd>, <kbd>S</kbd>, <kbd>C</kbd>, <kbd>1</kbd>, <kbd>2</kbd>, <kbd>?</kbd>).
  - Automatically persists chosen game, voiceover profile, BGM track, color aesthetic, and format mode across browser reloads.

---

## 📁 Project Architecture

```
gta_6_shorts/
├── main.py                       ← Master CLI orchestrator (Shorts, Posts, Packs)
├── run_studio.py                 ← Launches Studio Pro Django server
├── run_studio.bat                ← 1-Click Windows shortcut to launch Web Studio
├── config.json                   ← Central settings (dates, audio, video, branding, YouTube)
├── requirements.txt              ← Python dependencies
├── .env                          ← Optional API keys (GEMINI_API_KEY)
├── studio/                       ← Studio Pro Full-Stack Django Web Application
│   ├── manage.py
│   ├── studio_project/           ← Settings, ASGI, and URL routing
│   ├── dashboard/                ← REST API endpoints (news, shots, render, media)
│   └── templates/
│       └── index.html            ← 3-Zone Studio Pro WYSIWYG Web Interface
├── scripts/
│   ├── config.py                 ← Central configuration loader (.env & config.json)
│   ├── instagram_generator.py    ← 4:5 Portrait News Card Generator (PIL Engine)
│   ├── game_image_fetcher.py     ← Universal multi-game screenshot fetcher & matcher
│   ├── news_scraper.py           ← Multi-game RSS news scraper & deduplicator
│   ├── script_generator.py       ← Gemini Flash / Claude / Ollama / Free builder
│   ├── voiceover.py              ← Studio voiceover, SM7B mastering & sidechain ducking
│   ├── video_assembler.py        ← High-speed streaming FFmpeg render engine & overlays
│   └── youtube_uploader.py       ← YouTube Data API v3 Shorts uploader
├── assets/
│   ├── backgrounds/              ← 200+ authentic 4K gaming wallpapers & trailer frames
│   ├── thumbs/                   ← Fast progressive 20 KB thumbnails (auto-generated)
│   ├── music/                    ← 4 distinct royalty-free studio audio tracks (.mp3)
│   ├── voice_samples/            ← In-browser audition audio clips (Brian, Christopher, Prabhat)
│   ├── clips/                    ← Optional custom background gameplay clips (.mp4)
│   └── stories_*.json            ← Cached game news stories
└── output/
    ├── *_post_*.png              ← Generated 4:5 Instagram news images
    └── gta6_short_*.mp4          ← Rendered 9:16 YouTube Shorts videos
```

---

## 🚀 Quickstart (3 Minutes)

### Step 1: Install Dependencies
Requires Python 3.10+ on Windows:
```bash
pip install -r requirements.txt
```

### Step 2: (Optional) Free Google Gemini Flash API
Get a free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/):
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```
*(If omitted, the engine automatically uses its built-in viral rule-based script builder at zero cost.)*

### Step 3: Launch Studio Pro Web App
Double-click `run_studio.bat` or run:
```bash
python run_studio.py
```
Open your browser to: **`http://127.0.0.1:8000`**

---

## 🎨 Studio Pro Web UI Guide

```
┌─────────────────┬──────────────────────────────────────────────┬──────────────────────────────────┐
│  ZONE 1: NAV    │             ZONE 2: HERO PREVIEW             │      ZONE 3: CONTROL DOCK        │
├─────────────────┼──────────────────────────────────────────────┼──────────────────────────────────┤
│ ⚡ Create       │ [ ● GTA VI ]             [ @SamWithJoystick ]│ ⚡ AUTO-SCRAPE FRESH STORY       │
│ 📰 News Feed    │                                              │ ──────────────────────────────── │
│ 🖼️ 4K Gallery   │        [ 4:5 LIVE CANVAS / 9:16 SHORT ]      │ 🎮 Target Video Game             │
│ 📦 Archive      │                                              │    (GTA VI, Wolverine, Yōtei...) │
│ ⚙️ Shortcuts    │ LEAKED                                       │ 📝 News Headline & Word Chips    │
│                 │ CYBERLEAK CONFIRMS 25 MINUTES...             │    [CYBERLEAK] [25] [MINUTES]    │
│                 │                                              │ 🏷️ Hook Word & Category Pill    │
│                 │ ──────────────────────────────────────────   │ 💬 Story Context (Voiceover)     │
│                 │ 📸 Background Shot Strip (Cycle/Upload/URL)  │ ▾ Advanced Options (Voice/Audio) │
│                 │ 📥 Download (PNG) | Video (MP4) | Caption    │ ──────────────────────────────── │
│                 │ 📋 Live Social Caption & Hashtag Box         │ 🚀 GENERATE (1-Click)            │
│                 │                                              │ 📊 4-Stage Progress Indicator    │
└─────────────────┴──────────────────────────────────────────────┴──────────────────────────────────┘
```

1. **Auto-Scrape**: Click the bright `⚡ AUTO-SCRAPE FRESH STORY` button at the top of the right panel. It pulls the latest breaking leak for your selected game.
2. **Review Headline & Word Highlights**: Click any word chip in the headline editor to toggle Electric Yellow (`#FFE600`) highlights live in the preview.
3. **Pick Background**: Click any 16:9 thumbnail in the horizontal strip beneath the card, or hit **Cycle** to jump to the next matching scene.
4. **Generate**: Click **Generate Instagram Post** (~1.5s) or switch to **YouTube Short 9:16** to render a 50s video with voiceover and captions.
5. **Download & Copy**: Click **Download Post (PNG)** and **Copy Caption** (copies caption + hashtags with instant `"Copied!"` feedback).

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| <kbd>G</kbd> or <kbd>Ctrl</kbd> + <kbd>Enter</kbd> | Trigger Generate (Post or Short) |
| <kbd>D</kbd> | Download generated file (PNG or MP4) |
| <kbd>S</kbd> | Auto-Scrape fresh story |
| <kbd>C</kbd> | Copy social caption & hashtags to clipboard |
| <kbd>1</kbd> | Switch to Instagram 4:5 Post mode |
| <kbd>2</kbd> | Switch to YouTube Short 9:16 Video mode |
| <kbd>?</kbd> | Toggle Keyboard Shortcuts Modal |

---

## 💻 CLI Production Commands

Prefer working from the terminal? You can run every engine feature directly via `main.py`:

### 1. Instagram 4:5 News Post Generation
```bash
# Auto-scrape top daily story and render 4:5 Instagram news card
python main.py --post

# Generate post for a specific game
python main.py --post --game "Marvel's Wolverine"
python main.py --post --game "Ghost of Yōtei"
python main.py --post --game "The Witcher 4"

# Custom headline and story
python main.py --post --game "GTA VI" --title "CYBERLEAK CONFIRMS 25 MINUTES OF GAMEPLAY" --news "Internal development build footage surfaces online."
```

### 2. YouTube Shorts 9:16 Video Generation
```bash
# Test render (offline, no upload)
python main.py --test --no-upload

# Auto-scrape top story and render Short
python main.py --no-upload --game "GTA VI"

# Supply custom background gameplay clip (.mp4)
python main.py --clip "assets/clips/my_gameplay.mp4" --no-upload

# Full auto-production & YouTube upload
python main.py
```

### 3. Complete Production Pack (Post + Short)
```bash
# Generates both the 4:5 Instagram post and the 9:16 Short simultaneously
python main.py --all --game "GTA VI"
```

---

## 🎙️ Neural Voice Options

Configurable in `config.json` or directly in Studio Pro:

| Voice | Tone | Optimal Use |
| :--- | :--- | :--- |
| `en-US-BrianMultilingualNeural` *(Default)* | YouTuber / Human (+4%) | Natural, conversational gaming shorts |
| `en-US-ChristopherNeural` | Broadcast (+12%) | Fast-paced high-energy breaking news |
| `en-IN-PrabhatNeural` | Indian English (+13%) | Indian gaming community audience |

---

## 🎵 Royalty-Free Audio Tracks

Built-in curated tracks with automatic dynamic sidechain ducking (-14 dB to -21 dB):

| Track File | Title | Genre / Vibe |
| :--- | :--- | :--- |
| `vice_city_night_drive.mp3` | Outrun Boulevard | 80s Analog Synthwave (124 BPM) |
| `leonida_action_beat.mp3` | Harry Spotter | Gym Phonk & 808 Cowbell Trap (140 BPM) |
| `miami_heist_pulse.mp3` | Cut and Run | Cinematic Heist Suspense (136 BPM) |
| `sunset_boulevard.mp3` | Laser Groove | Miami Beach Synth Funk (112 BPM) |

---

## 📊 Performance & Optimization Benchmarks

| Metric | Previous Legacy State | Modernized Studio Pro |
| :--- | :--- | :--- |
| **Gallery Page Load** | 20+ sec freeze (220 MB raw 4K) | **<200 ms** (480p progressive thumbs + lazy load) |
| **Browser GPU Memory** | 3.25 GB texture spike | **<50 MB** texture allocation |
| **Shorts Render Time** | 23 min 15 sec | **~65 sec** (H.264 GPU streaming pipe) |
| **Instagram Post Render** | N/A (did not exist) | **~1.5 sec** (PIL multiline layout) |
| **Voice Quality** | Robotic flat TTS | **Conversational Neural + Shure SM7B Mastering** |
| **Music Mixing** | Silent / unmixed | **FFmpeg Dynamic Sidechain Audio Ducking** |
| **Subtitles** | Static text block | **Kinetic Word Highlights (`#FFE600`)** |
| **Game Scope** | Hardcoded to GTA 6 | **Universal: ANY Game on Demand** |
| **Operating Cost** | $0.00 | **$0.00 (Zero monthly fees)** |

---

*Engineered with Python, Django, Pillow, and FFmpeg · 100% Free Tier & Local Utilities · Made for `@SamWithJoystick`*
