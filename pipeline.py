"""pipeline - tạo biến thể từ video mẫu: GIỮ NGUYÊN cấu trúc cảnh + thời lượng, chỉ thay nhân vật / dáng.

Quy trình mỗi biến thể:  (1) tạo ẢNH từng cảnh bằng Muse (qua LUO Chat)  (2) dựng lại bằng ffmpeg đúng mốc thời gian của video gốc
(3) đưa video thành phẩm vào LUO Chat để xem.  Các đoạn quay màn hình hướng dẫn / end card của video gốc được dùng lại nguyên bản.

  python pipeline.py run Z0073 Z0077 Z0083 Z0084 Z0104 [--variants 10] [--src D:\\test_tool] [--out D:\\test_tool\\out]
  python pipeline.py dry Z0083          (dựng thử bằng ảnh giả, không gọi Muse: kiểm tra mốc thời gian)
"""
import argparse, json, os, shutil, subprocess, sys, threading, time, urllib.request, urllib.error

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = os.path.dirname(os.path.abspath(__file__))
FF = os.path.join(ROOT, "bin", "ffmpeg.exe")
FONT = "C\\:/Windows/Fonts/arialbd.ttf"
CHAT_DATA = os.path.join(ROOT, "userdata", "chat")
MEDIA = os.path.join(CHAT_DATA, "media")
FILES = {"Z0073": "Z0073 (1).mp4", "Z0077": "Z0077 (1).mp4", "Z0083": "Z0083.mp4", "Z0084": "Z0084.mp4", "Z0104": "Z0104.mp4"}
LOCK = threading.Lock()
CHATS = {}


# ------------------------------------------------------------------ LUO Chat API
def base():
    return os.environ.get("LUO_CHAT_URL") or json.load(open(os.path.join(CHAT_DATA, "running.json"), encoding="utf-8"))["url"].rstrip("/")


def call(path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base() + path, data=data, method=method or ("POST" if body is not None else "GET"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode("utf-8", "replace"))


def chat_id(title):
    with LOCK:
        if title not in CHATS:
            old = [c["id"] for c in call("/api/chats")["chats"] if c["title"] == title]
            CHATS[title] = old[0] if old else call("/api/chats", {"title": title})["id"]
        return CHATS[title]


def existing(title, text, ref=None):
    """Ảnh đã tạo xong trước đó với đúng prompt (và đúng ảnh tham chiếu) trong chat 'title' -> đường dẫn, hoặc None. Đọc thẳng chats.json."""
    try:
        ch = json.load(open(os.path.join(CHAT_DATA, "chats.json"), encoding="utf-8"))
    except Exception:
        return None
    for c in ch.values():
        if c["title"] != title:
            continue
        for m in c["messages"]:
            if m["status"] == "done" and m.get("media") and m["text"] == text.strip():
                if ref is None or any(f["name"] == os.path.basename(ref) for f in m.get("files", [])):
                    return os.path.join(MEDIA, m["media"][0]["file"])
    return None


def gen_images(title, items, tries=3, kind="image", duration=None):
    found = [existing(title, it["text"], (it.get("files") or [None])[0]) for it in items]
    if all(found):
        return found
    if not any(found):
        return _gen_images(title, items, tries, kind, duration)
    missing = [it for it, f in zip(items, found) if not f]
    new = iter(_gen_images(title, missing, tries, kind, duration))
    return [f or next(new) for f in found]


def _gen_images(title, items, tries=3, kind="image", duration=None):
    """items = [{text, files?}] -> [đường dẫn ảnh] theo đúng thứ tự (chờ xong; tự xếp hàng lại ảnh lỗi)."""
    cid = chat_id(title)
    r = call("/api/batch", {"chat": cid, "by": "claude", "defaults": {"kind": kind, "aspect": "9:16", "duration": duration},
                            "items": [{"text": it["text"], "files": it.get("files") or []} for it in items]})
    ids, fail = r["ids"], {}
    for attempt in range(tries):
        while True:
            time.sleep(5)
            msgs = {m["id"]: m for m in call("/api/chats/" + cid)["messages"]}
            st = [msgs[i]["status"] for i in ids]
            if all(s in ("done", "error", "stopped") for s in st):
                break
        bad = [i for i in ids if msgs[i]["status"] != "done"]
        if not bad:
            return [os.path.join(MEDIA, msgs[i]["media"][0]["file"]) for i in ids]
        if attempt == tries - 1:
            raise RuntimeError("ảnh lỗi: " + "; ".join(msgs[i]["error"][:120] for i in bad))
        for i in bad:
            call(f"/api/messages/{i}/retry", {})
    raise RuntimeError("không tạo được ảnh")


def publish(title, text, file):
    call("/api/attach", {"chat": chat_id(title), "file": file, "text": text, "kind": "video", "by": "claude"})


# ------------------------------------------------------------------ ffmpeg
FF_SEM = threading.Semaphore(3)   # dựng song song nhiều quá sẽ hết RAM (webp lớn): tối đa 3 ffmpeg cùng lúc


def run(cmd):
    with FF_SEM:
        r = subprocess.run(cmd, capture_output=True, creationflags=0x08000000 if os.name == "nt" else 0)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr.decode("utf-8", "replace")[-600:])


ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "30", "-an"]


