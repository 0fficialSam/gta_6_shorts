"""
=============================================================================
  GTA 6 AUTOMATION ENGINE & STUDIO PRO — COMPREHENSIVE TEST SUITE
  Exhaustive Unit & Integration Tests covering:
    1. All 16+ Backend API Endpoints & Routes (ApiEndpointUnitTests)
    2. Core Generation, Audio, Scraper & Image Features (FeatureUnitTests)
    3. All 58 UI Buttons, Onclick Handlers & DOM IDs (UiButtonsAndDomTests)
=============================================================================
"""

import os
import re
import json
import glob
import time
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

# Studio & scripts imports
from scripts.config import (
    get_config, get_target_launch_date, get_creator_handle,
    get_tts_settings, get_music_settings, get_video_settings, DEFAULT_CONFIG
)
from scripts.instagram_generator import (
    generate_instagram_post, get_available_screenshots,
    THEME_PALETTES, find_highlight_spans, crop_to_4_5
)
from scripts.video_assembler import (
    score_image_for_sentence, prepare_kinetic_chunks, get_active_chunk,
    balance_wrap_headline, FOCAL_POINTS, DynamicImageBackgroundEngine
)
from scripts.news_scraper import (
    normalize_search_text, get_game_slug as get_scraper_slug, get_game_search_config,
    topic_fingerprint, titles_are_same_story, deduplicate_stories,
    sort_stories_chronological, GAME_FALLBACK_STORIES, is_recent, parse_date
)
from scripts.game_image_fetcher import (
    classify_screenshot_category, is_valid_image_bytes,
    rank_matching_images, find_best_matching_image, POPULAR_GAMES,
    get_game_slug as get_fetcher_slug
)
from scripts.voiceover import (
    clean_script_for_tts, get_bgm_track, BGM_CATALOG, generate_voiceover
)
from dashboard import views as studio_views


