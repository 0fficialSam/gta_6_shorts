"""
=============================================================================
  GTA 6 AUTOMATION ENGINE — STUDIO LAUNCHER
  Launches the Django Web Studio Dashboard and opens it in your browser.
=============================================================================
"""

import os
import sys
import time
import webbrowser
import threading
import subprocess

def open_browser(url: str, delay: float = 1.2):
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    studio_dir = os.path.join(root_dir, "studio")
    manage_py = os.path.join(studio_dir, "manage.py")

    port = 8000
    host = "127.0.0.1"
    url = f"http://{host}:{port}"

    print("=" * 70)
    print("  🕹️  GTA 6 CREATOR STUDIO (DJANGO WEB DASHBOARD)")
    print("  Author: @SamWithJoystick")
    print("=" * 70)
    print(f"  • Status         : Online & Ready")
    print(f"  • Web Dashboard  : {url}")
    print(f"  • Formats        : 9:16 YouTube Shorts + 4:5 Instagram News Cards")
    print(f"  • Operating Mode : Zero-Cost ($0.00) Local Production Engine")
    print("=" * 70)
    print("\nStarting local Django server & opening browser...\n")

    # Launch browser automatically in background
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    # Run Django development server
    cmd = [sys.executable, manage_py, "runserver", f"{host}:{port}"]
    try:
        subprocess.run(cmd, cwd=root_dir)
    except KeyboardInterrupt:
        print("\nStudio server stopped gracefully.")

if __name__ == "__main__":
    main()