def fit(w, h):
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30,format=yuv420p"


def still(img, w, h, dur, out):
    run([FF, "-y", "-loglevel", "error", "-loop", "1", "-t", f"{dur:.3f}", "-i", img, "-vf", fit(w, h), *ENC, out])


def reveal(a, b, w, h, total, t0, d, out, trans="wipedown", line=False):
    """Ảnh a hiển thị, tới t0 thì 'quét' d giây sang ảnh b, giữ tới hết total. line=True: thêm vạch trắng chạy theo mép quét (như video gốc)."""
    fx = f"[a][b]xfade=transition={trans}:duration={d}:offset={t0}"
    if line:
        y = f"ih-ih*(t-{t0})/{d}" if "up" in trans else f"ih*(t-{t0})/{d}"
        fx += f"[x];[x]drawbox=x=0:y='{y}':w=iw:h=3:color=white:t=fill:enable='between(t,{t0},{t0 + d})'"
    run([FF, "-y", "-loglevel", "error", "-loop", "1", "-t", f"{t0 + d:.3f}", "-i", a, "-loop", "1", "-t", f"{total - t0:.3f}", "-i", b, "-filter_complex",
         f"[0:v]{fit(w, h)}[a];[1:v]{fit(w, h)}[b];{fx},format=yuv420p[v]", "-map", "[v]", *ENC, out])


def crossfade(a, b, w, h, ta, tb, d, out):
    """a hiển thị ta giây (gồm d giây chồng), b hiển thị tb giây. Tổng = ta + tb - d."""
    run([FF, "-y", "-loglevel", "error", "-loop", "1", "-t", f"{ta:.3f}", "-i", a, "-loop", "1", "-t", f"{tb:.3f}", "-i", b, "-filter_complex",
         f"[0:v]{fit(w, h)}[a];[1:v]{fit(w, h)}[b];[a][b]xfade=transition=fade:duration={d}:offset={ta - d:.3f},format=yuv420p[v]", "-map", "[v]", *ENC, out])


def timeline(clips, w, h, total, out):
    """clips = [{img, t, trans, d}]: cảnh k bắt đầu 'quét' vào tại t (giây), hiệu ứng trans kéo dài d giây; cảnh đầu t=0. Tổng thời lượng = total."""
    inputs, fc = [], []
    for k, c in enumerate(clips):
        e = (clips[k + 1]["t"] + clips[k + 1]["d"]) if k + 1 < len(clips) else total
        if str(c["img"]).lower().endswith((".mp4", ".webm", ".mov")):   # cảnh là video ngắn (vd. bàn tay đang vẽ): dùng từ khung đầu, cắt đúng độ dài cảnh
            inputs += ["-t", f"{e - c['t']:.3f}", "-i", c["img"]]
        else:
            inputs += ["-loop", "1", "-t", f"{e - c['t']:.3f}", "-i", c["img"]]
        fc.append(f"[{k}:v]{fit(w, h)}[v{k}]")
    cur = "v0"
    for k in range(1, len(clips)):
        fc.append(f"[{cur}][v{k}]xfade=transition={clips[k]['trans']}:duration={clips[k]['d']}:offset={clips[k]['t']}[x{k}]")
        cur = f"x{k}"
    run([FF, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc), "-map", f"[{cur}]", "-t", f"{total:.3f}", *ENC, out])


def frame_at(src, t, out):
    run([FF, "-y", "-loglevel", "error", "-ss", f"{t}", "-i", src, "-frames:v", "1", out])


def cut(src, ss, to, w, h, out, vf=""):
    run([FF, "-y", "-loglevel", "error", "-ss", f"{ss}", "-to", f"{to}", "-i", src, "-vf", fit(w, h) + vf, *ENC, out])


