"""specrun - dựng biến thể cho MỘT video mẫu bất kỳ từ file spec JSON (do Claude phân tích video rồi viết ra).

  python specrun.py run  spec.json [--out D:\\ketqua\\...] [--only 1,2]
  python specrun.py dry  spec.json            (ảnh giả, không gọi Muse: kiểm tra mốc thời gian + thời lượng)

Spec (JSON):
{
  "id": "Z0200", "src": "D:/.../video.mp4", "size": [720, 1280],          # size = kích thước dựng (cùng tỉ lệ video gốc)
  "type": "timeline",                                                      # "timeline" (các cảnh ảnh nối nhau) | "grid2x2" (lưới 2x2 lộ dần)
  "clips": [ {"img": "s0"}, {"img": "src@1.6", "t": 1.25, "trans": "wipeup", "d": 0.25}, {"img": "s1", "t": 1.7, "trans": "wipeup", "d": 0.15} ],
        # img = khoá ảnh của biến thể, hoặc "src@<giây>" = lấy nguyên khung hình của video gốc; t = lúc bắt đầu chuyển vào; trans = hiệu ứng xfade (fade, wipedown, wipeup, slideleft...)
  "captions": [[0.0, 0.8, "<y>HOW</y> TO MAKE"]],                          # tuỳ chọn: phụ đề đốt lên phần đầu (<y>..</y> = chữ vàng)
  "tail": {"mode": "reuse", "from": 5.9}                                   # phần sau: reuse = giữ nguyên video gốc từ giây 'from'; none; hoặc upload (xem dưới)
  "tail": {"mode": "upload", "from": 5.9, "photo": "photo", "results": ["a","b"], "t_in": 2.8, "t_res": [4.9, 7.0],
           "voice": {"name": "en-US-JennyNeural", "rate": "+15%", "lines": [[0.3, "First, upload your photo."]]}},
  "variants": [ {"stages": [ [ {"key": "s0", "prompt": "..."}, ... ],  [ {"key": "e0", "prompt": "...", "ref": "s0"} ] ]} ]   # stage sau có thể dùng ảnh stage trước làm tham chiếu (ref)
}
  "revoice": {"name": "pt-BR-FranciscaNeural", "rate": "+8%", "lines": [[0.2, "Câu mới bằng ngôn ngữ đích"], [4.6, "..."]]}   # tuỳ chọn: thay HẲN lời đọc gốc bằng lồng tiếng mới (giữ đúng thời lượng video)
grid2x2: {"type":"grid2x2","hero_end":13.83,"panels":[{"imgs":["bob"],"label":"Blunt Bob"},{"imgs":["base","curls"],"reveal":[8.8,0.8],"label":"Loose Curls"}, ...x4]}
         (variant có thể có "labels":[4 nhãn] để đổi nhãn). Phần sau hero_end luôn giữ nguyên video gốc.
"""
import argparse, json, os, subprocess, sys, threading

import pipeline as P


def resolve(imgs, key, src, work):
    if isinstance(key, str) and key.startswith("src@"):
        out = os.path.join(work, "srcframe_" + key[4:].replace(".", "_") + ".png")
        if not os.path.exists(out):
            P.frame_at(src, float(key[4:]), out)
        return out
    return imgs[key]


def head_audio(spec, src, seconds, work):
    """Âm thanh cho đoạn đầu dài 'seconds': nếu spec có revoice thì lồng tiếng mới (thay hẳn tiếng gốc), ngược lại giữ nguyên tiếng gốc."""
    rv = spec.get("revoice")
    wav = os.path.join(work, "head_audio.wav")
    if rv:
        lines = [(t, txt) for t, txt in rv["lines"] if t < seconds]
        vw, _ = P.voice(lines, seconds, work, rv["name"], rate=rv.get("rate", "+8%"))
        return vw
    P.run([P.FF, "-y", "-loglevel", "error", "-i", src, "-t", f"{seconds}", "-vn", "-ar", "44100", "-ac", "2", wav])
    return wav


