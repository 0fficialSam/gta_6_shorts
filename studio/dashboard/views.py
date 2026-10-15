import os
import re
import json
import time
import glob
import threading
from datetime import datetime
from pathlib import Path

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt

import scripts.config as project_config
from scripts.config import get_config
from scripts.instagram_generator import generate_instagram_post, get_available_screenshots

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
OUTPUT_DIR = ROOT_DIR / "output"
ASSETS_DIR = ROOT_DIR / "assets"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

# Global task state for background rendering
TASK_LOCK = threading.Lock()
TASK_STATE = {
    "task_id": None,
    "task_type": "idle",
    "status": "idle",     # idle | running | success | error
    "progress": 0,
    "message": "Ready to generate.",
    "output_file": None,
    "output_url": None,
    "caption": "",
    "error": None,
    "logs": [],
}


def log_task(msg: str, progress: int = None):
    """Appends to the current live task log and updates progress."""
    with TASK_LOCK:
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {msg}"
        TASK_STATE["logs"].append(entry)
        TASK_STATE["message"] = msg
        if progress is not None:
            TASK_STATE["progress"] = progress
        print(f"[Studio Log] {entry}")


# ── VIEWS ──────────────────────────────────────────────────────────────────────

def index(request):
    """Renders the main Studio UI."""
    cfg = get_config()
    creator_handle = cfg.get("branding", {}).get("creator_handle", "@SamWithJoystick")
    target_date = cfg.get("target_release_date", "2026-11-19")
    
    # Calculate days remaining
    try:
        t_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        days_left = max((t_date - datetime.now().date()).days, 0)
    except Exception:
        days_left = 38

    context = {
        "creator_handle": creator_handle,
        "target_date": target_date,
        "days_left": days_left,
        "version": "2.0 (Django Studio)",
    }
    return render(request, "index.html", context)


