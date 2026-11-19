"""v2v - loại IMAGE TO VIDEO: nhận MỘT THƯ MỤC video, gen lại từng video "y như video gốc" bằng Muse, chạy hàng loạt đa luồng, mỗi video một cuộc trò chuyện trong LUO Chat.

  python v2v.py <thư_mục_video> [--out thư_mục_kết_quả] [--jobs 10] [--seg 10] [--only chuỗi_tên] [--limit N] [--dry]
Mỗi video:
  1. cắt theo TỪNG CẢNH (mọi mốc đổi cảnh), cảnh dài hơn --seg giây thì chia đều, vì Muse chỉ tạo clip tối đa ~10s;
  2. với mỗi đoạn gửi Muse (kind video): khung hình đầu của đoạn + CHÍNH đoạn video gốc làm tham chiếu (chuyển động, máy quay, bố cục, nhịp, phong cách) + lệnh "dựng lại y như gốc";
  3. ghép các clip Muse lại đúng độ dài từng đoạn, giữ âm thanh gốc (--audio muse để giữ âm thanh Muse);
  4. đưa clip + thành phẩm vào CUỘC TRÒ CHUYỆN RIÊNG của video đó (tiêu đề = tên file).
Có thể đặt <tên video>.txt (mô tả chung) hoặc <tên video>.json {"segments": ["mô tả cảnh 1", ...]} (mô tả từng cảnh) cạnh video: Claude xem video rồi viết, sẽ gắn thêm vào lệnh để Muse bám sát hơn.
Quy tắc nội dung vẫn áp dụng (xem QUY-TAC-XU-LY-VIDEO.md): không sao chép gương mặt người thật, ăn mặc đầy đủ... LUO Chat tự chặn/bổ sung câu quy tắc.
--dry: không gọi Muse, dùng chính đoạn gốc làm "clip Muse" để thử cắt/ghép/độ dài.
"""
import argparse, math, os, shutil, subprocess, sys, threading, time

import analyze
import pipeline as P

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")
MUSE_DURATIONS = (5, 6, 8, 10)
BASE_PROMPT = ("Recreate the attached reference video as closely as possible: the same scene and set, the same subjects and their actions, the same camera framing and camera movement, "
               "the same pacing and timing, the same lighting, colours and visual style. The attached image is the exact first frame. Keep it natural and photorealistic. "
               "If the reference shows a real identifiable person, do not copy their face: use a different fictional adult with a similar look and the same actions.")


def segments(video, dur, max_seg=10.0, min_seg=1.5):
    """Chia video theo TỪNG CẢNH (cắt tại mọi mốc đổi cảnh cách nhau >= min_seg); cảnh dài hơn max_seg được chia đều. Mỗi đoạn gửi Muse riêng nên giữ đúng từng cảnh của video gốc."""
    try:
        cuts = sorted(c for c in analyze.scenes(video, 0.3) if 1.0 < c < dur - 1.0)
    except Exception:  # noqa: BLE001
        cuts = []
    bounds = [0.0]
    for c in cuts:
        if c - bounds[-1] >= min_seg:
            bounds.append(c)
    if len(bounds) > 1 and dur - bounds[-1] < min_seg:
        bounds.pop()
    bounds.append(dur)
    out = []
    for s, e in zip(bounds, bounds[1:]):
        n = max(1, math.ceil((e - s) / max_seg - 1e-6))
        step = (e - s) / n
        out += [(round(s + i * step, 3), round(s + (i + 1) * step if i < n - 1 else e, 3)) for i in range(n)]
    return out


def muse_duration(seconds):
    return next((d for d in MUSE_DURATIONS if d >= seconds - 0.05), MUSE_DURATIONS[-1])


def aspect_of(video):
    r = subprocess.run([P.FF, "-hide_banner", "-i", video], capture_output=True, creationflags=0x08000000 if os.name == "nt" else 0).stderr.decode("utf-8", "replace")
    import re
    m = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", r)
    w, h = (int(m[1]), int(m[2])) if m else (720, 1280)
    return ("9:16" if h > w * 1.2 else "16:9" if w > h * 1.2 else "1:1"), w, h


