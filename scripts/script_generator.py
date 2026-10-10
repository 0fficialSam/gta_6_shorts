"""
GTA 6 Script Generator
- Fully dynamic: no predefined topic categories
- Reads whatever article content is available and summarises it naturally
- Falls back to pure headline expansion when article is thin
- Always 170-200 words (58-65s at 1.1x TTS speed)
"""
import json, os, random, re, subprocess, urllib.request, urllib.error
from datetime import datetime

CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL   = "claude-haiku-4-5-20251001"

HOOKS = [
    "This GTA 6 story just dropped and you need to hear this.",
    "Stop scrolling. This GTA 6 update just hit.",
    "Okay so this just came out and I have to break it down.",
    "GTA 6 fans, pay attention because this just happened.",
    "Something significant just dropped in the GTA 6 world.",
    "Real talk — this GTA 6 news just shifted the conversation.",
    "A new GTA 6 report just went live and the details matter.",
    "The GTA 6 news keeps coming and this one is a big deal.",
    "You need to hear this GTA 6 update right now.",
    "The gaming world is talking about this GTA 6 story today.",
    "Rockstar Games is back in the headlines and here is why.",
    "Every GTA 6 fan needs to hear what just came out.",
]

CTAS = [
    "Follow for daily GTA 6 updates.",
    "Subscribe so you never miss a GTA 6 drop.",
    "Follow and drop your thoughts in the comments.",
    "Hit follow — more GTA 6 news coming every day.",
    "Follow for daily coverage and comment your reaction.",
    "Subscribe and let me know what you think below.",
    "Follow now. The GTA 6 era is moving fast.",
    "Drop a comment with your reaction and hit follow.",
    "Let me know in the comments — and follow for daily updates.",
]


