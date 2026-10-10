"""
GTA 6 News Scraper
- Deduplicates by semantic similarity (catches same story from different outlets)
- Prioritises direct gaming site RSS over Google News aggregates
- Fetches full article body text
- Tracks used stories to never repeat
"""
import feedparser, json, os, re, requests, hashlib, time, random
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

# ── Direct gaming sites first, Google News as fallback only ───────────────────
RSS_FEEDS = [
    # Direct gaming sites — unique original articles, easier to scrape
    {"url": "https://kotaku.com/rss",                                     "name": "Kotaku",        "priority": 1},
    {"url": "https://www.ign.com/rss/articles",                           "name": "IGN",           "priority": 1},
    {"url": "https://www.eurogamer.net/?format=rss",                      "name": "Eurogamer",     "priority": 1},
    {"url": "https://www.gamesradar.com/rss/",                            "name": "GamesRadar",    "priority": 1},
    {"url": "https://gamerant.com/feed/",                                 "name": "Game Rant",     "priority": 1},
    {"url": "https://www.vg247.com/feed",                                 "name": "VG247",         "priority": 1},
    {"url": "https://www.rockpapershotgun.com/feed",                      "name": "RPS",           "priority": 1},
    {"url": "https://www.pcgamer.com/rss/",                               "name": "PC Gamer",      "priority": 1},
    {"url": "https://www.polygon.com/rss/index.xml",                      "name": "Polygon",       "priority": 1},
    {"url": "https://www.thegamer.com/feed/",                             "name": "TheGamer",      "priority": 1},
    {"url": "https://screenrant.com/feed/",                               "name": "Screen Rant",   "priority": 1},
    {"url": "https://attackofthefanboy.com/feed/",                        "name": "AOTF",          "priority": 1},
    {"url": "https://www.sportskeeda.com/gta/feed",                       "name": "Sportskeeda",   "priority": 1},
    {"url": "https://www.dexerto.com/feed/",                              "name": "Dexerto",       "priority": 1},
    {"url": "https://www.destructoid.com/feed/",                          "name": "Destructoid",   "priority": 1},
    {"url": "https://www.pushsquare.com/feeds/latest",                    "name": "Push Square",   "priority": 1},
    {"url": "https://www.purexbox.com/feeds/latest",                      "name": "Pure Xbox",     "priority": 1},
    # Google News as fallback — lower priority, high duplication
    {"url": "https://news.google.com/rss/search?q=%22GTA+6%22+2026&hl=en-US&gl=US&ceid=US:en",               "name": "Google News", "priority": 2},
    {"url": "https://news.google.com/rss/search?q=%22GTA+6%22+leak+OR+confirmed+OR+trailer&hl=en-US&gl=US&ceid=US:en", "name": "Google Leaks","priority": 2},
]

# PRIMARY: must contain at least one of these exact phrases
KEYWORDS_PRIMARY = [
    'gta 6', 'gta6', 'gta vi', 'grand theft auto 6', 'grand theft auto vi',
    'gta 6 release', 'gta 6 leak', 'gta 6 trailer', 'gta 6 gameplay',
    'gta 6 map', 'gta 6 price', 'gta 6 date', 'gta 6 delay',
    'gta 6 ps5', 'gta 6 xbox', 'gta 6 online', 'gta 6 pc',
    'gta 6 2026', 'gta six',
]

# SECONDARY: only valid when combined with a primary GTA term
KEYWORDS_SECONDARY = [
    'rockstar games', 'vice city', 'lucia', 'jason',
]

# HARD EXCLUSIONS: reject any story containing these regardless
EXCLUSIONS = [
    'twitch', 'streamer', 'youtuber', 'tiktok', 'instagram', 'twitter user',
    'charity stream', 'island survival', 'weight loss', 'raised money',
    'content creator', 'esports', 'fortnite', 'minecraft', 'call of duty',
    'warzone', 'roblox', 'valorant', 'league of legends', 'apex legends',
    'world of warcraft', 'pokemon', 'nba 2k', 'fifa', 'ea sports',
    'activision', 'ubisoft', 'nintendo', 'the last of us', 'god of war',
    'elden ring', 'cyberpunk', 'starfield', 'halo', 'destiny',
]

