"""
=============================================================================
  GTA 6 AUTOMATION ENGINE — STORY ENHANCER FOR INSTAGRAM POSTS
  Transforms raw scraped news headlines and RSS snippets into high-impact,
  editorial 4:5 Instagram news post content using Google Gemini Flash.

  Enforces strict editorial constraints:
  1. Strips all trailing source outlet suffixes (" - Root", " | IGN", etc.)
  2. Synthesizes a completely NEW one-sentence summary (strictly 12-18 words),
     never identical to the headline, zero domain names.
  3. Strict hook rules: 'CONFIRMED' / 'OFFICIAL' ONLY for Rockstar / Take-Two;
     otherwise strictly from: NEW, REPORT, RUMOR, LEAK, UPDATE, TRAILER.
  4. Precise category mapping (trailer story = TRAILER, never RELEASE DATE).
  5. Deterministic fallback on API failure: cleaned title, 14-word summary,
     hook = "UPDATE".
=============================================================================
"""

import os
import re
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

try:
    from scripts.config import get_llm_settings
except ImportError:
    from config import get_llm_settings


# ── 1. TITLE CLEANING & SOURCE SUFFIX STRIPPING ─────────────────────────────

KNOWN_OUTLETS = [
    r'Root(?:\-Nation(?:\.com)?)?', r'Mashable', r'Variety', r'Kotaku',
    r'The Hollywood Reporter', r'IGN', r'Dexerto', r'GameSpot',
    r'GamesRadar\+?', r'Polygon', r'PC Gamer', r'Forbes', r'Bloomberg',
    r'Eurogamer(?:\.net)?', r'Screen Rant', r'ComicBook(?:\.com)?', r'Comic Book',
    r'GamingBible', r'TechRadar', r'Digital Trends', r'Insider Gaming',
    r'Rockstar Intel', r'Reddit(?:\s*r/\w+)?', r'BBC', r'CNN', r'The Verge',
    r'YouTube', r'X', r'Twitter', r'Game Rant', r'VG247', r'Rock Paper Shotgun',
    r'Push Square', r'Pure Xbox', r'Sportskeeda', r'Destructoid', r'TheGamer',
    r'AOTF', r'Attack of the Fanboy', r'Tom\'s Guide', r'Tom\'s Hardware',
    r'Wccftech', r'Windows Central', r'Engadget', r'Gizmodo', r'Newsweek',
    r'Yahoo(?:\s*News)?', r'Game Informer', r'Eurogamer', r'Reuters',
    r'DualShockers', r'Hardcore Gamer', r'Video Games Chronicle', r'VGC',
    r'KMVU FOX 26 Medford', r'FOX\s*\d+', r'Complex', r'Stereogum'
]

OUTLET_PATTERN = re.compile(
    r'\s*[\-–—|/]\s*(?:' + '|'.join(KNOWN_OUTLETS) + r')\s*$',
    flags=re.IGNORECASE
)
DOMAIN_PATTERN = re.compile(
    r'\s*[\-–—|/]\s*[\w\.\-]+\.(?:com|org|net|co|io|uk|de|ca|gov|edu)\s*$',
    flags=re.IGNORECASE
)
# For generic unknown outlets at the end of a title, require whitespace before the delimiter
# and match only 2-25 letters/spaces/periods without hyphens:
GENERIC_SUFFIX_PATTERN = re.compile(
    r'\s+[\-–—|/]\s+[A-Za-z0-9\s\.]{2,25}\s*$',
    flags=re.IGNORECASE
)


