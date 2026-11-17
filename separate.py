"""separate - tách NHẠC NỀN khỏi giọng nói trong video mẫu (Demucs), để lồng tiếng mới mà vẫn giữ nhạc nền gốc.

  python separate.py video.mp4 [--out thư_mục_stems]
Kết quả (cache cạnh video, chạy lại không tách lại): <thư mục video>\\stems\\no_vocals.wav (nhạc nền) và vocals.wav (giọng nói).
In JSON: {"accompaniment": đường dẫn, "vocals": đường dẫn, "music_db": mức âm lượng nhạc nền, "has_music": true/false}.
Cần: torch + demucs + soundfile (đã cài trong .venv của LUO Chat). Lần đầu tải mô hình htdemucs (~80 MB).
"""
import argparse, json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
FF = os.path.join(ROOT, "bin", "ffmpeg.exe")
CNW = 0x08000000 if os.name == "nt" else 0


def rms_db(path):
    r = subprocess.run([FF, "-hide_banner", "-i", path, "-af", "astats=metadata=0", "-f", "null", "-"], capture_output=True, creationflags=CNW).stderr.decode("utf-8", "replace")
    m = re.findall(r"RMS level dB:\s*(-?[\d.]+|-inf)", r)
    try:
        return float(m[-1])
    except (IndexError, ValueError):
        return -99.0


def stems_dir(video):
    """Thư mục lưu nhạc nền đã tách, riêng cho từng video: <thư mục video>\stems_<tên video>."""
    v = os.path.abspath(video)
    return os.path.join(os.path.dirname(v), "stems_" + os.path.splitext(os.path.basename(v))[0].replace(" ", "_"))


def separate(video, out_dir=None):
    out_dir = out_dir or stems_dir(video)
    os.makedirs(out_dir, exist_ok=True)
    acc, voc = os.path.join(out_dir, "no_vocals.wav"), os.path.join(out_dir, "vocals.wav")
    if not (os.path.exists(acc) and os.path.exists(voc)):
        import numpy as np, soundfile as sf, torch
        from demucs.apply import apply_model
        from demucs.pretrained import get_model
        with tempfile.TemporaryDirectory() as td:
            wav = os.path.join(td, "a.wav")
            r = subprocess.run([FF, "-y", "-loglevel", "error", "-i", video, "-vn", "-ac", "2", "-ar", "44100", wav], capture_output=True, creationflags=CNW)
            if r.returncode != 0 or not os.path.exists(wav):
                return {"accompaniment": None, "vocals": None, "music_db": -99.0, "has_music": False, "note": "video không có âm thanh"}
            data, sr = sf.read(wav, dtype="float32", always_2d=True)
        model = get_model("htdemucs")
        model.eval()
        x = torch.from_numpy(np.ascontiguousarray(data.T))                 # (kênh, mẫu)
        ref = x.mean(0)
        x = (x - ref.mean()) / (ref.std() + 1e-8)
        with torch.no_grad():
            est = apply_model(model, x[None], device="cpu", split=True, overlap=0.25, progress=False)[0]   # (nguồn, kênh, mẫu)
        est = est * (ref.std() + 1e-8) + ref.mean()
        names = list(model.sources)
        vi = names.index("vocals")
        vocals = est[vi]
        accomp = sum(est[i] for i in range(len(names)) if i != vi)
        sf.write(voc, vocals.numpy().T, sr)
        sf.write(acc, accomp.numpy().T, sr)
    db = rms_db(acc)
    return {"accompaniment": acc.replace("\\", "/"), "vocals": voc.replace("\\", "/"), "music_db": db, "has_music": db > -42.0}


def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    print(json.dumps(separate(a.video, a.out), ensure_ascii=False))


if __name__ == "__main__":
    main()
