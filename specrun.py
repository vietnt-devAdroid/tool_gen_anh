"""specrun - dựng biến thể cho MỘT video mẫu bất kỳ từ file spec JSON (do Claude phân tích video rồi viết ra).

  python specrun.py run  spec.json [--out D:\\ketqua\\...] [--only 1,2]
  python specrun.py dry  spec.json            (ảnh giả, không gọi Muse: kiểm tra mốc thời gian + thời lượng)

Spec (JSON):
{
  "id": "Z0200", "src": "D:/.../video.mp4", "size": [720, 1280],          # size = kích thước dựng (cùng tỉ lệ video gốc)
  "type": "timeline",                                                      # "timeline" (các cảnh ảnh nối nhau) | "grid2x2" (lưới 2x2 lộ dần)
  "clips": [ {"img": "s0"}, {"img": "src@1.6", "t": 1.25, "trans": "wipeup", "d": 0.25}, {"img": "s1", "t": 1.7, "trans": "wipeup", "d": 0.15} ],
        # img = khoá ảnh của biến thể, hoặc "src@<giây>" = lấy nguyên khung hình của video gốc; t = lúc bắt đầu chuyển vào; trans = hiệu ứng xfade (fade, wipedown, wipeup, slideleft...)
        # Chuyển cảnh nên <= 0.8s, cảnh nối liền nhau, KHÔNG để khoảng chết quá 1s.
  "captions": [[0.0, 0.8, "<y>HOW</y> TO MAKE"]],                          # tuỳ chọn: phụ đề đốt lên phần đầu (<y>..</y> = chữ vàng). Video có lồng tiếng mới thì KHÔNG dùng.
  "tail": {"mode": "reuse", "from": 5.9}        # giữ nguyên video gốc từ giây 'from'  |  {"mode": "none"}
  "tail": {"mode": "flow", "from": 5.9, "before": "before", "after": "after", "dur": 9.0, "t_in": 1.6, "load_dur": 1.6}
        # FLOW (khung upload của bạn): mẫu upload -> ảnh BEFORE vào khung -> LOADING -> ảnh AFTER toàn màn hình.
        # 'from' = giây bắt đầu đoạn app của người khác bị thay; bỏ 'from' = nối thêm sau phần đầu (video không có đoạn app khác).
        # Tự kéo dài nếu quá ngắn; video có thể dài hơn gốc.
  "audio": "loop"                               # mặc định: LẶP lại nhạc/âm thanh gốc cho hết video (giữ nhạc gốc) | "silent"
  "revoice": {"name": "pt-BR-FranciscaNeural", "rate": "+8%", "lines": [[0.2, "Câu mới"], [4.6, "..."]]}
        # video gốc có LỜI NÓI: lồng tiếng mới bằng ngôn ngữ đích (thời điểm tính trên cả video, gồm đoạn flow), KHÔNG phụ đề; GIỮ nhạc nền gốc (tách bằng Demucs, lặp hết video, tự hạ khi có giọng).
  "assets": {"after_sample": "D:/.../after.png"}   # ảnh có sẵn dùng làm tham chiếu: item "ref": ["before", "after_sample"]
  "variants": [ {"stages": [ [ {"key": "before", "prompt": "..."} ],
                             [ {"key": "after", "prompt": "...", "ref": ["before", "after_sample"]} ] ]} ]   # stage sau dùng ảnh stage trước (và assets) làm tham chiếu
}
grid2x2: {"type":"grid2x2","hero_end":13.83,"trans":"wipeup","line":false,"panels":[{"imgs":["bob"],"label":"Blunt Bob"},{"imgs":["base","curls"],"reveal":[8.8,0.8],"label":"Loose Curls"}, ...x4]}
         (variant có thể có "labels":[4 nhãn] để đổi nhãn). Sau hero_end: tail reuse (mặc định, giữ end card gốc) hoặc tail flow (thay end card bằng khung upload).
"""
import argparse, json, os, subprocess, sys, threading

import pipeline as P

CNW = 0x08000000 if os.name == "nt" else 0


