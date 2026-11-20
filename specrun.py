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
        # Đoạn flow CỐ ĐỊNH 6.0s (tail.dur để đổi, tối thiểu 5.6s); video có thể dài/ngắn hơn gốc.
  "total": 20.0                                 # TỔNG độ dài mong muốn (giây). Phần đầu = total - đoạn flow cố định (6s). Video chỉ có NHẠC: tự chọn số giây; video có LỜI: đặt gần độ dài gốc.
  clips cũng nhận {"each": {"keys": ["s0","s1",...], "trans": "wipeup", "d": 0.3}}: rải đều N ảnh biến đổi (N = số khoá) lên hết phần đầu -> chọn N để mỗi ảnh ~1.2-2.5s.
  "audio": "loop"                               # mặc định: LẶP lại nhạc/âm thanh gốc cho hết video (giữ nhạc gốc) | "silent"
  "revoice": {"name": "pt-BR-FranciscaNeural", "rate": "+8%", "lines": [[0.2, "Câu mới"], [4.6, "..."]]}
        # video gốc có LỜI NÓI: lồng tiếng mới bằng ngôn ngữ đích (thời điểm tính trên cả video, gồm đoạn flow), KHÔNG phụ đề; GIỮ nhạc nền gốc (tách bằng Demucs, lặp hết video, tự hạ khi có giọng).
  item stage có "kind": "video" (+ "duration": 5-10): tạo CLIP chuyển động bằng Muse từ ảnh "ref" (khung đầu); dùng đường dẫn .mp4 đó như ảnh trong clips và làm "after" của flow
        (loại IMAGE TO VIDEO: cả video chuyển động). Clip chậm/tốn hơn ảnh nhiều: giữ số clip tối thiểu.
  item stage có "use": "<đường dẫn ảnh>": dùng thẳng ảnh có sẵn làm khoá đó (không tạo) - dùng cho ảnh nhân vật từ bộ nhân vật (xem characters.py): {"key": "before", "use": "D:/180 nhan vat Photo/V04_.../xxx.webp"}
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


def looped_audio(path, total, work, name="loop.wav", xf=0.5):
    """Lặp âm thanh/nhạc 'path' cho đủ 'total' giây, các chỗ nối chồng mờ (crossfade) để không bị giật. Trả đường dẫn wav stereo 44.1k."""
    out = os.path.join(work, name)
    base = os.path.join(work, "loop_base.wav")
    P.run([P.FF, "-y", "-loglevel", "error", "-i", path, "-vn", "-ar", "44100", "-ac", "2", base])
    L = P.duration(base)
    if L >= total or L <= xf * 3:
        P.run([P.FF, "-y", "-loglevel", "error", "-i", base, "-t", f"{total:.3f}", out])
        return out
    n = int((total - xf) // (L - xf)) + 1   # mỗi lần nối mất xf giây
    n = max(2, n if (L * n - xf * (n - 1)) >= total else n + 1)
    inputs, fc, cur = [], [], "[0:a]"
    for i in range(n):
        inputs += ["-i", base]
    for i in range(1, n):
        fc.append(f"{cur}[{i}:a]acrossfade=d={xf}:c1=tri:c2=tri[x{i}]")
        cur = f"[x{i}]"
    P.run([P.FF, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc), "-map", cur, "-t", f"{total:.3f}", "-ar", "44100", "-ac", "2", out])
    return out