KEYWORDS = KEYWORDS_PRIMARY  # backwards compat

VIRAL_WORDS = [
    'leak','confirmed','secret','exclusive','release date','gameplay',
    'official','huge','shocking','revealed','breaking','trailer',
    'price','map','online','delay','insider','rumour','rumor','2026',
    'esrb','rating','pre-order','bundle','soundtrack','modding',
]

MAX_AGE_DAYS   = 7   # Only last 7 days
USED_NEWS_FILE = "assets/used_news.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

# ── HTML STRIPPER ─────────────────────────────────────────────────────────────
class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
        self.skip = {'script','style','nav','footer','header','aside','iframe','noscript','svg','form','button'}
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip: self.depth += 1

    def handle_endtag(self, tag):
        if tag in self.skip and self.depth > 0: self.depth -= 1

    def handle_data(self, d):
        if self.depth == 0: self.fed.append(d)

    def get_data(self):
        return ' '.join(self.fed)

def strip_html(html: str) -> str:
    s = HTMLStripper()
    try:
        s.feed(html)
        return re.sub(r'\s+', ' ', s.get_data()).strip()
    except:
        return re.sub(r'<[^>]+>', ' ', html).strip()


# ── SEMANTIC DEDUPLICATION ────────────────────────────────────────────────────
def normalise_title(title: str) -> str:
    """
    Strip outlet names, punctuation, common words → core topic fingerprint.
    'GTA 6 Price Leak - IGN' and 'GTA 6 Price Leak | Kotaku' → same fingerprint.
    """
    # Remove outlet name suffixes added by Google News / aggregators
    title = re.sub(r'\s*[-–|]\s*[\w\s,&\.]{2,35}$', '', title)
    # Lowercase, remove punctuation
    title = title.lower()
    title = re.sub(r'[^\w\s]', ' ', title)
    # Remove stop words and filler
    stopwords = {'the','a','an','is','are','for','to','in','on','at','of','and',
                 'or','but','with','by','from','this','that','has','have','been',
                 'will','would','could','should','may','might','all','you','your',
                 'check','here','details','everything','know','need','what','how',
                 'why','when','where','who','which','expected','reportedly','said'}
    words = [w for w in title.split() if w not in stopwords and len(w) > 2]
    return ' '.join(sorted(words))  # sorted so word order doesn't matter


def topic_fingerprint(title: str) -> str:
    """Create a short fingerprint of the core topic for dedup."""
    norm = normalise_title(title)
    # Extract the most meaningful 4 words
    words = norm.split()[:8]
    key = ' '.join(words)
    return hashlib.md5(key.encode()).hexdigest()[:8]


def titles_are_same_story(t1: str, t2: str) -> bool:
    """
    True if two titles are covering the same story.
    Uses word overlap — 60%+ overlap = same story.
    """
    n1 = set(normalise_title(t1).split())
    n2 = set(normalise_title(t2).split())
    if not n1 or not n2:
        return False
    overlap = len(n1 & n2)
    smaller = min(len(n1), len(n2))
    return (overlap / smaller) >= 0.60