def resolve(imgs, key, src, work):
    if isinstance(key, str) and key.startswith("src@"):
        out = os.path.join(work, "srcframe_" + key[4:].replace(".", "_") + ".png")
        if not os.path.exists(out):
            P.frame_at(src, float(key[4:]), out)
        return out
    return imgs[key]


def has_audio(path):
    r = subprocess.run([P.FF, "-hide_banner", "-i", path], capture_output=True, creationflags=CNW)
    return "Audio:" in r.stderr.decode("utf-8", "replace")


_STEM_LOCK = threading.Lock()


def music_stem(src):
    """Nhạc nền đã tách khỏi giọng nói của video mẫu (cache cạnh video). None nếu không có nhạc nền hoặc tách không được."""
    with _STEM_LOCK:   # nhiều biến thể chạy song song: chỉ tách một lần
        try:
            import separate
            r = separate.separate(src)
        except Exception as e:  # noqa: BLE001
            print("không tách được nhạc nền:", str(e)[:200], flush=True)
            return None
    return r["accompaniment"] if r.get("has_music") else None


def build_audio(spec, src, total, work):
    """Âm thanh cho cả video (dài đúng 'total' giây).
    - Có `revoice` (video gốc có lời nói): lồng tiếng mới, KHÔNG phụ đề. GIỮ NHẠC NỀN gốc: tách nhạc nền khỏi giọng gốc (Demucs), lặp cho hết video, tự hạ nhỏ khi có giọng mới.
      Không tách được hoặc video gốc không có nhạc nền thì chỉ có giọng mới.
    - Không có `revoice`: LẶP LẠI âm thanh/nhạc gốc cho hết video (mặc định, audio="loop"); audio="silent" thì không tiếng."""
    out = os.path.join(work, "audio.m4a")
    rv = spec.get("revoice")
    fade = max(0.0, total - 0.6)
    if rv:
        vw, _ = P.voice([(t, txt) for t, txt in rv["lines"] if t < total], total, work, rv["name"], rate=rv.get("rate", "+8%"))
        music = music_stem(src) if rv.get("keep_music", True) else None
        if music:
            fc = ("[0:a]aresample=44100,aformat=channel_layouts=stereo,volume=0.85[m];[1:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[v1][v2];"
                  "[m][v1]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[md];[md][v2]amix=inputs=2:normalize=0:duration=longest,"
                  f"alimiter=limit=0.95,atrim=0:{total:.3f},afade=t=out:st={fade:.3f}:d=0.6[a]")
            P.run([P.FF, "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", music, "-i", vw, "-filter_complex", fc, "-map", "[a]", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}", out])
        else:
            P.run([P.FF, "-y", "-loglevel", "error", "-i", vw, "-c:a", "aac", "-b:a", "128k", out])
        return out
    if spec.get("audio", "loop") == "silent" or not has_audio(src):
        P.run([P.FF, "-y", "-loglevel", "error", "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=44100:cl=stereo", "-c:a", "aac", "-b:a", "64k", out])
        return out
    P.run([P.FF, "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", src, "-vn", "-t", f"{total:.3f}", "-ar", "44100", "-ac", "2", "-af", f"afade=t=out:st={fade:.3f}:d=0.6",
           "-c:a", "aac", "-b:a", "128k", out])
    return out


def flow_duration(tail, orig, head_end):
    """Độ dài đoạn upload: bằng đoạn gốc bị thay (nếu có), tối thiểu đủ cho upload + loading + giữ ảnh after >= 1.5s."""
    t_in, load = tail.get("t_in", 1.6), tail.get("load_dur", 1.6)
    need = t_in + 0.9 + load + 1.5
    dur = tail.get("dur") or ((orig - head_end) if tail.get("from") is not None else 8.0)
    return max(dur, need)


def render_timeline(spec, V, imgs, src, work, out):
    W, H = spec["size"]
    PJ = lambda n: os.path.join(work, n)
    tail = spec.get("tail") or {"mode": "none"}
    mode = tail.get("mode", "none")
    orig = P.duration(src)
    head_end = tail["from"] if (mode != "none" and tail.get("from") is not None) else orig
    clips = [{"img": resolve(imgs, c["img"], src, work), "t": c.get("t", 0), "trans": c.get("trans", "fade"), "d": c.get("d", 0.3)} for c in spec["clips"]]
    clips[0]["t"] = 0
    P.timeline(clips, W, H, head_end, PJ("hero.mp4"))
    hero = PJ("hero.mp4")
    if spec.get("captions"):
        P.ass_file(PJ("cap.ass"), [tuple(c) for c in spec["captions"]], W, H, int(H * 0.2))
        with P.FF_SEM:
            subprocess.run([P.FF, "-y", "-loglevel", "error", "-i", "hero.mp4", "-vf", "ass=cap.ass", *P.ENC, "hero_cap.mp4"], cwd=work, check=True, creationflags=CNW)
        hero = PJ("hero_cap.mp4")
    parts, total = [hero], head_end
    if mode == "reuse":
        P.cut(src, tail["from"], 999, W, H, PJ("tut.mp4"))
        parts.append(PJ("tut.mp4"))
        total = orig
    elif mode == "flow":   # thay đoạn app của người khác (hoặc nối thêm ở cuối): khung upload -> ảnh before -> loading -> ảnh after
        fd = flow_duration(tail, orig, head_end)
        P.upload_flow(imgs[tail["before"]], imgs[tail["after"]], fd, W, H, work, PJ("flow.mp4"), t_in=tail.get("t_in", 1.6), load_dur=tail.get("load_dur", 1.6))
        parts.append(PJ("flow.mp4"))
        total = head_end + fd
    P.concat(parts, build_audio(spec, src, total, work), out, work)


def render_grid(spec, V, imgs, src, work, out):
    W, H = spec["size"]
    PJ = lambda n: os.path.join(work, n)
    panels = spec["panels"]
    labels = V.get("labels") or [p.get("label", "") for p in panels]
    tail = spec.get("tail") or {"mode": "reuse"}
    kw = dict(trans=spec.get("trans", "wipeup"), line=spec.get("line", False))
    pimgs = [tuple(imgs[k] for k in p["imgs"]) for p in panels]
    reveals = [p.get("reveal") for p in panels]
    if tail.get("mode") == "flow":   # bỏ end card app khác, thay bằng khung upload
        hero = P.grid_video(src, pimgs, labels, reveals, spec["hero_end"], work, out, W, H, build_end=False, **kw)
        fd = flow_duration(tail, P.duration(src), spec["hero_end"])
        P.upload_flow(imgs[tail["before"]], imgs[tail["after"]], fd, W, H, work, PJ("flow.mp4"), t_in=tail.get("t_in", 1.6), load_dur=tail.get("load_dur", 1.6))
        P.concat([hero, PJ("flow.mp4")], build_audio(spec, src, spec["hero_end"] + fd, work), out, work)
        return
    audio = build_audio(spec, src, P.duration(src), work) if spec.get("revoice") else None
    P.grid_video(src, pimgs, labels, reveals, spec["hero_end"], work, out, W, H, audio_src=audio, **kw)


def run_variant(spec, i, args):
    V = spec["variants"][i]
    src = spec["src"]
    work = os.path.join(args.out, "_work", f"{spec['id']}_{i + 1:02d}")
    os.makedirs(work, exist_ok=True)
    out = os.path.join(args.out, f"{spec['id']}_bienthe_{i + 1:02d}.mp4")
    if os.path.exists(out):
        return out
    imgs, title, assets = {}, f"{spec['id']} - ảnh cảnh", spec.get("assets", {})
    pool = lambda k: imgs[k] if k in imgs else assets[k]

    def files(it):
        r = it.get("ref")
        return [] if not r else [pool(x) for x in (r if isinstance(r, list) else [r])]
    for stage in V["stages"]:
        if args.dry:
            paths = [os.path.join(work, f"dry_{it['key']}.png") for it in stage]
            for p in paths:
                dummy_image(p)
        else:
            paths = P.gen_images(title, [{"text": it["prompt"], "files": files(it)} for it in stage])
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
    subprocess.run([P.FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x6a7bff:s=720x1280:d=1", "-frames:v", "1", p], check=True, creationflags=CNW)


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