def build_audio(spec, src, total, work):
    """Âm thanh cho cả video (dài đúng 'total' giây).
    - Có `revoice` (video gốc có lời nói): lồng tiếng mới, KHÔNG phụ đề. GIỮ NHẠC NỀN gốc: tách nhạc nền khỏi giọng gốc (Demucs), lặp (chồng mờ ở chỗ nối) cho hết video, tự hạ khi có giọng mới.
      Không tách được hoặc video gốc không có nhạc nền thì chỉ có giọng mới.
    - Không có `revoice` (video chỉ có nhạc): LẶP LẠI nhạc gốc (chồng mờ ở chỗ nối) cho hết video (audio="loop", mặc định); audio="silent" thì không tiếng."""
    out = os.path.join(work, "audio.m4a")
    if spec.get("audio") == "orig_head":   # GIỮ NGUYÊN âm thanh gốc ở phần đầu (đúng độ dài gốc); phần đuôi dùng nhạc nền đã tách, lặp lại
        head = float(spec.get("audio_head") or P.duration(src))
        hw = os.path.join(work, "orig_head.wav")
        P.run([P.FF, "-y", "-loglevel", "error", "-i", src, "-vn", "-t", f"{head:.3f}", "-ar", "44100", "-ac", "2", hw])
        music = music_stem(src)
        fadeo = max(0.0, total - 0.6)
        base = f"[0:a]aresample=44100,aformat=channel_layouts=stereo,apad=whole_dur={total:.3f}[o]"
        if music:
            mloop = looped_audio(music, total, work, "music_loop.wav")
            fc = (base + f";[1:a]aresample=44100,aformat=channel_layouts=stereo,atrim=start={head:.3f},asetpts=PTS-STARTPTS,adelay={int(head * 1000)}|{int(head * 1000)},"
                  f"afade=t=in:st={head:.3f}:d=0.4,volume=0.8[m];[o][m]amix=inputs=2:normalize=0:duration=longest,atrim=0:{total:.3f},afade=t=out:st={fadeo:.3f}:d=0.6[a]")
            P.run([P.FF, "-y", "-loglevel", "error", "-i", hw, "-i", mloop, "-filter_complex", fc, "-map", "[a]", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}", out])
        else:
            P.run([P.FF, "-y", "-loglevel", "error", "-i", hw, "-filter_complex", base + f";[o]atrim=0:{total:.3f},afade=t=out:st={fadeo:.3f}:d=0.6[a]", "-map", "[a]", "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.3f}", out])
        return out
    rv = spec.get("revoice")
    fade = max(0.0, total - 0.6)
    if rv and spec.get("audio") == "orig_keep":
        # GIỮ NGUYÊN nhạc/bài hát gốc: chỉ thay đoạn lời nói gốc đầu video (0..cut) bằng lời mới trên nền nhạc đã tách, từ cut trở đi dùng NGUYÊN âm thanh gốc (kể cả giọng hát/lead);
        # đuôi (flow) dùng lại đoạn cuối âm thanh gốc. Lời mới hạ nhạc nhẹ (sidechain).
        ak = spec.get("audio_keep") or {}
        cut, head = float(ak.get("cut", 3.3)), float(ak.get("head") or P.duration(src))
        tail_d = max(0.0, total - head)
        ow = os.path.join(work, "orig_full.wav")
        P.run([P.FF, "-y", "-loglevel", "error", "-i", src, "-vn", "-ar", "44100", "-ac", "2", ow])
        vw, _ = P.voice([(t, txt) for t, txt in rv["lines"] if t < total], total, work, rv["name"], rate=rv.get("rate", P.VOICE_RATE))
        music = music_stem(src)
        fcm = ("[0:a]atrim=%.3f:%.3f,asetpts=PTS-STARTPTS[B];" % (cut, head)) + (("[1:a]atrim=0:%.3f,asetpts=PTS-STARTPTS,afade=t=out:st=%.3f:d=0.2,volume=1.6[A];[A][B]acrossfade=d=0.2:c1=tri:c2=tri[H];" % (cut + 0.2, cut)) if music else "[B]acopy[H];")
        if not music:
            fcm = "[0:a]atrim=0:%.3f,asetpts=PTS-STARTPTS[H];" % head
        fcm += ("[0:a]atrim=%.3f:%.3f,asetpts=PTS-STARTPTS,volume=0.85[T];[H][T]concat=n=2:v=0:a=1[M];" % (max(0.0, head - tail_d), head)) if tail_d > 0.05 else "[H]acopy[M];"
        fcm += ("[2:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[v1][v2];[M][v1]sidechaincompress=threshold=0.02:ratio=3:attack=15:release=350[md];[md][v2]amix=inputs=2:normalize=0:duration=longest,"
                f"alimiter=limit=0.95,atrim=0:{total:.3f},afade=t=out:st={fade:.3f}:d=0.6[a]")
        ins = ["-i", ow] + (["-i", music] if music else ["-i", ow]) + ["-i", vw]
        P.run([P.FF, "-y", "-loglevel", "error", *ins, "-filter_complex", fcm, "-map", "[a]", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}", out])
        return out
    if rv:
        vw, _ = P.voice([(t, txt) for t, txt in rv["lines"] if t < total], total, work, rv["name"], rate=rv.get("rate", P.VOICE_RATE))
        music = music_stem(src) if rv.get("keep_music", True) else None
        if music:
            mloop = looped_audio(music, total, work, "music_loop.wav")
            fc = ("[0:a]aresample=44100,aformat=channel_layouts=stereo,volume=0.85[m];[1:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[v1][v2];"
                  "[m][v1]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[md];[md][v2]amix=inputs=2:normalize=0:duration=longest,"
                  f"alimiter=limit=0.95,atrim=0:{total:.3f},afade=t=out:st={fade:.3f}:d=0.6[a]")
            P.run([P.FF, "-y", "-loglevel", "error", "-i", mloop, "-i", vw, "-filter_complex", fc, "-map", "[a]", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}", out])
        else:
            P.run([P.FF, "-y", "-loglevel", "error", "-i", vw, "-c:a", "aac", "-b:a", "128k", out])
        return out
    if spec.get("audio", "loop") == "silent" or not has_audio(src):
        P.run([P.FF, "-y", "-loglevel", "error", "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=44100:cl=stereo", "-c:a", "aac", "-b:a", "64k", out])
        return out
    loop = looped_audio(src, total, work)
    P.run([P.FF, "-y", "-loglevel", "error", "-i", loop, "-af", f"afade=t=out:st={fade:.3f}:d=0.6", "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.3f}", out])
    return out


FLOW_FIXED = 6.0   # đoạn khung upload -> loading -> ảnh after CỐ ĐỊNH 6.0s: 0-0.6 mẫu upload, 0.6-1.1 ảnh before vào + loading NGAY, 1.1-2.7 loading, 2.7-6.0 ảnh after (không có khoảng chờ)


def flow_duration(tail, orig=None, head_end=None):
    """Độ dài đoạn upload: CỐ ĐỊNH FLOW_FIXED (đổi bằng tail.dur), tối thiểu đủ cho upload + loading + giữ ảnh after >= 1.5s."""
    t_in, load, gap = tail.get("t_in", 0.6), tail.get("load_dur", 1.6), tail.get("gap", 0.5)
    return max(tail.get("dur") or FLOW_FIXED, t_in + gap + load + 1.5)


def expand_clips(spec, clips, head_end, imgs, src, work):
    """Mở {"each": {...}} thành N cảnh rải đều trên head_end; cảnh thường giữ nguyên."""
    out = []
    for c in clips:
        if "each" in c:
            e = c["each"]
            keys = e["keys"]
            n = len(keys)
            for i, k in enumerate(keys):
                out.append({"img": resolve(imgs, k, src, work), "t": round(i * head_end / n, 3), "trans": e.get("trans", "fade"), "d": e.get("d", 0.3)})
        else:
            out.append({"img": resolve(imgs, c["img"], src, work), "t": c.get("t", 0), "trans": c.get("trans", "fade"), "d": c.get("d", 0.3), "edge": c.get("edge")})
    return out


def render_timeline(spec, V, imgs, src, work, out):
    W, H = spec["size"]
    PJ = lambda n: os.path.join(work, n)
    tail = spec.get("tail") or {"mode": "none"}
    mode = tail.get("mode", "none")
    orig = P.duration(src)
    head_end = tail["from"] if (mode != "none" and tail.get("from") is not None) else orig
    if mode == "flow" and spec.get("total"):   # tổng độ dài chọn trước: phần đầu = tổng - đoạn flow cố định
        head_end = max(2.0, spec["total"] - flow_duration(tail))
    clips = expand_clips(spec, spec["clips"], head_end, imgs, src, work)
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
        P.upload_flow(imgs[tail["before"]], imgs[tail["after"]], fd, W, H, work, PJ("flow.mp4"), t_in=tail.get("t_in", 0.6), load_dur=tail.get("load_dur", 1.6), gap=tail.get("gap", 0.5))
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
        P.upload_flow(imgs[tail["before"]], imgs[tail["after"]], fd, W, H, work, PJ("flow.mp4"), t_in=tail.get("t_in", 0.6), load_dur=tail.get("load_dur", 1.6), gap=tail.get("gap", 0.5))
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
        paths = [None] * len(stage)
        pre = {n: it["use"] for n, it in enumerate(stage) if it.get("use")}   # "use": đường dẫn ảnh CÓ SẴN (vd ảnh nhân vật từ bộ nhân vật) dùng thẳng, không tạo
        if args.dry:
            for n, it in enumerate(stage):
                if n in pre:
                    paths[n] = pre[n]
                elif it.get("kind") == "video":
                    paths[n] = os.path.join(work, f"dry_{it['key']}.mp4")
                    dummy_video(paths[n])
                else:
                    paths[n] = os.path.join(work, f"dry_{it['key']}.png")
                    dummy_image(paths[n])
        else:
            img_idx = [n for n, it in enumerate(stage) if it.get("kind") != "video" and n not in pre]
            for n, u in pre.items():
                paths[n] = u
            if img_idx:
                for n, pth in zip(img_idx, P.gen_images(title, [{"text": stage[n]["prompt"], "files": files(stage[n])} for n in img_idx])):
                    paths[n] = pth
            by_dur = {}   # loại image-to-video: clip chuyển động do Muse tạo từ ảnh tham chiếu (khung đầu); gom theo độ dài
            for n, it in enumerate(stage):
                if it.get("kind") == "video" and n not in pre:
                    by_dur.setdefault(int(it.get("duration", 5)), []).append(n)
            for dur, idx in by_dur.items():
                for n, pth in zip(idx, P.gen_images(f"{spec['id']} - clip chuyển động", [{"text": stage[n]["prompt"], "files": files(stage[n])} for n in idx], kind="video", duration=dur)):
                    paths[n] = pth
        for it, pth in zip(stage, paths):
            if it.get("text") and pth and not str(pth).lower().endswith((".mp4", ".webm", ".mov")):
                pth = overlay_text(pth, it["text"], os.path.join(work, f"txt_{it['key']}.png"))
            imgs[it["key"]] = pth
    (render_grid if spec.get("type") == "grid2x2" else render_timeline)(spec, V, imgs, src, work, out)
    if not args.dry:
        try:
            P.publish(f"{spec['id']} - thành phẩm", f"{spec['id']} biến thể {i + 1:02d}", out)
        except Exception as e:  # noqa: BLE001
            print("chưa đưa vào LUO Chat được:", str(e)[:100], flush=True)
    return out


def overlay_text(src, t, out):
    """item "text": một mục hoặc DANH SÁCH mục, đóng lên ảnh SAU khi ảnh được tạo (Muse viết chữ không chuẩn).
    Mục chữ: {"s": "My Love", "x": 0.5, "y": 0.8, "size": 0.09, "color": "#141414", "font": "segoesc.ttf", "rot": -4, "outline": "#000", "ow": 0, "alpha": 0.92, "blur": 0.5}
      x,y = tâm chữ (tỉ lệ khung); size = chiều cao chữ / chiều cao ảnh; rot = độ nghiêng; ow = độ dày viền (0 = không viền); "s" có \n thì nhiều dòng.
    Mục hình: {"shape": "line", "x1":..,"y1":..,"x2":..,"y2":.., "w": 0.003, "color": ..} | {"shape": "heart", "x":..,"y":..,"size": 0.03, "color": ..} | {"shape": "arrow", "x1","y1","x2","y2","w","color"}"""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import math
    im = Image.open(src).convert("RGBA")
    W, H = im.size
    items = t if isinstance(t, list) else [t]
    for it in items:
        if isinstance(it, str):
            it = {"s": it}
        lay = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        col = it.get("color", "#ffffff")
        sh = it.get("shape")
        if sh in ("line", "arrow"):
            pts = [(W + it["x1"] * W - W * 0.5 * 0, H + it["y1"] * H - H * 0.5 * 0)]
            x1, y1, x2, y2 = it["x1"] * W, it["y1"] * H, it["x2"] * W, it["y2"] * H
            lw = max(1, int(it.get("w", 0.003) * H))
            d.line([(x1 + W * 0.5, y1 + H * 0.5), (x2 + W * 0.5, y2 + H * 0.5)], fill=col, width=lw)
            if sh == "arrow":
                ang = math.atan2(y2 - y1, x2 - x1)
                for da in (2.6, -2.6):
                    d.line([(x2 + W * 0.5, y2 + H * 0.5), (x2 + W * 0.5 + 0.03 * H * math.cos(ang + da), y2 + H * 0.5 + 0.03 * H * math.sin(ang + da))], fill=col, width=lw)
        elif sh == "image":
            lg = Image.open(it["path"]).convert("RGBA")
            lw_ = int(it.get("w", 0.3) * W)
            lg = lg.resize((lw_, int(lg.height * lw_ / lg.width)), Image.LANCZOS)
            lay.alpha_composite(lg, (int(it.get("x", 0.2) * W + W * 0.5 - lg.width / 2), int(it.get("y", 0.9) * H + H * 0.5 - lg.height / 2)))
        elif sh == "heart" and it.get("fill"):   # trái tim tô màu có viền (đường cong chuẩn), x,y = tâm, size = chiều cao/ảnh, rot = nghiêng
            hh = it.get("size", 0.03) * H
            cx, cy = it["x"] * W + W * 0.5, it["y"] * H + H * 0.5
            pts = []
            for k in range(180):
                tt = 2 * math.pi * k / 180
                hx = 16 * math.sin(tt) ** 3
                hy = 13 * math.cos(tt) - 5 * math.cos(2 * tt) - 2 * math.cos(3 * tt) - math.cos(4 * tt)
                a_ = math.radians(it.get("rot", 0))
                px, py = hx * (hh / 30.0), -hy * (hh / 30.0)
                pts.append((cx + px * math.cos(a_) + py * math.sin(a_), cy - px * math.sin(a_) + py * math.cos(a_)))
            d.polygon(pts, fill=it["fill"], outline=col)
            d.line(pts + [pts[0]], fill=col, width=max(2, int(hh / 14)))
        elif sh == "heart":
            r = it.get("size", 0.03) * H
            cx, cy = it["x"] * W + W * 0.5, it["y"] * H + H * 0.5
            lw = max(2, int(r / 10))
            d.ellipse((cx - r, cy - r * 0.9, cx, cy + r * 0.1), outline=col, width=lw)
            d.ellipse((cx, cy - r * 0.9, cx + r, cy + r * 0.1), outline=col, width=lw)
            d.line([(cx - r * 0.95, cy - r * 0.15), (cx + r * 0.5, cy + r * 1.1), (cx + r * 0.95, cy - r * 0.15)], fill=col, width=lw)
        else:
            fs = max(12, int(H * it.get("size", 0.07)))
            try:
                f = ImageFont.truetype("C:/Windows/Fonts/" + it.get("font", "arialbd.ttf"), fs)
            except OSError:
                f = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", fs)
            ow = it.get("ow", max(2, fs // 14) if "ow" not in it and "outline" in it else it.get("ow", 0))
            kw = {"stroke_width": ow, "stroke_fill": it.get("outline", "#000000")} if ow else {}
            cx, cy = it.get("x", 0.5) * W, it.get("y", 0.85) * H
            d.multiline_text((cx + W * 0.5, cy + H * 0.5), it["s"], font=f, anchor="mm", fill=col, align="center", **kw) if False else d.text((cx + W * 0.5, cy + H * 0.5), it["s"], font=f, anchor="mm", fill=col, align="center", **kw)
        if it.get("rot") and not (sh == "heart" and it.get("fill")):
            c = (it.get("x", 0.5) * W + W * 0.5, it.get("y", 0.85) * H + H * 0.5) if not sh else (W, H)
            lay = lay.rotate(it["rot"], resample=Image.BICUBIC, center=c)
        if it.get("blur"):
            lay = lay.filter(ImageFilter.GaussianBlur(it["blur"]))
        if it.get("alpha", 1) < 1:
            al = lay.getchannel("A").point(lambda v: int(v * it["alpha"]))
            lay.putalpha(al)
        lc = lay.crop((int(W * 0.5), int(H * 0.5), int(W * 1.5), int(H * 1.5)))
        if it.get("blend") == "multiply":   # chữ "in" lên bề mặt: nhân với màu nền nên thấy rõ vân tường xuyên qua nét chữ
            import numpy as np
            base = np.asarray(im).astype(float)
            la = np.asarray(lc).astype(float)
            a = (la[..., 3:4] / 255.0)
            if it.get("grain"):
                rng = np.random.default_rng(7)
                a = np.clip(a * (1 - it["grain"] * rng.random(a.shape)), 0, 1)   # nét chì: chỗ đậm chỗ nhạt
            mul = base[..., :3] * (la[..., :3] / 255.0)
            blended = base[..., :3] * (1 - a) + mul * a
            im = Image.fromarray(np.dstack([blended, base[..., 3:4]]).clip(0, 255).astype("uint8"), "RGBA")
        else:
            im.alpha_composite(lc)
    im.convert("RGB").save(out)
    return out


def dummy_video(p):
    if os.path.exists(p):
        return
    subprocess.run([P.FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x3a8f6a:s=720x1280:d=6:r=24", "-c:v", "libx264", "-pix_fmt", "yuv420p", p], check=True, creationflags=CNW)


def dummy_image(p):
    if os.path.exists(p):
        return
    subprocess.run([P.FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x6a7bff:s=720x1280:d=1", "-frames:v", "1", p], check=True, creationflags=CNW)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "dry"])
    ap.add_argument("spec", nargs="+", help="một hoặc nhiều file spec.json (nhiều video)")
    ap.add_argument("--out", default=None, help="thư mục kết quả (nhiều spec: mỗi spec một thư mục con theo tên thư mục chứa spec)")
    ap.add_argument("--only", default="", help="chỉ chạy các biến thể này, ví dụ 1,3")
    ap.add_argument("--overlap", type=int, default=1, help="số video chạy CHỒNG nhau (video sau đẩy ảnh lên Muse trong lúc video trước còn dựng/chờ): mặc định 1 = lần lượt")
    a = ap.parse_args()
    a.dry = a.mode == "dry"
    only = {int(x) for x in a.only.split(",") if x.strip()}
    errors = []
    gate = threading.Semaphore(max(1, a.overlap))
    multi = len(a.spec) > 1

    def run_spec(path):
        with gate:
            spec = json.load(open(path, encoding="utf-8"))
            tag = os.path.basename(os.path.dirname(os.path.abspath(path))) or spec.get("id", "")
            out = (os.path.join(a.out, tag) if (a.out and multi) else a.out) or os.path.join(os.path.dirname(os.path.abspath(path)), "out")
            os.makedirs(out, exist_ok=True)
            va = argparse.Namespace(**{**vars(a), "out": out})
            ths = []

            def worker(i):
                try:
                    print("xong", run_variant(spec, i, va), flush=True)
                except Exception as e:  # noqa: BLE001
                    errors.append((tag, i + 1, str(e)))
                    print("LỖI", tag, "biến thể", i + 1, str(e)[:300], flush=True)
            for i in range(len(spec["variants"])):
                if only and (i + 1) not in only:
                    continue
                t = threading.Thread(target=worker, args=(i,), daemon=True)
                t.start()
                ths.append(t)
            for t in ths:
                t.join()
            print(f"[video xong] {tag}", flush=True)
    vts = [threading.Thread(target=run_spec, args=(p,), daemon=True) for p in a.spec]
    for t in vts:
        t.start()
    for t in vts:
        t.join()
    print(f"Hoàn tất. Lỗi: {len(errors)}")
    for e in errors:
        print(" ", e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