def duration(path):
    r = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True, creationflags=0x08000000 if os.name == "nt" else 0)
    m = __import__("re").search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr.decode("utf-8", "replace"))
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def voice(lines, dur, work, voice_name, rate="+8%"):
    """Lồng tiếng bằng Edge TTS. lines = [(thời điểm muốn bắt đầu, câu)] -> (wav dài đúng dur giây, [(bắt đầu, kết thúc, câu)] thực tế). Câu sau tự lùi nếu câu trước chưa đọc xong."""
    import asyncio, edge_tts
    parts, timing, prev_end = [], [], 0.0
    for n, (t0, text) in enumerate(lines):
        mp3 = os.path.join(work, f"v{n}.mp3")
        for attempt in range(3):
            try:
                asyncio.run(edge_tts.Communicate(text, voice_name, rate=rate).save(mp3))
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2)
        wav = os.path.join(work, f"v{n}.wav")   # cắt khoảng lặng đầu/cuối để canh giờ chính xác
        run([FF, "-y", "-loglevel", "error", "-i", mp3, "-af", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse", wav])
        mp3 = wav
        d = duration(mp3)
        st = max(t0, prev_end + 0.25)
        prev_end = st + d
        parts.append((mp3, st))
        timing.append((st, prev_end, text))
    if prev_end > dur + 0.05:
        raise RuntimeError(f"lời đọc dài hơn đoạn video ({prev_end:.1f}s > {dur:.1f}s)")
    inputs, fc = [], []
    for n, (mp3, st) in enumerate(parts):
        inputs += ["-i", mp3]
        fc.append(f"[{n}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={int(st * 1000)}|{int(st * 1000)},apad[a{n}]")
    out = os.path.join(work, "voice.wav")
    run([FF, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc) + ";" + "".join(f"[a{n}]" for n in range(len(parts))) + f"amix=inputs={len(parts)}:normalize=0:duration=longest[a]",
         "-map", "[a]", "-t", f"{dur:.3f}", "-ar", "44100", "-ac", "2", out])
    return out, timing


def concat(parts, audio_src, out, workdir):
    lst = os.path.join(workdir, "list.txt")
    open(lst, "w", encoding="utf-8").write("".join("file '" + p.replace("\\", "/") + "'\n" for p in parts))
    tmp = os.path.join(workdir, "joined.mp4")
    run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", tmp])
    dur = duration(audio_src)   # thời lượng y hệt video gốc: kéo dài khung cuối nếu thiếu vài khung hình, cắt nếu dư
    run([FF, "-y", "-loglevel", "error", "-i", tmp, "-i", audio_src, "-map", "0:v", "-map", "1:a:0", "-vf", "tpad=stop_mode=clone:stop_duration=1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-t", f"{dur:.3f}", "-movflags", "+faststart", out])


def label(name, w, h):
    return f"drawtext=fontfile='{FONT}':text='{name}':x=(w-text_w)/2:y=h-{int(h * 0.075)}:fontsize={int(w / 15)}:fontcolor=white:borderw=4:bordercolor=black"


def grid_video(src, imgs, labels, reveals, hero_end, work, out, W=1080, H=1920, trans="wipeup", line=False, audio_src=None):
    """2x2: imgs[i] = (ảnh gốc, ảnh mới) hoặc (ảnh,) nếu cố định. reveals[i] = (t0, d). Sau hero_end nối nguyên end card của video gốc."""
    pw, ph = W // 2, H // 2
    panels = []
    for i, im in enumerate(imgs):
        o = os.path.join(work, f"panel{i}.mp4")
        if len(im) == 1:
            still(im[0], pw, ph, hero_end, o)
        else:
            reveal(im[0], im[1], pw, ph, hero_end, reveals[i][0], reveals[i][1], o, trans=trans, line=line)
        panels.append(o)
    inputs = sum([["-i", p] for p in panels], [])
    fc = "[0:v][1:v]hstack[t];[2:v][3:v]hstack[b];[t][b]vstack[g]"
    dts = []
    for i, name in enumerate(labels):
        cx, cy = (i % 2) * pw + pw // 2, (i // 2) * ph + ph - int(ph * 0.075)
        dts.append(f"drawtext=fontfile='{FONT}':text='{name}':x={cx}-text_w/2:y={cy}-text_h:fontsize={int(pw / 14)}:fontcolor=white:borderw=4:bordercolor=black")
    fc += ";[g]" + ",".join(dts) + "[v]"
    hero = os.path.join(work, "hero.mp4")
    run([FF, "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-map", "[v]", *ENC, hero])
    endcard = os.path.join(work, "end.mp4")
    cut(src, hero_end, 999, W, H, endcard)
    concat([hero, endcard], audio_src or src, out, work)


def ass_file(path, events, w, h, marginv):
    Y, Wh = r"{\c&H00FFFF&}", r"{\c&HFFFFFF&}"
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
            f"Style: Default,Arial,{int(w / 15)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,2,20,20,{marginv},1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")

    def t(x):
        return f"0:{int(x // 60):02d}:{x % 60:05.2f}"
    open(path, "w", encoding="utf-8").write(head + "".join(f"Dialogue: 0,{t(a)},{t(b)},Default,,0,0,0,,{txt.replace('<y>', Y).replace('</y>', Wh)}\n" for a, b, txt in events))


# ------------------------------------------------------------------ dữ liệu biến thể
ETH = ["Black", "East Asian", "Latino", "Caucasian", "South Asian", "Mediterranean", "Middle Eastern", "Scandinavian", "Southeast Asian", "mixed-race"]
LOOK = "photorealistic, sharp focus, natural skin texture, vertical 9:16 composition"