def clean_scraped_title(title: str) -> str:
    """
    Strips trailing source outlet names and domain suffixes from scraped headlines.
    Examples:
      'Rockstar Reveals the GTA VI Launch Trailer and New Story Details - Root' -> 'Rockstar Reveals the GTA VI Launch Trailer and New Story Details'
      '‘GTA VI’ Trailer Confirms Justice - Variety' -> '‘GTA VI’ Trailer Confirms Justice'
    """
    if not title:
        return ""
    t = str(title).strip()

    # Step 1: Strip domain-style endings (e.g., " - Root-Nation.com")
    t = DOMAIN_PATTERN.sub('', t).strip()

    # Step 2: Strip known gaming outlets
    t = OUTLET_PATTERN.sub('', t).strip()

    # Step 3: Strip any trailing generic delimiter + outlet name if title remains substantial
    m = GENERIC_SUFFIX_PATTERN.search(t)
    if m:
        candidate = t[:m.start()].strip()
        if len(candidate) >= 15:
            t = candidate

    # Step 4: Clean any trailing punctuation artifacts
    t = re.sub(r'[\-–—|/]\s*$', '', t).strip()

    # Step 5: Clean matching outer wrapping quotes only
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        t = t[1:-1].strip()
    elif (t.startswith('‘') and t.endswith('’')) or (t.startswith('“') and t.endswith('”')):
        t = t[1:-1].strip()

    return t


# ── 2. EDITORIAL RULES & VOCABULARY ──────────────────────────────────────────

ALLOWED_GENERAL_HOOKS = {"NEW", "REPORT", "RUMOR", "LEAK", "UPDATE", "TRAILER"}
OFFICIAL_HOOKS = {"CONFIRMED", "OFFICIAL"}


def is_official_source(source: str, headline: str = "") -> bool:
    """Detects if the source is officially Rockstar Games or Take-Two Interactive."""
    src = (source or "").lower()
    hl = (headline or "").lower()
    official_keywords = ["rockstar", "take-two", "take two", "take2", "rockstargames"]
    
    # Official source name
    if any(k in src for k in official_keywords):
        return True
    
    # Or explicitly official communication in headline
    if "rockstar games officially" in hl or "take-two officially" in hl or "official rockstar statement" in hl:
        return True
        
    return False


def infer_story_category(title: str) -> str:
    """Infers the most accurate category tag from headline keywords."""
    tl = (title or "").lower()
    if "trailer" in tl or "teaser" in tl:
        return "TRAILER"
    if any(k in tl for k in ["release", "launch", "date", "window", "delay", "postpone"]):
        return "RELEASE DATE"
    if any(k in tl for k in ["leak", "cyberleek", "datamine", "hacker", "build"]):
        return "EXCLUSIVE LEAK"
    if any(k in tl for k in ["map", "vice city", "leonida", "location", "island", "keys"]):
        return "MAP REVEAL"
    if any(k in tl for k in ["storage", "file size", "gb", "gigabyte", "spec", "specs", "requirement", "hardware", "fps"]):
        return "TECH AND SPECS"
    if any(k in tl for k in ["music", "soundtrack", "score", "song", "radio", "artist"]):
        return "SOUNDTRACK"
    if any(k in tl for k in ["gameplay", "physics", "combat", "mechanic", "weather", "ai", "police"]):
        return "GAMEPLAY"
    if any(k in tl for k in ["award", "game awards", "eligible", "price", "sales", "earnings", "billion"]):
        return "INDUSTRY"
    return "SPECIAL REPORT"


def infer_fallback_hook(title: str, is_official: bool) -> str:
    """Infers valid hook conforming to strict editorial constraints."""
    if is_official:
        return "OFFICIAL"
    tl = (title or "").lower()
    if "trailer" in tl or "teaser" in tl:
        return "TRAILER"
    if "leak" in tl or "cyberleek" in tl or "datamine" in tl:
        return "LEAK"
    if "rumor" in tl or "rumour" in tl:
        return "RUMOR"
    if "report" in tl or "claim" in tl or "analyst" in tl:
        return "REPORT"
    if "new" in tl:
        return "NEW"
    return "UPDATE"


