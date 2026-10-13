"""
=============================================================================
  UNIVERSAL GAME IMAGE FETCHER (ON-DEMAND MULTI-SOURCE ENGINE)
  Fetches genuine 1080p / 4K screenshots, wallpapers & official press art
  for ANY video game on demand (Zero-Cost, $0.00, No API Key Required).
  Sources:
    1. Steam Official Publisher Press CDN (Akamai 1080p/4K)
    2. Wallhaven 4K/8K Community & Concept Art Repository
    3. Bing Direct High-Res Image Scraper
    4. Local 98 4K GTA 6 Screenshot Vault
=============================================================================
"""

import os
import re
import json
import time
import random
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import quote_plus

try:
    from scripts.video_assembler import FOCAL_POINTS
except ImportError:
    try:
        from video_assembler import FOCAL_POINTS
    except ImportError:
        FOCAL_POINTS = {}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

POPULAR_GAMES = [
    {"name": "GTA VI", "slug": "gta6", "category": "Open World / Crime"},
    {"name": "Ghost of Yōtei", "slug": "ghost_of_yotei", "category": "Action / Samurai"},
    {"name": "The Witcher 4", "slug": "the_witcher_4", "category": "RPG / Fantasy"},
    {"name": "Elden Ring", "slug": "elden_ring", "category": "Action RPG / Souls"},
    {"name": "Cyberpunk 2077", "slug": "cyberpunk_2077", "category": "Sci-Fi / RPG"},
    {"name": "Marvel's Wolverine", "slug": "marvel_s_wolverine", "category": "Superhero / Action"},
    {"name": "Call of Duty: Black Ops 6", "slug": "black_ops_6", "category": "FPS / Shooter"},
    {"name": "Assassin's Creed Shadows", "slug": "ac_shadows", "category": "Stealth / Historical"},
    {"name": "Death Stranding 2", "slug": "death_stranding_2", "category": "Sci-Fi / Adventure"},
    {"name": "Doom: The Dark Ages", "slug": "doom_the_dark_ages", "category": "FPS / Action"},
]

NEGATIVE_MEDIA_KEYWORDS = [
    'endgame', 'avengers', 'mcu', 'movie', 'film', 'box office',
    'hollywood', 'theatrical', 'actor', 'actress', 'cast', 'disney+',
    'cinematic universe', 'poster', 'blu-ray', 'dvd', 'cinema'
]

def sanitize_slug(name: str) -> str:
    """Converts a game title into a safe folder slug."""
    s = re.sub(r'[^a-zA-Z0-9]+', '_', name.strip().lower()).strip('_')
    return s if s else "custom_game"


def get_game_slug(name: str) -> str:
    """Returns official preset slug if matching popular games, or sanitizes title."""
    norm = re.sub(r'[^a-z0-9]', '', name.strip().lower())
    for g in POPULAR_GAMES:
        g_norm = re.sub(r'[^a-z0-9]', '', g["name"].lower())
        g_slug_norm = re.sub(r'[^a-z0-9]', '', g["slug"].lower())
        if norm in (g_norm, g_slug_norm):
            return g["slug"]
    if 'wolverine' in norm:
        return 'marvel_s_wolverine'
    if 'yotei' in norm or 'ytei' in norm:
        return 'ghost_of_yotei'
    if 'witcher' in norm:
        return 'the_witcher_4'
    if 'elden' in norm:
        return 'elden_ring'
    if 'cyberpunk' in norm:
        return 'cyberpunk_2077'
    return sanitize_slug(name)


def is_gta6(game_name: str) -> bool:
    """Checks if the query is referring to GTA 6."""
    norm = game_name.strip().lower()
    return norm in {"gta 6", "gta vi", "gta6", "gtavi", "grand theft auto 6", "grand theft auto vi"}


def is_valid_image_bytes(data: bytes) -> bool:
    """Validates that bytes represent a genuine JPEG, PNG, or WebP image."""
    if len(data) < 16:
        return False
    if data.startswith(b'\xff\xd8\xff'):
        return True
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return True
    if data.startswith(b'RIFF') and b'WEBP' in data[8:16]:
        return True
    return False


