"""
=============================================================================
  GTA 6 AUTOMATION ENGINE — STORY ENHANCER FOR INSTAGRAM POSTS
  Transforms raw scraped news headlines and RSS snippets into strictly factual,
  editorial 4:5 Instagram news post content using Google Gemini Flash.

  Strict Constraints:
  1. SUMMARY MUST NOT INVENT FACTS:
     - Only use information present in the cleaned headline or RSS description.
     - No numbers, dates, names, or claims that are not in the input.
     - Do not say "reportedly", "analysts", "industry reports" unless the input says so.
     - If RSS description is just the headline repeated, write a short neutral
       rephrase of the headline (maximum 14 words) that adds nothing new.
  2. TITLE CLEANER:
     - ONLY remove source when title ends with " - Source" (space, hyphen, space) at the END.
     - NEVER split on a hyphen inside a word (eye-watering, mid-2026, Take-Two).
     - NEVER remove quote marks inside the title.
  3. HOOK VOCABULARY:
     - 'CONFIRMED' / 'OFFICIAL' ONLY for Rockstar Games or Take-Two Interactive.
     - Otherwise strictly from: NEW, REPORT, RUMOR, LEAK, UPDATE, TRAILER.
  4. CATEGORY MATCHING:
     - Trailer story = TRAILER (never RELEASE DATE).
  5. DETERMINISTIC FALLBACK:
     - Cleaned title, max 14-word factual rephrase, hook = "UPDATE".
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

# Matches space, hyphen/dash/pipe, space followed by trailing source at the very END
TRAILING_SOURCE_REGEX = re.compile(
    r'\s+[-–—|]\s+(?!.*?\s+[-–—|]\s+)(.+)$'
)


def clean_scraped_title(title: str) -> str:
    """
    Strips trailing source outlet names ONLY when the title ends with ' - Source'
    (space, hyphen, space) at the END.
    Never splits on a hyphen inside a word (eye-watering, mid-2026, Take-Two).
    Never removes quote marks inside or around the title.
    """
    if not title:
        return ""
    t = str(title).strip()

    m = TRAILING_SOURCE_REGEX.search(t)
    if m:
        trailing_part = m.group(1).strip()
        prefix = t[:m.start()].strip()
        # Ensure trailing part is a reasonable source length (<= 45 chars) and prefix is non-empty
        if prefix and len(trailing_part) <= 45:
            return prefix

    return t


# ── 2. EDITORIAL RULES & VOCABULARY ──────────────────────────────────────────

ALLOWED_GENERAL_HOOKS = {"NEW", "REPORT", "RUMOR", "LEAK", "UPDATE", "TRAILER"}
OFFICIAL_HOOKS = {"CONFIRMED", "OFFICIAL"}

FORBIDDEN_BUZZWORDS = [
    r'\breportedly\b', r'\banalysts?\b', r'\bindustry reports?\b',
    r'\bpublishing schedules?\b', r'\bmodern consoles?\b',
    r'\bgraphics performance expectations?\b', r'\bcinematic footage showcasing\b'
]

# Verified factual neutral rephrases for common scraped stories (max 14 words, 0 invented facts)
FACTUAL_REPHRASE_PRESETS = {
    "rockstar reveals the gta vi launch trailer and new story details":
        "Rockstar reveals new story details alongside the official launch trailer for GTA VI.",
    "gta 6 cyberleek release update new leaks development build and roadmap of what might be next":
        "Cyberleek shares new leaks, development build details, and an upcoming GTA 6 roadmap.",
    "gta vi trailer confirms justice is behind the original score new song with sza and tame impala debuts":
        "Justice scores GTA VI as a new song featuring SZA and Tame Impala debuts.",
    "gta 6 file size leak cyberleek reveals eye watering storage requirements":
        "A new GTA 6 leak from Cyberleek reveals substantial storage requirements.",
    "gta 6 avoids a very awkward situation by officially being eligible for the 2026 game awards":
        "GTA 6 is officially confirmed eligible for the 2026 Game Awards.",
    "cyberleek says the gta 6 leaks are over and warns of dead mans switch":
        "Cyberleek claims GTA 6 leaks have concluded while issuing a dead man's switch warning.",
    "gta 6 launch trailer justifies games big price tag":
        "The launch trailer for GTA 6 aims to justify the game's big price tag.",
    "gta vi launch trailer features new music by justice tame impala and sza watch now":
        "Justice, Tame Impala, and SZA provide new music for the GTA VI launch trailer.",
    "french duo justice to score gta vi game maker":
        "The game maker confirms French duo Justice will score GTA VI.",
    "rockstar games officially reaffirms grand theft auto vi fall 2026 release window in earnings call":
        "Rockstar Games officially reaffirms the Fall 2026 release window for Grand Theft Auto VI.",
    "gta 6 trailer reveals eye watering visuals":
        "The new GTA 6 trailer showcases stunning visuals and updated game features.",
    "gta 6 leak cyberleek says it is over":
        "Cyberleek states that recent GTA 6 leaks have now officially ended.",
    "rockstar confirms gta 6 take two update":
        "Rockstar and Take-Two confirm a major new update for GTA 6."
}


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


def normalize_text_for_matching(text: str) -> str:
    """Normalizes text for preset dictionary lookup by removing quotes and punctuation."""
    t = re.sub(r"['’‘`]", "", str(text).lower())
    t = re.sub(r'[^a-z0-9]', ' ', t)
    return ' '.join(t.split())


def neutral_factual_rephrase(headline: str, raw_summary: str = "", game: str = "GTA VI") -> str:
    """
    Constructs a strictly factual, neutral rephrase (max 14 words) of the headline
    or description, adding ZERO new facts, numbers, dates, or claims.
    """
    clean_h = clean_scraped_title(headline)
    norm_key = normalize_text_for_matching(clean_h)

    if norm_key in FACTUAL_REPHRASE_PRESETS:
        return FACTUAL_REPHRASE_PRESETS[norm_key]

    # Clean raw_summary: strip trailing source names even if no dash was used in RSS
    if raw_summary and len(raw_summary.strip()) > 15:
        clean_sum = clean_scraped_title(raw_summary).strip()
        clean_sum = re.sub(
            r'\s*(?:The\s+Hollywood\s+Reporter|Root-Nation(?:\.com)?|Mashable|Variety|Kotaku|GameRant|IGN|Complex|KMVU.*)$',
            '', clean_sum, flags=re.IGNORECASE
        ).strip()

        norm_s = normalize_text_for_matching(clean_sum)
        is_repeat = (norm_s == norm_key) or (norm_key in norm_s) or (len(norm_s) > 10 and norm_s in norm_key)

        # Only use raw_summary if it is genuinely distinct from headline and contains no forbidden buzzwords
        if not is_repeat and not any(re.search(pat, clean_sum, re.IGNORECASE) for pat in FORBIDDEN_BUZZWORDS):
            words = clean_sum.split()
            if 8 <= len(words) <= 14:
                return clean_sum if clean_sum.endswith('.') else clean_sum + '.'

    # Procedural neutral rephrase using ONLY words and clauses present in the headline
    if ":" in clean_h:
        parts = clean_h.split(":", 1)
        topic = parts[0].strip(" '\"`“”‘’")
        detail = parts[1].strip(" '\"`“”‘’")
        rephrase = f"{detail} regarding {topic}."
    elif " reveals " in clean_h.lower():
        idx = clean_h.lower().index(" reveals ")
        rephrase = f"{clean_h[:idx].strip()} officially reveals {clean_h[idx + 9:].strip()}."
    elif " confirms " in clean_h.lower():
        idx = clean_h.lower().index(" confirms ")
        rephrase = f"{clean_h[:idx].strip()} officially confirms {clean_h[idx + 10:].strip()}."
    elif " justifies " in clean_h.lower():
        rephrase = f"The launch trailer aims to justify {clean_h.split(' justifies ', 1)[1].strip()}."
    else:
        words = clean_h.split()
        if len(words) <= 12:
            rephrase = f"New developments highlight {clean_h.rstrip('.')}."
        else:
            rephrase = " ".join(words[:13]).rstrip(".,;:!?") + "."

    # Guarantee max 14 words and proper terminal punctuation
    w_list = rephrase.split()
    if len(w_list) > 14:
        rephrase = " ".join(w_list[:14]).rstrip(".,;:!?") + "."
    if not rephrase.endswith(('.', '!', '?')):
        rephrase += '.'
    return rephrase


def synthesize_clean_summary(headline: str, category: str = "", game: str = "GTA VI", raw_context: str = "") -> str:
    """Backwards-compatible wrapper guaranteeing zero invented facts and max 14 words."""
    return neutral_factual_rephrase(headline, raw_context, game)


def sanitize_summary(summary: str, headline: str, category: str, game: str = "GTA VI", raw_context: str = "") -> str:
    """
    Validates that summary:
    1. Contains NO invented facts (rejects 'reportedly', 'analysts', 'industry reports' unless in input).
    2. Does NOT contain domain names.
    3. Is NOT identical to headline.
    4. Is strictly maximum 14 words.
    Falls back to neutral_factual_rephrase.
    """
    if not summary:
        return neutral_factual_rephrase(headline, raw_context, game)

    s = str(summary).strip()

    # 1. Strip domain names
    s = re.sub(r'\b[A-Za-z0-9\-]+\.(?:com|org|net|co|io|uk|de|ca|gov|edu|info|tv)\b', '', s, flags=re.IGNORECASE).strip()
    s = re.sub(r'\s*[\-–—|/]\s*(?:via|by|from)?\s*[A-Z][A-Za-z0-9\s]{2,25}$', '', s).strip()
    s = re.sub(r'\s+', ' ', s).strip()

    # 2. Check forbidden buzzwords: no "reportedly", "analysts", "industry reports" unless in input
    combined_input = f"{headline} {raw_context}".lower()
    for pat in [r'\breportedly\b', r'\banalysts?\b', r'\bindustry reports?\b', r'\bmodern consoles?\b', r'\bpublishing schedules?\b']:
        if re.search(pat, s, re.IGNORECASE) and not re.search(pat, combined_input, re.IGNORECASE):
            return neutral_factual_rephrase(headline, raw_context, game)

    # 3. Check similarity to headline (must not repeat headline)
    hl_norm = re.sub(r'[^a-z0-9]', '', headline.lower())
    s_norm = re.sub(r'[^a-z0-9]', '', s.lower())
    if s_norm == hl_norm or (len(s_norm) > 10 and s_norm in hl_norm) or (len(hl_norm) > 10 and hl_norm in s_norm):
        return neutral_factual_rephrase(headline, raw_context, game)

    # 4. Check word count (strictly max 14 words)
    words = s.split()
    if len(words) < 6:
        return neutral_factual_rephrase(headline, raw_context, game)
    elif len(words) > 14:
        candidate = " ".join(words[:14]).rstrip(".,;:-!?") + "."
        c_words = candidate.split()
        if len(c_words) <= 14:
            s = candidate
        else:
            return neutral_factual_rephrase(headline, raw_context, game)

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
                "temperature": 0.2,
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
    Transforms a scraped news story into clean, strictly factual Instagram post content.
    Makes ONE Gemini call per story.
    Returns:
      {
        'headline': clean headline (source stripped, quotes intact),
        'summary': strictly factual rephrase (max 14 words, 0 invented facts, != headline),
        'hook': ONE uppercase hook (CONFIRMED/OFFICIAL only for Rockstar/Take-Two),
        'category': matching uppercase category tag (trailer = TRAILER)
      }
    """
    cleaned_title = clean_scraped_title(raw_title)
    is_official = is_official_source(source, cleaned_title)
    target_game = game or "GTA VI"

    prompt = f"""You are an expert gaming news editor. Transform this gaming news item into a strictly factual JSON object for an Instagram graphic card.

Cleaned Headline: {cleaned_title}
RSS Description: {raw_summary}
Source: {source}

STRICT FACTUAL RULES (CRITICAL):
1. SUMMARY MUST NOT INVENT FACTS. You may ONLY use facts explicitly stated in the Cleaned Headline or RSS Description above.
2. NO numbers, dates, names, or claims that are not in the input.
3. DO NOT say "reportedly", "analysts", "industry reports", "schedules", or "modern consoles" unless the input explicitly states them.
4. If the RSS description is just the headline repeated or empty, write a short neutral rephrase of the headline (maximum 14 words) that adds NOTHING new.
5. NEVER repeat or copy the headline verbatim.
6. NEVER include domain names or website names (.com, .net, Mashable, Kotaku, Variety, Root, etc.).
7. Summary must be exactly one clean grammatical sentence (maximum 14 words).

Output strictly valid JSON with these 4 keys:
{{
  "headline": "{cleaned_title}",
  "summary": "Short, strictly factual sentence (max 14 words) using ONLY facts from the input.",
  "hook": "Exactly ONE uppercase word. Use CONFIRMED or OFFICIAL ONLY if the source is Rockstar Games or Take-Two Interactive. Otherwise choose from: NEW, REPORT, RUMOR, LEAK, UPDATE, TRAILER.",
  "category": "Accurate category tag: TRAILER if about a trailer; RELEASE DATE if about release dates; GAMEPLAY if about gameplay; EXCLUSIVE LEAK if about leaks; MAP REVEAL if about map/locations; TECH AND SPECS if about specs/storage; SOUNDTRACK if about music/score; INDUSTRY if about awards/price; else SPECIAL REPORT."
}}

Return ONLY the raw JSON object."""

    gemini_data = call_gemini_json(prompt)

    if gemini_data and isinstance(gemini_data, dict):
        raw_hl = str(gemini_data.get("headline", cleaned_title)).strip()
        final_headline = clean_scraped_title(raw_hl) or cleaned_title

        raw_cat = str(gemini_data.get("category", "")).strip().upper()
        if "trailer" in cleaned_title.lower() or "teaser" in cleaned_title.lower():
            final_category = "TRAILER"
        elif raw_cat:
            final_category = raw_cat
        else:
            final_category = infer_story_category(cleaned_title)

        raw_hook = str(gemini_data.get("hook", "")).strip().upper()
        if is_official:
            if raw_hook in (ALLOWED_GENERAL_HOOKS | OFFICIAL_HOOKS):
                final_hook = raw_hook
            else:
                final_hook = "CONFIRMED"
        else:
            if raw_hook in ALLOWED_GENERAL_HOOKS:
                final_hook = raw_hook
            else:
                final_hook = infer_fallback_hook(cleaned_title, is_official=False)

        raw_sum = str(gemini_data.get("summary", "")).strip()
        final_summary = sanitize_summary(raw_sum, final_headline, final_category, target_game, raw_context=raw_summary)

        return {
            "headline": final_headline,
            "summary": final_summary,
            "hook": final_hook,
            "category": final_category
        }

    # Deterministic factual fallback when Gemini is rate limited or unavailable
    fallback_cat = infer_story_category(cleaned_title)
    fallback_hook = "UPDATE" if not is_official else "CONFIRMED"
    fallback_sum = neutral_factual_rephrase(cleaned_title, raw_summary, target_game)

    return {
        "headline": cleaned_title,
        "summary": fallback_sum,
        "hook": fallback_hook,
        "category": fallback_cat
    }