def synthesize_clean_summary(headline: str, category: str, game: str = "GTA VI") -> str:
    """
    Synthesizes a guaranteed 12-18 word summary sentence tailored to the topic.
    Free of domain names, source names, and never identical to the headline.
    """
    g = game or "GTA VI"
    cat = (category or "").upper()
    hl = (headline or "").lower()

    if cat == "TRAILER" or "trailer" in hl:
        # 15 words
        return "Rockstar Games prepares to release brand new cinematic footage showcasing updated story details and graphics."
    elif cat == "SOUNDTRACK" or "score" in hl or "music" in hl or "song" in hl:
        # 16 words
        return "Renowned artists and music producers are reportedly collaborating on an expansive original soundtrack for the game."
    elif cat == "TECH AND SPECS" or "storage" in hl or "size" in hl or "spec" in hl:
        # 15 words
        return "Newly uncovered technical reports outline massive storage requirements and graphics performance expectations on modern consoles."
    elif cat == "RELEASE DATE" or "launch" in hl or "date" in hl or "delay" in hl:
        # 16 words
        return "Publishing schedules and industry analyst reports indicate the highly anticipated title is targeting a 2026 launch."
    elif cat == "EXCLUSIVE LEAK" or "cyberleek" in hl or "leak" in hl:
        # 14 words
        return "Internal development build leaks surface online revealing critical gameplay systems and early engine features."
    elif cat == "MAP REVEAL" or "map" in hl or "vice city" in hl:
        # 15 words
        return "Detailed cartography breakdowns reveal an unprecedented open world map spanning Vice City and surrounding regions."
    elif cat == "GAMEPLAY" or "physics" in hl or "combat" in hl:
        # 15 words
        return "Fresh development reports highlight realistic gameplay mechanics, advanced character physics, and immersive open world features."
    elif cat == "INDUSTRY" or "award" in hl or "price" in hl:
        # 16 words
        return "Industry analysts and gaming publications examine potential awards eligibility and pricing strategy for the upcoming blockbuster."
    else:
        # 15 words
        return f"Latest developments reveal brand new details regarding the upcoming {g} release and gameplay features."


def sanitize_summary(summary: str, headline: str, category: str, game: str = "GTA VI") -> str:
    """
    Validates that summary is strictly 12-18 words, has no domains,
    and is not identical to the headline.
    """
    if not summary:
        return synthesize_clean_summary(headline, category, game)

    # 1. Strip domain names
    s = re.sub(r'\b[A-Za-z0-9\-]+\.(?:com|org|net|co|io|uk|de|ca|gov|edu|info|tv)\b', '', summary, flags=re.IGNORECASE).strip()
    # 2. Strip trailing source mentions
    s = re.sub(r'\s*[\-–—|/]\s*(?:via|by|from)?\s*[A-Z][A-Za-z0-9\s]{2,25}$', '', s).strip()
    s = re.sub(r'\s+', ' ', s).strip()

    # 3. Check similarity to headline
    hl_norm = re.sub(r'[^a-z0-9]', '', headline.lower())
    s_norm = re.sub(r'[^a-z0-9]', '', s.lower())
    if s_norm == hl_norm or (len(s_norm) > 10 and s_norm in hl_norm) or (len(hl_norm) > 10 and hl_norm in s_norm):
        return synthesize_clean_summary(headline, category, game)

    # 4. Check word count
    words = s.split()
    if len(words) < 12 or len(words) > 18:
        # If slightly long, try to truncate to 15 words ending with period
        if len(words) > 18:
            candidate = " ".join(words[:15]).rstrip(".,;:-!?") + "."
            c_words = candidate.split()
            if 12 <= len(c_words) <= 18:
                return candidate
        return synthesize_clean_summary(headline, category, game)

    if not s.endswith(('.', '!', '?')):
        s += '.'
    return s


# ── 3. GEMINI FLASH CALL WITH FALLBACK ────────────────────────────────────────

