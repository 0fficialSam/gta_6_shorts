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
DEFAULT_VOICE = _tts_cfg.get("voice", "en-IN-PrabhatNeural")       # High-energy, natural Indian English narration
DEFAULT_RATE  = _tts_cfg.get("rate", "+13%")                          # Punchy YouTube Shorts pacing
DEFAULT_BGM_VOL = 0.28                                                 # Audible gaming mix ratio
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
    """Clean script for smooth neural TTS output."""
    script = re.sub(r'[^\x00-\x7F]+', '', script)   # Remove emojis/non-ascii
    script = re.sub(r'#\w+', '', script)            # Remove hashtags
    script = re.sub(r'\.{2,}', '. ', script)        # Fix ellipsis
    script = script.replace('—', ', ').replace('–', ', ')
    script = re.sub(r'\s+', ' ', script).strip()
    return script


def synth_procedural_track(path: str, bpm: int = 124, root_f: float = 73.42, duration: float = 65.0):
    """
    Synthesizes a high-energy 80s Vice City synthwave gaming beat
    with punchy kick drum, 80s snare/clap, 16th hats, rolling bassline, and lead arp.
    """
    sr = 44100
    total = int(sr * duration)
    t = np.linspace(0, duration, total, endpoint=False)
    b_dur = 60.0 / bpm
    bar_dur = b_dur * 4.0

    # 1. 4-on-the-floor punchy kick drum
    b_phase = (t % b_dur) / b_dur
    k_env = np.exp(-14.0 * b_phase)
    k_freq = 150.0 * np.exp(-18.0 * b_phase) + 48.0
    kick = np.sin(2 * np.pi * k_freq * b_phase * b_dur) * k_env

    # 2. Snare / Clap on beats 2 & 4
    s_mask = ((t % (2 * b_dur)) >= b_dur) & ((t % (2 * b_dur)) < b_dur * 1.5)
    s_phase = (t % b_dur) / b_dur
    noise = (np.random.rand(total) * 2 - 1)
    s_tone = np.sin(2 * np.pi * 190.0 * s_phase * b_dur) * np.exp(-12.0 * s_phase)
    s_noise = noise * np.exp(-8.0 * s_phase)
    snare = (s_tone * 0.4 + s_noise * 0.6) * s_mask

    # 3. 16th-note Hi-Hats with rhythmic accents
    h_dur = b_dur / 4.0
    h_phase = (t % h_dur) / h_dur
    h_accent = 1.0 + 0.5 * (((t // h_dur) % 4) == 2)
    hat = (np.random.rand(total) * 2 - 1) * np.exp(-28.0 * h_phase) * 0.25 * h_accent

    # 4. Driving Bassline (16th-note arpeggiated bass)
    bass = np.zeros(total)
    chords = [root_f, root_f * (2**(3/12)), root_f * (2**(5/12)), root_f * (2**(10/12))]
    for i, rf in enumerate(chords):
        c_mask = (t % (bar_dur * 4) >= i * bar_dur) & (t % (bar_dur * 4) < (i + 1) * bar_dur)
        sub_phase = (t % (b_dur / 2.0)) / (b_dur / 2.0)
        pulse = np.exp(-6.0 * sub_phase)
        saw = 0.5 * np.sin(2 * np.pi * rf * t) + 0.3 * np.sin(4 * np.pi * rf * t) + 0.15 * np.sin(6 * np.pi * rf * t)
        bass += saw * pulse * c_mask

    # 5. Synth Lead Arpeggio
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
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(raw.tobytes())
    return path


def ensure_music_library():
    """Ensures a rich library of 4 distinct Vice City tracks is ready."""
    music_dir = "assets/music"
    os.makedirs(music_dir, exist_ok=True)
    tracks_spec = [
        ("vice_city_night_drive.wav", 124, 73.42),
        ("miami_heist_pulse.wav",     128, 65.41),
        ("sunset_boulevard.wav",      116, 82.41),
        ("leonida_action_beat.wav",   130, 55.00),
    ]
    for filename, bpm, root_f in tracks_spec:
        p = os.path.join(music_dir, filename)
        if not os.path.exists(p) or os.path.getsize(p) < 100000:
            synth_procedural_track(p, bpm, root_f)


def get_bgm_track(seed: str = None) -> str:
    """Find a background music track in assets/music/, rotating daily."""
    music_dir = "assets/music"
    ensure_music_library()
    tracks = (glob_files(music_dir, "*.mp3") +
              glob_files(music_dir, "*.wav") +
              glob_files(music_dir, "*.ogg"))
    tracks = [t for t in tracks if not os.path.basename(t).startswith("test_")]

    if tracks:
        if seed:
            import hashlib
            idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(tracks)
            return tracks[idx]
        return random.choice(tracks)

    return os.path.join(music_dir, "vice_city_night_drive.wav")


def glob_files(folder: str, pattern: str) -> list:
    return [str(p) for p in Path(folder).glob(pattern) if p.is_file()]


def mix_voice_and_bgm(voice_path: str, bgm_path: str, output_path: str,
                      bgm_volume: float = DEFAULT_BGM_VOL, voice_volume: float = 1.15) -> bool:
    """
    Mix background music under the voiceover with ducking using FFmpeg.
    Uses normalize=0 to guarantee the music is clearly audible without clipping.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False

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
    - Highpass (80 Hz): removes synthetic sub-rumble
    - Proximity warmth EQ (+2.2 dB at 220 Hz): rich radio presence
    - Consonant clarity EQ (+3.8 dB at 3400 Hz): crisp intelligibility over music
    - Studio air EQ (+1.8 dB at 8000 Hz): high-end clarity
    - Broadcast dynamic compressor: evens out quiet and punchy syllables
    - Output volume leveling
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        shutil.copy2(input_path, output_path)
        return False

    vocal_filter = (
        "highpass=f=80,"
        "equalizer=f=220:width_type=o:width=1.0:g=2.2,"
        "equalizer=f=3400:width_type=o:width=1.2:g=3.8,"
        "equalizer=f=8200:width_type=o:width=1.0:g=1.8,"
        "acompressor=threshold=-18dB:ratio=3.5:attack=15:release=120:makeup=2.5dB,"
        "volume=1.2"
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