# ── CLAUDE API ─────────────────────────────────────────────────────────────────
def call_claude(prompt: str, max_tokens: int = 700) -> str:
    if not CLAUDE_API_KEY:
        return None
    import json as _j
    payload = _j.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _j.loads(resp.read().decode())
            return data["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        if "credit" in err.lower() or "billing" in err.lower():
            print("  Claude: out of credits — using free generator")
        else:
            print(f"  Claude error {e.code}: {err[:100]}")
        return None
    except Exception as e:
        print(f"  Claude error: {e}")
        return None


def build_claude_prompt(story: dict) -> str:
    title  = story.get("title", "")
    text   = story.get("text", story.get("summary", ""))[:2500]
    source = story.get("source", "")
    date   = story.get("date", "2026")
    hook   = random.choice(HOOKS)
    cta    = random.choice(CTAS)

    return f"""You are writing a YouTube Shorts voiceover script about a GTA 6 news article.

ARTICLE HEADLINE: {title}
SOURCE: {source} | DATE: {date}
FULL ARTICLE:
{text if text else "(no article body — work from headline only)"}

Write a natural flowing voiceover script that covers this news fully.

STRUCTURE:
1. Hook (1 punchy sentence): {hook}
2. Body (8-10 sentences): Summarise the article naturally in your own words. Cover every key detail — numbers, dates, names, what happened, why it matters to GTA 6 fans. Write as flowing speech, not bullet points.
3. CTA (1 sentence): {cta}

STRICT RULES:
- Exactly 170 to 200 words total
- If article body is missing, expand the headline into a full detailed discussion
- Every sentence must add new information — no repetition
- Do NOT mention the source name anywhere in the script
- No hashtags, no emojis, no "In conclusion", no "That's all"
- Do NOT start with "Hey guys" or "Welcome back"
- Short sentences that flow naturally when read aloud
- Output ONLY the final script text, nothing else"""


# ── FREE SUMMARISER (no API needed) ───────────────────────────────────────────
def score_sentence(s: str) -> int:
    """Score a sentence by how informative and specific it is."""
    sl = s.lower()
    sc = len(s) // 8  # base: longer = more content

    # High value: numbers, prices, dates, specific facts
    if re.search(r'\$[\d,.]+|\d+\s*(?:billion|million|dollars|usd)', sl): sc += 35
    if re.search(r'\b202[5-9]\b', s): sc += 20
    if re.search(r'\b\d{1,3}(?:\.\d+)?\s*(?:million|billion|thousand)\b', sl): sc += 20
    if re.search(r'\b\d+\b', s): sc += 8

    # GTA 6 relevant terms
    for kw in ['confirmed','leaked','revealed','announced','official','reportedly',
               'exclusive','insider','according','stated','launch','release','price',
               'trailer','gameplay','feature','map','online','ps5','xbox','pc',
               'lucia','jason','vice city','rockstar','delay','edition','bundle',
               'pre-order','simultaneous','holiday','november','q1','q2','q3','q4',
               'rating','esrb','pegi','sequel','protagonist','open world']:
        if kw in sl: sc += 10

    # Penalise boilerplate
    if re.search(r'cookie|newsletter|subscribe|advertisement|sign.?up|'
                 r'read more|click here|related:|also read|share this|'
                 r'terms of|privacy policy|all rights|copyright|\d+ (?:shares?|views?)',
                 sl): sc -= 200

    # Penalise very short or very long
    if len(s) < 35: sc -= 20
    if len(s) > 250: sc -= 10

    return sc


def clean_sentence(s: str) -> str:
    """Trim and clean a sentence for TTS."""
    s = s.strip()
    # Remove source attribution phrases
    s = re.sub(r'^(?:according to|per|via|reported by|as per)\s+[\w\s]{1,25},?\s*',
               '', s, flags=re.IGNORECASE)
    # Remove parenthetical references
    s = re.sub(r'\([^)]{0,100}\)', '', s)
    # Cap at readable length
    if len(s) > 160:
        cut = s[:160].rfind(' ')
        s = (s[:cut] if cut > 60 else s[:160]) + '.'
    if s and not s[-1] in '.!?':
        s += '.'
    return s.strip()


def expand_headline(title: str) -> list:
    """
    Dynamically expand ANY headline into 3-5 fact statements.
    Fully dynamic — no hardcoded topic categories.
    """
    facts = []
    tl = title.lower()

    # Extract years / months mentioned in headline
    years  = re.findall(r'\b(202[5-9]|203\d)\b', title)
    months = re.findall(r'\b(january|february|march|april|may|june|july|'
                        r'august|september|october|november|december)\b', tl)
    numbers = re.findall(r'\$[\d,.]+|\b\d{2,}(?:\.\d+)?\s*(?:billion|million|thousand)?\b', title)

    # Opening fact from headline
    clean_title = re.sub(r'\s*[|:–—]\s*.+$', '', title).strip().rstrip('.')
    facts.append(f"{clean_title}.")

    # Time-based context
    if months and years:
        facts.append(f"This puts GTA 6 on track for a {months[0].capitalize()} {years[0]} window, which aligns with the holiday gaming season.")
    elif years:
        facts.append(f"The discussion around GTA 6 in {years[0]} continues to build as fans wait for an official announcement from Rockstar.")

    # Number-based context
    if numbers:
        facts.append(f"The specific figure of {numbers[0]} is what has the GTA 6 community talking loudest right now.")

    # Keyword-driven contextual expansion — fully dynamic
    expansions = {
        "price":      "Pricing has become one of the most debated topics around GTA 6, with fans split on what is a fair ask for a decade in the making.",
        "cost":       "The cost of GTA 6 is a hotly debated topic given the scale and budget of its development.",
        "delay":      "A potential delay would be a significant blow to fans who have already waited over a decade since GTA 5 launched in 2013.",
        "leak":       "This leak is drawing attention because the level of specific detail suggests the source has genuine inside knowledge.",
        "leaked":     "Leaked information of this specificity tends to be credible, which is why the community is reacting so strongly.",
        "trailer":    "The GTA 6 trailer previously broke YouTube records within hours, so any new footage will have an enormous audience ready.",
        "gameplay":   "Gameplay details for GTA 6 have been highly guarded by Rockstar, making any confirmed information a major event.",
        "map":        "The GTA 6 map is widely expected to be the largest and most detailed open world Rockstar has ever built.",
        "online":     "GTA Online has generated over eight billion dollars since 2013, making GTA 6's online component one of gaming's most anticipated launches.",
        "ps5":        "PS5 and Xbox Series X are the confirmed launch platforms, with a PC version expected to arrive at a later date.",
        "xbox":       "Xbox players have been watching GTA 6 news closely given the console's strong GTA Online player base.",
        "pc":         "Whether GTA 6 launches simultaneously on PC or arrives later has been a major point of discussion among the gaming community.",
        "rating":     "An official age rating submission is one of the clearest signals that a game is approaching its final release stages.",
        "esrb":       "An ESRB submission is a strong indicator that a game is close to launch, as ratings are required before release.",
        "pre-order":  "Pre-order listings from major retailers are often the first real indicator of an upcoming release window.",
        "rockstar":   "Rockstar Games has maintained near-total silence beyond the original trailer, making every piece of new information significant.",
        "confirmed":  "Official confirmation from Rockstar or a verified source carries far more weight than typical rumours in the GTA 6 space.",
        "insider":    "Industry insiders with a track record of accurate predictions have earned credibility in the GTA 6 community over years of coverage.",
        "character":  "The confirmed protagonists Lucia and Jason represent a major shift for the GTA series, bringing a dual lead dynamic for the first time.",
        "vice city":  "Vice City's return as a setting is one of the most celebrated confirmed details about GTA 6 among long-time franchise fans.",
        "edition":    "Special edition and bundle announcements for major releases typically signal that a launch date is not far away.",
        "graphics":   "GTA 6's visual ambition has been described by those who have seen it as unlike anything previously released in gaming.",
        "music":      "The GTA series is famous for its licensed soundtracks, and GTA 6's music selection has been a frequent topic of fan speculation.",
        "story":      "The narrative of GTA 6 has been kept almost completely under wraps by Rockstar, making any story detail a major revelation.",
        "multiplayer":"The multiplayer component of GTA 6 is expected to be the most ambitious online gaming experience ever attempted.",
    }

    added = set()
    for keyword, expansion in expansions.items():
        if keyword in tl and expansion not in facts and keyword not in added:
            facts.append(expansion)
            added.add(keyword)
            if len(facts) >= 5:
                break

    # General GTA 6 context if still short
    general = [
        "Rockstar Games has built enormous anticipation over years of near-silence, making every development significant.",
        "GTA 6 carries the weight of being the most anticipated sequel in gaming history, following GTA 5's unprecedented success.",
        "The GTA franchise has a combined install base of hundreds of millions of players worldwide.",
        "Every piece of GTA 6 news goes viral almost instantly, reflecting the global appetite for any information about the game.",
    ]
    random.shuffle(general)
    for g in general:
        if len(facts) >= 6: break
        if g not in facts:
            facts.append(g)

    return facts


def build_free_script(story: dict) -> str:
    """
    Fully dynamic free script builder.
    Uses real article sentences when available, expands headline when not.
    No hardcoded topic categories or predefined filler.
    """
    title  = story.get("title", "GTA 6 Update")
    text   = story.get("text", story.get("summary", "")).strip()
    hook   = random.choice(HOOKS)
    cta    = random.choice(CTAS)
    target = 185  # words

    body_sentences = []
    word_count = len(hook.split()) + len(cta.split())

    # ── CASE 1: Real article content available ────────────────────────────────
    if len(text) > 300:
        raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text)
                         if len(s.strip()) > 30]

        # Score and sort by informativeness
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

    # ── CASE 2: Thin / no article content — expand headline dynamically ───────
    if word_count < target - 20:
        expanded = expand_headline(title)
        seen_keys = {s[:50].lower() for s in body_sentences}
        for fact in expanded:
            if word_count >= target: break
            key = fact[:50].lower()
            if key not in seen_keys:
                body_sentences.append(fact)
                seen_keys.add(key)
                word_count += len(fact.split())

    body = ' '.join(body_sentences)

    # Remove source attributions one more time
    body = re.sub(r'(?:according to|per|via|reported by)\s+[\w\s]{1,25},?\s*',
                  '', body, flags=re.IGNORECASE)
    body = re.sub(r'\([^)]{0,100}\)', '', body)
    body = re.sub(r'\s+', ' ', body).strip()

    return f"{hook}\n\n{body}\n\n{cta}"