def v73(i):
    """5 cảnh ảnh cặp đôi Giáng sinh. Mỗi cảnh giữ đúng kiểu bối cảnh của cảnh gốc, đổi người + dáng."""
    BG = ["a snowy winter forest at golden sunset with a lit Christmas tree and white roses and holly on the ground",
          "a Christmas arch of evergreen garlands, red poinsettias and a golden bow at pink dusk, candles on a stone terrace",
          "a snow-dusted garden with hanging string lights, glass ornaments, topiary trees and pink-white roses",
          "a snowy path lined with red poinsettias, candle lanterns and lit evergreens against a deep blue twilight sky",
          "an icy blue-and-silver winter wonderland with frosted white trees, snowflakes and blue roses"]
    POSES = ["standing close, looking at each other with warm smiles, her hand resting on his chest",
             "standing side by side, he has one hand in his pocket, both smiling at the camera",
             "his arm around her waist, her head leaning on his shoulder, both looking at the camera",
             "facing each other, holding both hands, laughing softly",
             "she stands slightly in front, he hugs her from behind, both looking at the camera",
             "walking toward the camera hand in hand, mid-step, smiling",
             "she looks up at him while he looks into the camera, her hand on his lapel",
             "arm in arm, standing tall and elegant, relaxed postures",
             "dancing pose, he holds her hand up as she turns, both smiling",
             "foreheads almost touching, eyes closed, gentle smiles"]
    OUT = [("an elegant long satin gown", "a black tuxedo with a bow tie"), ("a velvet evening dress with long gloves", "a dark three-piece suit"),
           ("a floral tulle midi dress", "a navy suit with a pocket square"), ("a sequin gown", "a silver-grey tuxedo jacket"),
           ("a lace cocktail dress", "a burgundy velvet blazer"), ("a wrap dress in deep green", "a charcoal suit with a red tie"),
           ("a champagne beaded gown", "a classic white-tie tailcoat"), ("a ruby-red long dress", "a black suit with a gold bow tie"),
           ("a blush-pink chiffon dress", "a grey suit with a patterned vest"), ("an ivory silk dress with a shawl", "a midnight-blue velvet jacket")]
    AGE = ["in their 50s", "in their 60s", "in their 40s", "in their 50s", "in their 60s"]
    scenes = []
    for s in range(5):
        k = i * 5 + s
        eth = ETH[(k * 3 + 1) % 10]
        w, m = OUT[(k * 7 + s) % 10]
        scenes.append({"key": f"s{s}", "text": f"Photorealistic full-length formal couple portrait of an elegant {eth} couple {AGE[(k + s) % 5]}, she wears {w}, he wears {m}. Pose: {POSES[(k * 3 + i) % 10]}. "
                                                  f"Setting: {BG[s]}. Warm cinematic light, professional photo shoot, {LOOK}."})
    return scenes


def build73(src, imgs, work, out):
    W, H = 720, 1280
    P = lambda n: os.path.join(work, n)
    frame_at(src, 1.6, P("balloons.png"))                       # ảnh bóng bay của đoạn chuyển cảnh gốc: dùng lại nguyên bản
    clips = [{"img": imgs[0], "t": 0, "trans": "", "d": 0}, {"img": P("balloons.png"), "t": 1.25, "trans": "wipeup", "d": 0.25},
             {"img": imgs[1], "t": 1.7, "trans": "wipeup", "d": 0.15}, {"img": imgs[2], "t": 2.55, "trans": "fade", "d": 0.3},
             {"img": imgs[3], "t": 4.0, "trans": "slideleft", "d": 0.12}, {"img": imgs[4], "t": 5.66, "trans": "slideleft", "d": 0.12}]
    timeline(clips, W, H, duration(src), P("hero.mp4"))
    concat([P("hero.mp4")], src, out, work)


HEROES = ["a young woman with long wavy hair and drop earrings, soft smile, head slightly tilted",
          "a young woman with big voluminous curly hair, calm expression, looking forward",
          "a young woman with long wavy blonde hair, one hand softly touching her cheek",
          "a woman wearing a wide-brim straw hat decorated with roses, holding a single rose, looking to the side"]


def v77(i):
    WOMEN = ["a young Black woman with long box braids", "an elderly East Asian woman with short wavy hair", "a young Latina woman with long dark waves",
             "a Caucasian woman in her 40s with a loose side braid", "a South Asian woman with long thick black hair", "a young Middle Eastern woman wearing a light headscarf",
             "a Scandinavian woman with a high ponytail and bangs", "a mixed-race woman with a big curly afro", "an older woman with silver curly hair and glasses", "a Southeast Asian woman with a shoulder-length bob"]
    POSE = [["head tilted slightly to the left, soft smile", "chin resting on one hand, dreamy eyes", "looking over her shoulder, shy smile", "three-quarter view, eyes closed, serene", "looking up toward the light",
             "laughing softly, head thrown back a little", "leaning forward, eyes on the viewer", "profile view, calm gaze", "hair blown by wind, looking sideways", "both hands near the collar, direct gaze"],
            ["frontal view, relaxed smile", "head tilted to the right, hand in hair", "looking down gently", "turning her head toward the left, thoughtful", "side glance with a smirk",
             "chin lifted, confident", "eyes closed, enjoying a breeze", "hands clasped under chin", "looking over the shoulder", "leaning on one elbow"],
            ["one hand on the cheek, gentle gaze", "both hands framing the face", "hand touching the neck, looking away", "finger on the lips, playful", "hand in hair, side view",
             "chin on the palm, elbow on the table", "hand on the collarbone, soft look", "hand behind the ear, listening pose", "touching an earring, glancing sideways", "hand over the heart, calm smile"],
            ["holding a rose near the chin, looking to the side", "smelling a flower held in both hands", "holding a bouquet against the chest", "holding a single flower at the lips, eyes down", "holding a flower toward the viewer",
             "holding a flower behind the ear, smiling", "holding a flower stem with both hands, looking up", "twirling a flower, side glance", "holding a flower at the waist, looking forward", "holding a flower to the cheek, eyes closed"]]
    ACC = ["", " wearing drop earrings", " wearing small pearl earrings", " wearing a delicate necklace", " wearing hoop earrings"]
    scenes = []
    for s in range(4):
        k = i * 4 + s
        subj = WOMEN[(k * 3 + s) % 10]
        hat = " wearing a wide-brim straw hat decorated with roses," if s == 3 else ACC[(k) % 5] + ","
        scenes.append({"key": f"s{s}", "text": f"Overhead photo of a spiral-bound sketchbook page with a hyper-realistic black-and-white graphite pencil portrait of {subj}{hat} {POSE[s][(i * 3 + s * 2) % 10]}. "
                                                  f"A real human hand holds a black pencil at the lower right and is adding the final shading. Soft even light, the drawing fills most of the page, fine pencil texture, {LOOK}."})
    return scenes


