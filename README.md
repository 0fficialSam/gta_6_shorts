# 🎮 GTA 6 YouTube Shorts Automation
### Fully FREE · Runs Daily on Your PC · Zero Cost

---

## 📁 Project Structure
```
gta6_shorts/
├── main.py                    ← Run this (master orchestrator)
├── requirements.txt           ← Python dependencies
├── client_secrets.json        ← YouTube API credentials (you add this)
├── scripts/
│   ├── news_scraper.py        ← Scrapes Reddit + RSS for GTA 6 news
│   ├── script_generator.py   ← Writes viral short scripts (AI or template)
│   ├── voiceover.py           ← Generates voice narration (gTTS free)
│   ├── video_assembler.py     ← Assembles final 9:16 video
│   └── youtube_uploader.py   ← Auto-uploads to YouTube
├── assets/
│   ├── clips/                 ← 🎮 PUT GTA 6 VIDEO CLIPS HERE (.mp4)
│   ├── voiceover.mp3          ← Auto-generated
│   └── current_script.json   ← Auto-generated
├── output/
│   └── gta6_short_*.mp4      ← Your finished videos!
└── logs/
    └── YYYY-MM-DD.log         ← Daily logs
```

---

## ⚡ QUICK SETUP (15 minutes)

### Step 1: Install Python & Dependencies
```bash
# Install Python 3.10+ from https://python.org

pip install -r requirements.txt
```

### Step 2: Install FFmpeg (required for audio/video)
**Windows:**
1. Download from https://ffmpeg.org/download.html
2. Extract to `C:\ffmpeg\`
3. Add `C:\ffmpeg\bin` to System PATH

**OR easier way:**
```bash
pip install imageio[ffmpeg]
```

### Step 3: Set Up Reddit API (Free)
1. Go to https://www.reddit.com/prefs/apps
2. Click "Create app" → select "script"
3. Fill in name: `GTA6ShortsBot`
4. Copy your **client_id** and **client_secret**
5. Open `scripts/news_scraper.py` and paste them:
```python
REDDIT_CLIENT_ID = "paste_here"
REDDIT_CLIENT_SECRET = "paste_here"
```

### Step 4: Set Up YouTube API (Free)
1. Go to https://console.cloud.google.com/
2. Create a new project → name it "GTA6Shorts"
3. Go to **APIs & Services** → Enable **YouTube Data API v3**
4. Go to **Credentials** → Create **OAuth 2.0 Client ID**
5. Select "Desktop App" → Download JSON
6. Rename it to `client_secrets.json` and place in project root
7. First run will open browser for authorization (one-time only)

### Step 5: Add Background Clips (Makes Videos Look AMAZING)
- Download GTA 6 trailer clips / gameplay videos
- Place `.mp4` files in `assets/clips/`
- The bot will loop them as background automatically

### Step 6: Test It!
```bash
# Test run (no upload, uses sample story)
python main.py --test --no-upload

# Real run without uploading
python main.py --no-upload

# Full run with YouTube upload
python main.py
```

---

## ⏰ AUTOMATE DAILY (Windows Task Scheduler)

Run this to create a daily scheduled task:

```batch
# Create a file: run_daily.bat
@echo off
cd C:\path\to\gta6_shorts
python main.py >> logs\daily.log 2>&1
```

**Then in Task Scheduler:**
1. Open Task Scheduler → Create Basic Task
2. Name: "GTA6 Shorts Daily"
3. Trigger: Daily at 5:00 PM (peak YouTube time)
4. Action: Start a program → Browse to `run_daily.bat`
5. ✅ Done! Runs automatically every day.

---

## 🚀 MAKE VIDEOS GO VIRAL — PRO TIPS

### 🎯 Best Upload Times (EST)
- **6 PM - 9 PM** → Peak viewing hours
- **Tuesday - Thursday** → Best engagement days

### 🎬 Better Background Videos = More Views
Replace the default animated background with:
- GTA 6 trailer clips (YouTube → download as MP4)
- GTA 5 gameplay (as placeholder)
- Aerial city/Vice City footage
- Put in `assets/clips/` folder

### 📱 Optimize for the Algorithm
The bot auto-adds `#Shorts` — also do this:
- Post **every single day** (consistency = growth)
- First 3 seconds are CRITICAL (bot handles this)
- Reply to every comment in first hour
- Upload same time daily for subscriber trust

### 🤖 Upgrade to Local AI (Free & Better Scripts)
Install Ollama for much better AI scripts:
```bash
# Download from https://ollama.ai
ollama pull mistral
# Bot automatically uses it!
```

### 💡 Content Ideas the Bot Handles Automatically
- Release date news/rumors
- Gameplay feature reveals
- Map leaks
- Character details
- Price reveals
- Comparison with GTA 5

---

## 🛠️ TROUBLESHOOTING

| Problem | Fix |
|---------|-----|
| `ffmpeg not found` | Install ffmpeg or run `pip install imageio[ffmpeg]` |
| `praw.exceptions` | Check Reddit API credentials |
| `gTTS connection error` | Check internet / use pyttsx3 (offline) |
| `YouTube quota exceeded` | API has 10,000 units/day free (1 upload = ~1600 units) |
| `No clips found` | Add MP4 files to `assets/clips/` |
| Black video | MoviePy installed correctly? Try `pip install moviepy==1.0.3` |

---

## 📊 What Each Day Looks Like

```
5:00 PM  → Bot starts automatically
5:01 PM  → Scrapes Reddit + 4 RSS feeds for GTA 6 news
5:02 PM  → Picks highest-scoring story
5:03 PM  → Generates viral 55-second script  
5:04 PM  → Creates voiceover audio (Google TTS)
5:05 PM  → Assembles video with subtitles + overlays
5:08 PM  → Uploads to YouTube with optimized title/tags
5:09 PM  → Done! Logs saved.
```

**Daily cost: $0.00** 🎉

---

## 🔥 EXPECTED GROWTH TIMELINE

| Week | Expected |
|------|----------|
| Week 1-2 | 0-50 views/video (algorithm learning) |
| Week 3-4 | 100-500 views (if posting daily) |
| Month 2 | 500-5,000 views (viral potential) |
| Month 3+ | Consistent growth if one video hits |

**Key:** Post EVERY day without fail. One viral Short can bring 10,000+ subscribers overnight.

---

*Built with Python · Powered by free APIs · No monthly costs*
