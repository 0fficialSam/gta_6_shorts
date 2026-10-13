"""
GTA 6 YouTube Shorts Automation
================================
Usage:

  # Fully automatic (scrapes latest GTA 6 news, generates script)
  python main.py

  # Pass your own voiceover script (spoken word for word, no AI rewriting)
  python main.py --news "GTA 6 just got a surprise trailer drop. Rockstar showed four minutes..."

  # Pass script + custom cover headline
  python main.py --news "Your script..." --title "GTA 6 SURPRISE TRAILER JUST DROPPED"

  # Custom background video
  python main.py --clip "C:/Videos/gta6_trailer.mp4"

  # Skip upload, save locally
  python main.py --no-upload

  # Test mode (no scraping, no upload)
  python main.py --test --no-upload

HOW --news AND --title WORK:
  --news "..."    Your full voiceover script. Spoken word for word. No AI rewriting.
  --title "..."   The headline shown on the cover card + the YouTube video title.
                  If --title is NOT given, the first sentence of --news is used as headline.
"""
import os, sys, re, json, argparse, traceback, shutil, random
from datetime import datetime
from scripts.config import get_config, get_youtube_settings

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def setup():
    for d in ["assets", "assets/clips", "assets/backgrounds", "output", "logs"]:
        os.makedirs(d, exist_ok=True)


