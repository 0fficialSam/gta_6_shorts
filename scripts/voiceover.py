"""
GTA 6 Voiceover Generator - Studio Audio Engine & Music Mixing
==============================================================
- Primary: edge-tts (100% free neural studio voices, energetic pacing, word/sentence boundaries)
- Audio Mixer: Sidechain-ducked background synthwave/gaming music (-20 dB)
- Timing: Exports exact sentence boundaries to assets/subtitles_timing.json
- Fallbacks: gTTS (Google) -> pyttsx3 (offline SAPI5)
"""
import asyncio, json, os, re, subprocess, shutil, sys, wave, math, random
from pathlib import Path
import numpy as np

DEFAULT_VOICE = "en-US-ChristopherNeural"   # High-energy, crisp gaming narration
DEFAULT_RATE  = "+12%"                      # Punchy YouTube Shorts pacing
DEFAULT_BGM_VOL = 0.09                      # ~-21 dB background music ducking


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


def generate_procedural_bgm(output_path: str = "assets/music/synthwave_ambience.wav", duration: float = 65.0) -> str:
    """
    Generates a dark retro Vice City synthwave ambient bassline track if no music is provided.
    100% offline, procedural, royalty-free.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        return output_path

    print("  Creating procedural Vice City synthwave ambient track...")
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    # 120 BPM dark synthwave chord progression (D -> Bb -> C -> A)
    bass_freqs = [73.42, 58.27, 65.41, 55.0]
    bass = np.zeros_like(t)

    for i, f in enumerate(bass_freqs):
        start_t = i * 2.0
        mask = (t % 8.0 >= start_t) & (t % 8.0 < start_t + 2.0)
        # Rich sawtooth harmonic stack
        saw = 0.5 * np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)
        # Rhythmic eighth-note pulse envelope
        pulse = np.exp(-4.5 * ((t % 0.25) / 0.25))
        bass += mask * saw * pulse

    # Warm analog pad synth (D minor triad)
    pad = (0.15 * np.sin(2 * np.pi * 146.83 * t) +
           0.15 * np.sin(2 * np.pi * 220.0 * t) +
           0.10 * np.sin(2 * np.pi * 293.66 * t))

    # Subtle vinyl texture
    noise = 0.015 * (np.random.rand(len(t)) * 2 - 1)

    music = np.clip(bass * 0.45 + pad * 0.35 + noise, -0.9, 0.9)
    audio_int16 = (music * 32767).astype(np.int16)

    with wave.open(output_path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())

    return output_path


def get_bgm_track() -> str:
    """Find a background music track in assets/music/ or generate one."""
    music_dir = "assets/music"
    os.makedirs(music_dir, exist_ok=True)

    tracks = (glob_files(music_dir, "*.mp3") +
              glob_files(music_dir, "*.wav") +
              glob_files(music_dir, "*.ogg"))

    if tracks:
        return random.choice(tracks)

    return generate_procedural_bgm()


def glob_files(folder: str, pattern: str) -> list:
    return [str(p) for p in Path(folder).glob(pattern) if p.is_file()]


def mix_voice_and_bgm(voice_path: str, bgm_path: str, output_path: str, bgm_volume: float = DEFAULT_BGM_VOL) -> bool:
    """
    Mix background music under the voiceover with ducking using FFmpeg.
    Music is looped seamlessly and clamped to voice duration.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False

    try:
        # Loop music indefinitely, scale volume to ~-21 dB, mix with voice, end when voice ends
        cmd = [
            ffmpeg, "-y",
            "-i", voice_path,
            "-stream_loop", "-1", "-i", bgm_path,
            "-filter_complex",
            f"[1:a]volume={bgm_volume}[bg];[0:a]volume=1.0[v];[v][bg]amix=inputs=2:duration=first:dropout_transition=2[out]",
            "-map", "[out]",
            "-c:a", "libmp3lame", "-b:a", "192k",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=40)
        return result.returncode == 0
    except Exception as e:
        print(f"  Audio mixing error: {e}")
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
def generate_voiceover(script_data: dict, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE, enable_music: bool = True) -> str:
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
    dry_path = "assets/voiceover_dry.mp3"
    final_path = "assets/voiceover.mp3"
    timing_file = "assets/subtitles_timing.json"

    words = len(script.split())
    print(f"  Script: {words} words")

    timings = []
    success = False

    # 1. Edge-TTS (Primary)
    success, timings = generate_voice_edge_tts(script, dry_path, voice=voice, rate=rate)

    # 2. gTTS Fallback
    if not success:
        print("  Falling back to gTTS...")
        success = generate_voice_gtts(script, dry_path)

    # 3. pyttsx3 Fallback
    if not success:
        print("  Falling back to pyttsx3 (offline)...")
        success = generate_voice_pyttsx3(script, dry_path)

    if not success or not os.path.exists(dry_path):
        print("ERROR: All TTS engines failed.")
        sys.exit(1)

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
        bgm_track = get_bgm_track()
        print(f"  Mixing BGM: {os.path.basename(bgm_track)} (ducked at -21 dB)...")
        mixed = mix_voice_and_bgm(dry_path, bgm_track, final_path)
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