VOICE77 = "pt-BR-FranciscaNeural"
SCRIPT77 = [(0.3, "Primeiro, envie a sua foto."), (3.0, "Escolha uma foto com o rosto visível."),
            (6.4, "Pronto! Veja o seu retrato a lápis."), (9.8, "Salve e compartilhe!")]


HAND_PROMPT = ("Use the attached image as the exact first frame. The camera is top-down and stays completely still. The pencil drawing on the sketchbook page stays exactly the same; "
               "only the real hand holding the black pencil moves, making small natural shading strokes back and forth over the drawing at the lower right, the way a person draws. No cuts, no text.")


def build77(src, heroes, imgs, photo, work, out):
    W, H = 576, 1024
    P = lambda n: os.path.join(work, n)
    clips = [{"img": heroes[0], "t": 0, "trans": "", "d": 0}, {"img": heroes[1], "t": 1.85, "trans": "fade", "d": 0.2},
             {"img": heroes[2], "t": 3.6, "trans": "fade", "d": 0.25}, {"img": heroes[3], "t": 5.65, "trans": "fade", "d": 0.25}]
    timeline(clips, W, H, 8.4, P("hero.mp4"))
    dur = duration(src) - 8.4
    vwav, timing = voice(SCRIPT77, dur, work, VOICE77)
    # đoạn giới thiệu app của người khác -> mẫu upload của bạn: ảnh nhân vật vào khung, rồi hiện 3 ảnh kết quả (3 tranh đầu của video)
    upload_scene(photo, dur, W, H, work, P("tut.mp4"), t_in=3.0, results=imgs[:3], t_res=[6.4, 8.4, 10.4], caps=timing)
    run([FF, "-y", "-loglevel", "error", "-i", src, "-t", "8.4", "-vn", "-ar", "44100", "-ac", "2", P("a1.wav")])
    run([FF, "-y", "-loglevel", "error", "-i", P("a1.wav"), "-i", vwav, "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]", "-map", "[a]", "-c:a", "aac", "-b:a", "128k", P("audio.m4a")])
    concat([P("hero.mp4"), P("tut.mp4")], P("audio.m4a"), out, work)


def v83(i):
    PEOPLE = [("a young woman with long straight dark hair", ["Blunt Bob", "Sleek Bun", "Loose Curls", "Dutch Braid"]),
              ("a Black woman with long straight black hair", ["Twist Out", "Box Braids", "Puff", "Sleek Bun"]),
              ("a young East Asian man with medium-length black hair", ["Buzz Cut", "Undercut", "Man Bun", "Curtain Fringe"]),
              ("a freckled woman with long straight red hair", ["Pixie Cut", "Long Layers", "Braided Crown", "Messy Bun"]),
              ("a Latina woman with very long straight dark brown hair", ["Curtain Bangs", "Half-up Bun", "Long Braid", "Wolf Cut"]),
              ("an older woman with long straight silver hair", ["Short Bob", "Soft Perm", "Low Chignon", "Pearl Waves"]),
              ("a Black man with a medium-length afro", ["High Top", "Twists", "Waves", "Locs"]),
              ("a young South Asian woman with long straight black hair", ["Side Braid", "Messy Bun", "Straight Layers", "High Pony"]),
              ("a young woman in her 20s with long straight light-brown hair", ["Pigtails", "Bubble Ponytail", "Space Buns", "Heart Braids"]),
              ("a white man with a short beard and shoulder-length brown hair", ["Slicked Back", "Quiff", "Curly Top", "Top Knot"])]
    who, styles = PEOPLE[i % 10]
    base = {"key": "base", "text": f"Photorealistic close-up phone selfie of {who} sitting in a car (seat headrest and window visible behind), wearing a black tank top, soft natural daylight, head slightly tilted, face and upper chest filling the frame, {LOOK}."}
    edits = [{"key": f"e{n}", "ref": "base", "name": st, "text": f"Edit this exact selfie: change ONLY the hairstyle to a {st}. Keep the same person, face, expression, pose, black top, car interior and lighting identical. {LOOK}."} for n, st in enumerate(styles)]
    return {"base": base, "edits": edits, "labels": styles}


def build83(src, base, edits, labels, work, out):
    # cả 4 ô đều biến đổi từ ảnh gốc, đúng mốc video gốc (quét từ dưới lên), chuyển nhanh 0,5s
    grid_video(src, [(base, edits[0]), (base, edits[1]), (base, edits[2]), (base, edits[3])], labels, [(0.5, 0.5), (4.0, 0.5), (7.4, 0.5), (11.0, 0.5)], 13.833, work, out)