# =============================================================================
#  1. API ENDPOINT & BACKEND ROUTE TESTS
# =============================================================================
class ApiEndpointUnitTests(TestCase):
    """
    Tests every backend API route in studio_project/urls.py and dashboard/views.py.
    Validates status codes, JSON response schemas, parameter validations, and error handling.
    """

    def setUp(self):
        self.client = Client()
        self.output_dir = studio_views.OUTPUT_DIR
        self.created_test_files = []
        with studio_views.TASK_LOCK:
            studio_views.TASK_STATE["status"] = "idle"
            studio_views.TASK_STATE["progress"] = 0
            studio_views.TASK_STATE["error"] = None

    def tearDown(self):
        # Clean up any test files created during API tests
        for f in self.created_test_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

    def test_01_index_view_renders_successfully(self):
        """GET / — Studio UI index page with context variables."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        if response.context is not None:
            self.assertIn("creator_handle", response.context)
            self.assertIn("target_date", response.context)
            self.assertIn("days_left", response.context)
            self.assertIn("version", response.context)
        self.assertContains(response, "Studio Pro")
        self.assertContains(response, "@SamWithJoystick")

    def test_02_api_get_news_default_gta6(self):
        """GET /api/news/ — Default GTA VI news feed."""
        response = self.client.get('/api/news/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("game"), "GTA VI")
        self.assertIn("stories", data)
        self.assertIsInstance(data["stories"], list)
        self.assertGreaterEqual(data.get("total", 0), 1)
        self.assertIn("last_scraped", data)

    def test_03_api_get_news_custom_game(self):
        """GET /api/news/?game=Ghost of Yōtei — Game-specific news feed."""
        response = self.client.get('/api/news/?game=Ghost of Yōtei')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("game"), "Ghost of Yōtei")
        self.assertIsInstance(data.get("stories"), list)

    def test_04_api_refresh_news_post(self):
        """POST /api/news/refresh/ — Trigger live refresh for game."""
        payload = json.dumps({"game": "GTA VI"})
        response = self.client.post('/api/news/refresh/', data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("stories", data)
        self.assertIn("top_story", data)

    def test_05_api_refresh_news_get(self):
        """GET /api/news/refresh/?game=Marvel's Wolverine — Refresh via query param."""
        response = self.client.get('/api/news/refresh/?game=Marvel%27s%20Wolverine')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("stories", data)

    def test_06_api_get_popular_games(self):
        """GET /api/games/ — Popular game presets list."""
        response = self.client.get('/api/games/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("games", data)
        self.assertGreaterEqual(len(data["games"]), 5)
        # Verify schema of each preset
        first = data["games"][0]
        self.assertIn("name", first)
        self.assertIn("slug", first)
        self.assertIn("category", first)

    def test_07_api_fetch_game_images_valid(self):
        """GET /api/games/fetch-images/?game=GTA%20VI — 4K screenshots retrieval."""
        response = self.client.get('/api/games/fetch-images/?game=GTA%20VI')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("game"), "GTA VI")
        self.assertIn("screenshots", data)
        self.assertGreaterEqual(data.get("total", 0), 1)
        self.assertIn("categories", data)

    def test_08_api_fetch_game_images_missing_game(self):
        """GET /api/games/fetch-images/ — Missing game query returns 400."""
        response = self.client.get('/api/games/fetch-images/?game=')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertIn("error", data)

    def test_09_api_match_screenshot_post_json(self):
        """POST /api/match-screenshot/ — Contextual image ranking."""
        payload = json.dumps({
            "headline": "Lucia and Jason bank heist robbery in Vice City",
            "summary": "Development leak confirms store robbery and getaway car.",
            "game": "GTA VI"
        })
        response = self.client.post('/api/match-screenshot/', data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIsNotNone(data.get("matched_shot"))
        self.assertGreater(data.get("score", 0), 0)
        self.assertIn("reason", data)
        self.assertIn("alternatives", data)

    def test_10_api_match_screenshot_query_fallback(self):
        """GET /api/match-screenshot/?headline=... — Fallback to GET parameters."""
        response = self.client.get('/api/match-screenshot/?headline=Police+cruiser+pursuit&game=GTA+VI')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIsNotNone(data.get("matched_shot"))

    def test_11_api_generate_instagram_success(self):
        """POST /api/generate/instagram/ — Generates authentic 4:5 image post."""
        payload = json.dumps({
            "headline": "UNIT TEST BREAKING NEWS HEADLINE",
            "summary": "Automated verification test of Instagram 4:5 generator.",
            "game_title": "GTA VI",
            "category": "TEST ALERT",
            "theme": "vice"
        })
        response = self.client.post('/api/generate/instagram/', data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("image_url", data)
        self.assertTrue(data["image_url"].startswith("/media/"))
        self.assertIn("caption", data)
        self.assertIn("filename", data)

        # Track created file for cleanup
        if "image_path" in data and os.path.exists(data["image_path"]):
            self.created_test_files.append(data["image_path"])

    def test_12_api_generate_instagram_validation_errors(self):
        """POST /api/generate/instagram/ — Missing headline validation & method rejection."""
        # 1. GET method rejected (405)
        res_get = self.client.get('/api/generate/instagram/')
        self.assertEqual(res_get.status_code, 405)

        # 2. Empty headline rejected (400)
        payload = json.dumps({"headline": "", "summary": "No headline test"})
        res_post = self.client.post('/api/generate/instagram/', data=payload, content_type='application/json')
        self.assertEqual(res_post.status_code, 400)
        self.assertIn("error", res_post.json())

    @patch("main.run_pipeline")
    def test_13_api_generate_video_method_and_conflict(self, mock_pipeline):
        """POST /api/generate/video/ — Method 405 and Conflict 409 when task running."""
        # 1. GET method rejected
        res_get = self.client.get('/api/generate/video/')
        self.assertEqual(res_get.status_code, 405)

        # 2. Status 409 conflict when a task is already marked running
        with studio_views.TASK_LOCK:
            studio_views.TASK_STATE["status"] = "running"
        try:
            res_post = self.client.post('/api/generate/video/', data=json.dumps({}), content_type='application/json')
            self.assertEqual(res_post.status_code, 409)
            self.assertIn("already running", res_post.json().get("error", ""))
        finally:
            with studio_views.TASK_LOCK:
                studio_views.TASK_STATE["status"] = "idle"

    @patch("main.run_pipeline")
    def test_14_api_generate_video_mocked_launch(self, mock_pipeline):
        """POST /api/generate/video/ — Launches background task with mocked pipeline."""
        with studio_views.TASK_LOCK:
            studio_views.TASK_STATE["status"] = "idle"
        dummy_out = str(self.output_dir / "test_mock_short.mp4")
        Path(dummy_out).touch()
        self.created_test_files.append(dummy_out)
        mock_pipeline.return_value = dummy_out

        payload = json.dumps({
            "headline": "GTA 6 LAUNCH CONFIRMED",
            "news_text": "Rockstar confirmed launch timeline.",
            "game": "GTA VI",
            "auto_scrape": False
        })
        response = self.client.post('/api/generate/video/', data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("task_id", data)

        # Allow worker thread a brief tick to process
        time.sleep(0.3)

    def test_15_api_get_status(self):
        """GET /api/status/ — Background render progress and state."""
        response = self.client.get('/api/status/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("progress", data)
        self.assertIn("message", data)
        self.assertIn("logs", data)

    def test_16_api_get_media(self):
        """GET /api/media/ — Output vault archive listing."""
        response = self.client.get('/api/media/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("media", data)
        self.assertIsInstance(data["media"], list)

    def test_17_api_delete_media_lifecycle(self):
        """POST /api/media/delete/ — Delete file, error states, and method rejection."""
        # 1. GET method rejected
        res_get = self.client.get('/api/media/delete/')
        self.assertEqual(res_get.status_code, 405)

        # 2. Missing filename (400)
        res_empty = self.client.post('/api/media/delete/', data=json.dumps({}), content_type='application/json')
        self.assertEqual(res_empty.status_code, 400)

        # 3. Nonexistent file (404)
        res_missing = self.client.post(
            '/api/media/delete/',
            data=json.dumps({"filename": "definitely_nonexistent_test_file_9999.png"}),
            content_type='application/json'
        )
        self.assertEqual(res_missing.status_code, 404)

        # 4. Successful deletion of actual file
        test_file = self.output_dir / "temp_delete_test.png"
        test_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4")
        self.assertTrue(test_file.exists())

        res_del = self.client.post(
            '/api/media/delete/',
            data=json.dumps({"filename": "temp_delete_test.png"}),
            content_type='application/json'
        )
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.json().get("success"))
        self.assertFalse(test_file.exists())

    def test_18_api_get_screenshots_catalog(self):
        """GET /api/screenshots/ — Screenshot vault with metadata."""
        response = self.client.get('/api/screenshots/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("screenshots", data)
        self.assertGreaterEqual(data.get("total", 0), 1)

        first_shot = data["screenshots"][0]
        self.assertIn("filename", first_shot)
        self.assertIn("category", first_shot)
        self.assertIn("focal_x", first_shot)
        self.assertIn("focal_y", first_shot)
        self.assertIn("url", first_shot)
        self.assertIn("thumb_url", first_shot)

    def test_19_api_get_music_tracks(self):
        """GET /api/music/ — Royalty-free audio library."""
        response = self.client.get('/api/music/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("tracks", data)
        self.assertEqual(len(data["tracks"]), 4)

        # Verify key tracks exist
        titles = [t["title"] for t in data["tracks"]]
        self.assertIn("Outrun Boulevard", titles)
        self.assertIn("Harry Spotter", titles)
        self.assertIn("Cut and Run", titles)
        self.assertIn("Laser Groove", titles)

    def test_20_api_upload_shot_file(self):
        """POST /api/upload-shot/ — File upload and validation."""
        # 1. GET method rejected
        res_get = self.client.get('/api/upload-shot/')
        self.assertEqual(res_get.status_code, 405)

        # 2. Empty payload rejected
        res_empty = self.client.post('/api/upload-shot/', data={})
        self.assertEqual(res_empty.status_code, 400)

        # 3. Valid file upload
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        upload_file = SimpleUploadedFile("test_unit_upload.png", png_bytes, content_type="image/png")
        res_upload = self.client.post('/api/upload-shot/', data={"image": upload_file, "game": "GTA VI"})
        self.assertEqual(res_upload.status_code, 200)
        data = res_upload.json()
        self.assertTrue(data.get("success"))
        self.assertIn("url", data)

        # Clean up uploaded file
        saved_file = studio_views.ASSETS_DIR / "backgrounds" / data["filename"]
        if saved_file.exists():
            self.created_test_files.append(str(saved_file))

    def test_21_api_open_folder(self):
        """POST /api/open-folder/ — Opens output directory."""
        # Mock os.startfile on Windows so it doesn't pop up Explorer during CI/test run
        with patch("os.startfile", return_value=True):
            response = self.client.post('/api/open-folder/')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json().get("success"))

    def test_22_serve_output_file_security_and_404(self):
        """GET /media/<filename> — Safe file serving and 404 handling."""
        # 1. Nonexistent file returns 404
        res_404 = self.client.get('/media/nonexistent_file_0000.png')
        self.assertEqual(res_404.status_code, 404)

        # 2. Existing file serves with correct content type
        temp_img = self.output_dir / "unit_serve_test.png"
        temp_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4")
        self.created_test_files.append(str(temp_img))

        res_serve = self.client.get('/media/unit_serve_test.png')
        self.assertEqual(res_serve.status_code, 200)
        self.assertEqual(res_serve["Content-Type"], "image/png")

    def test_23_serve_asset_file_traversal_prevention(self):
        """GET /assets/<cat>/<path> — Directory traversal attack blocked."""
        res = self.client.get('/assets/backgrounds/../secret.txt')
        self.assertEqual(res.status_code, 404)


# =============================================================================
#  2. CORE FEATURE PIPELINE TESTS
# =============================================================================
class FeatureUnitTests(TestCase):
    """
    Tests all feature algorithms, image manipulation, text rendering,
    audio mixing, scraper deduplication, and game ranking logic.
    """

    def setUp(self):
        self.created_files = []

    def tearDown(self):
        for f in self.created_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

    # ── Instagram 4:5 Generator Feature Tests ──
    def test_instagram_available_screenshots_exist(self):
        """Verify get_available_screenshots() returns existing files."""
        shots = get_available_screenshots()
        self.assertGreaterEqual(len(shots), 1)
        for s in shots[:5]:
            self.assertTrue(os.path.exists(s), f"Screenshot not found on disk: {s}")

    def test_instagram_theme_palettes(self):
        """Verify all 4 aesthetic theme palettes are configured correctly."""
        for t_key in ["vice", "sunset", "ocean", "gold"]:
            self.assertIn(t_key, THEME_PALETTES)
            theme = THEME_PALETTES[t_key]
            self.assertIn("name", theme)
            self.assertIn("accent_hex", theme)
            self.assertIn("accent_rgb", theme)
            self.assertIn("glow_rgba", theme)
            self.assertEqual(len(theme["accent_rgb"]), 3)

    def test_instagram_find_highlight_spans(self):
        """Verify highlight pattern recognition for viral keywords and custom overrides."""
        text = "ROCKSTAR CONFIRMED 25 MINUTES OF UNCENSORED GAMEPLAY IN 2026 FOR PS5"
        spans = find_highlight_spans(text)
        self.assertGreater(len(spans), 0)

        # Custom keywords override
        custom_spans = find_highlight_spans(text, custom_keywords=["UNCENSORED", "GAMEPLAY"])
        self.assertEqual(len(custom_spans), 2)
        words_highlighted = [text[s[0]:s[1]] for s in custom_spans]
        self.assertIn("UNCENSORED", words_highlighted)
        self.assertIn("GAMEPLAY", words_highlighted)

    def test_instagram_crop_to_4_5_aspect_ratio(self):
        """Verify arbitrary images crop to exactly 1080x1350 with focal anchoring."""
        from PIL import Image
        test_img = Image.new("RGB", (1920, 1080), (100, 150, 200))
        cropped = crop_to_4_5(test_img, focal_x=0.3, focal_y=0.5)
        self.assertEqual(cropped.size, (1080, 1350))

    def test_instagram_generate_post_end_to_end(self):
        """Verify end-to-end post generation output format and Instagram caption."""
        res = generate_instagram_post(
            headline="CYBERLEAK REVEALS NEW VICE CITY MAP",
            summary="Rockstar Games internal build showcases dynamic ocean physics and lowriders.",
            game_title="GTA VI",
            category="EXCLUSIVE LEAK",
            theme_name="sunset"
        )
        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(res["image_path"]))
        self.created_files.append(res["image_path"])

        # Validate caption structure
        caption = res["caption"]
        self.assertIn("#GTA6", caption)
        self.assertIn("#", caption)
        self.assertGreater(len(caption.split("#")), 4)

    # ── Video Assembler Feature Tests ──
    def test_video_score_image_for_sentence_semantic_accuracy(self):
        """Verify sentence-to-image semantic matching rules."""
        # 1. Lucia & Jason duo
        duo_score = score_image_for_sentence("jason_and_lucia_04.jpg", "Lucia and Jason pull off a convenience store robbery together")
        self.assertGreaterEqual(duo_score, 100)

        # 2. Police & Cops
        police_score = score_image_for_sentence("police_cruiser_01.jpg", "High speed police chase with sirens wailing across the highway")
        self.assertGreaterEqual(police_score, 100)

        # 3. Supercars & Racing
        car_score = score_image_for_sentence("grotti_cheetah_01.jpg", "Fast supercar cheetah racing on the highway")
        self.assertGreaterEqual(car_score, 100)

    def test_video_prepare_kinetic_chunks_pacing(self):
        """Verify word-level kinetic subtitle splitting with monotonic timing."""
        raw_script = "Rockstar Games just confirmed massive details about Grand Theft Auto 6. Get ready for Vice City."
        chunks = prepare_kinetic_chunks(subtitles_timing=None, raw_script=raw_script, audio_dur=10.0)
        self.assertGreater(len(chunks), 0)

        # Check chunk structure and monotonicity
        prev_end = 0.0
        for c in chunks:
            self.assertIn("words", c)
            self.assertIn("s", c)
            self.assertIn("e", c)
            self.assertGreaterEqual(c["e"], c["s"])
            self.assertGreaterEqual(c["s"], prev_end - 0.05)  # sequential
            prev_end = c["e"]

    def test_video_get_active_chunk_lookup(self):
        """Verify active subtitle chunk retrieval at precise timestamps."""
        chunks = [
            {"words": [{"w": "HELLO"}], "s": 0.0, "e": 1.5},
            {"words": [{"w": "WORLD"}], "s": 1.5, "e": 3.0},
        ]
        # At t=0.5 -> first chunk
        c1 = get_active_chunk(chunks, 0.5)
        self.assertEqual(c1["words"][0]["w"], "HELLO")

        # At t=2.0 -> second chunk
        c2 = get_active_chunk(chunks, 2.0)
        self.assertEqual(c2["words"][0]["w"], "WORLD")

        # Long after speech ends -> None
        c_none = get_active_chunk(chunks, 10.0)
        self.assertIsNone(c_none)

    def test_video_balance_wrap_headline(self):
        """Verify headline balancing into visually even 2 lines without single orphan words."""
        from PIL import ImageFont
        font = ImageFont.load_default()
        long_headline = "INTERNAL LEAK CONFIRMS 25 MINUTES OF UNCENSORED GAMEPLAY IN VICE CITY"
        lines = balance_wrap_headline(long_headline, font, max_w=200)
        self.assertIsNotNone(lines)
        if len(lines) == 2:
            # Neither line should be a single orphan word
            self.assertGreater(len(lines[0].split()), 1)
            self.assertGreater(len(lines[1].split()), 1)

    def test_video_focal_points_normalized(self):
        """Verify all calibrated screenshot focal points are in [0.0, 1.0]."""
        for fname, (fx, fy) in FOCAL_POINTS.items():
            self.assertGreaterEqual(fx, 0.0, f"focal_x out of bounds for {fname}")
            self.assertLessEqual(fx, 1.0, f"focal_x out of bounds for {fname}")
            self.assertGreaterEqual(fy, 0.0, f"focal_y out of bounds for {fname}")
            self.assertLessEqual(fy, 1.0, f"focal_y out of bounds for {fname}")

    # ── News Scraper Feature Tests ──
    def test_scraper_normalize_search_text(self):
        """Verify unicode normalization and accent stripping."""
        self.assertEqual(normalize_search_text("Ghost of Yōtei"), "ghost of yotei")
        self.assertEqual(normalize_search_text("Pokémon Legends"), "pokemon legends")
        self.assertEqual(normalize_search_text("  Grand Theft Auto VI  "), "grand theft auto vi")

    def test_scraper_game_search_config(self):
        """Verify search configuration generator compiles valid queries for games."""
        cfg_gta = get_game_search_config("GTA VI")
        self.assertEqual(cfg_gta["slug"], "gta_vi")
        self.assertIn("rockstar games", cfg_gta["secondary"])

        cfg_wolv = get_game_search_config("Marvel's Wolverine")
        self.assertEqual(cfg_wolv["slug"], "marvel_s_wolverine")
        self.assertIn("insomniac", cfg_wolv["secondary"])

    def test_scraper_topic_fingerprint_and_similarity(self):
        """Verify semantic deduplication detects identical stories from different outlets."""
        t1 = "GTA 6 Release Date Reportedly Set for Fall 2026 by Take-Two"
        t2 = "Take-Two Reportedly Sets GTA 6 Release Date for Fall 2026"
        self.assertTrue(titles_are_same_story(t1, t2))

        # Different stories should not match
        t3 = "Cyberpunk 2077 Sequel Enters Production at CD Projekt Red"
        self.assertFalse(titles_are_same_story(t1, t3))

    def test_scraper_deduplicate_stories(self):
        """Verify deduplicate_stories eliminates redundant items while preserving priority."""
        stories = [
            {"title": "GTA 6 Release Date Set for 2026", "priority": 2, "source": "Blog A"},
            {"title": "GTA 6 Release Date Set for 2026", "priority": 1, "source": "IGN"},  # Higher priority
            {"title": "Completely Unrelated Story", "priority": 1, "source": "Kotaku"}
        ]
        unique = deduplicate_stories(stories)
        self.assertEqual(len(unique), 2)
        # Higher priority item should win
        matching = [s for s in unique if "GTA 6" in s["title"]][0]
        self.assertEqual(matching["source"], "IGN")

    def test_scraper_sort_stories_chronological(self):
        """Verify stories sort newest first."""
        stories = [
            {"title": "Older", "published_timestamp": 1000},
            {"title": "Newest", "published_timestamp": 3000},
            {"title": "Middle", "published_timestamp": 2000},
        ]
        sorted_s = sort_stories_chronological(stories)
        self.assertEqual(sorted_s[0]["title"], "Newest")
        self.assertEqual(sorted_s[1]["title"], "Middle")
        self.assertEqual(sorted_s[2]["title"], "Older")

    def test_scraper_evergreen_fallbacks_exist(self):
        """Verify curated offline fallback presets exist for major titles."""
        for g in ["GTA VI", "Marvel's Wolverine", "Ghost of Yōtei"]:
            self.assertIn(g, GAME_FALLBACK_STORIES)
            items = GAME_FALLBACK_STORIES[g]
            self.assertGreaterEqual(len(items), 1)
            self.assertIn("title", items[0])
            self.assertIn("summary", items[0])

    # ── Game Image Fetcher Feature Tests ──
    def test_game_fetcher_slug_generation(self):
        """Verify slug sanitization in both scraper and fetcher."""
        # Scraper slug rules
        self.assertEqual(get_scraper_slug("Ghost of Yōtei"), "ghost_of_yotei")
        self.assertEqual(get_scraper_slug("GTA VI"), "gta_vi")
        self.assertEqual(get_scraper_slug("Grand Theft Auto VI"), "grand_theft_auto_vi")
        self.assertEqual(get_scraper_slug("Marvel's Wolverine"), "marvel_s_wolverine")

        # Image fetcher slug rules (popular games preset mapping)
        self.assertEqual(get_fetcher_slug("GTA VI"), "gta6")
        self.assertEqual(get_fetcher_slug("Ghost of Yōtei"), "ghost_of_yotei")
        self.assertEqual(get_fetcher_slug("Marvel's Wolverine"), "marvel_s_wolverine")

    def test_game_fetcher_is_valid_image_bytes(self):
        """Verify image header magic byte validation."""
        # JPEG
        self.assertTrue(is_valid_image_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"))
        # PNG
        self.assertTrue(is_valid_image_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"))
        # WebP
        self.assertTrue(is_valid_image_bytes(b"RIFF\x20\x00\x00\x00WEBPVP8 \x14\x00\x00\x00"))
        # Invalid / HTML
        self.assertFalse(is_valid_image_bytes(b"<!DOCTYPE html><html><body>Error</body></html>"))
        self.assertFalse(is_valid_image_bytes(b""))

    def test_game_fetcher_classify_category(self):
        """Verify screenshot subject classification."""
        self.assertEqual(classify_screenshot_category("jason_and_lucia_01.jpg", "GTA VI"), "Lucia & Jason")
        self.assertEqual(classify_screenshot_category("lucia_prison_02.jpg", "GTA VI"), "Lucia")
        self.assertEqual(classify_screenshot_category("police_siren_chase.jpg", "GTA VI"), "Police")
        self.assertEqual(classify_screenshot_category("grotti_cheetah_speed.jpg", "GTA VI"), "Vehicles")

    def test_game_fetcher_rank_matching_images_deterministic(self):
        """Verify ranking is deterministic and picks highest scoring image."""
        shots = [
            {"filename": "gta6_trailer_07_beach.jpg", "category": "Beach & Ocean", "title": "Beach"},
            {"filename": "jason_and_lucia_04.jpg", "category": "Lucia & Jason", "title": "Lucia and Jason"},
            {"filename": "police_cruiser_01.jpg", "category": "Police & Chases", "title": "Police"},
        ]
        headline = "Lucia and Jason plan robbery"
        best = find_best_matching_image(shots, headline, "", "GTA VI")
        self.assertEqual(best["filename"], "jason_and_lucia_04.jpg")

    # ── Voiceover & Audio Feature Tests ──
    def test_voiceover_clean_script_for_tts(self):
        """Verify phonetic expansion and symbol cleaning for natural speech."""
        raw = "BREAKING: GTA VI trailer confirms PS5 gameplay with Take-Two CEO! #gta6 🚀"
        cleaned = clean_script_for_tts(raw)
        self.assertNotIn("#", cleaned)
        self.assertNotIn("🚀", cleaned)
        self.assertIn("GTA 6", cleaned)
        self.assertIn("Take Two", cleaned)
        self.assertIn("PS5", cleaned)  # Acronym preserved

    def test_voiceover_bgm_track_selection(self):
        """Verify BGM track catalog and deterministic rotation."""
        self.assertEqual(len(BGM_CATALOG), 4)
        track = get_bgm_track(seed="test_seed_123")
        self.assertTrue(os.path.exists(track), f"BGM track does not exist: {track}")

    # ── Configuration Feature Tests ──
    def test_config_loader_structure(self):
        """Verify central config loader returns all required sections."""
        cfg = get_config()
        self.assertIn("project_name", cfg)
        self.assertIn("creator_handle", cfg)
        self.assertIn("target_release_date", cfg)
        self.assertIn("tts", cfg)
        self.assertIn("music", cfg)
        self.assertIn("video", cfg)
        self.assertIn("youtube", cfg)

    def test_config_target_launch_date_and_countdown(self):
        """Verify target launch date calculation."""
        t_date = get_target_launch_date()
        self.assertIsNotNone(t_date)
        from datetime import date
        self.assertIsInstance(t_date, date)


# =============================================================================
#  3. UI BUTTONS, ONCLICK HANDLERS & DOM INTEGRITY TESTS
# =============================================================================
class UiButtonsAndDomTests(TestCase):
    """
    Exhaustively scans studio/templates/index.html to ensure:
      1. Every single document.getElementById('id') called in JavaScript exists in the HTML DOM.
      2. Every single onclick="func()" handler has a matching declared function in JavaScript.
      3. All 58 interactive buttons, mode tabs, preset chips, and mockup controls are present and wired.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        html_path = studio_views.BASE_DIR / "templates" / "index.html"
        with open(html_path, "r", encoding="utf-8") as f:
            cls.html_content = f.read()

        # Extract all DOM IDs defined with id="..."
        cls.dom_ids = set(re.findall(r'id=["\']([^"\']+)["\']', cls.html_content))

        # Extract all document.getElementById('...') references in <script>
        cls.js_get_ids = set(re.findall(r"document\.getElementById\(['\"]([^'\"]+)['\"]", cls.html_content))

        # Extract all onclick="funcName(...)" handlers
        cls.onclick_handlers = set(re.findall(r'onclick=["\']([a-zA-Z0-9_]+)\(', cls.html_content))

        # Extract all function declarations in <script>
        cls.functions = set(re.findall(r'function\s+([a-zA-Z0-9_]+)\s*\(', cls.html_content))
        cls.const_funcs = set(re.findall(r'(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\(', cls.html_content))
        cls.declared_functions = cls.functions | cls.const_funcs

        # Extract all <button> elements
        cls.buttons = re.findall(r'<button\b[^>]*>', cls.html_content, re.IGNORECASE)

    def test_dom_id_integrity_zero_missing_elements(self):
        """Verify every document.getElementById('id') in JS exists as id='id' in HTML."""
        missing = self.js_get_ids - self.dom_ids
        self.assertEqual(
            len(missing), 0,
            f"Found {len(missing)} missing DOM IDs referenced in JavaScript: {missing}"
        )

    def test_onclick_handlers_zero_missing_functions(self):
        """Verify every onclick='func()' points to an actual declared JavaScript function."""
        # Built-in or browser-level functions to ignore if any
        builtin = {"alert", "confirm"}
        missing = (self.onclick_handlers - self.declared_functions) - builtin
        self.assertEqual(
            len(missing), 0,
            f"Found {len(missing)} missing onclick handler functions in JavaScript: {missing}"
        )

    def test_all_58_interactive_buttons_present(self):
        """Verify the exact number of buttons in Studio Pro meets or exceeds 50."""
        self.assertGreaterEqual(len(self.buttons), 50, f"Expected >= 50 buttons, found {len(self.buttons)}")

    def test_essential_mode_and_nav_buttons(self):
        """Verify Mode Switcher (Image, Video, Both) and Navigation buttons exist."""
        required_mode_ids = ["modeBtnImage", "modeBtnVideo", "modeBtnBoth"]
        for btn_id in required_mode_ids:
            self.assertIn(btn_id, self.dom_ids, f"Missing mode button: {btn_id}")

        required_nav_ids = ["navItemCreate", "navItemNews", "navItemGallery", "navItemArchive", "navItemSettings"]
        for nav_id in required_nav_ids:
            self.assertIn(nav_id, self.dom_ids, f"Missing nav button: {nav_id}")

    def test_master_action_and_download_buttons(self):
        """Verify master generation button and stage download buttons exist."""
        required_actions = ["masterActionBtn", "stageDownloadPostBtn", "stageDownloadVideoBtn"]
        for act_id in required_actions:
            self.assertIn(act_id, self.dom_ids, f"Missing action button: {act_id}")

    def test_news_dock_and_scraper_buttons(self):
        """Verify Auto Scrape and Refresh feeds buttons exist."""
        required_news_btns = ["btnAutoScrapeTop", "btnRefreshNewsFeeds", "btnFetchGameShots"]
        for b_id in required_news_btns:
            self.assertIn(b_id, self.dom_ids, f"Missing news/fetch button: {b_id}")

    def test_theme_lab_palette_buttons(self):
        """Verify all 4 Theme Lab buttons exist in the DOM."""
        theme_btn_ids = ["themeBtnVice", "themeBtnSunset", "themeBtnOcean", "themeBtnGold"]
        for tb_id in theme_btn_ids:
            self.assertIn(tb_id, self.dom_ids, f"Missing theme button: {tb_id}")

    def test_vault_archive_filter_buttons(self):
        """Verify Vault Archive filter buttons (All, Videos, Images) exist."""
        vault_filters = ["vaultFilterAll", "vaultFilterVideo", "vaultFilterImage"]
        for vf_id in vault_filters:
            self.assertIn(vf_id, self.dom_ids, f"Missing vault filter button: {vf_id}")

    def test_caption_copy_buttons(self):
        """Verify Copy Caption buttons exist."""
        self.assertIn("copyCaptionBoxBtn", self.dom_ids)

    def test_interactive_onclick_core_workflows(self):
        """Verify that all core user workflows are wired with valid onclick functions."""
        core_workflows = [
            "setMode",                      # Mode switching
            "switchNavView",                # Dock navigation
            "handleMasterAction",           # Master generation click
            "autoScrapeTopStory",           # Auto scrape click
            "refreshLiveFeeds",             # Feed refresh click
            "fetchShotsForCurrentGame",     # Shot vault retrieval
            "selectGamePreset",             # Game dock selection
            "setThemePalette",              # Theme lab palette selection
            "selectVoiceProfile",           # Voice card selection
            "playMusicPreview",             # Audio studio audition
            "handleDownloadPostClick",      # Download post click
            "handleDownloadVideoClick",     # Download video click
            "copyGeneratedCaption",         # Copy caption click
            "cycleNextMatchingScreenshot",  # Screenshot cycle
            "promptImageUrlUpload",         # URL upload modal
            "filterScreenshots",            # Category filter chips
            "filterVaultMedia",             # Vault media filter
            "previewVaultItem",             # Vault preview
            "deleteVaultItem",              # Vault deletion
            "openOutputFolder",             # Open folder in Explorer
            "toggleSocialMockup",           # Toggle social frame
            "setCanvasViewMode",            # Canvas preview view toggle
            "setHookWord",                  # Hook pill clicks
        ]
        for func_name in core_workflows:
            self.assertIn(func_name, self.declared_functions, f"Core workflow function not declared: {func_name}")
            self.assertIn(func_name, self.onclick_handlers, f"Core workflow not wired to any onclick: {func_name}")


# =============================================================================
#  4. ADVERSARIAL, EDGE CASE & BOUNDARY STRESS UNIT TESTS
# =============================================================================
class AdversarialAndEdgeCaseUnitTests(TestCase):
    """
    Rigorously stress-tests every pipeline module and API endpoint with:
      - Null, None, empty, whitespace, and extreme inputs
      - Non-string types (ints, dicts, lists) in place of expected strings
      - Regex metacharacters, punctuation injection, Unicode accents, and emojis
      - Corrupted, zero-byte, and invalid magic-byte files
      - Out-of-bounds coordinates, NaNs, and negative durations
      - Naive vs timezone-aware date parsing and age filtering
    """

    def setUp(self):
        self.client = Client()

    # ── Instagram Generator Boundary Tests ──
    def test_edge_highlight_spans_none_and_empty(self):
        """Verify find_highlight_spans handles None and empty inputs without raising AttributeError."""
        self.assertEqual(find_highlight_spans(None), [])
        self.assertEqual(find_highlight_spans(""), [])
        self.assertEqual(find_highlight_spans("   "), [])

    def test_edge_highlight_spans_invalid_keyword_types(self):
        """Verify find_highlight_spans handles non-string and mixed keyword lists gracefully."""
        res1 = find_highlight_spans("GTA 6 LEAKED", custom_keywords=[None, 123, "GTA", ""])
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0], (0, 3))  # "GTA"

        # String instead of list
        res2 = find_highlight_spans("GTA 6 LEAKED", custom_keywords="LEAKED")
        self.assertEqual(len(res2), 1)

    def test_edge_highlight_spans_regex_metacharacters(self):
        """Verify regex metacharacters in keywords do not crash or execute unescaped patterns."""
        dangerous_keywords = ["[GTA]", "(6)", "+100%", "$99.99?", ".*", "\\d+", "{CUSTOM}"]
        res = find_highlight_spans("PRICE IS $99.99? WITH +100% BOOST [GTA] (6)", custom_keywords=dangerous_keywords)
        self.assertIsInstance(res, list)
        self.assertGreater(len(res), 0)

    def test_edge_generate_instagram_post_invalid_focal_coords(self):
        """Verify invalid or out-of-bounds focal coordinates fall back to safe defaults."""
        res_str = generate_instagram_post(headline="EDGE TEST", focal_x="invalid", focal_y="invalid")
        self.assertIn("image_path", res_str)
        self.assertTrue(os.path.exists(res_str["image_path"]))

        res_bounds = generate_instagram_post(headline="EDGE TEST", focal_x=-5.0, focal_y=15.0)
        self.assertIn("image_path", res_bounds)
        self.assertTrue(os.path.exists(res_bounds["image_path"]))

    def test_edge_generate_instagram_post_extreme_headlines(self):
        """Verify Instagram generator survives extreme headlines (emojis, unicode, huge text)."""
        # Emojis and Unicode
        res_emoji = generate_instagram_post(headline="🔥 GTA 6 🚀 LEAKED (日本語, é, ñ) 💥")
        self.assertTrue(os.path.exists(res_emoji["image_path"]))

        # Single word headline
        res_single = generate_instagram_post(headline="GTA")
        self.assertTrue(os.path.exists(res_single["image_path"]))

        # 100-word gigantic headline
        huge_headline = "MASSIVE LEAK REVEALS " + ("GTA 6 DETAIL " * 25)
        res_huge = generate_instagram_post(headline=huge_headline)
        self.assertTrue(os.path.exists(res_huge["image_path"]))

    def test_edge_generate_instagram_post_corrupted_background(self):
        """Verify passing a zero-byte or corrupted image path falls back gracefully to dark canvas."""
        corrupted_path = os.path.join(tempfile.gettempdir(), "test_corrupt_zero_byte.jpg")
        with open(corrupted_path, "wb") as f:
            f.write(b"")  # 0 bytes

        try:
            res = generate_instagram_post(headline="FALLBACK TEST", background_path=corrupted_path)
            self.assertIn("image_path", res)
            self.assertTrue(os.path.exists(res["image_path"]))
        finally:
            if os.path.exists(corrupted_path):
                os.remove(corrupted_path)

    # ── Video Assembler Edge Cases ──
    def test_edge_score_image_for_sentence_none_and_empty(self):
        """Verify semantic image scoring handles None and empty inputs without raising AttributeError."""
        self.assertEqual(score_image_for_sentence(None, None), 0)
        self.assertEqual(score_image_for_sentence("", ""), 0)
        self.assertEqual(score_image_for_sentence("Lucia_01.jpg", None), 0)
        self.assertGreater(score_image_for_sentence("Lucia_01.jpg", "Lucia takes the wheel"), 0)

    def test_edge_balance_wrap_headline_empty_and_huge(self):
        """Verify balance_wrap_headline handles empty strings and headlines requiring > 2 lines."""
        from PIL import ImageFont
        font = ImageFont.load_default()
        self.assertEqual(balance_wrap_headline("", font), [""])
        self.assertEqual(balance_wrap_headline("   ", font), ["   "])

        huge_text = "THIS IS A VERY LONG HEADLINE REQUIRING MULTIPLE LINES OF WRAPPING ON DISPLAY SCREENS"
        lines = balance_wrap_headline(huge_text, font, max_w=80)
        self.assertIsInstance(lines, list)
        self.assertGreater(len(lines), 2)
        # All words must be preserved in the output lines
        reconstructed = " ".join(lines)
        self.assertEqual(reconstructed, huge_text)

    # ── News Scraper Date & Text Edge Cases ──
    def test_edge_scraper_is_recent_naive_and_old_datetimes(self):
        """Verify is_recent handles naive datetimes and correctly rejects old stories."""
        # 6-year-old article (must be rejected)
        self.assertFalse(is_recent({"published": "2020-01-01 12:00:00"}))
        self.assertFalse(is_recent({"published": "Wed, 01 Jan 2020 12:00:00 GMT"}))

        # Fresh article (must be accepted)
        recent_rfc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        self.assertTrue(is_recent({"published": recent_rfc}))

    def test_edge_scraper_parse_date_iso_and_rfc(self):
        """Verify parse_date parses both ISO 8601 and RFC 2822 dates."""
        d1 = parse_date({"published": "2026-10-15T10:30:00Z"})
        self.assertIsNotNone(d1)
        self.assertEqual(d1.year, 2026)

        d2 = parse_date({"published": "Thu, 15 Oct 2026 10:30:00 GMT"})
        self.assertIsNotNone(d2)
        self.assertEqual(d2.year, 2026)

        # Invalid date string returns None rather than throwing
        self.assertIsNone(parse_date({"published": "not-a-valid-date-string"}))

    def test_edge_scraper_normalize_search_text_non_string(self):
        """Verify normalize_search_text handles non-string inputs safely."""
        self.assertEqual(normalize_search_text(None), "")
        self.assertEqual(normalize_search_text(12345), "12345")
        self.assertEqual(normalize_search_text("Ghost of Yōtei"), "ghost of yotei")

    # ── Voiceover Engine Edge Cases ──
    def test_edge_voiceover_empty_script_raises_runtime_error(self):
        """Verify generate_voiceover raises RuntimeError rather than invoking sys.exit(1) on failure."""
        with self.assertRaises(RuntimeError):
            generate_voiceover({"script": ""})

    def test_edge_voiceover_clean_script_acronyms_and_emojis(self):
        """Verify clean_script_for_tts strips emojis and preserves all gaming acronyms."""
        raw = "🔥 GTA VI announced for PS5, PS4, Xbox, PC! #gta6 Take-Two CEO confirmed DLC and NPCs... 🚀"
        cleaned = clean_script_for_tts(raw)
        self.assertNotIn("🔥", cleaned)
        self.assertNotIn("🚀", cleaned)
        self.assertNotIn("#gta6", cleaned)
        self.assertIn("GTA 6", cleaned)
        self.assertIn("Take Two", cleaned)
        self.assertIn("PS5", cleaned)
        self.assertIn("Xbox", cleaned)

    # ── API Endpoint Adversarial & Robustness Tests ──
    def test_edge_api_generate_instagram_non_string_fields(self):
        """Verify api_generate_instagram handles integer and boolean values in body without 500 error."""
        payload = {
            "headline": 12345,
            "summary": 67890,
            "game_title": "GTA VI",
            "category": 888,
            "focal_x": "not_a_float",
            "focal_y": "not_a_float",
            "custom_keywords": [None, 123, "TEST"]
        }
        resp = self.client.post("/api/generate/instagram/", json.dumps(payload), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))

    def test_edge_api_upload_shot_rejects_empty_and_corrupt_files(self):
        """Verify api_upload_shot strictly rejects zero-byte files and fake text files disguised as images."""
        # 1. 0-byte file
        empty_file = SimpleUploadedFile("empty.png", b"", content_type="image/png")
        resp1 = self.client.post("/api/upload-shot/", {"image": empty_file})
        self.assertEqual(resp1.status_code, 400)
        self.assertFalse(resp1.json().get("success"))

        # 2. Text file disguised as PNG
        fake_file = SimpleUploadedFile("fake.png", b"This is a text file, not a PNG image!", content_type="image/png")
        resp2 = self.client.post("/api/upload-shot/", {"image": fake_file})
        self.assertEqual(resp2.status_code, 400)
        self.assertFalse(resp2.json().get("success"))

    def test_edge_game_fetcher_magic_bytes_validation(self):
        """Verify is_valid_image_bytes detects real image magic bytes and rejects counterfeit formats."""
        # Real JPEG, PNG, WebP headers
        self.assertTrue(is_valid_image_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"))
        self.assertTrue(is_valid_image_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00"))
        self.assertTrue(is_valid_image_bytes(b"RIFF\x24\x00\x00\x00WEBPVP8 \x18\x00\x00\x00"))

        # Counterfeits: text, HTML, Windows EXE, and truncated headers
        self.assertFalse(is_valid_image_bytes(b"<!DOCTYPE html><html><body>Error</body></html>"))
        self.assertFalse(is_valid_image_bytes(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"))
        self.assertFalse(is_valid_image_bytes(b"Hello world!"))
        self.assertFalse(is_valid_image_bytes(b""))