def serve_output_file(request, filename):
    """Serves generated media files from output/ directory safely."""
    safe_name = os.path.basename(filename)
    file_path = OUTPUT_DIR / safe_name
    if not file_path.exists():
        raise Http404("Media file not found")
    
    content_type = "video/mp4" if safe_name.endswith(".mp4") else "image/png"
    response = FileResponse(open(file_path, "rb"), content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{safe_name}"'
    response["Accept-Ranges"] = "bytes"
    return response


def serve_asset_file(request, category, filepath):
    """Serves background screenshots, audio tracks, and fast thumbnails from assets/ directory."""
    safe_cat = os.path.basename(category)
    clean_subpath = os.path.normpath(filepath).replace('\\', '/').lstrip('/')
    if '..' in clean_subpath:
        raise Http404("Invalid asset path")

    file_path = (ASSETS_DIR / safe_cat / clean_subpath).resolve()
    if not str(file_path).startswith(str(ASSETS_DIR.resolve())):
        raise Http404("Forbidden path")

    # If thumbnail requested but does not exist yet, generate on-the-fly from background image
    if safe_cat == "thumbs" and not file_path.exists():
        orig_file = (ASSETS_DIR / "backgrounds" / clean_subpath).resolve()
        if not orig_file.exists():
            stem = os.path.splitext(clean_subpath)[0]
            bg_dir = ASSETS_DIR / "backgrounds"
            # Check direct stem or nested folder stem
            candidates = list(bg_dir.glob(f"{stem}.*")) + list(bg_dir.glob(f"**/{stem}.*"))
            if candidates:
                orig_file = candidates[0]
        if orig_file.exists() and str(orig_file).startswith(str(ASSETS_DIR.resolve())):
            try:
                from PIL import Image
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(orig_file) as im:
                    im = im.convert('RGB')
                    im.thumbnail((480, 270), Image.Resampling.LANCZOS)
                    im.save(file_path, "JPEG", quality=80, optimize=True)
            except Exception as e:
                print(f"[Thumbnail Error] Could not generate thumbnail for {clean_subpath}: {e}")

    if not file_path.exists():
        raise Http404("Asset not found")

    ext = file_path.suffix.lower()
    content_type = "audio/mpeg" if ext == ".mp3" else ("image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png")
    response = FileResponse(open(file_path, "rb"), content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{file_path.name}"'
    response["Accept-Ranges"] = "bytes"
    return response


@csrf_exempt
def api_open_folder(request):
    """Opens the local output folder in Windows File Explorer."""
    try:
        if os.name == 'nt':
            os.startfile(str(OUTPUT_DIR))
            return JsonResponse({"success": True, "message": "Opened output folder"})
        return JsonResponse({"success": True, "message": "Non-Windows OS"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def api_get_screenshots(request):
    """Returns list of all available 4K background screenshots with fast thumbnails and categories."""
    from scripts.game_image_fetcher import classify_screenshot_category, FOCAL_POINTS
    shots = get_available_screenshots()
    items = []
    for s in shots:
        fname = os.path.basename(s)
        cat = classify_screenshot_category(fname, "GTA VI")
        fx, fy = FOCAL_POINTS.get(fname, (0.5, 0.45))
        base_name = os.path.splitext(fname)[0]
        items.append({
            "path": s,
            "filename": fname,
            "category": cat,
            "focal_x": fx,
            "focal_y": fy,
            "url": f"/assets/backgrounds/{fname}",
            "thumb_url": f"/assets/thumbs/{base_name}.jpg",
        })
    return JsonResponse({"success": True, "screenshots": items, "total": len(items)})


@csrf_exempt
def api_match_screenshot(request):
    """
    Intelligently matches the news story to the most contextually relevant photo
    across local or on-demand shots for any video game.
    """
    headline = request.GET.get("headline", "") or request.POST.get("headline", "")
    summary = request.GET.get("summary", "") or request.POST.get("summary", "")
    game = request.GET.get("game", "") or request.POST.get("game", "") or "GTA VI"

    if not headline:
        try:
            body = json.loads(request.body.decode("utf-8")) if request.body else {}
            headline = body.get("headline", "")
            summary = body.get("summary", "")
            game = body.get("game", game)
        except Exception:
            pass

    from scripts.game_image_fetcher import fetch_game_images_on_demand, rank_matching_images
    shots = fetch_game_images_on_demand(game, target_count=16)
    ranked = rank_matching_images(shots, headline, summary, game)

    top_shot = ranked[0][2] if ranked else (shots[0] if shots else None)
    top_score = ranked[0][0] if ranked else 0
    top_reason = ranked[0][1] if ranked else "Editorial Fit"

    alternatives = [
        {"shot": s, "score": sc, "reason": r}
        for sc, r, s in ranked[:8]
    ]

    return JsonResponse({
        "success": True,
        "matched_shot": top_shot,
        "score": top_score,
        "reason": top_reason,
        "alternatives": alternatives
    })


def api_get_music_tracks(request):
    """Returns curated royalty-free music library with streaming URLs."""
    tracks = [
        {"id": "vice_city_night_drive.mp3", "title": "Outrun Boulevard", "genre": "80s Analog Synthwave", "bpm": 124, "url": "/assets/music/vice_city_night_drive.mp3"},
        {"id": "leonida_action_beat.mp3", "title": "Harry Spotter", "genre": "Gym Phonk & 808 Trap", "bpm": 140, "url": "/assets/music/leonida_action_beat.mp3"},
        {"id": "miami_heist_pulse.mp3", "title": "Cut and Run", "genre": "Cinematic Heist Suspense", "bpm": 136, "url": "/assets/music/miami_heist_pulse.mp3"},
        {"id": "sunset_boulevard.mp3", "title": "Laser Groove", "genre": "Miami Beach Synth Funk", "bpm": 112, "url": "/assets/music/sunset_boulevard.mp3"},
    ]
    return JsonResponse({"success": True, "tracks": tracks})


# ── APIS ───────────────────────────────────────────────────────────────────────

def api_get_news(request):
    """Fetches scraped news for specified game or loads cached stories."""
    game = request.GET.get("game", "GTA VI").strip() or "GTA VI"
    try:
        from scripts.news_scraper import get_game_stories, get_game_search_config
        stories = get_game_stories(game=game, refresh=False)
        cfg = get_game_search_config(game)
        cache_file = os.path.join("assets", f"stories_{cfg['slug']}.json")
        today_file = "assets/today_stories.json"

        last_scraped_str = ""
        if stories and stories[0].get('scraped_at'):
            last_scraped_str = stories[0]['scraped_at']
        elif cfg['slug'] == 'gta_vi' and os.path.exists(today_file):
            last_scraped_str = datetime.fromtimestamp(os.path.getmtime(today_file)).strftime('%b %d, %Y, %I:%M %p')
        elif os.path.exists(cache_file):
            last_scraped_str = datetime.fromtimestamp(os.path.getmtime(cache_file)).strftime('%b %d, %Y, %I:%M %p')
        else:
            last_scraped_str = datetime.now().strftime('%b %d, %Y, %I:%M %p')

        return JsonResponse({
            "success": True,
            "game": game,
            "stories": stories,
            "total": len(stories),
            "last_scraped": last_scraped_str
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def api_refresh_news(request):
    """Triggers live scraper execution to pull fresh RSS items for specified game."""
    try:
        game = request.GET.get("game", "").strip() or ""
        if not game and request.method == "POST":
            try:
                body = json.loads(request.body.decode("utf-8")) if request.body else {}
                game = body.get("game", "").strip()
            except Exception:
                game = request.POST.get("game", "").strip()
        game = game or "GTA VI"

        from scripts.news_scraper import get_top_story, get_game_stories
        stories = get_game_stories(game=game, refresh=True)
        story = stories[0] if stories else get_top_story(game=game)
        now_scraped = datetime.now().strftime('%b %d, %Y, %I:%M %p')
        return JsonResponse({
            "success": True,
            "game": game,
            "top_story": story,
            "stories": stories,
            "last_scraped": now_scraped
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def api_generate_instagram(request):
    """Generates an Instagram 4:5 news card in ~2 seconds."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        body = request.POST.dict()

    headline = str(body.get("headline", "") or "").strip()
    summary = str(body.get("summary", "") or "").strip()
    game_title = str(body.get("game_title", "GTA VI") or "GTA VI").strip()
    category = str(body.get("category", "LEAKS & RUMORS") or "LEAKS & RUMORS").strip()
    hook_word = str(body.get("hook_word", "") or "").strip() or None
    source_credit = str(body.get("source_credit", "ROCKSTAR INTEL") or "ROCKSTAR INTEL").strip()
    
    # Visual background selection
    background_filename = body.get("background_filename", None)
    background_path = body.get("background_path", None)
    focal_x = body.get("focal_x", None)
    focal_y = body.get("focal_y", None)
    if background_filename:
        clean_bg = os.path.normpath(background_filename).replace('\\', '/').lstrip('/')
        if '..' not in clean_bg:
            cand_path = (ASSETS_DIR / "backgrounds" / clean_bg).resolve()
            if not cand_path.exists():
                matches = list((ASSETS_DIR / "backgrounds").glob(f"**/{os.path.basename(clean_bg)}"))
                if matches:
                    cand_path = matches[0].resolve()
            if cand_path.exists() and str(cand_path).startswith(str((ASSETS_DIR / "backgrounds").resolve())):
                background_path = str(cand_path)

    # Custom word-level highlights selected on UI
    custom_keywords = body.get("custom_keywords", None)
    theme_name = body.get("theme", body.get("theme_name", "vice"))

    if not headline:
        return JsonResponse({"success": False, "error": "Headline is required"}, status=400)

    try:
        res = generate_instagram_post(
            headline=headline,
            summary=summary,
            game_title=game_title,
            category=category,
            hook_word=hook_word,
            background_path=background_path,
            source_credit=source_credit,
            custom_keywords=custom_keywords,
            theme_name=theme_name,
            focal_x=focal_x,
            focal_y=focal_y
        )
        fname = os.path.basename(res["image_path"])
        res["image_url"] = f"/media/{fname}"
        res["filename"] = fname
        return JsonResponse(res)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def api_get_popular_games(request):
    """Returns curated popular game presets for rapid selection."""
    from scripts.game_image_fetcher import POPULAR_GAMES
    return JsonResponse({"success": True, "games": POPULAR_GAMES})


@csrf_exempt
def api_fetch_game_images(request):
    """Fetches high-res official screenshots on demand for any video game."""
    game = request.GET.get("game", "") or request.POST.get("game", "")
    if not game:
        try:
            body = json.loads(request.body.decode("utf-8")) if request.body else {}
            game = body.get("game", "")
        except Exception:
            pass

    game = game.strip()
    if not game:
        return JsonResponse({"success": False, "error": "Game title or query is required"}, status=400)

    force = request.GET.get("force", "false").lower() == "true"
    try:
        from scripts.game_image_fetcher import fetch_game_images_on_demand
        shots = fetch_game_images_on_demand(game, target_count=12, force_refresh=force)
        # Extract unique categories
        categories = []
        for s in shots:
            c = s.get("category", "Cinematic")
            if c and c not in categories:
                categories.append(c)
        return JsonResponse({
            "success": True,
            "game": game,
            "total": len(shots),
            "categories": categories,
            "screenshots": shots
        })
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def api_upload_shot(request):
    """Allows uploading a local custom screenshot or pasting an external image URL."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=405)

    import requests
    from scripts.game_image_fetcher import get_game_slug, is_valid_image_bytes

    game_title = request.POST.get("game", "")
    image_url = request.POST.get("image_url", "").strip()

    # Handle JSON payload if submitted as JSON
    if not image_url and not request.FILES:
        try:
            body = json.loads(request.body.decode("utf-8")) if request.body else {}
            image_url = body.get("image_url", "").strip()
            game_title = body.get("game", "")
        except Exception:
            pass

    slug = get_game_slug(game_title) if game_title else "custom"
    target_dir = ASSETS_DIR / "backgrounds" / slug
    os.makedirs(target_dir, exist_ok=True)

    timestamp = int(time.time() * 1000)
    saved_path = None
    filename = None

    if "image" in request.FILES:
        uploaded_file = request.FILES["image"]
        if uploaded_file.size < 16:
            return JsonResponse({"success": False, "error": "Uploaded file is too small or empty"}, status=400)

        header = uploaded_file.read(64)
        if not is_valid_image_bytes(header):
            return JsonResponse({"success": False, "error": "Uploaded file is not a valid image (JPEG, PNG, WebP)"}, status=400)
        uploaded_file.seek(0)

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".png" if header.startswith(b'\x89PNG') else ".jpg"
        filename = f"custom_{timestamp}{ext}"
        saved_path = target_dir / filename
        with open(saved_path, "wb") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
    elif image_url:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            }
            r = requests.get(image_url, headers=headers, timeout=15)
            if r.status_code == 200 and len(r.content) > 10000:
                if not is_valid_image_bytes(r.content[:64]):
                    return JsonResponse({"success": False, "error": "URL does not return a valid image file"}, status=400)
                ext = ".png" if r.content.startswith(b'\x89PNG') else ".jpg"
                filename = f"custom_{timestamp}{ext}"
                saved_path = target_dir / filename
                with open(saved_path, "wb") as f:
                    f.write(r.content)
            else:
                return JsonResponse({"success": False, "error": f"Failed to download image (HTTP {r.status_code})"}, status=400)
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Image URL download failed: {str(e)}"}, status=400)
    else:
        return JsonResponse({"success": False, "error": "No file uploaded or image URL provided"}, status=400)

    if saved_path and saved_path.exists():
        rel_url = f"/assets/backgrounds/{slug}/{filename}"
        return JsonResponse({
            "success": True,
            "filename": f"{slug}/{filename}",
            "url": rel_url,
            "thumb_url": rel_url,
            "title": f"Custom Upload ({filename})",
            "source": "custom_upload"
        })

    return JsonResponse({"success": False, "error": "Failed to save screenshot"}, status=500)




@csrf_exempt
def api_generate_video(request):
    """Triggers YouTube Short video generation asynchronously."""
    global TASK_STATE

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=405)

    with TASK_LOCK:
        if TASK_STATE["status"] == "running":
            return JsonResponse({
                "success": False,
                "error": "A generation task is already running in the background. Please wait."
            }, status=409)

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        body = request.POST.dict()

    headline = body.get("headline", "").strip()
    news_text = body.get("news_text", "").strip()
    use_auto_scrape = body.get("auto_scrape", False)
    game = body.get("game", "GTA VI").strip() or "GTA VI"
    bgm_track = body.get("bgm_track", None)
    voice = body.get("voice", "en-US-BrianMultilingualNeural")

    background_filename = body.get("background_filename", None)
    bg_cand = None
    if background_filename:
        clean_bg = os.path.normpath(background_filename).replace('\\', '/').lstrip('/')
        if '..' not in clean_bg:
            cand_p = (ASSETS_DIR / "backgrounds" / clean_bg).resolve()
            if not cand_p.exists():
                matches = list((ASSETS_DIR / "backgrounds").glob(f"**/{os.path.basename(clean_bg)}"))
                if matches:
                    cand_p = matches[0].resolve()
            if cand_p.exists() and str(cand_p).startswith(str((ASSETS_DIR / "backgrounds").resolve())):
                bg_cand = str(cand_p)

    task_id = f"task_{int(time.time())}"

    with TASK_LOCK:
        TASK_STATE["task_id"] = task_id
        TASK_STATE["task_type"] = "video"
        TASK_STATE["status"] = "running"
        TASK_STATE["progress"] = 5
        TASK_STATE["message"] = "Initializing render pipeline..."
        TASK_STATE["output_file"] = None
        TASK_STATE["output_url"] = None
        TASK_STATE["caption"] = ""
        TASK_STATE["error"] = None
        TASK_STATE["logs"] = []

    def run_worker():
        global TASK_STATE
        try:
            log_task(f"Engine started for {game}. Preparing parameters...", 10)
            
            # Setup arguments mimicking main.py CLI
            class PipelineArgs:
                def __init__(self):
                    self.news = news_text if not use_auto_scrape else None
                    self.title = headline if (headline and not use_auto_scrape) else None
                    self.game = game
                    self.test = False
                    is_vid = False
                    is_img = False
                    if bg_cand:
                        ext = os.path.splitext(bg_cand)[1].lower()
                        if ext in [".mp4", ".mov", ".mkv", ".webm", ".avi"]:
                            is_vid = True
                        elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
                            is_img = True
                    self.clip = bg_cand if is_vid else None
                    self.hero_image = None  # Video Shorts always auto-curate multi-image scenes from the script
                    self.voice = voice
                    self.bgm_track = bgm_track
                    self.date = None
                    self.no_upload = True  # Never upload directly from UI test click

            args = PipelineArgs()

            # Execute pipeline step by step with live logs
            import main
            log_task("Starting Short video synthesis...", 10)

            # Pass log_task as callback to report live progress to frontend
            output_file = main.run_pipeline(args, progress_cb=log_task)

            if output_file and os.path.exists(output_file):
                fname = os.path.basename(output_file)
                log_task(f"Short rendered successfully! File: {fname}", 100)
                with TASK_LOCK:
                    TASK_STATE["status"] = "success"
                    TASK_STATE["progress"] = 100
                    TASK_STATE["output_file"] = output_file
                    TASK_STATE["output_url"] = f"/media/{fname}"
                    TASK_STATE["message"] = "Short video generated successfully!"
            else:
                raise RuntimeError("Video rendering finished but output file could not be located.")

        except BaseException as e:
            import traceback
            err_trace = traceback.format_exc()
            print(f"[Studio Render Error]\n{err_trace}")
            log_task(f"Error: {str(e)}", 100)
            with TASK_LOCK:
                TASK_STATE["status"] = "error"
                TASK_STATE["error"] = str(e)
                TASK_STATE["message"] = f"Render failed: {str(e)}"

    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()

    return JsonResponse({
        "success": True,
        "task_id": task_id,
        "message": "Video generation launched in background."
    })


def api_get_status(request):
    """Returns current live status and logs of background rendering."""
    with TASK_LOCK:
        return JsonResponse(dict(TASK_STATE))


def api_get_media(request):
    """Returns list of recent generated videos and images in output/."""
    items = []
    files = glob.glob(str(OUTPUT_DIR / "*"))

    for fpath in sorted(files, key=os.path.getmtime, reverse=True):
        fname = os.path.basename(fpath)
        ext = os.path.splitext(fname)[1].lower()
        if ext not in [".mp4", ".png", ".jpg"]:
            continue

        st = os.stat(fpath)
        size_mb = round(st.st_size / (1024 * 1024), 2)
        mod_time = datetime.fromtimestamp(st.st_mtime).strftime("%b %d, %I:%M %p")

        items.append({
            "filename": fname,
            "type": "video" if ext == ".mp4" else "image",
            "url": f"/media/{fname}",
            "size": f"{size_mb} MB",
            "created": mod_time,
            "path": fpath
        })

    return JsonResponse({"success": True, "media": items})


@csrf_exempt
def api_delete_media(request):
    """Deletes a generated media file from output/ directory safely."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST method required"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        body = request.POST.dict()

    filename = body.get("filename", "")
    safe_name = os.path.basename(filename)
    if not safe_name:
        return JsonResponse({"success": False, "error": "Filename is required"}, status=400)

    target_file = OUTPUT_DIR / safe_name
    if target_file.exists():
        try:
            os.remove(target_file)
            return JsonResponse({"success": True, "message": f"Successfully deleted {safe_name}"})
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Failed to delete: {str(e)}"}, status=500)

    return JsonResponse({"success": False, "error": f"File '{safe_name}' not found"}, status=404)