def classify_screenshot_category(filename: str, game_name: str = "GTA VI") -> str:
    """Classifies a screenshot filename into a smart, user-friendly gallery category."""
    fn = filename.lower()
    
    # 1. GTA 6 Categorization
    if is_gta6(game_name):
        # Duo Shots: Both Jason & Lucia
        if ("jason" in fn and "lucia" in fn) or any(k in fn for k in ["jason_and_lucia", "trailer_29"]):
            return "Lucia & Jason"
        # Solo Lucia
        if any(k in fn for k in ["lucia", "trailer_02", "trailer_03", "trailer_05", "trailer_16", "girl", "bikini", "dress"]) and "jason" not in fn:
            return "Lucia"
        # Solo Jason
        if any(k in fn for k in ["jason", "trailer_20", "duval", "bandana"]) and "lucia" not in fn:
            return "Jason"
        # Heists & Robberies
        if any(k in fn for k in ["stock_305", "heist", "robbery", "trailer_31", "trailer_32", "trailer_34", "store", "cash"]):
            return "Robbery & Heist"
        # Vehicles & Supercars
        if any(k in fn for k in ["cheetah", "car", "grotti", "ambrosia", "_05", "_09", "_15", "_21", "lowrider", "truck", "drive", "ganado", "stanier"]):
            return "Vehicles"
        # Police & Arrest
        if any(k in fn for k in ["cop", "police", "trailer_01", "trailer_11", "trailer_14", "trailer_33", "arrest", "siren"]):
            return "Police"
        # Beach & Ocean
        if any(k in fn for k in ["beach", "_06", "_07", "_08", "_26", "ocean", "water", "boat", "squalo"]):
            return "Beach"
        # Night & Neon
        if any(k in fn for k in ["night", "neon", "_20", "_22", "_28", "_30", "club", "strip"]):
            return "Night & Neon"
        # Nature & Swamps
        if any(k in fn for k in ["swamp", "alligator", "nature", "everglades", "_17", "_18", "_19", "grassrivers"]):
            return "Nature & Swamps"
        return "Cinematic"

    # 2. Marvel's Wolverine
    if "wolverine" in game_name.lower():
        if any(k in fn for k in ["claw", "adamantium"]):
            return "Claws"
        if any(k in fn for k in ["bar", "princess"]):
            return "Princess Bar"
        if any(k in fn for k in ["combat", "logan", "fight"]):
            return "Combat"
        if any(k in fn for k in ["casino", "jean", "patch", "grey"]):
            return "Madripoor"
        if any(k in fn for k in ["suit", "hero", "logo"]):
            return "Key Art"
        return "Cinematic"

    # 3. Ghost of Yotei
    if "yotei" in game_name.lower() or "ghost" in game_name.lower():
        if any(k in fn for k in ["katana", "sword", "dual", "combat"]):
            return "Katana & Combat"
        if any(k in fn for k in ["yotei", "mountain", "hokkaido", "landscape", "snow"]):
            return "Landscape"
        if any(k in fn for k in ["atsui", "mask", "ronin"]):
            return "Character"
        return "Feudal World"

    # 4. The Witcher 4
    if "witcher" in game_name.lower():
        if any(k in fn for k in ["lynx", "medallion", "school"]):
            return "Lynx School"
        if any(k in fn for k in ["monster", "combat", "sword"]):
            return "Combat"
        return "The Continent"

    # 5. Cyberpunk 2077
    if "cyberpunk" in game_name.lower():
        if any(k in fn for k in ["neon", "night", "city"]):
            return "Night City"
        if any(k in fn for k in ["car", "vehicle", "ride"]):
            return "Vehicles"
        return "Characters"

    # 6. Elden Ring
    if "elden" in game_name.lower():
        if any(k in fn for k in ["boss", "combat", "fight"]):
            return "Bosses & Combat"
        if any(k in fn for k in ["erdtree", "shadow", "tree"]):
            return "Erdtree"
        return "Lands Between"

    # Universal Fallback
    if any(k in fn for k in ["combat", "fight", "action"]):
        return "Combat"
    if any(k in fn for k in ["world", "map", "environment", "landscape"]):
        return "World"
    if any(k in fn for k in ["logo", "art", "poster", "cover"]):
        return "Key Art"
    return "Cinematic"


