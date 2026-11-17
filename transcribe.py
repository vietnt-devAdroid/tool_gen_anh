"""transcribe - nhận dạng giọng nói trong video (đa ngôn ngữ) để viết lại lời lồng tiếng bằng ngôn ngữ khác.

  python transcribe.py video.mp4            -> JSON {has_speech, language, segments:[{start,end,text}]}
  python transcribe.py --voices vi          -> liệt kê giọng Edge TTS của ngôn ngữ (vd vi, pt, en-US, es)
Dùng faster-whisper (mô hình 'small' đa ngôn ngữ đã có sẵn trong userdata/hf của LUO Studio). Tự chạy lại bằng Python của LUO Studio nếu bản này chưa có thư viện.
"""
import argparse, json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
FF = os.path.join(ROOT, "bin", "ffmpeg.exe")
MAIN_PY = os.environ.get("LUO_WHISPER_PY", r"D:\luo-studio-main\luo-studio-main\.venv\Scripts\python.exe")
HF_HOME = os.environ.get("HF_HOME") or r"D:\luo-studio-main\luo-studio-main\userdata\hf"
CNW = 0x08000000 if os.name == "nt" else 0


def transcribe(video):
    from faster_whisper import WhisperModel
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "a.wav")
        r = subprocess.run([FF, "-y", "-loglevel", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav], capture_output=True, creationflags=CNW)
        if r.returncode != 0 or not os.path.exists(wav):
            return {"has_speech": False, "language": None, "segments": [], "note": "video không có âm thanh"}
        for threads in (0, 2, 1):   # lỗi hết RAM thoáng qua (mkl_malloc) thì thử lại với ít luồng hơn
            try:
                model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=threads)
                segs, info = model.transcribe(wav, vad_filter=True, beam_size=5)
                segs = list(segs)
                break
            except RuntimeError:
                if threads == 1:
                    raise
        out = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(), "logprob": round(s.avg_logprob, 2)} for s in segs if s.text.strip()]
    spoken = sum(s["end"] - s["start"] for s in out)
    good = [s for s in out if s["logprob"] > -1.0]
    return {"has_speech": spoken >= 1.5 and len(good) >= 1, "language": info.language, "language_prob": round(info.language_probability, 2),
            "speech_seconds": round(spoken, 1), "segments": out}


def voices(locale):
    import asyncio, edge_tts
    vs = asyncio.run(edge_tts.list_voices())
    return [{"name": v["ShortName"], "gender": v["Gender"], "locale": v["Locale"]} for v in vs if v["Locale"].lower().startswith(locale.lower())]


def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("--voices", default=None)
    a = ap.parse_args()
    if a.voices:
        print(json.dumps(voices(a.voices), ensure_ascii=False, indent=1))
        return
    try:
        import faster_whisper  # noqa: F401
    except ImportError:   # chạy lại bằng Python của LUO Studio (đã cài whisper)
        if os.path.exists(MAIN_PY) and not os.environ.get("_TRANSCRIBE_RETRY"):
            r = subprocess.run([MAIN_PY, os.path.abspath(__file__), a.video], env=dict(os.environ, _TRANSCRIBE_RETRY="1", HF_HOME=HF_HOME, PYTHONIOENCODING="utf-8"), capture_output=True)
            sys.stdout.write(r.stdout.decode("utf-8", "replace"))
            sys.stderr.write(r.stderr.decode("utf-8", "replace")[-500:])
            sys.exit(r.returncode)
        raise SystemExit("Không có faster-whisper (cài trong LUO Studio hoặc đặt LUO_WHISPER_PY)")
    os.environ.setdefault("HF_HOME", HF_HOME)
    print(json.dumps(transcribe(a.video), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
