"""
Central Configuration Loader for GTA 6 YouTube Shorts Automation
- Loads config.json with fallback defaults
- Automatically loads .env file into os.environ (zero external dependencies)
- Provides structured accessor functions across all pipeline modules
"""
import os
import json
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")


def load_dotenv():
    """Parse .env file into os.environ if present, avoiding third-party dependency."""
    if not os.path.exists(ENV_PATH):
        return
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        print(f"[config] Warning loading .env: {e}")


# Automatically load environment variables on import
load_dotenv()


DEFAULT_CONFIG = {
    "project_name": "GTA 6 YouTube Shorts Automation",
    "creator_handle": "@SamWithJoystick",
    "target_release_date": "2026-11-19",
    "llm": {
        "provider": "auto",
        "gemini_model": "gemini-2.0-flash",
        "claude_model": "claude-haiku-4-5-20251001",
        "temperature": 0.7
    },
    "tts": {
        "engine": "edge-tts",
        "voice": "en-IN-PrabhatNeural",
        "rate": "+13%",
        "pitch": "+0Hz"
    },
    "music": {
        "enabled": True,
        "volume_ducking_db": -21,
        "bgm_path": "assets/music/synthwave_ambience.wav"
    },
    "video": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "cover_duration_seconds": 2.0,
        "max_duration_seconds": 58.0
    },
    "youtube": {
        "privacy_status": "unlisted",
        "category_id": "20",
        "default_tags": [
            "GTA6", "GTA VI", "Grand Theft Auto 6", "GTA 6 news",
            "GTA 6 2026", "Rockstar Games", "GTA 6 leak", "GTA 6 trailer",
            "GTA 6 gameplay", "GTA 6 release date", "gaming news 2026",
            "GamingShorts", "Shorts"
        ]
    }
}


def get_config() -> dict:
    """Load configuration from config.json, merging on top of DEFAULT_CONFIG."""
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                for k, v in user_cfg.items():
                    if isinstance(v, dict) and isinstance(config.get(k), dict):
                        config[k].update(v)
                    else:
                        config[k] = v
        except Exception as e:
            print(f"[config] Warning reading config.json: {e}. Using defaults.")
    return config


def get_target_launch_date() -> date:
    """Returns the parsed target release date as a datetime.date object."""
    cfg = get_config()
    raw_date = cfg.get("target_release_date", "2026-11-19")
    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except Exception:
        return date(2026, 11, 19)


def get_tts_settings() -> dict:
    return get_config().get("tts", DEFAULT_CONFIG["tts"])


def get_music_settings() -> dict:
    return get_config().get("music", DEFAULT_CONFIG["music"])


def get_llm_settings() -> dict:
    return get_config().get("llm", DEFAULT_CONFIG["llm"])


def get_youtube_settings() -> dict:
    return get_config().get("youtube", DEFAULT_CONFIG["youtube"])


def get_video_settings() -> dict:
    return get_config().get("video", DEFAULT_CONFIG["video"])


def get_creator_handle() -> str:
    return get_config().get("creator_handle", DEFAULT_CONFIG["creator_handle"])