def rank_matching_images(shots: list, headline: str, summary: str = "", game_name: str = "GTA VI") -> list:
    """
    Ranks a list of candidate screenshots by semantic relevance to the news topic.
    Returns list of tuples: (score, reason, shot_dict), sorted with highest score first.
    """
    if not shots:
        return []

    full_text = f"{headline} {summary}".lower()
    game_clean = (game_name or "GTA VI").strip().lower()
    ranked = []

    for s in shots:
        fn = (s.get("filename") or "").lower()
        cat = (s.get("category") or "").lower()
        title = (s.get("title") or "").lower()
        score = 0
        reasons = []

        if is_gta6(game_clean):
            has_lucia_text = bool(re.search(r'\b(lucia|female|woman|girl)\b', full_text))
            has_jason_text = bool(re.search(r'\b(jason|male|guy)\b', full_text))
            has_duo_text = (has_lucia_text and has_jason_text) or bool(re.search(r'\b(duo|partners|couple|protagonists|both|lucia\s*(?:&|and)\s*jason|jason\s*(?:&|and)\s*lucia)\b', full_text))

            # 1. DUO MATCH (Lucia AND Jason)
            if has_duo_text:
                if "jason_and_lucia" in fn:
                    score += 100
                    reasons.append("Lucia & Jason Duo Render")
                elif "lucia & jason" in cat or ("jason" in fn and "lucia" in fn):
                    score += 85
                    reasons.append("Both Lucia & Jason Duo Match")
                elif "trailer_29" in fn:
                    score += 75
                    reasons.append("Duo Car Conversation Scene")
                elif "lucia" in fn or "jason" in fn:
                    score += 15
                    reasons.append("Partial Duo Match")

            # 2. SOLO LUCIA MATCH (News is about Lucia, NOT Jason)
            elif has_lucia_text and not has_jason_text:
                if "lucia_caminos" in fn:
                    score += 100
                    reasons.append("Solo Lucia Hero Render")
                elif any(k in fn for k in ["trailer_02", "trailer_03", "trailer_05", "trailer_16"]):
                    score += 75
                    reasons.append("Solo Lucia Scene")
                elif cat == "lucia" or ("lucia" in fn and "jason" not in fn):
                    score += 65
                    reasons.append("Lucia Character Match")
                elif "lucia & jason" in cat or "jason" in fn:
                    # Penalize duo / Jason shots when news is strictly about Lucia
                    score -= 40

            # 3. SOLO JASON MATCH (News is about Jason, NOT Lucia)
            elif has_jason_text and not has_lucia_text:
                if "jason_duval" in fn:
                    score += 100
                    reasons.append("Solo Jason Hero Render")
                elif any(k in fn for k in ["trailer_20"]):
                    score += 75
                    reasons.append("Solo Jason Scene")
                elif cat == "jason" or ("jason" in fn and "lucia" not in fn):
                    score += 65
                    reasons.append("Jason Character Match")
                elif "lucia & jason" in cat or "lucia" in fn:
                    # Penalize duo / Lucia shots when news is strictly about Jason
                    score -= 40

            # 4. VEHICLES & SUPERCAR PHYSICS
            if any(k in full_text for k in ["car", "vehicle", "drive", "physics", "supercar", "cheetah", "lowrider", "drift", "racing", "speed", "custom"]):
                if cat == "vehicles" or any(k in fn for k in ["cheetah", "grotti", "car", "customs", "trailer_17", "trailer_18", "trailer_22", "ganado", "stanier"]):
                    score += 50
                    reasons.append("Vehicle & Supercar Topic")

            # 5. POLICE, ARREST & PRISON
            if any(k in full_text for k in ["cop", "police", "arrest", "jail", "prison", "siren", "wanted", "pursuit", "bodycam", "cctv"]):
                if cat == "police" or any(k in fn for k in ["police", "cop", "trailer_02", "trailer_04", "trailer_11", "trailer_14"]):
                    score += 50
                    reasons.append("Police & Law Enforcement Topic")

            # 6. BEACH & OCEAN
            if any(k in full_text for k in ["beach", "bikini", "ocean", "coast", "water", "yacht", "boat", "sea", "dolphins"]):
                if cat == "beach" or any(k in fn for k in ["beach", "trailer_06", "trailer_07", "trailer_12", "trailer_14", "squalo"]):
                    score += 50
                    reasons.append("Beach & Ocean Environment")

            # 7. NIGHT & NEON CLUBS
            if any(k in full_text for k in ["night", "neon", "club", "strip", "skyline", "party", "dance", "dj"]):
                if cat == "night & neon" or any(k in fn for k in ["night", "neon", "trailer_19", "trailer_28", "trailer_30"]):
                    score += 50
                    reasons.append("Night & Neon Nightlife")

            # 8. NATURE & SWAMPS
            if any(k in full_text for k in ["swamp", "alligator", "everglades", "nature", "wildlife", "wetlands", "lake", "grassrivers"]):
                if cat == "nature & swamps" or any(k in fn for k in ["swamp", "alligator", "grassrivers", "trailer_10", "trailer_11", "trailer_25"]):
                    score += 50
                    reasons.append("Everglades & Swamp Wildlife")

            # 9. HEIST & STORE ROBBERIES
            if any(k in full_text for k in ["heist", "robbery", "store", "cash", "money", "convenience"]):
                if any(k in fn for k in ["stock_305", "trailer_32", "trailer_33", "trailer_34"]):
                    score += 50
                    reasons.append("Heist & Robbery Action")

        else:
            # ── UNIVERSAL GAME SPECIFIC MATCHING ──
            # Wolverine
            if "wolverine" in game_clean:
                if any(k in full_text for k in ["claw", "adamantium", "combat", "fight", "gore", "bloody", "weapon", "kill"]):
                    if cat in ["claws", "combat"] or any(k in fn for k in ["claw", "combat", "fight"]):
                        score += 55
                        reasons.append("Adamantium Claws & Combat")
                if any(k in full_text for k in ["bar", "princess", "madripoor", "patch", "jean", "casino"]):
                    if cat in ["princess bar", "madripoor"] or any(k in fn for k in ["bar", "princess", "madripoor"]):
                        score += 55
                        reasons.append("Princess Bar & Madripoor")
                if any(k in full_text for k in ["suit", "costume", "yellow", "hero", "look"]):
                    if cat == "key art" or any(k in fn for k in ["suit", "hero", "logo"]):
                        score += 50
                        reasons.append("Costume & Key Art")

            # Ghost of Yōtei
            elif "yotei" in game_clean or "ghost" in game_clean:
                if any(k in full_text for k in ["katana", "sword", "dual", "combat", "fight", "weapon"]):
                    if cat in ["katana & combat", "combat"] or any(k in fn for k in ["katana", "sword", "combat"]):
                        score += 55
                        reasons.append("Dual Katana Combat")
                if any(k in full_text for k in ["mountain", "landscape", "snow", "hokkaido", "map", "world", "yotei"]):
                    if cat in ["landscape", "feudal world"] or any(k in fn for k in ["mountain", "yotei", "landscape", "snow"]):
                        score += 55
                        reasons.append("Mount Yōtei Landscape")
                if any(k in full_text for k in ["atsui", "female", "protagonist", "mask", "ronin"]):
                    if cat == "character" or any(k in fn for k in ["atsui", "mask", "character"]):
                        score += 55
                        reasons.append("Atsui Protagonist")

            # The Witcher 4
            elif "witcher" in game_clean:
                if any(k in full_text for k in ["lynx", "school", "medallion", "ciri", "teaser"]):
                    if cat == "lynx school" or any(k in fn for k in ["lynx", "medallion", "teaser"]):
                        score += 55
                        reasons.append("Lynx School Medallion")
                if any(k in full_text for k in ["monster", "combat", "sword", "fight"]):
                    if cat == "combat" or any(k in fn for k in ["monster", "combat", "sword"]):
                        score += 50
                        reasons.append("Monster Combat")

            # Cyberpunk 2077
            elif "cyberpunk" in game_clean:
                if any(k in full_text for k in ["car", "vehicle", "drive", "ride"]):
                    if cat == "vehicles" or any(k in fn for k in ["car", "vehicle"]):
                        score += 50
                        reasons.append("Night City Vehicles")
                if any(k in full_text for k in ["night city", "neon", "city", "street"]):
                    if cat == "night city" or any(k in fn for k in ["neon", "night", "city"]):
                        score += 50
                        reasons.append("Night City Atmosphere")

            # Elden Ring
            elif "elden" in game_clean:
                if any(k in full_text for k in ["boss", "combat", "messmer", "malenia", "fight"]):
                    if cat == "bosses & combat" or any(k in fn for k in ["boss", "combat"]):
                        score += 55
                        reasons.append("Boss Battle Combat")
                if any(k in full_text for k in ["erdtree", "tree", "shadow", "world"]):
                    if cat in ["erdtree", "lands between"] or any(k in fn for k in ["erdtree", "tree"]):
                        score += 50
                        reasons.append("Erdtree & Lands Between")

            # Universal keyword token overlap
            text_tokens = set(re.findall(r'[a-z0-9]{4,}', full_text))
            stop = {'game', 'this', 'that', 'with', 'from', 'have', 'more', 'about', 'leak', 'news', 'update', 'video', 'confirmed', 'revealed', 'report'}
            meaningful_tokens = text_tokens - stop
            for tok in meaningful_tokens:
                if tok in fn or tok in title or tok in cat:
                    score += 15
                    reasons.append(f"Keyword match '{tok}'")

        primary_reason = reasons[0] if reasons else "Editorial Fit"
        ranked.append((score, primary_reason, s))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked


def find_best_matching_image(shots: list, headline: str, summary: str = "", game_name: str = "GTA VI") -> dict:
    """
    Finds the single best matching screenshot for a news headline and summary.
    100% Deterministic: resolves ties stably by highest score, then alphabetical filename.
    """
    if not shots:
        return None

    ranked = rank_matching_images(shots, headline, summary, game_name)
    if not ranked:
        return shots[0]

    top_score = ranked[0][0]
    if top_score > 0:
        top_tier = [s for sc, r, s in ranked if sc == top_score]
        # Deterministic tie-breaker: sort by filename alphabetically
        top_tier.sort(key=lambda s: s.get("filename", ""))
        return top_tier[0]

    return ranked[0][2]


def get_cached_game_images(slug: str, base_dir: str = None) -> list:
    """Returns local cached images for a game slug, validating magic bytes."""
    if not base_dir:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    game_dir = os.path.join(base_dir, "assets", "backgrounds", slug)
    if not os.path.exists(game_dir):
        return []

    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    cached = []
    for f in sorted(os.listdir(game_dir)):
        ext = os.path.splitext(f)[1].lower()
        if ext in valid_exts:
            full_path = os.path.join(game_dir, f)
            if os.path.getsize(full_path) > 30000:
                try:
                    with open(full_path, "rb") as bf:
                        header = bf.read(64)
                    if not is_valid_image_bytes(header):
                        continue
                except Exception:
                    continue

                rel_url = f"/assets/backgrounds/{slug}/{f}"
                cat = classify_screenshot_category(f, slug.replace("_", " "))
                fx, fy = FOCAL_POINTS.get(f, (0.5, 0.45))
                cached.append({
                    "id": f"{slug}_{f}",
                    "filename": f"{slug}/{f}",
                    "path": full_path,
                    "url": rel_url,
                    "thumb_url": rel_url,
                    "category": cat,
                    "focal_x": fx,
                    "focal_y": fy,
                    "source": "local_cache"
                })
    return cached