def v84(i):
    WOMEN = ["a young East Asian woman with long straight black hair", "a woman with curly brown hair", "a woman with a long blonde ponytail", "a Black woman with shoulder-length braids",
             "a woman with shoulder-length auburn hair", "a South Asian woman with a high bun", "a Latina woman with long wavy chestnut hair", "a woman with a short pixie cut",
             "a Middle Eastern woman with long dark hair", "a Southeast Asian woman with a low ponytail"]
    PLACE = ["in a small apartment kitchen in the morning light", "at a city bus stop with the shelter and street traffic behind her", "between the shelves of a neighbourhood supermarket",
             "on a narrow apartment balcony with laundry hanging on lines", "on a path in a local neighbourhood park", "in front of a small street-food stall at a market",
             "at a school gate with parked scooters", "leaning on the doorway of a neighbourhood bakery", "in a cosy living room next to a sofa", "on a small-town street corner with a corner shop"]
    who, place = WOMEN[i % 10], PLACE[(i * 3 + 1) % 10]
    base = {"key": "base", "text": f"Photorealistic vertical phone photo of {who}, standing relaxed {place}, wearing a plain white fitted T-shirt and light beige trousers, one hand resting on something nearby, gentle smile, natural daylight, "
                                    f"upper body to thigh visible, candid iPhone look, {LOOK}."}
    keep = "Keep the same woman, face, pose, framing, background and lighting identical. "
    edits = [{"key": "bride", "ref": "base", "name": "Bride", "text": f"Edit this exact photo: dress her as a bride in a white wedding gown with a long veil, holding a small bouquet of white flowers. {keep}{LOOK}."},
             {"key": "preg", "ref": "base", "name": "Pregnant", "text": f"Edit this exact photo: she is visibly pregnant with a large round baby bump, wearing the same white T-shirt. {keep}{LOOK}."},
             {"key": "child", "ref": "base", "name": "Have a child", "text": f"Edit this exact photo: she holds a cheerful toddler in pastel clothes on her hip. {keep}{LOOK}."},
             {"key": "old", "ref": "base", "name": "Old Age", "text": f"Edit this exact photo: age her to about 80 years old with long grey-white hair and gentle wrinkles, same clothes. {keep}{LOOK}."}]
    return {"base": base, "edits": edits, "labels": ["Bride", "Pregnant", "Have a child", "Old Age"]}


def build84(src, base, edits, labels, work, out):
    # đúng mốc bắt đầu của video gốc (0.9 / 4.3 / 8.2 / 11.9s), quét từ dưới lên kèm vạch trắng, nhanh hơn (0,7s)
    grid_video(src, [(base, edits[0]), (base, edits[1]), (base, edits[2]), (base, edits[3])], labels, [(0.9, 0.7), (4.3, 0.7), (8.2, 0.7), (11.9, 0.7)], 13.833, work, out, line=True)


def v104(i):
    PEOPLE = ["a woman in her 60s with a short silver bob, glasses and a black sleeveless top", "a young woman with long ombre brown hair in a patterned red top",
              "a man in his 40s with a short beard and a green sweater", "a young Black woman with a big natural afro and gold hoop earrings",
              "a young man in his 20s with messy brown hair and a blue hoodie", "an East Asian woman with long straight black hair, bangs and a white sweater",
              "a bald man with glasses and a red-and-black checked jacket", "a Latina woman with a high messy bun and red lipstick in a green blouse",
              "an elderly man with a white beard and a woollen hat", "a young woman with curly blonde hair and freckles in a striped sweater",
              "a middle-aged Indian woman with a long braid and a maroon cardigan", "a young man with a fade haircut and a denim jacket",
              "a woman in her 50s with a curly auburn bob and a leopard-print top", "a Southeast Asian man with glasses and a beige polo shirt",
              "a woman with long platinum hair and a black turtleneck", "a young man with a ponytail and a yellow hoodie",
              "an older woman with a grey bun and a floral blouse", "a Black man with short locs and a navy sweater",
              "a young woman with a pixie cut and a plaid shirt", "a middle-aged man with a mustache and a brown leather jacket"]
    ROOMS = ["a bright living room with framed pictures and shelves behind", "the driver seat of a car, headrest and window behind"]
    out = []
    for s in range(2):
        who = PEOPLE[(i * 2 + s) % 20]
        out.append({"base": {"key": f"self{s}", "text": f"Photorealistic phone selfie of {who}, smiling warmly at the camera, in {ROOMS[s]}, head and shoulders centered, natural light, {LOOK}."},
                    "edit": {"key": f"toon{s}", "ref": f"self{s}", "text": "Transform this selfie into a classic flat-colour 1960s Christmas TV-special comic-strip cartoon: thick simple outlines, round head, minimal facial features, "
                                                                      "keeping the hairstyle, glasses and clothing colours recognisable. The cartoon character stands on the red roof of a small doghouse decorated with a green wreath, a little white beagle hugging them, "
                                                                      "in a snowy village with bare trees, a white picket fence and a small house behind. Title text 'A Charlie Brown Christmas' at the top. Vertical 9:16."}})
    return out


UPLOAD_TPL = os.path.join(ROOT, "assets", "upload_template.png")   # 1080x1920: nút "UPLOAD YOUR PHOTO" + khung tải ảnh (x188-892, y422-1497)


