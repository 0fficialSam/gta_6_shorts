"""
GTA 6 Background Image Fetcher
Auto-downloads real GTA 6 screenshots/artwork to use as video backgrounds.
Run once: python scripts/background_fetcher.py
"""
import os, sys, requests, hashlib, time
from pathlib import Path

SAVE_DIR = "assets/backgrounds"
HEADERS  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Direct-link GTA 6 / Vice City / Rockstar artwork (publicly available promo images)
GTA6_IMAGE_URLS = [
    # Official Rockstar / Newswire press kit images
    "https://media-rockstargames-com.akamaized.net/mfe6/prod/__common/img/71d4d17edcd49703a5f7257df4ee597d.jpg",
    "https://media-rockstargames-com.akamaized.net/mfe6/prod/__common/img/a83aef09a5e43cef60a4f09ad4a4b6d1.jpg",
    # GTA 6 Trailer stills (widely redistributed press images)
    "https://upload.wikimedia.org/wikipedia/en/thumb/a/a5/Grand_Theft_Auto_VI_cover.jpg/220px-Grand_Theft_Auto_VI_cover.jpg",
    # Fallback: vibrant Miami/Vice City style stock photos (free Unsplash)
    "https://images.unsplash.com/photo-1533106418989-88406c7cc8ca?w=1080&q=80",  # Miami neon city
    "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1080&q=80",  # Night cityscape
    "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=1080&q=80",  # Sports car
    "https://images.unsplash.com/photo-1542281286-9e0a16bb7366?w=1080&q=80",  # City night
    "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1080&q=80",  # Urban skyline
    "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1080&q=80",  # City street night
    "https://images.unsplash.com/photo-1514214246283-d427a95c5d2f?w=1080&q=80",  # Neon lights
    "https://images.unsplash.com/photo-1518998053901-5348d3961a04?w=1080&q=80",  # Miami beach
    "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=1080&q=80",  # Luxury car
]


def download_image(url: str, save_path: str) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            size_kb = os.path.getsize(save_path) // 1024
            if size_kb < 5:   # Too small = failed/placeholder
                os.remove(save_path)
                return False
            print(f"  Downloaded ({size_kb}KB): {os.path.basename(save_path)}")
            return True
    except Exception as e:
        print(f"  Failed: {url[:60]}... ({e})")
    return False


def fetch_backgrounds():
    os.makedirs(SAVE_DIR, exist_ok=True)
    existing = list(Path(SAVE_DIR).glob("*.jpg")) + list(Path(SAVE_DIR).glob("*.png"))

    if len(existing) >= 6:
        print(f"Already have {len(existing)} background images in {SAVE_DIR}/")
        return [str(p) for p in existing]

    print(f"Downloading GTA 6 background images to {SAVE_DIR}/...")
    downloaded = []

    for i, url in enumerate(GTA6_IMAGE_URLS):
        ext  = ".jpg" if "jpg" in url or "jpeg" in url else ".jpg"
        uid  = hashlib.md5(url.encode()).hexdigest()[:8]
        path = os.path.join(SAVE_DIR, f"bg_{i:02d}_{uid}{ext}")

        if os.path.exists(path):
            print(f"  Already exists: {os.path.basename(path)}")
            downloaded.append(path)
            continue

        if download_image(url, path):
            downloaded.append(path)
        time.sleep(0.3)   # Be polite

    print(f"\nTotal backgrounds ready: {len(downloaded)}")
    return downloaded


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    imgs = fetch_backgrounds()
    print("Background images:", imgs)