def render_timeline(spec, V, imgs, src, work, out):
    W, H = spec["size"]
    PJ = lambda n: os.path.join(work, n)
    tail = spec.get("tail") or {"mode": "none"}
    mode = tail.get("mode", "none")
    total = tail["from"] if mode != "none" else P.duration(src)
    clips = [{"img": resolve(imgs, c["img"], src, work), "t": c.get("t", 0), "trans": c.get("trans", "fade"), "d": c.get("d", 0.3)} for c in spec["clips"]]
    clips[0]["t"] = 0
    P.timeline(clips, W, H, total, PJ("hero.mp4"))
    hero = PJ("hero.mp4")
    if spec.get("captions"):
        P.ass_file(PJ("cap.ass"), [tuple(c) for c in spec["captions"]], W, H, int(H * 0.2))
        with P.FF_SEM:
            subprocess.run([P.FF, "-y", "-loglevel", "error", "-i", "hero.mp4", "-vf", "ass=cap.ass", *P.ENC, "hero_cap.mp4"], cwd=work, check=True, creationflags=0x08000000 if os.name == "nt" else 0)
        hero = PJ("hero_cap.mp4")
    audio, parts = src, [hero]
    if mode == "reuse":
        P.cut(src, tail["from"], 999, W, H, PJ("tut.mp4"))
        parts.append(PJ("tut.mp4"))
    elif mode == "upload":
        dur = P.duration(src) - tail["from"]
        v = tail.get("voice")
        timing = None
        if v:
            vwav, timing = P.voice([(a, b) for a, b in v["lines"]], dur, work, v["name"], rate=v.get("rate", "+8%"))
        P.upload_scene(imgs[tail["photo"]], dur, W, H, work, PJ("tut.mp4"), t_in=tail.get("t_in", 3.0), results=[imgs[k] for k in tail.get("results", [])],
                       t_res=tail.get("t_res", []), caps=timing, full_results=tail.get("results_full", False))
        parts.append(PJ("tut.mp4"))
        if v:
            ha = head_audio(spec, src, tail["from"], work)
            P.run([P.FF, "-y", "-loglevel", "error", "-i", ha, "-i", vwav, "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]", "-map", "[a]", "-c:a", "aac", "-b:a", "128k", PJ("audio.m4a")])
            audio = PJ("audio.m4a")
    if spec.get("revoice") and audio == src:   # lồng tiếng mới cho toàn video (không có đoạn upload có giọng riêng)
        total_dur = P.duration(src)
        vw = head_audio(spec, src, total_dur, work)
        P.run([P.FF, "-y", "-loglevel", "error", "-i", vw, "-c:a", "aac", "-b:a", "128k", PJ("audio.m4a")])
        audio = PJ("audio.m4a")
    P.concat(parts, audio, out, work)


def render_grid(spec, V, imgs, src, work, out):
    W, H = spec["size"]
    panels = spec["panels"]
    labels = V.get("labels") or [p.get("label", "") for p in panels]
    audio = None
    if spec.get("revoice"):
        total_dur = P.duration(src)
        vw = head_audio(spec, src, total_dur, work)
        audio = os.path.join(work, "audio.m4a")
        P.run([P.FF, "-y", "-loglevel", "error", "-i", vw, "-c:a", "aac", "-b:a", "128k", audio])
    P.grid_video(src, [tuple(imgs[k] for k in p["imgs"]) for p in panels], labels, [p.get("reveal") for p in panels], spec["hero_end"], work, out, W, H, audio_src=audio,
                 trans=spec.get("trans", "wipeup"), line=spec.get("line", False))


def run_variant(spec, i, args):
    V = spec["variants"][i]
    src = spec["src"]
    work = os.path.join(args.out, "_work", f"{spec['id']}_{i + 1:02d}")
    os.makedirs(work, exist_ok=True)
    out = os.path.join(args.out, f"{spec['id']}_bienthe_{i + 1:02d}.mp4")
    if os.path.exists(out):
        return out
    imgs, title = {}, f"{spec['id']} - ảnh cảnh"
    for stage in V["stages"]:
        if args.dry:
            paths = [os.path.join(work, f"dry_{it['key']}.png") for it in stage]
            for p in paths:
                dummy_image(p)
        else:
            paths = P.gen_images(title, [{"text": it["prompt"], "files": [imgs[it["ref"]]] if it.get("ref") else []} for it in stage])
        for it, p in zip(stage, paths):
            imgs[it["key"]] = p
    (render_grid if spec.get("type") == "grid2x2" else render_timeline)(spec, V, imgs, src, work, out)
    if not args.dry:
        try:
            P.publish(f"{spec['id']} - thành phẩm", f"{spec['id']} biến thể {i + 1:02d}", out)
        except Exception as e:  # noqa: BLE001
            print("chưa đưa vào LUO Chat được:", str(e)[:100], flush=True)
    return out


def dummy_image(p):
    if os.path.exists(p):
        return
    subprocess.run([P.FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x6a7bff:s=720x1280:d=1", "-frames:v", "1", p], check=True, creationflags=0x08000000 if os.name == "nt" else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "dry"])
    ap.add_argument("spec")
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", default="", help="chỉ chạy các biến thể này, ví dụ 1,3")
    a = ap.parse_args()
    a.dry = a.mode == "dry"
    spec = json.load(open(a.spec, encoding="utf-8"))
    a.out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.spec)), "out")
    os.makedirs(a.out, exist_ok=True)
    only = {int(x) for x in a.only.split(",") if x.strip()}
    errors, threads = [], []

    def worker(i):
        try:
            print("xong", run_variant(spec, i, a), flush=True)
        except Exception as e:  # noqa: BLE001
            errors.append((i + 1, str(e)))
            print("LỖI biến thể", i + 1, str(e)[:300], flush=True)
    for i in range(len(spec["variants"])):
        if only and (i + 1) not in only:
            continue
        t = threading.Thread(target=worker, args=(i,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    print(f"Hoàn tất. Lỗi: {len(errors)}")
    for e in errors:
        print(" ", e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