def upload_scene(photo, dur, W, H, work, out, t_in=3.0, results=(), t_res=(), caps=None, full_results=False):
    """Mẫu upload hiện ra; tới t_in giây ảnh của nhân vật hiện dần vào đúng khung (bo góc); rồi (nếu có) lần lượt hiện các ảnh kết quả tại t_res. caps = [(bắt đầu, kết thúc, chữ)]."""
    from PIL import Image, ImageDraw
    k = W / 1080
    x, y, w, h, r = round(188 * k), round(422 * k), round(704 * k) // 2 * 2, round(1075 * k) // 2 * 2, round(50 * k)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    mp = os.path.join(work, "mask.png")
    mask.save(mp)
    imgs, ts = [photo, *results], [t_in, *t_res]
    nm = 1 if full_results else len(imgs)   # số ảnh cần mặt nạ bo góc
    inputs = ["-loop", "1", "-t", f"{dur:.3f}", "-i", UPLOAD_TPL, "-loop", "1", "-t", f"{dur:.3f}", "-i", mp]
    fc = [f"[0:v]scale={W}:{H},setsar=1,fps=30,format=yuv420p[bg]", (f"[1:v]format=gray,split={nm}" + "".join(f"[m{i}]" for i in range(nm)) if nm > 1 else "[1:v]format=gray[m0]")]
    cur = "bg"
    for i, (im, t) in enumerate(zip(imgs, ts)):
        inputs += ["-loop", "1", "-t", f"{dur - t:.3f}", "-i", im]
        if full_results and i > 0:   # ảnh kết quả phủ TOÀN MÀN HÌNH (không còn khung upload)
            fc.append(f"[{i + 2}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=yuva420p,fade=t=in:st=0:d=0.3:alpha=1,setpts=PTS+{t}/TB[ov{i}]")
            fc.append(f"[{cur}][ov{i}]overlay=0:0:eof_action=pass[o{i}]")
        else:
            fc.append(f"[{i + 2}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=yuva420p[s{i}]")
            fc.append(f"[s{i}][m{i}]alphamerge,fade=t=in:st=0:d={0.6 if i == 0 else 0.4}:alpha=1,setpts=PTS+{t}/TB[ov{i}]")
            fc.append(f"[{cur}][ov{i}]overlay={x}:{y}:eof_action=pass[o{i}]")
        cur = f"o{i}"
    raw = out if not caps else os.path.join(work, "up_raw.mp4")
    run([FF, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc) + f";[{cur}]format=yuv420p[v]", "-map", "[v]", "-t", f"{dur:.3f}", *ENC, raw])
    if caps:
        ass_file(os.path.join(work, "up.ass"), caps, W, H, int(H * 0.09))
        with FF_SEM:
            subprocess.run([FF, "-y", "-loglevel", "error", "-i", "up_raw.mp4", "-vf", "ass=up.ass", *ENC, os.path.basename(out)], cwd=work, check=True, creationflags=0x08000000 if os.name == "nt" else 0)


VOICE104 = "en-US-JennyNeural"
SCRIPT104 = [(0.3, "First, upload your photo."), (4.9, "Boom! Your cartoon is ready."), (8.0, "Share it!")]


def build104(src, pairs, work, out):
    W, H = 720, 1280
    P = lambda n: os.path.join(work, n)
    (s0, c0), (s1, c1) = pairs
    clips = [{"img": s0, "t": 0, "trans": "", "d": 0}, {"img": c0, "t": 0.8, "trans": "wipedown", "d": 1.4},
             {"img": s1, "t": 2.75, "trans": "wipedown", "d": 0.1}, {"img": c1, "t": 3.2, "trans": "wipedown", "d": 1.6}]
    timeline(clips, W, H, 5.9, P("hero.mp4"))
    ev = [(0.0, 0.8, "<y>HOW</y> TO MAKE"), (0.8, 1.6, "A <y>CHARLIE</y> BROWN"), (1.6, 2.75, "<y>CHRISTMAS</y> PHOTO."), (2.75, 3.4, "IT'S <y>SUPER</y> EASY"),
          (3.4, 4.6, "TO DO. <y>OKAY,</y>"), (4.6, 5.15, "<y>HERE'S</y> HOW TO"), (5.15, 5.9, "DO IT. FIRST,")]
    ass_file(P("cap.ass"), ev, W, H, int(H * 0.2))
    with FF_SEM:
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", "hero.mp4", "-vf", "ass=cap.ass", *ENC, "hero_cap.mp4"], cwd=work, check=True, creationflags=0x08000000 if os.name == "nt" else 0)
    dur = duration(src) - 5.9
    vwav, timing = voice(SCRIPT104, dur, work, VOICE104, rate="+15%")
    # thay đoạn giới thiệu app của người khác bằng mẫu "Upload your photo" của bạn: ảnh vào khung rồi hiện 2 ảnh hoạt hình kết quả
    upload_scene(pairs[0][0], dur, W, H, work, P("tut.mp4"), t_in=2.8, results=[c0, c1], t_res=[4.9, 7.0], caps=timing, full_results=True)
    run([FF, "-y", "-loglevel", "error", "-i", src, "-t", "5.9", "-vn", "-ar", "44100", "-ac", "2", P("a1.wav")])
    run([FF, "-y", "-loglevel", "error", "-i", P("a1.wav"), "-i", vwav, "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]", "-map", "[a]", "-c:a", "aac", "-b:a", "128k", P("audio.m4a")])
    concat([P("hero_cap.mp4"), P("tut.mp4")], P("audio.m4a"), out, work)


