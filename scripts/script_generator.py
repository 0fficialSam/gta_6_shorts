"""
GTA 6 Script Generator - Viral Hook Engine & Multi-LLM Orchestrator
===================================================================
- Priority 1: Google Gemini 2.0 / 1.5 Flash API (100% Free Tier, zero credit card)
- Priority 2: Claude Haiku API (if ANTHROPIC_API_KEY set)
- Priority 3: Local Ollama (if installed & running)
- Priority 4: Dynamic Rule-Based Free Builder (works 100% offline, zero APIs)
- Viral Retention: 3 proven Shorts hook frameworks (Curiosity Gap, Contrarian Take, High-Stakes Reveal)
- Target Length: Strictly 160-185 words (52-58s at high-energy pacing)
"""
import json
import os
import random
import re
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

try:
    from scripts.config import get_config, get_llm_settings
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.config import get_config, get_llm_settings

# ── VIRAL RETENTION HOOK FRAMEWORKS ───────────────────────────────────────────
VIRAL_HOOK_FORMULAS = {
    "curiosity_gap": [
        "Rockstar Games just quietly updated something massive, and barely anyone noticed.",
        "There is a hidden detail in the latest GTA 6 report that changes everything.",
        "Nobody was supposed to see this GTA 6 leak yet, but here it is.",
        "Rockstar just made a silent move that has the entire community digging for answers.",
        "A covert GTA 6 development just surfaced, and the implications are crazy.",
        "Stop scrolling. A quiet change from Rockstar just leaked the biggest GTA 6 clue yet.",
    ],
    "contrarian_take": [
        "Everyone thinks GTA 6 is getting delayed, but this latest update proves the opposite.",
        "Gamers are panicking about GTA 6 rumors, but they are looking at the completely wrong clue.",
        "You think you know what Rockstar is planning for Vice City, but this leak says otherwise.",
        "Most people completely misunderstood the latest GTA 6 announcement.",
        "The internet is reacting to this GTA 6 rumor all wrong — here is the actual reality.",
        "Everyone is convinced this GTA 6 feature is cancelled, but new evidence just proved them wrong.",
    ],
    "high_stakes_reveal": [
        "If this new GTA 6 report is accurate, Rockstar just changed open-world gaming forever.",
        "This GTA 6 leak just dropped, and it might be the biggest gaming reveal of 2026.",
        "Stop scrolling right now, because GTA 6 just hit a massive new milestone.",
        "This GTA 6 news just shifted the entire conversation around Rockstar's next masterpiece.",
        "The gaming world just stopped in its tracks over this GTA 6 update.",
        "Take-Two executives just confirmed something about GTA 6 that breaks every record.",
    ]
}

# Standard CTA closers for high YouTube Shorts subscriber conversion
CTAS = [
    "Subscribe for daily GTA 6 leaks and drops.",
    "Follow so you never miss another GTA 6 update.",
    "Drop your reaction in the comments and hit subscribe.",
    "Subscribe now — more GTA 6 news coming every single day.",
    "Let me know what you think in the comments and subscribe.",
    "Hit subscribe and stay ahead of every GTA 6 reveal.",
]


def get_viral_hook(formula_type: str = None) -> tuple[str, str]:
    """Select a viral hook and its formula category."""
    if not formula_type or formula_type not in VIRAL_HOOK_FORMULAS:
        formula_type = random.choice(list(VIRAL_HOOK_FORMULAS.keys()))
    hook_sentence = random.choice(VIRAL_HOOK_FORMULAS[formula_type])
    return formula_type, hook_sentence