# ── USED NEWS TRACKER ─────────────────────────────────────────────────────────
def load_used_news() -> dict:
    os.makedirs('assets', exist_ok=True)
    if os.path.exists(USED_NEWS_FILE):
        try:
            with open(USED_NEWS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {'used_ids': [], 'used_titles': [], 'history': []}

def save_used_news(registry: dict):
    with open(USED_NEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

def story_id(story: dict) -> str:
    key = story.get('title', '') + story.get('url', '')
    return hashlib.md5(key.lower().encode()).hexdigest()[:12]

def is_already_used(story: dict, registry: dict) -> bool:
    sid = story_id(story)
    if sid in registry.get('used_ids', []):
        return True
    # Also check semantic similarity against previously used titles
    title = story.get('title', '')
    for used_title in registry.get('used_titles', []):
        if titles_are_same_story(title, used_title):
            return True
    return False

def mark_as_used(story: dict, registry: dict):
    sid = story_id(story)
    if sid not in registry['used_ids']:
        registry['used_ids'].append(sid)
    title = story.get('title', '')
    if title and title not in registry.get('used_titles', []):
        registry.setdefault('used_titles', []).append(title)
    registry['history'].append({
        'id': sid,
        'title': title,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'source': story.get('source', ''),
    })
    # Keep last 300
    if len(registry['used_ids']) > 300:
        registry['used_ids']    = registry['used_ids'][-300:]
        registry['used_titles'] = registry.get('used_titles', [])[-300:]
        registry['history']     = registry['history'][-300:]
    save_used_news(registry)


# ── DATE PARSING ──────────────────────────────────────────────────────────────
def parse_date(entry) -> datetime | None:
    for field in ['published', 'updated']:
        val = entry.get(field, '')
        if val:
            try: return parsedate_to_datetime(val)
            except: pass
    return None

def is_recent(entry) -> bool:
    dt = parse_date(entry)
    if dt is None: return True
    try: return dt >= datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    except: return True

def get_date_str(entry) -> str:
    dt = parse_date(entry)
    return dt.strftime('%b %d, %Y') if dt else 'Recent'

def score_headline(title: str) -> int:
    tl = title.lower()
    if not any(kw in tl for kw in KEYWORDS): return 0
    score = 20
    for w in VIRAL_WORDS:
        if w in tl: score += 8
    if '2026' in title: score += 15
    return score

def is_gta6(title: str, summary: str = '') -> bool:
    """
    Strict GTA 6 relevance check.
    Requires a primary GTA 6 keyword AND no hard exclusions.
    Secondary keywords (rockstar, vice city, lucia, jason) only count
    when a primary keyword is also present.
    """
    combined = (title + ' ' + summary).lower()

    # Reject immediately if any exclusion keyword found
    for excl in EXCLUSIONS:
        if excl in combined:
            return False

    # Must contain at least one PRIMARY keyword
    has_primary = any(kw in combined for kw in KEYWORDS_PRIMARY)
    if has_primary:
        return True

    # Secondary keywords only valid alongside rockstar/GTA context
    has_secondary = any(kw in combined for kw in KEYWORDS_SECONDARY)
    if has_secondary:
        # Must also have gta or rockstar in the same text
        has_context = any(w in combined for w in ['gta', 'grand theft', 'rockstar'])
        return has_context

    return False

def clean_title(title: str) -> str:
    """Remove source name suffixes that Google News / aggregators append."""
    # Pattern: "Article Title - Source Name" or "Article Title | Source Name"
    cleaned = re.sub(r'\s*[-–—|]\s*[\w\s,&\.]{2,40}$', '', title).strip()
    return cleaned if len(cleaned) > 20 else title


# ── FULL ARTICLE FETCHER ──────────────────────────────────────────────────────
GENERIC_SELECTORS = [
    r'<article[^>]*>(.*?)</article>',
    r'<div[^>]*itemprop="articleBody"[^>]*>(.*?)</div>',
    r'<div[^>]*class="[^"]*(?:article-body|article__body|post-body|post-content|entry-content|story-body|content-body|article-content|story-content|body-content)[^"]*"[^>]*>(.*?)(?=<div[^>]*class="[^"]*(?:related|tags|comments|sidebar|footer|share))',
    r'<main[^>]*>(.*?)</main>',
]

BOILERPLATE = [
    r'subscribe\s+(?:to|for)[^.]{0,60}\.',
    r'sign\s+up\s+for[^.]{0,60}\.',
    r'(?:follow|like)\s+us\s+on[^.]{0,40}\.',
    r'advertisement[^.]{0,30}\.',
    r'cookie\s+(?:policy|settings?)[^.]{0,40}\.',
    r'(?:read|see)\s+(?:more|also)[:\s][^.]{0,80}\.',
    r'related:[^.]{0,80}\.',
    r'click\s+here[^.]{0,40}\.',
    r'share\s+this[^.]{0,40}\.',
    r'©\s*\d{4}[^.]{0,60}\.',
    r'all\s+rights?\s+reserved[^.]{0,40}\.',
    r'\d+\s+(?:shares?|comments?|views?)\b[^.]{0,30}\.',
]

def fetch_article(url: str) -> str:
    if not url or 'google.com' in url:
        return ''
    try:
        resp = requests.get(url, headers=HEADERS, timeout=18, allow_redirects=True)
        if resp.status_code != 200:
            return ''
        html = resp.text

        # Strip non-content blocks
        html = re.sub(
            r'<(script|style|nav|footer|header|aside|iframe|noscript|form)[^>]*>.*?</\1>',
            ' ', html, flags=re.DOTALL | re.IGNORECASE
        )

        # Try selectors
        extracted = ''
        for sel in GENERIC_SELECTORS:
            m = re.search(sel, html, re.DOTALL | re.IGNORECASE)
            if m:
                candidate = strip_html(m.group(1))
                if len(candidate) > len(extracted):
                    extracted = candidate
            if len(extracted) > 600:
                break

        # Fallback: all <p> tags
        if len(extracted) < 300:
            paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE)
            p_text = ' '.join(strip_html(p) for p in paras if len(strip_html(p)) > 40)
            if len(p_text) > len(extracted):
                extracted = p_text

        if len(extracted) < 100:
            return ''

        # Clean boilerplate
        for pat in BOILERPLATE:
            extracted = re.sub(pat, '', extracted, flags=re.IGNORECASE)

        extracted = re.sub(r'\s+', ' ', extracted).strip()
        return extracted[:4000]

    except Exception as e:
        return ''


# ── RSS SCRAPING ──────────────────────────────────────────────────────────────
def scrape_feeds() -> list:
    print('Scraping RSS feeds...')
    raw_stories = []
    seen_urls   = set()

    # Sort feeds: direct sites first (priority 1), Google News last (priority 2)
    sorted_feeds = sorted(RSS_FEEDS, key=lambda f: f.get('priority', 2))

    for feed_info in sorted_feeds:
        try:
            resp = requests.get(feed_info['url'], headers=HEADERS, timeout=12)
            feed = feedparser.parse(resp.content)
            count = 0
            for entry in feed.entries[:40]:
                raw_title = entry.get('title', '').strip()
                title     = clean_title(raw_title)
                summary   = strip_html(entry.get('summary', ''))[:600]
                url       = entry.get('link', '')

                if not url or url in seen_urls: continue
                if not is_gta6(title, summary):  continue
                if not is_recent(entry):          continue

                seen_urls.add(url)
                raw_stories.append({
                    'title':    title,
                    'raw_title': raw_title,
                    'url':      url,
                    'score':    score_headline(title),
                    'source':   feed_info['name'],
                    'priority': feed_info.get('priority', 2),
                    'summary':  summary,
                    'text':     '',
                    'date':     get_date_str(entry),
                    'upvotes':  0,
                })
                count += 1

            if count:
                print(f'  {feed_info["name"]}: {count} stories')

        except Exception as e:
            print(f'  {feed_info["name"]}: {str(e)[:60]}')

    return raw_stories


def deduplicate_stories(stories: list) -> list:
    """
    Remove stories covering the same topic.
    When duplicates exist, keep the one from a direct gaming site (priority 1).
    """
    unique   = []
    seen_fps = {}  # fingerprint → index in unique

    for story in stories:
        fp = topic_fingerprint(story['title'])

        if fp in seen_fps:
            existing_idx = seen_fps[fp]
            existing     = unique[existing_idx]
            # Prefer direct gaming site over Google News aggregate
            if story['priority'] < existing['priority']:
                unique[existing_idx] = story
                seen_fps[fp] = existing_idx
            # else keep existing
            continue

        # Also check word-overlap against all existing unique stories
        is_dup = False
        for i, u in enumerate(unique):
            if titles_are_same_story(story['title'], u['title']):
                # Keep better priority source
                if story['priority'] < u['priority']:
                    unique[i] = story
                is_dup = True
                break

        if not is_dup:
            seen_fps[fp] = len(unique)
            unique.append(story)

    removed = len(stories) - len(unique)
    if removed:
        print(f'  Deduplication: removed {removed} duplicate stories ({len(unique)} unique remain)')

    return unique


FALLBACKS = [
    {
        'title':   'GTA 6 2026 Release: Everything Confirmed So Far',
        'text':    'Rockstar Games has confirmed GTA 6 for PS5 and Xbox Series X with a 2026 release window. The debut trailer broke YouTube viewing records within hours of release. Lucia is confirmed as the first female protagonist in the mainline GTA series alongside Jason in a Bonnie and Clyde style narrative. The setting is Vice City, a modern reimagining of Miami and the Florida coastline. The map is reportedly larger than GTA 5 and Red Dead Redemption 2 combined. The development team is the largest in Rockstar history with a budget exceeding two billion dollars. GTA Online will continue operating alongside GTA 6. Premium pricing above the standard sixty-nine dollars is widely anticipated.',
        'source':  'GTA6 Daily', 'date': 'Recent', 'url': '', 'score': 60, 'upvotes': 0, 'summary': '', 'priority': 3,
    },
]


def get_top_story() -> dict:
    registry   = load_used_news()
    used_count = len(registry.get('used_ids', []))
    if used_count:
        print(f'  ({used_count} stories already used — skipping repeats)')

    # 1. Scrape all feeds
    raw = scrape_feeds()
    print(f'\n  Total scraped: {len(raw)} stories')

    # 2. Deduplicate by topic
    unique = deduplicate_stories(raw)
    print(f'  After dedup:  {len(unique)} unique topics')

    # 3. Filter already-used
    fresh   = [s for s in unique if not is_already_used(s, registry)]
    skipped = len(unique) - len(fresh)
    if skipped:
        print(f'  Skipped {skipped} already-used stories')
        print(f'  Fresh stories available: {len(fresh)}')

    if not fresh:
        if unique:
            print('  All stories used — resetting tracker for fresh start')
            registry['used_ids']    = []
            registry['used_titles'] = []
            registry['history']     = []
            save_used_news(registry)
            fresh = unique
        else:
            print('  No stories found — using evergreen fallback')
            story = dict(random.choice(FALLBACKS))
            mark_as_used(story, registry)
            return story

    # 4. Sort by score, try top candidates until one has good article content
    fresh.sort(key=lambda x: (x.get('priority', 2), -x.get('score', 0)))

    story = None
    for candidate in fresh[:5]:
        print(f'\n  Trying: "{candidate["title"][:60]}"')
        print(f'    Source: {candidate["source"]} | Score: {candidate["score"]}')

        full_text = fetch_article(candidate['url'])
        if full_text and len(full_text) > 400:
            candidate['text'] = full_text
            story = candidate
            print(f'    Article: {len(full_text)} chars ✓')
            break
        else:
            candidate['text'] = full_text or candidate.get('summary', '')
            print(f'    Article: {len(candidate["text"])} chars (thin) — trying next')
            if story is None:
                story = candidate  # keep as backup

    if story is None:
        story = fresh[0]

    mark_as_used(story, registry)

    # Save today's unique story list for reference
    os.makedirs('assets', exist_ok=True)
    with open('assets/today_stories.json', 'w', encoding='utf-8') as f:
        json.dump([{
            'title':  s['title'],
            'source': s['source'],
            'score':  s['score'],
            'date':   s['date'],
        } for s in fresh[:15]], f, indent=2, ensure_ascii=False)

    print(f'\n  SELECTED: "{story["title"][:65]}"')
    print(f'  Source: {story["source"]} | Content: {len(story["text"])} chars')
    return story


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    story = get_top_story()
    print(f'\n{"="*65}')
    print(f'Title:   {story["title"]}')
    print(f'Source:  {story["source"]}')
    print(f'Content: {len(story["text"])} chars')
    if story['text']:
        print(f'\nPreview:\n{story["text"][:400]}...')
