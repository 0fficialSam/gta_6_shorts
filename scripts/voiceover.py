"""
GTA 6 Voiceover Generator - Studio Audio Engine & Music Mixing
==============================================================
- Primary: edge-tts (100% free neural studio voices, energetic pacing, word/sentence boundaries)
- Audio Mixer: Sidechain-ducked background synthwave/gaming music (-20 dB)
- Timing: Exports exact sentence boundaries to assets/subtitles_timing.json
- Fallbacks: gTTS (Google) -> pyttsx3 (offline SAPI5)
"""
import asyncio, json, os, re, subprocess, shutil, sys, wave, math, random
from datetime import datetime
from pathlib import Path
import numpy as np

try:
    from scripts.config import get_tts_settings, get_music_settings
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.config import get_tts_settings, get_music_settings

_tts_cfg = get_tts_settings()
_mus_cfg = get_music_settings()
DEFAULT_VOICE = _tts_cfg.get("voice", "en-US-BrianMultilingualNeural")   # Flagship ultra-natural conversational creator voice
DEFAULT_RATE  = _tts_cfg.get("rate", "+4%")                               # Natural human conversational pacing
DEFAULT_BGM_VOL = 0.28                                                    # Audible gaming mix ratio
DEFAULT_ENABLE_MUSIC = _mus_cfg.get("enabled", True)


def find_ffmpeg():
    for cmd in ["ffmpeg", "ffmpeg.exe"]:
        if shutil.which(cmd):
            return cmd
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.exists(p):
            return p
    except:
        pass
    return None


def clean_script_for_tts(script: str) -> str:
    """Clean script for smooth, ultra-natural human-like neural TTS output."""
    # Convert shouting all-caps words to Titlecase so TTS doesn't spell them out or sound robotic
    def fix_caps(match):
        w = match.group(0)
        if w in {"GTA", "PS5", "PS4", "Xbox", "PC", "AI", "DLC", "NPC", "NPCs", "ESRB", "BGM", "CEO"}:
            return w
        return w.capitalize()

    script = re.sub(r'\b[A-Z]{3,}\b', fix_caps, script)
    # Natural phonetic expansions
    script = re.sub(r'\bGTA\s+VI\b', 'GTA 6', script, flags=re.IGNORECASE)
    script = re.sub(r'\bRDR\s*2\b', 'Red Dead 2', script, flags=re.IGNORECASE)
    script = re.sub(r'\bTake-Two\b', 'Take Two', script, flags=re.IGNORECASE)
    script = re.sub(r'[^\x00-\x7F]+', '', script)   # Remove emojis/non-ascii
    script = re.sub(r'#\w+', '', script)            # Remove hashtags
    script = re.sub(r'\.{2,}', '. ', script)        # Fix ellipsis
    script = script.replace('—', ', ').replace('–', ', ')
    script = re.sub(r'\s+', ' ', script).strip()
    return script


# ── BGM CATALOG & ROTATION ───────────────────────────────────────────────────
BGM_CATALOG = [
    {
        "filename": "vice_city_night_drive.mp3",
        "title": "Outrun Boulevard",
        "genre": "80s Retro Synthwave",
        "artist": "Kjartan Abel",
        "url": "https://upload.wikimedia.org/wikipedia/commons/0/02/Outrun-Boulevard-by-Kjartan-Abel.ogg",
        "style": "synthwave",
        "bpm": 124,
    },
    {
        "filename": "leonida_action_beat.mp3",
        "title": "Harry Spotter",
        "genre": "Gym Phonk / Heavy Bass Beat",
        "artist": "Alexi Action",
        "url": "https://upload.wikimedia.org/wikipedia/commons/f/f6/Alexi_Action_-_Harry_Spotter_%28Gym_Phonk%3B_midtempo_bass_music_popularized_by_fitness_Internet_meme%29.ogg",
        "style": "phonk",
        "bpm": 140,
    },
    {
        "filename": "miami_heist_pulse.mp3",
        "title": "Cut and Run",
        "genre": "Fast Action / Heist Suspense",
        "artist": "Kevin MacLeod",
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/b1/Cut_and_Run_%28ISRC_USUAN1100851%29.mp3",
        "style": "tension",
        "bpm": 136,
    },
    {
        "filename": "sunset_boulevard.mp3",
        "title": "Laser Groove",
        "genre": "Miami Beach Synth Funk Groove",
        "artist": "Kevin MacLeod",
        "url": "https://upload.wikimedia.org/wikipedia/commons/1/1e/Laser_Groove_%28ISRC_USUAN1700017%29.mp3",
        "style": "funk",
        "bpm": 112,
    },
]


