"""
GTA 6 Voiceover Generator - Fast energetic speed
gTTS: uses ffmpeg to speed up audio to 1.25x after generation
pyttsx3: rate set to 210 (fast, energetic)
"""
import json, os, re, subprocess, shutil, sys, tempfile


def clean_script_for_tts(script: str) -> str:
    """Clean script for clean TTS output."""
    script = re.sub(r'[^\x00-\x7F]+', '', script)   # Remove emojis/unicode
    script = re.sub(r'#\w+', '', script)              # Remove hashtags
    script = re.sub(r'\.{2,}', '. ', script)          # Fix ellipsis
    script = script.replace('—', ', ').replace('–', ', ')
    script = re.sub(r'\s+', ' ', script).strip()
    return script


def speed_up_audio(input_path: str, output_path: str, speed: float = 1.25) -> bool:
    """Use ffmpeg to speed up audio — makes TTS sound energetic, not robotic."""
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except: pass

    if not ffmpeg:
        return False

    try:
        result = subprocess.run([
            ffmpeg, "-y", "-i", input_path,
            "-filter:a", f"atempo={speed}",
            "-vn", output_path
        ], capture_output=True, timeout=30)
        return result.returncode == 0
    except Exception as e:
        print(f"  Speed-up failed: {e}")
        return False


def generate_voice_gtts(script: str, output_path: str) -> bool:
    """Google TTS at fast speed via ffmpeg post-processing."""
    try:
        from gtts import gTTS
        from pydub import AudioSegment

        clean = clean_script_for_tts(script)
        tts   = gTTS(text=clean, lang='en', slow=False)

        # Save raw TTS first
        raw_path = output_path.replace('.mp3', '_raw.mp3')
        tts.save(raw_path)

        # Speed it up to 1.25x using ffmpeg (sounds much more energetic)
        sped_up = speed_up_audio(raw_path, output_path, speed=1.10)  # 1.1x: energetic but not rushed

        if os.path.exists(raw_path):
            os.remove(raw_path)

        if not sped_up and os.path.exists(raw_path.replace('_raw','')):
            # Fallback: just rename raw
            if os.path.exists(raw_path):
                os.rename(raw_path, output_path)
            sped_up = True

        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"  gTTS voice ready: {output_path} ({size//1024}KB, 1.1x speed)")
            return True

    except ImportError as e:
        print(f"  gTTS not available: {e}")
    except Exception as e:
        print(f"  gTTS error: {e}")
    return False


def generate_voice_pyttsx3(script: str, output_path: str) -> bool:
    """Offline TTS at high speed rate."""
    try:
        import pyttsx3

        clean = clean_script_for_tts(script)
        engine = pyttsx3.init()

        # 210 wpm = fast, energetic, keeps viewer engaged
        engine.setProperty('rate', 190)  # 190 wpm: fast and clear, not breathless
        engine.setProperty('volume', 1.0)

        # Prefer male voice
        voices = engine.getProperty('voices')
        for voice in voices:
            name = voice.name.lower()
            if any(n in name for n in ['david','mark','male','guy','james','daniel']):
                engine.setProperty('voice', voice.id)
                break

        wav_path = output_path.replace('.mp3', '.wav')
        engine.save_to_file(clean, wav_path)
        engine.runAndWait()

        if not os.path.exists(wav_path):
            return False

        # Try to convert wav → mp3 and speed up
        sped_path = output_path.replace('.mp3', '_fast.wav')
        sped = speed_up_audio(wav_path, sped_path, speed=1.10)  # 1.1x: energetic

        if sped and os.path.exists(sped_path):
            os.replace(sped_path, wav_path)

        # Convert to mp3 if possible
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_wav(wav_path)
            audio.export(output_path, format="mp3")
            os.remove(wav_path)
            print(f"  pyttsx3 voice ready: {output_path} (210 wpm)")
        except:
            # Keep wav
            final = output_path.replace('.mp3', '.wav')
            os.rename(wav_path, final)
            print(f"  pyttsx3 voice ready: {final} (210 wpm)")

        return True

    except ImportError as e:
        print(f"  pyttsx3 not available: {e}")
    except Exception as e:
        print(f"  pyttsx3 error: {e}")
    return False


def generate_voiceover(script_data: dict) -> str:
    """Generate voiceover — fast, energetic speed."""
    print("Generating voiceover (fast speed)...")

    script = script_data["script"]
    output_path = "assets/voiceover.mp3"
    os.makedirs("assets", exist_ok=True)

    word_count = len(script.split())
    print(f"  Script: {word_count} words")

    # Try gTTS first (better quality + speed control via ffmpeg)
    if generate_voice_gtts(script, output_path):
        return output_path

    # Fallback: pyttsx3 offline
    wav_path = output_path.replace('.mp3', '.wav')
    if generate_voice_pyttsx3(script, output_path):
        return output_path if os.path.exists(output_path) else wav_path

    print("  ERROR: No TTS engine worked. Install: pip install gtts pydub")
    sys.exit(1)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open("assets/current_script.json") as f:
        script_data = json.load(f)
    path = generate_voiceover(script_data)
    print(f"Voiceover saved: {path}")
