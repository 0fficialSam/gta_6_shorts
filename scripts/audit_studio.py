import re
import os
import json
import sys
import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

with open("studio/templates/index.html", encoding="utf-8") as f:
    html = f.read()

print("=" * 60)
print("AUDIT: studio/templates/index.html")
print("=" * 60)

# 1. Find all getElementById in JS
get_ids = set(re.findall(r"document\.getElementById\(['\"]([^'\"]+)['\"]", html))

# 2. Find all id='...' in HTML
dom_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html))

missing_ids = get_ids - dom_ids
print(f"\n1. Missing element IDs referenced in JS ({len(missing_ids)}):")
for mid in sorted(missing_ids):
    print(f"  ❌ {mid}")

# 3. Find all onclick='...' handlers
onclicks = set(re.findall(r'onclick=["\']([a-zA-Z0-9_]+)\(', html))
functions = set(re.findall(r'function\s+([a-zA-Z0-9_]+)\s*\(', html))
const_funcs = set(re.findall(r'(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\(', html))
all_funcs = functions | const_funcs

missing_funcs = onclicks - all_funcs
print(f"\n2. Missing onclick functions ({len(missing_funcs)}):")
for mf in sorted(missing_funcs):
    print(f"  ❌ {mf}")

# 4. Find all fetch endpoints in JS
fetches = set(re.findall(r"fetch\(['\"]([^'\"]+)['\"]", html))
print(f"\n3. Fetch endpoints called from JS ({len(fetches)}):")
for ep in sorted(fetches):
    print(f"  🌐 {ep}")

# Check urls.py in studio/dashboard/urls.py
with open("studio/studio_project/urls.py", encoding="utf-8") as f:
    urls_py = f.read()
url_patterns = set(re.findall(r"path\(['\"]([^'\"]+)['\"]", urls_py))
print(f"\nConfigured Django URL routes ({len(url_patterns)}):")
for p in sorted(url_patterns):
    print(f"  🔗 /{p}")

print("\n" + "=" * 60)
print("TESTING ALL BACKEND API ENDPOINTS")
print("=" * 60)

base = "http://127.0.0.1:8000"
endpoints = [
    ("GET", "/"),
    ("GET", "/api/news/"),
    ("GET", "/api/games/"),
    ("GET", "/api/games/fetch-images/?game=GTA%20VI"),
    ("GET", "/api/status/"),
    ("GET", "/api/media/"),
    ("GET", "/api/screenshots/"),
    ("GET", "/api/music/"),
    ("POST", "/api/match-screenshot/", {"headline": "Lucia and Jason bank heist in Vice City", "summary": "New trailer details"}),
    ("POST", "/api/generate/instagram/", {"headline": "NEW GTA 6 TRAILER LEAKED", "summary": "Rockstar confirmed new footage.", "game_title": "GTA VI"}),
    ("POST", "/api/open-folder/", {}),
]

for item in endpoints:
    method = item[0]
    path = item[1]
    url = base + path
    try:
        if method == "GET":
            r = requests.get(url, timeout=10)
        else:
            payload = item[2]
            r = requests.post(url, json=payload, timeout=15)
        status_icon = "✅" if r.status_code == 200 else f"⚠️ {r.status_code}"
        print(f"{status_icon} {method} {path} -> {r.status_code} ({len(r.content)} bytes)")
        if r.status_code != 200:
            print(f"   Response: {r.text[:200]}")
    except Exception as e:
        print(f"❌ {method} {path} -> Failed: {e}")