def download_single_image(url: str, save_path: str, min_size_kb: int = 40) -> bool:
    """Downloads an image and validates size and magic bytes."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, stream=True)
        if r.status_code == 200:
            temp_path = save_path + ".tmp"
            content = bytearray()
            with open(temp_path, "wb") as f:
                for chunk in r.iter_content(16384):
                    f.write(chunk)
                    if len(content) < 64:
                        content.extend(chunk[:64 - len(content)])
            
            if not is_valid_image_bytes(bytes(content)):
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False

            size_kb = os.path.getsize(temp_path) // 1024
            if size_kb >= min_size_kb:
                if os.path.exists(save_path):
                    os.remove(save_path)
                os.rename(temp_path, save_path)
                return True
            else:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
    except Exception:
        pass
    return False


def fetch_from_steam(game_name: str, max_count: int = 10) -> list:
    """Fetches official press screenshots from the Steam Store API with title matching validation."""
    results = []
    try:
        search_url = f"https://store.steampowered.com/api/storesearch/?term={quote_plus(game_name)}&l=english&cc=US"
        r = requests.get(search_url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            items = r.json().get('items', [])
            if items:
                # Validate title relevance: calculate keyword overlap
                norm_query = set(re.findall(r'[a-z0-9]+', game_name.lower()))
                stop = {'the', 'a', 'an', 'of', 'and', 's', 'in', 'on', 'for', 'to', '4k', 'official'}
                q_keywords = norm_query - stop

                best_app_id = None
                for item in items:
                    item_name = item.get('name', '').lower()
                    item_words = set(re.findall(r'[a-z0-9]+', item_name)) - stop
                    if q_keywords:
                        overlap = len(q_keywords & item_words) / max(len(q_keywords), 1)
                        if overlap >= 0.5:
                            best_app_id = item['id']
                            break

                if best_app_id:
                    details_url = f"https://store.steampowered.com/api/appdetails?appids={best_app_id}"
                    dr = requests.get(details_url, headers=HEADERS, timeout=8)
                    if dr.status_code == 200:
                        ddata = dr.json().get(str(best_app_id), {}).get('data', {})
                        screenshots = ddata.get('screenshots', [])
                        for s in screenshots[:max_count]:
                            full_img = s.get('path_full')
                            thumb_img = s.get('path_thumbnail')
                            if full_img:
                                results.append({
                                    'url': full_img,
                                    'thumb': thumb_img or full_img,
                                    'title': f"{game_name} Official Press Shot",
                                    'source': 'steam'
                                })
    except Exception as e:
        print(f"Steam fetch error for '{game_name}': {e}")
    return results


def fetch_from_wallhaven(game_name: str, max_count: int = 8) -> list:
    """Fetches high-res wallpapers from Wallhaven API (General/Gaming categories only)."""
    results = []
    try:
        clean_q = re.sub(r"['’]s\b", "", game_name, flags=re.IGNORECASE)
        clean_q = re.sub(r'[^a-zA-Z0-9 ]', '', clean_q).strip()
        if clean_q.lower().startswith('marvel'):
            parts = clean_q.split()
            if len(parts) > 1:
                clean_q = " ".join(parts[1:])

        # categories=100 (General only: video games, digital art, 3D renders; excludes Anime & People)
        url = f"https://wallhaven.cc/api/v1/search?q={quote_plus(clean_q)}&categories=100&purity=100&sorting=relevance"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            data = r.json().get('data', [])
            for item in data[:max_count]:
                full_path = item.get('path')
                thumb = item.get('thumbs', {}).get('small') or full_path
                if full_path:
                    results.append({
                        'url': full_path,
                        'thumb': thumb,
                        'title': f"{game_name} 4K Art",
                        'source': 'wallhaven'
                    })
    except Exception as e:
        print(f"Wallhaven fetch error for '{game_name}': {e}")
    return results


def fetch_from_bing(game_name: str, max_count: int = 12) -> list:
    """Fetches high-res gameplay images via Bing with strict negative movie exclusions."""
    results = []
    try:
        clean_name = re.sub(r"['’]s\b", "", game_name, flags=re.IGNORECASE).strip()
        query = f'"{game_name}" video game gameplay screenshot 4k -movie -film -endgame -avengers -mcu -cinematic -"box office"'
        url = f"https://www.bing.com/images/search?q={quote_plus(query)}&form=HDRSC2&first=1"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', class_='iusc'):
                m_raw = a.get('m')
                if m_raw:
                    try:
                        m = json.loads(m_raw)
                        murl = m.get('murl')
                        turl = m.get('turl')
                        title = m.get('t', '').lower()
                        url_lower = (murl or '').lower()

                        if not murl or not murl.startswith('http'):
                            continue

                        # Strict negative filter: discard ANY movie/endgame/MCU reference
                        if any(neg in title or neg in url_lower for neg in NEGATIVE_MEDIA_KEYWORDS):
                            continue

                        # Discard vector / non-photo graphics
                        if any(bad in url_lower for bad in ['.gif', '.svg', 'logo', 'icon']):
                            continue

                        # Check that game title or character appears
                        core_words = [w for w in re.findall(r'[a-z0-9]+', clean_name.lower()) if len(w) > 3 and w not in {'marvel', 'game'}]
                        if core_words and not any(w in title or w in url_lower for w in core_words):
                            continue

                        results.append({
                            'url': murl,
                            'thumb': turl or murl,
                            'title': m.get('t', f"{game_name} Shot"),
                            'source': 'web'
                        })
                    except Exception:
                        pass
                if len(results) >= max_count:
                    break
    except Exception as e:
        print(f"Bing search error for '{game_name}': {e}")
    return results


def fetch_game_images_on_demand(game_name: str, target_count: int = 12, force_refresh: bool = False, base_dir: str = None) -> list:
    """
    Primary API to retrieve or fetch on demand high-resolution screenshots for any game.
    Returns a list of image dicts with local file paths, preview URLs, and metadata.
    """
    if not base_dir:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # If GTA 6, return the 98 authentic 4K screenshots from assets/backgrounds
    if is_gta6(game_name):
        bg_dir = os.path.join(base_dir, "assets", "backgrounds")
        valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
        shots = [
            os.path.join(bg_dir, f) for f in sorted(os.listdir(bg_dir))
            if os.path.isfile(os.path.join(bg_dir, f)) and os.path.splitext(f)[1].lower() in valid_exts
        ] if os.path.exists(bg_dir) else []
        return [
            {
                "id": f"gta6_{os.path.basename(s)}",
                "filename": os.path.basename(s),
                "path": s,
                "url": f"/assets/backgrounds/{os.path.basename(s)}",
                "thumb_url": f"/assets/backgrounds/{os.path.basename(s)}",
                "title": f"GTA VI 4K Frame ({os.path.basename(s)})",
                "category": classify_screenshot_category(os.path.basename(s), "GTA VI"),
                "focal_x": FOCAL_POINTS.get(os.path.basename(s), (0.5, 0.45))[0],
                "focal_y": FOCAL_POINTS.get(os.path.basename(s), (0.5, 0.45))[1],
                "source": "rockstar_universe"
            }
            for s in shots
        ]

    slug = get_game_slug(game_name)
    game_dir = os.path.join(base_dir, "assets", "backgrounds", slug)
    os.makedirs(game_dir, exist_ok=True)

    # 1. Check local cache first unless force refresh requested
    if not force_refresh:
        cached = get_cached_game_images(slug, base_dir)
        if len(cached) >= 4:
            return cached

    # 2. Fetch candidates from all 3 engines
    candidates = []
    
    # Try Steam first (high quality official publisher press shots)
    steam_shots = fetch_from_steam(game_name, max_count=10)
    candidates.extend(steam_shots)

    # Try Wallhaven (4K/8K wallpapers)
    if len(candidates) < target_count:
        wh_shots = fetch_from_wallhaven(game_name, max_count=8)
        candidates.extend(wh_shots)

    # Fallback to Bing Web Search if needed
    if len(candidates) < target_count:
        bing_shots = fetch_from_bing(game_name, max_count=12)
        candidates.extend(bing_shots)

    # Deduplicate candidate URLs
    seen_urls = set()
    unique_candidates = []
    for c in candidates:
        if c['url'] not in seen_urls:
            seen_urls.add(c['url'])
            unique_candidates.append(c)

    # 3. Download top unique candidates locally
    downloaded = []
    for idx, cand in enumerate(unique_candidates, 1):
        if len(downloaded) >= target_count:
            break
        ext = ".jpg"
        if ".png" in cand['url'].lower():
            ext = ".png"
        filename = f"{slug}_{idx:02d}{ext}"
        save_path = os.path.join(game_dir, filename)

        # Download if doesn't exist
        if not os.path.exists(save_path) or os.path.getsize(save_path) < 30000:
            success = download_single_image(cand['url'], save_path, min_size_kb=35)
            if not success and cand.get('thumb'):
                # Try downloading thumbnail if high-res fails
                download_single_image(cand['thumb'], save_path, min_size_kb=20)

        if os.path.exists(save_path) and os.path.getsize(save_path) > 20000:
            rel_url = f"/assets/backgrounds/{slug}/{filename}"
            fx, fy = FOCAL_POINTS.get(filename, (0.5, 0.45))
            downloaded.append({
                "id": f"{slug}_{filename}",
                "filename": f"{slug}/{filename}",
                "path": save_path,
                "url": rel_url,
                "thumb_url": rel_url,
                "title": cand.get('title', f"{game_name} Shot {idx}"),
                "category": classify_screenshot_category(filename, game_name),
                "focal_x": fx,
                "focal_y": fy,
                "source": cand.get('source', 'web')
            })

    # Return downloaded images, or fall back to any existing cached images
    if downloaded:
        return downloaded
    return get_cached_game_images(slug, base_dir)



if __name__ == "__main__":
    print("Testing on-demand fetch for 'Ghost of Yotei'...")
    res = fetch_game_images_on_demand("Ghost of Yotei", target_count=5)
    print(f"Fetched {len(res)} images:")
    for r in res:
        print(" -", r['filename'], "Path:", r['path'], "Size:", os.path.getsize(r['path']) // 1024, "KB")