def call_gemini_json(prompt: str) -> Optional[dict]:
    """Calls Gemini Flash API with a short prompt and parses strictly valid JSON."""
    llm_cfg = get_llm_settings()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or llm_cfg.get("gemini_api_key", "")
    if not api_key:
        return None

    preferred_model = llm_cfg.get("gemini_model", "gemini-2.5-flash")
    models_to_try = [preferred_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
    seen = set()
    models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 300
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    continue
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    continue
                raw_text = parts[0].get("text", "").strip()
                # Clean Markdown code fences
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                return json.loads(raw_text)
        except Exception:
            continue

    return None


# ── 4. PRIMARY TRANSFORMATION FUNCTION ───────────────────────────────────────

def enhance_story_for_post(
    raw_title: str,
    raw_summary: str = "",
    source: str = "",
    game: str = "GTA VI"
) -> Dict[str, str]:
    """
    Transforms a scraped news story into clean Instagram post content.
    Makes exactly ONE Gemini call per story.
    Returns:
      {
        'headline': clean headline (source stripped),
        'summary': 12-18 word new explanation (no domains, != headline),
        'hook': ONE uppercase hook (CONFIRMED/OFFICIAL only for Rockstar/Take-Two),
        'category': matching uppercase category tag (trailer = TRAILER)
      }
    """
    cleaned_title = clean_scraped_title(raw_title)
    is_official = is_official_source(source, cleaned_title)
    target_game = game or "GTA VI"

    prompt = f"""You are an expert gaming news editor. Transform this gaming news item into a JSON object for an Instagram graphic post card.

Original Title: {cleaned_title}
Context: {raw_summary}
Source: {source}
Game: {target_game}

Output strictly valid JSON with these 4 keys:
1. "headline": An engaging, punchy headline in title case or uppercase. NEVER include any source name, trailing dash, or website name.
2. "summary": A completely NEW, one-sentence explanation of what the story is about.
   - MUST be strictly between 12 and 18 words.
   - NEVER repeat or copy the headline.
   - NEVER include domain names or website names (.com, .net, Mashable, Kotaku, Variety, Root, etc.).
3. "hook": Exactly ONE uppercase word.
   - If the source is officially Rockstar Games or Take-Two Interactive, you may use "CONFIRMED" or "OFFICIAL".
   - Otherwise, choose the best word from: "NEW", "REPORT", "RUMOR", "LEAK", "UPDATE", "TRAILER".
4. "category": An accurate uppercase category tag matching the story.
   - If about a trailer or teaser: "TRAILER".
   - If about release date or launch window: "RELEASE DATE".
   - If about gameplay, physics, mechanics: "GAMEPLAY".
   - If about leaks, datamines, hackers: "EXCLUSIVE LEAK".
   - If about map, city, Vice City: "MAP REVEAL".
   - If about storage, file size, specs, tech: "TECH AND SPECS".
   - If about music, soundtrack, audio: "SOUNDTRACK".
   - If about awards, financial, price: "INDUSTRY".
   - Otherwise: "SPECIAL REPORT".

Return ONLY the raw JSON object."""

    gemini_data = call_gemini_json(prompt)

    if gemini_data and isinstance(gemini_data, dict):
        # Extract & sanitize headline
        raw_hl = str(gemini_data.get("headline", cleaned_title)).strip()
        final_headline = clean_scraped_title(raw_hl) or cleaned_title

        # Extract & validate category
        raw_cat = str(gemini_data.get("category", "")).strip().upper()
        # Trailer rule: if story mentions trailer, it MUST be TRAILER, not RELEASE DATE
        if "trailer" in cleaned_title.lower() or "teaser" in cleaned_title.lower():
            final_category = "TRAILER"
        elif raw_cat:
            final_category = raw_cat
        else:
            final_category = infer_story_category(cleaned_title)

        # Extract & validate hook
        raw_hook = str(gemini_data.get("hook", "")).strip().upper()
        if is_official:
            if raw_hook in (ALLOWED_GENERAL_HOOKS | OFFICIAL_HOOKS):
                final_hook = raw_hook
            else:
                final_hook = "CONFIRMED"
        else:
            # Rule 3: NEVER CONFIRMED or OFFICIAL unless Rockstar/Take-Two
            if raw_hook in ALLOWED_GENERAL_HOOKS:
                final_hook = raw_hook
            else:
                final_hook = infer_fallback_hook(cleaned_title, is_official=False)

        # Extract & validate summary
        raw_sum = str(gemini_data.get("summary", "")).strip()
        final_summary = sanitize_summary(raw_sum, final_headline, final_category, target_game)

        return {
            "headline": final_headline,
            "summary": final_summary,
            "hook": final_hook,
            "category": final_category
        }

    # Deterministic fallback when Gemini is unavailable
    fallback_cat = infer_story_category(cleaned_title)
    fallback_hook = "UPDATE"
    fallback_sum = synthesize_clean_summary(cleaned_title, fallback_cat, target_game)

    return {
        "headline": cleaned_title,
        "summary": fallback_sum,
        "hook": fallback_hook,
        "category": fallback_cat
    }