def download_curated_track(item: dict, dest_path: str) -> bool:
    """Download a royalty-free track from Wikimedia Commons and encode to 192k MP3."""
    url = item["url"]
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False
    try:
        import urllib.request
        headers = {'User-Agent': 'GTA6ShortsAutomation/1.0 (https://github.com/0fficialSam/gta_6_shorts; satarths1@gmail.com)'}
        temp_dl = dest_path + ".temp" + os.path.splitext(url)[1]
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp, open(temp_dl, 'wb') as out_f:
            out_f.write(resp.read())

        if os.path.exists(temp_dl) and os.path.getsize(temp_dl) > 50000:
            cmd = [
                ffmpeg, "-y",
                "-i", temp_dl,
                "-ar", "44100", "-ac", "2",
                "-b:a", "192k",
                dest_path
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_dl):
                os.remove(temp_dl)
            return os.path.exists(dest_path) and os.path.getsize(dest_path) > 100000
    except Exception as e:
        print(f"  Download warning for {item['filename']}: {e}")
        if 'temp_dl' in locals() and os.path.exists(temp_dl):
            try:
                os.remove(temp_dl)
            except:
                pass
    return False


def synth_procedural_track(path: str, style: str = "synthwave", bpm: int = 124, duration: float = 65.0):
    """
    Offline fallback synthesizer with 4 genuinely distinct genre arrangements:
    - synthwave: 80s analog saw bass, 4-on-the-floor kick, gated snare, bright arp
    - phonk: distorted 808 sub kick, trap snare on 3, pentatonic cowbell stabs
    - tension: 16th ticking mechanical hats, low 40Hz heartbeat pulse, dark drone
    - funk: swing groove, slap bass pops, brush snare, warm rhodes chord stabs
    """
    sr = 44100
    total = int(sr * duration)
    t = np.linspace(0, duration, total, endpoint=False)
    b_dur = 60.0 / bpm
    bar_dur = b_dur * 4.0

    if style == "phonk":
        # 140 BPM Phonk: Heavy 808 sub kick, snare on beat 3, cowbell melody
        b_phase = (t % b_dur) / b_dur
        k_mask = ((t % (2 * b_dur)) < b_dur * 0.4) | (((t % (2 * b_dur)) >= b_dur * 1.5) & ((t % (2 * b_dur)) < b_dur * 1.9))
        k_env = np.exp(-10.0 * b_phase)
        k_freq = 95.0 * np.exp(-12.0 * b_phase) + 38.0
        kick = np.sin(2 * np.pi * k_freq * b_phase * b_dur) * k_env * k_mask * 1.2
        kick = np.clip(kick * 1.4, -1.0, 1.0)

        s_phase = (t % (2 * b_dur)) / (2 * b_dur)
        s_mask = (s_phase >= 0.5) & (s_phase < 0.65)
        sn_sub_phase = ((t % (2 * b_dur)) - b_dur) / b_dur
        s_noise = (np.random.rand(total) * 2 - 1) * np.exp(-16.0 * np.maximum(sn_sub_phase, 0))
        snare = s_noise * s_mask * 0.8

        h_dur = b_dur / 4.0
        h_phase = (t % h_dur) / h_dur
        hat = (np.random.rand(total) * 2 - 1) * np.exp(-35.0 * h_phase) * 0.22

        cowbell = np.zeros(total)
        cow_notes = [739.99, 880.00, 987.77, 1108.73]
        step_dur = b_dur / 2.0
        step_idx = ((t // step_dur) % 8).astype(int)
        for i, c_freq in enumerate(cow_notes):
            mask = (step_idx == i * 2)
            c_phase = (t % step_dur) / step_dur
            tone = 0.6 * np.sin(2 * np.pi * c_freq * t) + 0.4 * np.sin(2 * np.pi * c_freq * 1.5 * t)
            cowbell += tone * np.exp(-14.0 * c_phase) * mask * 0.55

        mix = kick * 0.60 + snare * 0.50 + hat * 0.25 + cowbell * 0.60

    elif style == "tension":
        # 136 BPM Heist Suspense: Ominous low drone, heartbeat pulse, clock tick
        hb_phase = (t % (2 * b_dur)) / (2 * b_dur)
        k_env = np.exp(-8.0 * hb_phase)
        kick = np.sin(2 * np.pi * 42.0 * t) * k_env * 0.7

        h_dur = b_dur / 4.0
        h_phase = (t % h_dur) / h_dur
        hat = (np.random.rand(total) * 2 - 1) * np.exp(-40.0 * h_phase) * 0.35

        drone_f = 65.41
        drone = (np.sin(2 * np.pi * drone_f * t) * 0.5 +
                 np.sin(2 * np.pi * drone_f * 2.01 * t) * 0.3 +
                 np.sin(2 * np.pi * drone_f * 3.0 * t) * 0.15)
        drone_swell = 0.5 + 0.5 * np.sin(2 * np.pi * (t / (bar_dur * 4)))
        drone = drone * drone_swell * 0.65

        ping = np.sin(2 * np.pi * (440.0 + (t % bar_dur) * 120.0) * t) * 0.08
        mix = kick * 0.50 + hat * 0.35 + drone * 0.55 + ping

    elif style == "funk":
        # 112 BPM Miami Funk Groove: Swing beat, slap bass plucks, bright chords
        b_phase = (t % b_dur) / b_dur
        k_env = np.exp(-16.0 * b_phase)
        kick = np.sin(2 * np.pi * 55.0 * b_phase * b_dur) * k_env * 0.65

        s_mask = ((t % (2 * b_dur)) >= b_dur) & ((t % (2 * b_dur)) < b_dur * 1.4)
        s_phase = (t % b_dur) / b_dur
        snare = (np.random.rand(total) * 2 - 1) * np.exp(-12.0 * s_phase) * s_mask * 0.5

        h_dur = b_dur / 2.0
        h_phase = (t % h_dur) / h_dur
        hat = (np.random.rand(total) * 2 - 1) * np.exp(-25.0 * h_phase) * 0.25

        bass = np.zeros(total)
        funk_chords = [82.41, 98.00, 110.00, 123.47]
        for i, rf in enumerate(funk_chords):
            c_mask = (t % (bar_dur * 4) >= i * bar_dur) & (t % (bar_dur * 4) < (i + 1) * bar_dur)
            b_step = (t % (b_dur / 2.0)) / (b_dur / 2.0)
            slap = (np.sin(2 * np.pi * rf * t) * 0.6 + np.sin(2 * np.pi * rf * 2 * t) * 0.4) * np.exp(-8.0 * b_step)
            bass += slap * c_mask * 0.55

        mix = kick * 0.55 + snare * 0.45 + hat * 0.25 + bass * 0.50

    else:
        # Default: 80s Vice City Synthwave (124 BPM)
        b_phase = (t % b_dur) / b_dur
        k_env = np.exp(-14.0 * b_phase)
        k_freq = 150.0 * np.exp(-18.0 * b_phase) + 48.0
        kick = np.sin(2 * np.pi * k_freq * b_phase * b_dur) * k_env

        s_mask = ((t % (2 * b_dur)) >= b_dur) & ((t % (2 * b_dur)) < b_dur * 1.5)
        s_phase = (t % b_dur) / b_dur
        s_tone = np.sin(2 * np.pi * 190.0 * s_phase * b_dur) * np.exp(-12.0 * s_phase)
        s_noise = (np.random.rand(total) * 2 - 1) * np.exp(-8.0 * s_phase)
        snare = (s_tone * 0.4 + s_noise * 0.6) * s_mask

        h_dur = b_dur / 4.0
        h_phase = (t % h_dur) / h_dur
        hat = (np.random.rand(total) * 2 - 1) * np.exp(-28.0 * h_phase) * 0.25

        root_f = 73.42
        bass = np.zeros(total)
        chords = [root_f, root_f * (2**(3/12)), root_f * (2**(5/12)), root_f * (2**(10/12))]
        for i, rf in enumerate(chords):
            c_mask = (t % (bar_dur * 4) >= i * bar_dur) & (t % (bar_dur * 4) < (i + 1) * bar_dur)
            sub_phase = (t % (b_dur / 2.0)) / (b_dur / 2.0)
            saw = 0.5 * np.sin(2 * np.pi * rf * t) + 0.3 * np.sin(4 * np.pi * rf * t) + 0.15 * np.sin(6 * np.pi * rf * t)
            bass += saw * np.exp(-6.0 * sub_phase) * c_mask

        arp = np.zeros(total)
        arp_notes = [root_f * 2, root_f * 2.4, root_f * 3, root_f * 3.6]
        step_dur = b_dur / 2.0
        step_phase = (t % step_dur) / step_dur
        for idx, nf in enumerate(arp_notes):
            step_mask = (t % (b_dur * 2) >= idx * step_dur) & (t % (b_dur * 2) < (idx + 1) * step_dur)
            lead = np.sin(2 * np.pi * nf * t) * np.exp(-3.5 * step_phase)
            arp += lead * step_mask * 0.3

        mix = kick * 0.55 + snare * 0.48 + hat * 0.28 + bass * 0.50 + arp * 0.35

    mix = np.clip(mix * 0.90, -0.95, 0.95)
    raw = (mix * 32767).astype(np.int16)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_wav = path.replace(".mp3", ".wav") if path.endswith(".mp3") else path
    with wave.open(temp_wav, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(raw.tobytes())

    if path.endswith(".mp3"):
        ffmpeg = find_ffmpeg()
        if ffmpeg:
            cmd = [ffmpeg, "-y", "-i", temp_wav, "-ar", "44100", "-ac", "2", "-b:a", "192k", path]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
            return path
    return temp_wav


def ensure_music_library():
    """Ensures a rich library of 4 completely distinct studio BGM tracks is ready."""
    music_dir = "assets/music"
    os.makedirs(music_dir, exist_ok=True)

    for item in BGM_CATALOG:
        dest = os.path.join(music_dir, item["filename"])
        if not os.path.exists(dest) or os.path.getsize(dest) < 200000:
            print(f"  Fetching studio BGM: {item['filename']} ({item['genre']})...")
            ok = download_curated_track(item, dest)
            if not ok:
                print(f"  Generating procedural fallback for {item['filename']} ({item['style']})...")
                synth_procedural_track(dest, style=item["style"], bpm=item["bpm"])


def get_bgm_track(seed: str = None) -> str:
    """Find a background music track in assets/music/, rotating deterministically."""
    music_dir = "assets/music"
    ensure_music_library()
    tracks = (glob_files(music_dir, "*.mp3") +
              glob_files(music_dir, "*.wav") +
              glob_files(music_dir, "*.ogg"))
    tracks = [t for t in tracks if not os.path.basename(t).startswith("test_")]
    tracks.sort()

    if tracks:
        if seed:
            import hashlib
            idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(tracks)
            return tracks[idx]
        return random.choice(tracks)

    return os.path.join(music_dir, "vice_city_night_drive.mp3")


def glob_files(folder: str, pattern: str) -> list:
    return [str(p) for p in Path(folder).glob(pattern) if p.is_file()]


def mix_voice_and_bgm(voice_path: str, bgm_path: str, output_path: str,
                      bgm_volume: float = DEFAULT_BGM_VOL, voice_volume: float = 1.15) -> bool:
    """
    Mix background music under the voiceover with dynamic sidechain ducking.
    Music automatically ducks smoothly when the voice speaks and swells during pauses.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False

    # Dynamic sidechain ducking filtergraph
    sidechain_filter = (
        f"[0:a]volume={voice_volume},asplit=2[v1][v2];"
        f"[1:a]volume={bgm_volume * 1.25}[bg];"
        "[bg][v1]sidechaincompress=threshold=0.08:ratio=4.0:attack=40:release=350[ducked_bg];"
        "[v2][ducked_bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]"
    )

    try:
        cmd = [
            ffmpeg, "-y",
            "-i", voice_path,
            "-stream_loop", "-1", "-i", bgm_path,
            "-filter_complex", sidechain_filter,
            "-map", "[out]",
            "-c:a", "libmp3lame", "-b:a", "192k",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=40)
        if result.returncode == 0 and os.path.exists(output_path):
            return True
    except Exception as e:
        print(f"  Sidechain ducking warning: {e}, using static mix")

    # Graceful fallback to static volume mix
    try:
        cmd = [
            ffmpeg, "-y",
            "-i", voice_path,
            "-stream_loop", "-1", "-i", bgm_path,
            "-filter_complex",
            f"[1:a]volume={bgm_volume}[bg];[0:a]volume={voice_volume}[v];[v][bg]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[out]",
            "-map", "[out]",
            "-c:a", "libmp3lame", "-b:a", "192k",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=40)
        return result.returncode == 0
    except Exception as e:
        print(f"  Audio mixing error: {e}")
        return False


def apply_studio_vocal_chain(input_path: str, output_path: str) -> bool:
    """
    Applies professional studio microphone audio mastering to the voiceover:
    - Highpass (75 Hz): removes sub-bass rumble and breath thumps
    - Chest warmth EQ (+1.4 dB at 180 Hz): rich radio presence
    - De-boxiness EQ (-1.0 dB at 650 Hz): eliminates muddy cardboard resonance
    - De-harshing EQ (-1.2 dB at 3800 Hz): removes synthetic robotic digital rasp
    - Studio air EQ (+1.0 dB at 10000 Hz): clean modern acoustic breath
    - Transparent broadcast leveler: soft-knee compressor preserving natural human dynamics
    - Smooth output volume leveling
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        shutil.copy2(input_path, output_path)
        return False

    vocal_filter = (
        "highpass=f=75,"
        "equalizer=f=180:width_type=o:width=1.0:g=1.4,"
        "equalizer=f=650:width_type=o:width=1.2:g=-1.0,"
        "equalizer=f=3800:width_type=o:width=1.2:g=-1.2,"
        "equalizer=f=10000:width_type=o:width=1.0:g=1.0,"
        "acompressor=threshold=-22dB:ratio=2.0:attack=25:release=180:knee=4dB,"
        "volume=1.12"
    )

    try:
        cmd = [
            ffmpeg, "-y",
            "-i", input_path,
            "-af", vocal_filter,
            "-c:a", "libmp3lame", "-b:a", "192k",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0 and os.path.exists(output_path):
            return True
    except Exception as e:
        print(f"  Vocal mastering error: {e}")

    shutil.copy2(input_path, output_path)
    return False


# ── EDGE-TTS IMPLEMENTATION ───────────────────────────────────────────────────
async def _async_edge_tts(script: str, output_path: str, voice: str, rate: str):
    import edge_tts
    comm = edge_tts.Communicate(script, voice, rate=rate)
    audio_data = bytearray()
    timings = []

    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio_data.extend(chunk["data"])
        elif chunk["type"] == "SentenceBoundary":
            start_s = round(chunk["offset"] / 10_000_000, 3)
            dur_s = round(chunk["duration"] / 10_000_000, 3)
            end_s = round(start_s + dur_s, 3)
            timings.append({
                "text": chunk["text"].strip(),
                "start": start_s,
                "end": end_s,
                "duration": dur_s
            })

    with open(output_path, "wb") as f:
        f.write(audio_data)

    return timings


def generate_voice_edge_tts(script: str, output_path: str, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE) -> tuple[bool, list]:
    """Generate voiceover using Microsoft Edge neural TTS with sentence timings."""
    try:
        clean = clean_script_for_tts(script)
        timings = asyncio.run(_async_edge_tts(clean, output_path, voice, rate))

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            print(f"  Edge-TTS ready: voice '{voice}' ({rate}) -> {len(timings)} sentence timings")
            return True, timings

    except Exception as e:
        print(f"  Edge-TTS generation failed: {e}")

    return False, []


# ── FALLBACK 1: GTTS ──────────────────────────────────────────────────────────
def speed_up_audio(input_path: str, output_path: str, speed: float = 1.15) -> bool:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False
    try:
        result = subprocess.run([
            ffmpeg, "-y", "-i", input_path,
            "-filter:a", f"atempo={speed}",
            "-vn", output_path
        ], capture_output=True, timeout=30)
        return result.returncode == 0
    except:
        return False


def generate_voice_gtts(script: str, output_path: str) -> bool:
    try:
        from gtts import gTTS
        clean = clean_script_for_tts(script)
        tts = gTTS(text=clean, lang='en', slow=False)
        raw_path = output_path.replace('.mp3', '_raw.mp3')
        tts.save(raw_path)
        sped_up = speed_up_audio(raw_path, output_path, speed=1.10)
        if os.path.exists(raw_path):
            os.remove(raw_path)
        if os.path.exists(output_path):
            print(f"  gTTS voice ready: {output_path}")
            return True
    except Exception as e:
        print(f"  gTTS fallback failed: {e}")
    return False


# ── FALLBACK 2: PYTTSX3 (OFFLINE) ─────────────────────────────────────────────
def generate_voice_pyttsx3(script: str, output_path: str) -> bool:
    try:
        import pyttsx3
        clean = clean_script_for_tts(script)
        engine = pyttsx3.init()
        engine.setProperty('rate', 195)
        engine.setProperty('volume', 1.0)

        voices = engine.getProperty('voices')
        for v in voices:
            if any(n in v.name.lower() for n in ['david', 'guy', 'male', 'mark', 'daniel']):
                engine.setProperty('voice', v.id)
                break

        wav_path = output_path.replace('.mp3', '.wav')
        engine.save_to_file(clean, wav_path)
        engine.runAndWait()

        if os.path.exists(wav_path):
            # Convert to mp3 via ffmpeg
            ffmpeg = find_ffmpeg()
            if ffmpeg:
                subprocess.run([ffmpeg, "-y", "-i", wav_path, "-b:a", "192k", output_path], capture_output=True)
                if os.path.exists(wav_path):
                    os.remove(wav_path)
                return True
            return True
    except Exception as e:
        print(f"  pyttsx3 fallback failed: {e}")
    return False


# ── MASTER VOICEOVER GENERATOR ────────────────────────────────────────────────
def generate_voiceover(script_data: dict, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE, enable_music: bool = DEFAULT_ENABLE_MUSIC) -> str:
    """
    Generate professional studio voiceover:
    1. Edge-TTS neural voice + exact sentence boundaries
    2. Ducked background synthwave music (-20 dB)
    3. Saves subtitle timings to assets/subtitles_timing.json
    """
    print("Generating Studio Voiceover (Edge-TTS + Background Music)...")
    os.makedirs("assets", exist_ok=True)
    os.makedirs("assets/music", exist_ok=True)

    script = script_data.get("script", "")
    raw_path = "assets/voiceover_raw.mp3"
    dry_path = "assets/voiceover_dry.mp3"
    final_path = "assets/voiceover.mp3"
    timing_file = "assets/subtitles_timing.json"

    words = len(script.split())
    print(f"  Script: {words} words")

    timings = []
    success = False

    # 1. Edge-TTS (Primary)
    success, timings = generate_voice_edge_tts(script, raw_path, voice=voice, rate=rate)

    # 2. gTTS Fallback
    if not success:
        print("  Falling back to gTTS...")
        success = generate_voice_gtts(script, raw_path)

    # 3. pyttsx3 Fallback
    if not success:
        print("  Falling back to pyttsx3 (offline)...")
        success = generate_voice_pyttsx3(script, raw_path)

    if not success or not os.path.exists(raw_path):
        print("ERROR: All TTS engines failed.")
        sys.exit(1)

    # Professional Studio Vocal Chain (EQ + Broadcast Compression)
    print("  Applying studio vocal mastering (EQ, presence boost & broadcast compression)...")
    apply_studio_vocal_chain(raw_path, dry_path)

    # Save timings to assets/subtitles_timing.json & script_data
    if timings:
        with open(timing_file, "w", encoding="utf-8") as f:
            json.dump(timings, f, indent=2, ensure_ascii=False)
        script_data["subtitles_timing"] = timings
    else:
        # Approximate timings based on sentence length
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if s.strip()]
        total_w = max(sum(len(s.split()) for s in sentences), 1)
        ffmpeg = find_ffmpeg()
        est_dur = 55.0
        if ffmpeg:
            try:
                r = subprocess.run([ffmpeg, "-v", "error", "-show_entries", "format=duration",
                                    "-of", "default=noprint_wrappers=1:nokey=1", dry_path],
                                   capture_output=True, text=True)
                est_dur = float(r.stdout.strip())
            except:
                pass

        approx_timings = []
        cur_t = 0.0
        for s in sentences:
            dur = round((len(s.split()) / total_w) * est_dur, 3)
            approx_timings.append({
                "text": s,
                "start": round(cur_t, 3),
                "end": round(cur_t + dur, 3),
                "duration": dur
            })
            cur_t += dur
        with open(timing_file, "w", encoding="utf-8") as f:
            json.dump(approx_timings, f, indent=2, ensure_ascii=False)
        script_data["subtitles_timing"] = approx_timings

    # 4. Mix Background Music
    if enable_music:
        explicit_bgm = script_data.get("bgm_track")
        if explicit_bgm:
            if os.path.isabs(explicit_bgm) and os.path.exists(explicit_bgm):
                bgm_track = explicit_bgm
            else:
                cand = os.path.join("assets", "music", os.path.basename(explicit_bgm))
                bgm_track = cand if os.path.exists(cand) else get_bgm_track(seed=script_data.get("story", {}).get("title"))
        else:
            seed = script_data.get("story", {}).get("title", datetime.now().strftime("%Y-%m-%d"))
            bgm_track = get_bgm_track(seed=seed)

        print(f"  Mixing BGM: {os.path.basename(bgm_track)} (audible gaming mix, normalize=0)...")
        mixed = mix_voice_and_bgm(dry_path, bgm_track, final_path, bgm_volume=DEFAULT_BGM_VOL, voice_volume=1.15)
        if mixed and os.path.exists(final_path):
            print(f"  Voice + BGM mixed successfully: {final_path}")
            return final_path
        else:
            print("  BGM mix failed — using dry voiceover")

    # If music disabled or mixing failed, copy dry voice to final
    shutil.copy2(dry_path, final_path)
    return final_path


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open("assets/current_script.json", encoding="utf-8") as f:
        script_data = json.load(f)
    out = generate_voiceover(script_data)
    print(f"\nFinal Voiceover ready: {out} ({os.path.getsize(out)//1024} KB)")