# ── GOOGLE GEMINI FLASH API (100% FREE TIER) ──────────────────────────────────
def call_gemini(prompt: str, model: str = None) -> str:
    """
    Calls Google Gemini Flash API via official REST endpoint.
    Zero external dependencies required.
    Free tier allows 15 RPM / 1,500 requests per day with zero billing required.
    """
    llm_cfg = get_llm_settings()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or llm_cfg.get("gemini_api_key", "")
    if not api_key:
        return None

    preferred_model = model or llm_cfg.get("gemini_model", "gemini-2.0-flash")
    models_to_try = [preferred_model, "gemini-2.0-flash", "gemini-1.5-flash"]
    # Preserve order while deduplicating
    seen = set()
    models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        payload = json.dumps({
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": llm_cfg.get("temperature", 0.7),
                "maxOutputTokens": 800
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text = parts[0].get("text", "").strip()
                        if text and len(text.split()) >= 120:
                            print(f"  Gemini Flash ({m}): {len(text.split())} words generated successfully")
                            return text
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            print(f"  Gemini ({m}) HTTP {e.code}: {err[:120]}")
            continue
        except Exception as e:
            print(f"  Gemini ({m}) error: {e}")
            continue

    return None


# ── CLAUDE API ─────────────────────────────────────────────────────────────────
def call_claude(prompt: str, max_tokens: int = 700) -> str:
    llm_cfg = get_llm_settings()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "") or llm_cfg.get("claude_api_key", "")
    if not api_key:
        return None
    model = llm_cfg.get("claude_model", "claude-haiku-4-5-20251001")

    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        if "credit" in err.lower() or "billing" in err.lower():
            print("  Claude: out of credits — falling back to next provider")
        else:
            print(f"  Claude error {e.code}: {err[:100]}")
        return None
    except Exception as e:
        print(f"  Claude error: {e}")
        return None


# ── OLLAMA LOCAL FALLBACK ──────────────────────────────────────────────────────
def generate_with_ollama(prompt: str) -> str:
    try:
        result = subprocess.run(
            ["ollama", "run", "mistral", prompt],
            capture_output=True, text=True, timeout=90
        )
        out = result.stdout.strip()
        if result.returncode == 0 and len(out.split()) >= 120:
            print(f"  Ollama: {len(out.split())} words generated")
            return out
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


# ── PROMPT BUILDER ─────────────────────────────────────────────────────────────
def build_llm_prompt(story: dict, formula_name: str, hook: str, cta: str) -> str:
    title  = story.get("title", "")
    text   = story.get("text", story.get("summary", ""))[:2500]
    source = story.get("source", "")
    date   = story.get("date", "2026")

    return f"""You are an elite YouTube Shorts scriptwriter specializing in high-retention gaming content for Grand Theft Auto VI (GTA 6).

VIRAL HOOK FORMULA: {formula_name.upper().replace('_', ' ')}
MANDATORY OPENING SENTENCE: "{hook}"

ARTICLE CONTEXT:
Headline: {title}
Source: {source} | Date: {date}
Body details:
{text if text else "(No full article body available - thoroughly expand on the headline facts and implications for GTA 6 players)"}

MANDATORY CLOSING SENTENCE: "{cta}"

SCRIPT REQUIREMENTS:
1. Pacing & Length: Strictly 160 to 180 words total (timed for 52-58 seconds at high-energy speech).
2. Structure:
   - Line 1: Use the exact Opening Sentence provided above.
   - Body (7-8 flowing sentences): Break down the news with high excitement. Highlight concrete names, leaks, numbers, map details, dates, or console impact. Keep sentences punchy and conversational.
   - Line Last: Use the exact Closing Sentence provided above.
3. Strict Prohibitions:
   - Do NOT say "Hey guys", "Welcome back", or mention sources like "Kotaku" or "IGN".
   - Do NOT use hashtags, emojis, or markdown markup (no asterisks, bolding, brackets).
   - Do NOT output preamble, labels (like 'Hook:', 'Body:'), or notes. Output ONLY spoken voiceover dialogue.
"""


# ── DYNAMIC FREE SUMMARISER (OFFLINE RULE-BASED BUILDER) ───────────────────────
def score_sentence(s: str) -> int:
    """Score a sentence by its informativeness and GTA relevance."""
    sl = s.lower()
    sc = len(s) // 8

    if re.search(r'\$[\d,.]+|\d+\s*(?:billion|million|dollars|usd)', sl): sc += 35
    if re.search(r'\b202[5-9]\b', s): sc += 20
    if re.search(r'\b\d{1,3}(?:\.\d+)?\s*(?:million|billion|thousand)\b', sl): sc += 20
    if re.search(r'\b\d+\b', s): sc += 8

    for kw in ['confirmed','leaked','revealed','announced','official','reportedly',
               'exclusive','insider','according','stated','launch','release','price',
               'trailer','gameplay','feature','map','online','ps5','xbox','pc',
               'lucia','jason','vice city','rockstar','delay','edition','bundle',
               'pre-order','simultaneous','holiday','november','q1','q2','q3','q4',
               'rating','esrb','pegi','sequel','protagonist','open world']:
        if kw in sl: sc += 10

    if re.search(r'cookie|newsletter|subscribe|advertisement|sign.?up|'
                 r'read more|click here|related:|also read|share this|'
                 r'terms of|privacy policy|all rights|copyright|\d+ (?:shares?|views?)',
                 sl): sc -= 200

    if len(s) < 35: sc -= 20
    if len(s) > 250: sc -= 10
    return sc


def clean_sentence(s: str) -> str:
    s = s.strip()
    s = re.sub(r'^(?:according to|per|via|reported by|as per)\s+[\w\s]{1,25},?\s*',
               '', s, flags=re.IGNORECASE)
    s = re.sub(r'\([^)]{0,100}\)', '', s)
    if len(s) > 160:
        cut = s[:160].rfind(' ')
        s = (s[:cut] if cut > 60 else s[:160]) + '.'
    if s and not s[-1] in '.!?':
        s += '.'
    return s.strip()


def expand_headline(title: str) -> list:
    """Dynamically expands any headline into high-relevance GTA 6 factual statements."""
    facts = []
    tl = title.lower()

    years  = re.findall(r'\b(202[5-9]|203\d)\b', title)
    months = re.findall(r'\b(january|february|march|april|may|june|july|'
                        r'august|september|october|november|december)\b', tl)
    numbers = re.findall(r'\$[\d,.]+|\b\d{2,}(?:\.\d+)?\s*(?:billion|million|thousand)?\b', title)

    clean_title = re.sub(r'\s*[|:–—]\s*.+$', '', title).strip().rstrip('.')
    facts.append(f"{clean_title}.")

    if months and years:
        facts.append(f"This puts GTA 6 firmly in a {months[0].capitalize()} {years[0]} window, aligning with the major holiday gaming season.")
    elif years:
        facts.append(f"The discussions around GTA 6 in {years[0]} continue to ramp up as fans await the next major announcement from Rockstar.")

    if numbers:
        facts.append(f"The specific figure of {numbers[0]} is what has the GTA 6 community buzzing loudest right now.")

    expansions = {
        "price":      "Pricing has become one of the most hotly debated topics around GTA 6, with players discussing what is fair for a decade in development.",
        "cost":       "The cost of GTA 6 is a massive talking point given the unprecedented scale and budget behind Rockstar's development.",
        "delay":      "A potential delay would be a major development for fans who have already waited over a decade since GTA 5 launched in 2013.",
        "leak":       "This leak is drawing massive attention because the specific details suggest genuine inside production knowledge.",
        "leaked":     "Leaked information of this caliber is rare, which is why the gaming community is reacting so strongly.",
        "trailer":    "The initial GTA 6 trailer shattered YouTube records within twenty-four hours, meaning any new footage will instantly dominate the internet.",
        "gameplay":   "Gameplay details for GTA 6 have been tightly guarded by Rockstar, making any confirmed mechanics a massive story.",
        "map":        "The GTA 6 map is widely anticipated to be the largest and most detailed open world Rockstar Games has ever constructed.",
        "online":     "GTA Online has generated billions of dollars, making GTA 6's upcoming multiplayer suite one of the most anticipated releases in history.",
        "ps5":        "PlayStation 5 and Xbox Series consoles are the primary launch targets, with fans waiting eagerly to see pure next-gen performance.",
        "xbox":       "Xbox players are tracking GTA 6 updates closely given the massive active player community across modern platforms.",
        "pc":         "Whether GTA 6 launches day-and-date on PC or arrives later remains one of the top questions among PC enthusiasts.",
        "rating":     "Official age ratings are always among the strongest signals that a title is heading into final production polish.",
        "esrb":       "An ESRB rating is a major milestone, typically indicating a release window is drawing near.",
        "pre-order":  "Retailer pre-order preparations are often the earliest concrete signs that a release timeline is locked in.",
        "rockstar":   "Rockstar Games has kept an extraordinary level of secrecy, making every credible piece of news a major event.",
        "vice city":  "The return of Vice City brings neon-lit streets, sprawling coastlines, and a massive evolution in world immersion.",
        "lucia":      "Lucia and Jason represent a brand-new dynamic for the franchise as the first co-protagonist partnership in modern GTA.",
    }

    added = set()
    for kw, exp in expansions.items():
        if kw in tl and exp not in facts and kw not in added:
            facts.append(exp)
            added.add(kw)
            if len(facts) >= 5:
                break

    general = [
        "Rockstar Games has generated historic levels of anticipation, turning every whisper into a viral headline.",
        "GTA 6 carries the weight of being the most anticipated entertainment release in history.",
        "With hundreds of millions of players worldwide, the stakes for GTA 6 could not be higher.",
        "Every official hint from Rockstar is analyzed frame by frame by millions of players.",
    ]
    random.shuffle(general)
    for g in general:
        if len(facts) >= 6: break
        if g not in facts: facts.append(g)

    return facts


def build_free_script(story: dict, hook: str, cta: str) -> str:
    """Offline rule-based script builder using viral hook structure."""
    title  = story.get("title", "GTA 6 Update")
    text   = story.get("text", story.get("summary", "")).strip()
    target = 175

    body_sentences = []
    word_count = len(hook.split()) + len(cta.split())

    if len(text) > 300:
        raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 30]
        scored = sorted(raw_sentences, key=score_sentence, reverse=True)
        good   = [s for s in scored if score_sentence(s) > 0]

        seen_text = set()
        for s in good:
            if word_count >= target: break
            cleaned = clean_sentence(s)
            key = cleaned[:50].lower()
            if cleaned and key not in seen_text:
                body_sentences.append(cleaned)
                seen_text.add(key)
                word_count += len(cleaned.split())

    if word_count < target - 20:
        expanded = expand_headline(title)
        seen_keys = {s[:50].lower() for s in body_sentences}
        for f in expanded:
            if word_count >= target: break
            key = f[:50].lower()
            if key not in seen_keys:
                body_sentences.append(f)
                seen_keys.add(key)
                word_count += len(f.split())

    script = f"{hook}\n\n" + " ".join(body_sentences) + f"\n\n{cta}"
    return script