def process(video, out_dir, a):
    name = os.path.splitext(os.path.basename(video))[0]
    safe = P.re.sub(r"[^\w.\-]+", "_", name) if hasattr(P, "re") else "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    work = os.path.join(out_dir, "_work", safe)
    os.makedirs(work, exist_ok=True)
    final = os.path.join(out_dir, f"{safe}_v2v.mp4")
    if os.path.exists(final):
        return final
    dur = P.duration(video)
    asp, W, H = aspect_of(video)
    segs = segments(video, dur, a.seg, a.min_seg)
    desc, per_seg = "", []
    side = os.path.splitext(video)[0] + ".txt"
    if os.path.exists(side):
        desc = " Detailed description of the reference video: " + open(side, encoding="utf-8").read().strip()
    sidej = os.path.splitext(video)[0] + ".json"   # {"segments": ["mô tả cảnh 1", "mô tả cảnh 2", ...]} (Claude viết, mỗi cảnh một mô tả, đúng thứ tự cảnh)
    if os.path.exists(sidej):
        import json
        per_seg = json.load(open(sidej, encoding="utf-8")).get("segments", [])
    items, clips_src = [], []
    for k, (s, e) in enumerate(segs):
        clip, frame = os.path.join(work, f"seg_{k:02d}.mp4"), os.path.join(work, f"seg_{k:02d}.png")
        P.run([P.FF, "-y", "-loglevel", "error", "-ss", f"{s}", "-to", f"{e}", "-i", video, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", clip])
        P.run([P.FF, "-y", "-loglevel", "error", "-ss", f"{s + 0.05}", "-i", video, "-frames:v", "1", frame])
        items.append({"text": BASE_PROMPT + desc + (" Description of this scene: " + per_seg[k] if k < len(per_seg) else ""), "files": [frame, clip], "dur": muse_duration(e - s)})
        clips_src.append((s, e, clip))
    title = name   # MỖI VIDEO MỘT CUỘC TRÒ CHUYỆN: tiêu đề = tên file
    if a.dry:
        gen = [c for *_, c in clips_src]
    else:
        gen = [None] * len(items)
        by_dur = {}
        for n, it in enumerate(items):
            by_dur.setdefault(it["dur"], []).append(n)
        for d, idx in by_dur.items():
            res = P.gen_images(title, [{"text": items[n]["text"], "files": items[n]["files"]} for n in idx], kind="video", duration=d)
            for n, pth in zip(idx, res):
                gen[n] = pth
    parts = []
    for k, ((s, e, _), g) in enumerate(zip(clips_src, gen)):
        part = os.path.join(work, f"part_{k:02d}.mp4")
        P.run([P.FF, "-y", "-loglevel", "error", "-i", g, "-t", f"{e - s:.3f}", "-vf", P.fit(W, H), *P.ENC, part])
        parts.append(part)
    if a.audio == "original":
        P.concat(parts, video, final, work)
    else:
        lst = os.path.join(work, "list.txt")
        open(lst, "w", encoding="utf-8").write("".join("file '" + p.replace("\\", "/") + "'\n" for p in parts))
        P.run([P.FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", final])
    if not a.dry:
        try:
            P.call("/api/attach", {"chat": P.chat_id(title), "file": final, "text": f"{name} (gen lại y như gốc)", "kind": "video", "by": "claude"})
        except Exception as e:  # noqa: BLE001
            print("chưa đưa vào LUO Chat được:", str(e)[:100], flush=True)
    return final


def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--out", default=None)
    ap.add_argument("--jobs", type=int, default=10, help="số video xử lý cùng lúc (Muse tự giới hạn ~6 việc song song)")
    ap.add_argument("--seg", type=float, default=10.0, help="độ dài tối đa mỗi đoạn gửi Muse (giây)")
    ap.add_argument("--min-seg", type=float, default=1.5, help="độ dài tối thiểu một cảnh khi cắt theo mốc đổi cảnh")
    ap.add_argument("--audio", choices=["original", "muse"], default="original")
    ap.add_argument("--only", default="", help="chỉ chạy video có tên chứa chuỗi này (chạy thử 1 video trước)")
    ap.add_argument("--limit", type=int, default=0, help="chỉ chạy N video đầu tiên")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    vids = sorted(os.path.join(a.folder, f) for f in os.listdir(a.folder) if f.lower().endswith(VIDEO_EXT))
    if a.only:
        vids = [v for v in vids if a.only.lower() in os.path.basename(v).lower()]
    if a.limit:
        vids = vids[:a.limit]
    if not vids:
        sys.exit("Không có video phù hợp trong thư mục.")
    out_dir = a.out or os.path.join(a.folder, "v2v_out")
    os.makedirs(out_dir, exist_ok=True)
    sem, errors, done = threading.Semaphore(a.jobs), [], []

    def worker(v):
        with sem:
            try:
                r = process(v, out_dir, a)
                done.append(r)
                print("xong", r, flush=True)
            except Exception as e:  # noqa: BLE001
                errors.append((os.path.basename(v), str(e)))
                print("LỖI", os.path.basename(v), str(e)[:300], flush=True)
    ts = [threading.Thread(target=worker, args=(v,), daemon=True) for v in vids]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(f"Hoàn tất: {len(done)}/{len(vids)} video. Lỗi: {len(errors)}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