def log(msg: str):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(f"logs/{datetime.now().strftime('%Y-%m-%d')}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def parse_args():
    p = argparse.ArgumentParser(
        description="GTA 6 YouTube Shorts Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    p.add_argument("--news",      type=str, default=None,
                   help="Your full voiceover script (spoken word for word, no AI rewriting)")
    p.add_argument("--title",     type=str, default=None,
                   help="Cover card headline + YouTube title. Defaults to first sentence of --news.")
    p.add_argument("--clip",      type=str, default=None,
                   help="Path to a video clip (.mp4) to use as background")
    p.add_argument("--no-upload", action="store_true",
                   help="Skip YouTube upload, just save video locally")
    p.add_argument("--post",      action="store_true",
                   help="Generate Instagram 4:5 news post card only")
    p.add_argument("--all",       action="store_true",
                   help="Generate both YouTube Short video and Instagram 4:5 post card")
    p.add_argument("--game",      type=str, default="GTA VI",
                   help="Game title for universal post generator (e.g. 'The Witcher 4', 'Ghost of Yotei', 'Cyberpunk 2077')")
    p.add_argument("--test",      action="store_true",
                   help="Use built-in test story (no internet scraping)")
    return p.parse_args()


def extract_headline(script_text: str, max_len: int = 80) -> str:
    """Pull first sentence from script to use as cover card headline."""
    sentences = re.split(r'(?<=[.!?])\s+', script_text.strip())
    first = sentences[0].strip() if sentences else script_text[:80]
    if len(first) <= max_len:
        return first
    return first[:max_len].rsplit(' ', 1)[0] + "..."


def run_pipeline(args):
    cfg = get_config()
    tts_v = cfg.get("tts", {}).get("voice", "en-US-ChristopherNeural")
    launch_d = cfg.get("target_release_date", "2026-11-19")

    log("=" * 60)
    log("GTA 6 SHORTS AUTOMATION STARTED")
    log(f"  Target Launch : {launch_d}")
    log(f"  Voice Engine  : {tts_v}")
    log(f"  --news        : {(args.news[:60] + '...') if args.news else '(auto-scrape)'}")
    log(f"  --title       : {args.title or '(auto from first sentence of --news)'}")
    log(f"  --clip        : {args.clip or '(auto)'}")
    log(f"  --upload      : {not args.no_upload}")
    log("=" * 60)

    # ── STEP 1: GET NEWS / SCRIPT ──────────────────────────────────
    log("\nSTEP 1: Getting GTA 6 News...")

    if args.news:
        # ── MANUAL MODE ───────────────────────────────────────────
        # Cover card headline = --title if given, else first sentence of script
        if args.title:
            headline = args.title
        else:
            headline = extract_headline(args.news)
            log(f"  No --title given — using first sentence as headline")

        story = {
            "title":   headline,       # shown on cover card
            "url":     "",
            "source":  "Custom",
            "score":   100,
            "text":    args.news,      # full script for voiceover
            "summary": args.news,
            "date":    datetime.now().strftime("%b %d, %Y"),
            "upvotes": 0,
        }
        log(f"  Cover headline : {headline}")
        log(f"  Script preview : {args.news[:70]}...")

    elif args.test:
        # ── TEST MODE ─────────────────────────────────────────────
        story = {
            "title":   "GTA 6 Release Date CONFIRMED for 2026",
            "url":     "",
            "source":  "Test Mode",
            "score":   100,
            "text":    (
                "Rockstar has officially confirmed GTA 6 for a 2026 release on PS5 and Xbox Series X. "
                "The game features Lucia as the first female protagonist in the mainline GTA series. "
                "The setting is a modern reimagining of Vice City inspired by Miami. "
                "The map is reportedly larger than GTA 5 and Red Dead Redemption 2 combined. "
                "Industry analysts project GTA 6 will break all entertainment revenue records on launch day."
            ),
            "summary": "",
            "date":    datetime.now().strftime("%b %d, %Y"),
            "upvotes": 0,
        }
        log("  TEST MODE: Using built-in sample story")

    else:
        # ── AUTO MODE: scrape latest gaming news ───────────────────
        try:
            from scripts.news_scraper import get_top_story
            game_target = getattr(args, "game", "GTA VI") or "GTA VI"
            story = get_top_story(game=game_target)
            log(f"  Scraped ({game_target}): {story['title'][:70]}")
        except Exception as e:
            log(f"  Scraping failed: {e}\n{traceback.format_exc()}")
            sys.exit(1)

    # ── OPTIONAL: GENERATE INSTAGRAM POST ─────────────────────────
    if getattr(args, "post", False) or getattr(args, "all", False):
        log("\nGenerating Instagram 4:5 News Post Card...")
        try:
            from scripts.instagram_generator import generate_instagram_post
            game_title = getattr(args, "game", "GTA VI") or "GTA VI"
            ig_res = generate_instagram_post(
                headline=story.get("title", ""),
                summary=story.get("summary", story.get("text", "")[:250]),
                game_title=game_title,
                source_credit=story.get("source", "Rockstar Intel")
            )
            log(f"  Instagram Post saved: {os.path.abspath(ig_res['image_path'])}")
            if getattr(args, "post", False):
                log("\n" + "=" * 60)
                log(f"DONE (--post for {game_title})! Skipped video rendering.")
                log(f"  Card : {os.path.abspath(ig_res['image_path'])}")
                log("=" * 60)
                return ig_res["image_path"]
        except Exception as e:
            log(f"  Instagram card generation error: {e}")

    # ── STEP 2: GENERATE SCRIPT ───────────────────────────────────
    log("\nSTEP 2: Generating Script...")
    try:
        YT_TITLES = [
            "GTA 6 JUST CHANGED EVERYTHING",
            "Rockstar SECRETLY Confirmed This About GTA 6",
            "This GTA 6 News Has The Internet Going CRAZY",
            "GTA 6 LEAKED: Nobody Is Ready For This",
            "GTA 6 Just Got MASSIVE News No One Expected",
            "GTA 6 Insiders Are Panicking Right Now",
            "This Is The GTA 6 News We Have All Been Waiting For",
            "Rockstar Just BROKE The Internet With This GTA 6 Drop",
            "GTA 6 Update That Has Everyone Talking Right Now",
        ]

        if args.news and len(args.news.split()) >= 70:
            # ── MANUAL FULL SCRIPT: use script exactly as-is, zero rewriting ──
            yt_title    = args.title if args.title else random.choice(YT_TITLES)
            description = (
                "GTA 6 latest news!\n\n"
                + story["title"] + "\n\n"
                + "Subscribe for daily GTA 6 news, leaks, trailers and updates!\n\n"
                + "#Shorts #GTA6 #GTA6News #RockstarGames #Gaming"
            )
            script_data = {
                "story":       story,
                "script":      args.news,    # exact script, no AI rewriting
                "title":       yt_title,
                "description": description,
                "tags": get_youtube_settings().get("default_tags", [
                    "GTA6", "GTA VI", "Grand Theft Auto 6", "GTA 6 news",
                    "GTA 6 2026", "Rockstar Games", "GTA 6 leak", "GTA 6 trailer",
                    "GTA 6 gameplay", "GTA 6 release date", "gaming news 2026",
                    "GamingShorts", "Shorts",
                ]),
                "method": "Manual (user provided)",
            }
            log(f"  Using script as-is: {len(args.news.split())} words")

        else:
            # ── AUTO / TOPIC EXPANSION: generate full 50s Short script (120-135 words) ──
            from scripts.script_generator import generate_script
            script_data = generate_script(story)
            if args.title:
                script_data["title"] = args.title

        log(f"  Script ready: {len(script_data['script'].split())} words via {script_data['method']}")

    except Exception as e:
        log(f"  Script generation failed: {e}\n{traceback.format_exc()}")
        sys.exit(1)

    # ── STEP 3: VOICEOVER ─────────────────────────────────────────
    log("\nSTEP 3: Generating Voiceover...")
    try:
        from scripts.voiceover import generate_voiceover
        vo_kwargs = {}
        if getattr(args, "voice", None):
            vo_kwargs["voice"] = args.voice
        if getattr(args, "bgm_track", None):
            script_data["bgm_track"] = args.bgm_track
        audio_path = generate_voiceover(script_data, **vo_kwargs)
        log(f"  Audio saved: {audio_path}")
    except Exception as e:
        log(f"  Voiceover failed: {e}\n{traceback.format_exc()}")
        sys.exit(1)

    # ── STEP 4: RESOLVE BACKGROUND CLIP ──────────────────────────
    log("\nSTEP 4: Resolving Background...")
    clip_path = None

    if args.clip:
        if not os.path.exists(args.clip):
            log(f"  WARNING: Clip not found at '{args.clip}' — using auto background")
        else:
            dest = os.path.join("assets/clips", os.path.basename(args.clip))
            if not os.path.exists(dest):
                shutil.copy2(args.clip, dest)
                log(f"  Copied clip to: {dest}")
            clip_path = dest
            log(f"  Using custom clip: {args.clip}")
    else:
        log("  No clip provided — using auto background")

    # ── STEP 5: ASSEMBLE VIDEO ────────────────────────────────────
    log("\nSTEP 5: Assembling Video...")
    try:
        from scripts.video_assembler import assemble_video
        if not os.path.exists(audio_path):
            alt = audio_path.replace(".mp3", ".wav") if ".mp3" in audio_path else audio_path.replace(".wav", ".mp3")
            if os.path.exists(alt):
                audio_path = alt

        video_path = assemble_video(script_data, audio_path, clip_override=clip_path)
        log(f"  Video created: {video_path}")
    except Exception as e:
        log(f"  Video assembly failed: {e}\n{traceback.format_exc()}")
        sys.exit(1)

    # ── STEP 6: UPLOAD ────────────────────────────────────────────
    log("\nSTEP 6: YouTube Upload...")
    if args.no_upload:
        log("  Skipped (--no-upload flag set)")
        log(f"  Your video is at: {os.path.abspath(video_path)}")
    else:
        try:
            from scripts.youtube_uploader import upload_video
            result = upload_video(video_path, script_data, mode="upload")
            log(f"  Uploaded: {result}")
        except Exception as e:
            log(f"  Upload failed: {e}")
            log(f"  Video saved locally: {video_path}")

    log("\n" + "=" * 60)
    log("DONE!")
    log(f"  Story : {story['title'][:60]}")
    log(f"  Video : {os.path.abspath(video_path)}")
    log("=" * 60)
    return video_path


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    setup()
    args = parse_args()
    run_pipeline(args)