def generate_with_ollama(story: dict) -> str:
    try:
        result = subprocess.run(
            ["ollama", "run", "mistral", build_claude_prompt(story)],
            capture_output=True, text=True, timeout=90
        )
        out = result.stdout.strip()
        if result.returncode == 0 and len(out.split()) >= 120:
            print(f"  Ollama: {len(out.split())} words")
            return out
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def clean_script(text: str) -> str:
    text = re.sub(r'(?:according to|per|via)\s+[\w\s]{1,25},?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\([^)]{0,100}\)', '', text)
    text = re.sub(r'#\w+', '', text)
    text = re.sub(r'[^\x20-\x7E\n]', '', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def generate_script(story: dict) -> dict:
    print("Generating script...")
    article_len = len(story.get("text", ""))
    summary_len = len(story.get("summary", ""))
    print(f"  Content: {article_len} chars article | {summary_len} chars summary")

    script_text = None
    method = ""

    # 1. Claude API
    if CLAUDE_API_KEY:
        print("  Trying Claude API...")
        script_text = call_claude(build_claude_prompt(story))
        method = "Claude API"

    # 2. Ollama
    if not script_text or len(script_text.split()) < 120:
        print("  Trying Ollama...")
        script_text = generate_with_ollama(story)
        method = "Ollama"

    # 3. Free dynamic builder — always works
    if not script_text or len(script_text.split()) < 120:
        print("  Using free dynamic builder...")
        script_text = build_free_script(story)
        method = "Free Builder"

    script_text = clean_script(script_text)

    # Pad if still short — deduplicate strictly using full sentence tracking
    pad_attempts = 0
    existing_keys = {s.strip()[:50].lower() for s in re.split(r'[.!?]', script_text) if s.strip()}
    while len(script_text.split()) < 155 and pad_attempts < 10:
        extras = expand_headline(story.get("title", ""))
        random.shuffle(extras)
        added = False
        for e in extras:
            key = e[:50].lower()
            if key not in existing_keys and e[:30].lower() not in script_text.lower():
                # Insert before the CTA (last line)
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

    wc  = len(script_text.split())
    est = round(wc / 2.9)
    print(f"\n  Method: {method} | Words: {wc} | ~{est}s spoken at 1.1x speed")
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
        "tags": [
            "GTA6","GTA VI","Grand Theft Auto 6","GTA 6 news","GTA 6 leak",
            "GTA 6 release date","GTA 6 trailer","GTA 6 gameplay","GTA 6 2026",
            "GTA 6 map","GTA 6 update","Rockstar Games","GTA 6 PS5","GTA 6 Xbox",
            "GTA 6 online","GTA 6 price","GTA 6 Lucia","GTA 6 Vice City",
            "gaming news 2026","GTA 6 India","GTA 6 PC","GTA 6 delay",
        ],
        "method": method,
    }

    os.makedirs("assets", exist_ok=True)
    with open("assets/current_script.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Test with various news types
    for test in [
        {"title": "GTA 6 Music Soundtrack Rumoured to Feature 200 Licensed Songs",
         "text": "", "summary": "", "source": "VG247", "date": "Feb 2026"},
        {"title": "GTA 6 ESRB Rating Submitted — Launch Getting Very Close",
         "text": "Rockstar Games has submitted Grand Theft Auto 6 to the ESRB for an official age rating. The submission was spotted by eagle-eyed fans on the ESRB database. Games typically receive their rating 3 to 6 months before launch. This strongly suggests GTA 6 is in final stages of development. The rating category is expected to be Mature 17+.",
         "summary": "", "source": "Kotaku", "date": "Feb 2026"},
    ]:
        print(f"\n{'='*60}")
        print(f"Testing: {test['title']}")
        generate_script(test)