def clean_script(text: str) -> str:
    """Cleans raw LLM or template output for voice narration."""
    # Remove markdown headers and markers
    text = re.sub(r'^(?:hook|body|cta|intro|outro):\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'(?:according to|per|via)\s+[\w\s]{1,25},?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\([^)]{0,100}\)', '', text)
    text = re.sub(r'#\w+', '', text)
    text = re.sub(r'[^\x20-\x7E\n]', '', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── MASTER SCRIPT GENERATOR ────────────────────────────────────────────────────
def generate_script(story: dict) -> dict:
    print("Generating script...")
    article_len = len(story.get("text", ""))
    summary_len = len(story.get("summary", ""))
    print(f"  Content: {article_len} chars article | {summary_len} chars summary")

    formula_name, hook = get_viral_hook()
    cta = random.choice(CTAS)
    print(f"  Viral Hook Formula: {formula_name.upper().replace('_', ' ')}")
    print(f"  Opening Hook: \"{hook}\"")

    llm_prompt = build_llm_prompt(story, formula_name, hook, cta)
    script_text = None
    method = ""

    # Priority 1: Google Gemini Flash API (100% Free tier)
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        print("  Trying Google Gemini Flash API...")
        script_text = call_gemini(llm_prompt)
        if script_text:
            method = "Google Gemini Flash (Free)"

    # Priority 2: Claude API
    if not script_text and os.environ.get("ANTHROPIC_API_KEY"):
        print("  Trying Claude API...")
        script_text = call_claude(llm_prompt)
        if script_text:
            method = "Claude API"

    # Priority 3: Local Ollama
    if not script_text or len(script_text.split()) < 120:
        script_text = generate_with_ollama(llm_prompt)
        if script_text:
            method = "Ollama Local"

    # Priority 4: Dynamic Free Offline Builder
    if not script_text or len(script_text.split()) < 120:
        print("  Using dynamic free builder with viral hook...")
        script_text = build_free_script(story, hook, cta)
        method = f"Dynamic Free Builder ({formula_name})"

    script_text = clean_script(script_text)

    # Balance word count strictly around 160-185 words for YouTube Shorts duration
    pad_attempts = 0
    existing_keys = {s.strip()[:50].lower() for s in re.split(r'[.!?]', script_text) if s.strip()}
    while len(script_text.split()) < 155 and pad_attempts < 10:
        extras = expand_headline(story.get("title", ""))
        random.shuffle(extras)
        added = False
        for e in extras:
            key = e[:50].lower()
            if key not in existing_keys and e[:30].lower() not in script_text.lower():
                lines = script_text.rsplit("\n\n", 1)
                if len(lines) == 2:
                    script_text = lines[0] + " " + e + "\n\n" + lines[1]
                else:
                    script_text = script_text.rstrip() + f" {e}"
                existing_keys.add(key)
                added = True
                break
        pad_attempts += 1
        if not added:
            break

    wc = len(script_text.split())
    est_sec = round(wc / 2.9)
    print(f"\n  Method: {method} | Words: {wc} | ~{est_sec}s spoken at 1.12x speed")
    print(f"\n  SCRIPT:\n{'='*55}")
    print(script_text)
    print('='*55)

    yt_titles = [
        "GTA 6 JUST CHANGED EVERYTHING... 🤯",
        "Rockstar SECRETLY Confirmed This About GTA 6",
        "This GTA 6 News Has The Internet Going CRAZY",
        "GTA 6 LEAKED: Nobody Is Ready For This",
        "GTA 6 Just Got MASSIVE News No One Expected",
        "GTA 6 Insiders Are Panicking Right Now...",
        "This Is The GTA 6 News We've All Been Waiting For",
        "Rockstar Just BROKE The Internet With This GTA 6 Drop",
        "GTA 6: This Changes The Release Date Conversation",
        "GTA 6 Update That Has Everyone Talking Right Now",
    ]

    cfg_youtube = get_config().get("youtube", {})
    default_tags = cfg_youtube.get("default_tags", [
        "GTA6", "GTA VI", "Grand Theft Auto 6", "GTA 6 news", "GTA 6 leak",
        "GTA 6 release date", "GTA 6 trailer", "GTA 6 gameplay", "GTA 6 2026",
        "Rockstar Games", "Shorts"
    ])

    result = {
        "story":   story,
        "script":  script_text,
        "title":   random.choice(yt_titles),
        "description": (
            f"GTA 6 latest news!\n\n"
            f"{story.get('title','')}\n\n"
            f"Source: {story.get('source','')} | {story.get('date','')}\n\n"
            f"Subscribe for daily GTA 6 news, leaks, trailers and updates!\n\n"
            f"#Shorts #GTA6 #GTA6News #RockstarGames #Gaming"
        ),
        "tags": default_tags,
        "method": method,
        "hook_formula": formula_name,
    }

    os.makedirs("assets", exist_ok=True)
    with open("assets/current_script.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    test_story = {
        "title": "GTA 6 ESRB Rating Submitted — Launch Getting Very Close",
        "text": "Rockstar Games has submitted Grand Theft Auto 6 to the ESRB for an official age rating. The submission was spotted by eagle-eyed fans on the ESRB database. Games typically receive their rating 3 to 6 months before launch. This strongly suggests GTA 6 is in final stages of development. The rating category is expected to be Mature 17+.",
        "summary": "",
        "source": "Kotaku",
        "date": "2026"
    }
    print(f"\nTesting script generation:")
    generate_script(test_story)