# ------------------------------------------------------------------ chạy
def run_variant(kind, i, args):
    src = os.path.join(args.src, FILES[kind])
    work = os.path.join(args.out, "_work", f"{kind}_{i + 1:02d}")
    os.makedirs(work, exist_ok=True)
    out = os.path.join(args.out, f"{kind}_bienthe_{i + 1:02d}.mp4")
    if os.path.exists(out):
        return out
    title = f"{kind} - ảnh cảnh"
    G = (lambda items: [os.path.join(work, f"dry{n}.png") for n in range(len(items))]) if args.dry else (lambda items: gen_images(title, items))
    if kind in ("Z0073", "Z0077"):
        sc = (v73 if kind == "Z0073" else v77)(i)
        imgs = G(sc)
        if kind == "Z0073":
            build73(src, imgs, work, out)
        else:
            heroes = imgs
            if not args.dry:   # bàn tay cầm bút chì chuyển động như video gốc: Muse tạo clip ngắn từ từng tranh (tranh giữ nguyên, chỉ tay cử động)
                heroes = gen_images(f"{kind} - clip tay", [{"text": HAND_PROMPT, "files": [im]} for im in imgs], kind="video", duration=5)
            photo = G([{"text": "Using this pencil drawing as reference, create a photorealistic phone selfie photo of the same woman (same face, hair and expression), plain neutral background, "
                                "wearing a plain solid-colour crew-neck T-shirt that fully covers the shoulders and chest, head and torso framing with the shirt clearly visible, natural light, no hand, no paper, no pencil. Vertical 9:16.", "files": [imgs[0]]}])[0]
            build77(src, heroes, imgs, photo, work, out)
    elif kind in ("Z0083", "Z0084"):
        spec = (v83 if kind == "Z0083" else v84)(i)
        base = G([spec["base"]])[0]
        edits = G([{"text": e["text"], "files": [base]} for e in spec["edits"]])
        (build83 if kind == "Z0083" else build84)(src, base, edits, spec["labels"], work, out)
    else:
        pairs = []
        for p in v104(i):
            selfie = G([p["base"]])[0]
            toon = G([{"text": p["edit"]["text"], "files": [selfie]}])[0]
            pairs.append((selfie, toon))
        build104(src, pairs, work, out)
    if not args.dry:
        try:
            publish(f"{kind} - thành phẩm", f"{kind} biến thể {i + 1:02d}", out)
        except Exception as e:  # noqa: BLE001  (LUO Chat bản cũ chưa có /api/attach: video vẫn nằm trong thư mục out, chạy 'publish' sau)
            print("chưa đưa vào LUO Chat được:", str(e)[:100], flush=True)
    return out


def make_dummies(kind, i, args):
    """Ảnh giả (màu + số) để thử dựng khi chạy 'dry'."""
    work = os.path.join(args.out, "_work", f"{kind}_{i + 1:02d}")
    os.makedirs(work, exist_ok=True)
    cols = ["red", "green", "blue", "orange", "purple", "teal", "gold", "pink"]
    for n in range(8):
        subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={cols[n]}:s=720x1280:d=1", "-vf",
                        f"drawtext=fontfile='{FONT}':text='{n}':fontsize=300:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2", "-frames:v", "1", os.path.join(work, f"dry{n}.png")],
                       check=True, creationflags=0x08000000 if os.name == "nt" else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "dry", "publish"])
    ap.add_argument("kinds", nargs="+")
    ap.add_argument("--variants", type=int, default=10)
    ap.add_argument("--start", type=int, default=1, help="số thứ tự biến thể bắt đầu (1-10)")
    ap.add_argument("--src", default=r"D:\test_tool")
    ap.add_argument("--out", default=r"D:\test_tool\out")
    a = ap.parse_args()
    a.dry = a.mode == "dry"
    os.makedirs(a.out, exist_ok=True)
    if a.mode == "publish":   # đưa các video đã dựng trong thư mục out vào LUO Chat
        for k in a.kinds:
            for f in sorted(x for x in os.listdir(a.out) if x.startswith(k + "_bienthe_") and x.endswith(".mp4")):
                publish(f"{k} - thành phẩm", f"{k} biến thể {f[-6:-4]}", os.path.join(a.out, f))
                print("đã đưa vào LUO Chat:", f)
        return
    errors, threads = [], []

    def worker(kind, i):
        try:
            if a.dry:
                make_dummies(kind, i, a)
            print("xong", run_variant(kind, i, a), flush=True)
        except Exception as e:  # noqa: BLE001
            errors.append((kind, i + 1, str(e)))
            print("LỖI", kind, i + 1, str(e)[:300], flush=True)
    for kind in a.kinds:
        for i in range(a.start - 1, a.start - 1 + a.variants):
            t = threading.Thread(target=worker, args=(kind, i), daemon=True)
            t.start()
            threads.append(t)
    for t in threads:
        t.join()
    print(f"Hoàn tất. Lỗi: {len(errors)}")
    for e in errors:
        print(" ", e)


if __name__ == "__main__":
    main()
