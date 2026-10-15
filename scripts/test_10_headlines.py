"""
Test 10 Real Scraped Gaming News Headlines
Generates:
original title | final headline | summary | hook | category
And strictly validates:
- Summary != headline
- Source name stripped from headline
- Summary word count between 12 and 18 words
- Zero domain names in summary
- Hook == CONFIRMED/OFFICIAL only if source is Rockstar / Take-Two
- Trailer stories == TRAILER category
"""

import sys
import os
import json

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from scripts.story_enhancer import enhance_story_for_post, clean_scraped_title, is_official_source

# 10 Real scraped headlines directly from Google News RSS feeds for GTA VI
TEST_STORIES = [
    {
        "raw_title": "Rockstar Reveals the GTA VI Launch Trailer and New Story Details - Root-Nation.com",
        "raw_summary": "Rockstar Reveals the GTA VI Launch Trailer and New Story Details Root-Nation.com",
        "source": "Google News"
    },
    {
        "raw_title": "'GTA 6' Cyberleek release update: New leaks, development build, and roadmap of what might be next - Mashable",
        "raw_summary": "'GTA 6' Cyberleek release update: New leaks, development build, and roadmap of what might be next Mashable",
        "source": "Google News"
    },
    {
        "raw_title": "‘GTA VI’ Trailer Confirms Justice Is Behind the Original Score, New Song With SZA and Tame Impala Debuts - Variety",
        "raw_summary": "‘GTA VI’ Trailer Confirms Justice Is Behind the Original Score, New Song With SZA and Tame Impala Debuts Variety",
        "source": "Google News"
    },
    {
        "raw_title": "'GTA 6' file size leak: Cyberleek reveals eye-watering storage requirements - Mashable",
        "raw_summary": "'GTA 6' file size leak: Cyberleek reveals eye-watering storage requirements Mashable",
        "source": "Google News"
    },
    {
        "raw_title": "GTA 6 Avoids A Very Awkward Situation By Officially Being Eligible For The 2026 Game Awards - Kotaku",
        "raw_summary": "GTA 6 Avoids A Very Awkward Situation By Officially Being Eligible For The 2026 Game Awards Kotaku",
        "source": "Google News"
    },
    {
        "raw_title": "Cyberleek says the 'GTA 6' leaks are over and warns of 'dead man's switch' - Mashable",
        "raw_summary": "Cyberleek says the 'GTA 6' leaks are over and warns of 'dead man's switch' Mashable",
        "source": "Google News"
    },
    {
        "raw_title": "‘GTA 6’ Launch Trailer Justifies Game’s Big Price Tag - The Hollywood Reporter",
        "raw_summary": "‘GTA 6’ Launch Trailer Justifies Game’s Big Price Tag The Hollywood Reporter",
        "source": "Google News"
    },
    {
        "raw_title": "'GTA VI' Launch Trailer Features New Music by Justice, Tame Impala, and SZA: Watch Now - Complex",
        "raw_summary": "'GTA VI' Launch Trailer Features New Music by Justice, Tame Impala, and SZA: Watch Now Complex",
        "source": "Google News"
    },
    {
        "raw_title": "French duo Justice to score 'GTA VI': game maker - KMVU FOX 26 Medford",
        "raw_summary": "French duo Justice to score 'GTA VI': game maker KMVU FOX 26 Medford",
        "source": "Google News"
    },
    {
        "raw_title": "Rockstar Games Officially Reaffirms Grand Theft Auto VI Fall 2026 Release Window in Earnings Call",
        "raw_summary": "Take-Two Interactive and Rockstar Games confirm during annual financial conference that production remains on track for Fall 2026.",
        "source": "Rockstar Games"
    }
]

def run_evaluation():
    results = []
    print("\nRunning enhancement on 10 real scraped headlines...\n")

    for idx, story in enumerate(TEST_STORIES, 1):
        raw_t = story["raw_title"]
        raw_s = story["raw_summary"]
        src = story["source"]

        out = enhance_story_for_post(raw_title=raw_t, raw_summary=raw_s, source=src, game="GTA VI")

        hl = out["headline"]
        sum_text = out["summary"]
        hk = out["hook"]
        cat = out["category"]

        words = len(sum_text.split())
        is_official = is_official_source(src, hl)

        # Validation assertions
        assert hl.lower() != sum_text.lower(), f"Row {idx}: summary equals headline!"
        assert not any(dom in sum_text.lower() for dom in [".com", ".net", ".org", "mashable", "root", "variety", "kotaku"]), f"Row {idx}: summary contains domain or source name!"
        assert 12 <= words <= 18, f"Row {idx}: summary word count {words} is not between 12 and 18!"
        if not is_official:
            assert hk not in ["CONFIRMED", "OFFICIAL"], f"Row {idx}: unofficial source got hook '{hk}'!"
            assert hk in ["NEW", "REPORT", "RUMOR", "LEAK", "UPDATE", "TRAILER"], f"Row {idx}: hook '{hk}' not in allowed list!"
        if "trailer" in hl.lower() or "trailer" in raw_t.lower():
            assert cat == "TRAILER", f"Row {idx}: trailer story categorized as '{cat}' instead of 'TRAILER'!"

        # Check trailing source name in headline
        trailing_sources = [" - Root", " - Mashable", " - Variety", " - Kotaku", " - The Hollywood Reporter", " - Complex", " - KMVU", "Root-Nation.com"]
        for ts in trailing_sources:
            assert ts.lower() not in hl.lower(), f"Row {idx}: trailing source name '{ts}' still in headline '{hl}'!"

        results.append({
            "idx": idx,
            "original_title": raw_t,
            "final_headline": hl,
            "summary": sum_text,
            "words": words,
            "hook": hk,
            "category": cat
        })

    # Output Markdown table
    print("| original title | final headline | summary | hook | category |")
    print("| :--- | :--- | :--- | :--- | :--- |")
    for r in results:
        # Escape pipe symbols in titles for markdown table formatting
        orig = r['original_title'].replace('|', '/')
        final_h = r['final_headline'].replace('|', '/')
        s = r['summary'].replace('|', '/')
        print(f"| {orig} | {final_h} | {s} | {r['hook']} | {r['category']} |")

    print("\n[OK] ALL 10 ROWS PASSED 100% OF EDITORIAL CONSTRAINTS!\n")

if __name__ == "__main__":
    run_evaluation()
