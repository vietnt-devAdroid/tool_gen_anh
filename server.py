"""LUO Chat - máy chủ cục bộ cho giao diện chat Muse (video/ảnh/chat) có hàng đợi chạy ngầm.

- Giao diện: ui/ (3 cột: cuộc trò chuyện | khung chat | media).
- Gọi LUO-API (muse2api) qua HTTP: /v1/videos, /v1/images/tasks, /v1/chat/completions.
- Điều khiển tự động: Claude (hoặc script) gọi POST /api/batch / chatctl.py; prompt hiện trong giao diện để bạn kiểm tra.
Chỉ dùng thư viện chuẩn.
"""
import base64, json, mimetypes, os, re, shutil, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request, uuid, zipfile, io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "ui")
DATA = os.environ.get("LUO_CHAT_DATA") or os.path.join(HERE, "userdata", "chat")
MEDIA = os.path.join(DATA, "media")
UPLOADS = os.path.join(DATA, "uploads")
for _d in (DATA, MEDIA, UPLOADS):
    os.makedirs(_d, exist_ok=True)

DEFAULTS = {"api_url": os.environ.get("LUO_API_URL", "http://127.0.0.1:18610"), "api_key": os.environ.get("MUSE2API_KEY", ""),
            "parallel": 3, "retries": 2, "timeout": 900, "review_claude": False, "raw_prompt": False, "export_dir": ""}
LOCK = threading.RLock()
REV = {"n": 0}
CHATS = {}       # id -> chat
SETTINGS = dict(DEFAULTS)
STOP = {}        # message id -> threading.Event
WORKING = set()  # message id đang chạy


# ------------------------------------------------------------------ lưu trữ
def jread(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def jwrite(p, obj):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def bump():
    REV["n"] += 1


_save_timer = {"t": None}


def save_soon():
    """Gộp nhiều thay đổi liên tiếp thành một lần ghi đĩa."""
    bump()
    with LOCK:
        if _save_timer["t"]:
            return
        t = threading.Timer(0.6, _save_now)
        t.daemon = True
        _save_timer["t"] = t
        t.start()


def _save_now():
    with LOCK:
        _save_timer["t"] = None
        jwrite(os.path.join(DATA, "chats.json"), CHATS)


def load():
    global CHATS
    CHATS = jread(os.path.join(DATA, "chats.json"), {})
    SETTINGS.update(jread(os.path.join(DATA, "settings.json"), {}))
    for c in CHATS.values():   # việc đang chạy dở khi tắt app -> xếp hàng lại
        for m in c["messages"]:
            if m.get("status") in ("running",):
                m["status"] = "queued"
                m["progress"] = 0


def now():
    return time.time()


def uid(p=""):
    return p + uuid.uuid4().hex[:10]


def settings():
    s = dict(SETTINGS)
    # khoá API: ưu tiên cài đặt, rồi biến môi trường, rồi userdata/api/.env
    if not s.get("api_key"):
        env = os.path.join(HERE, "userdata", "api", ".env")
        try:
            for ln in open(env, encoding="utf-8").read().splitlines():
                if ln.startswith("MUSE2API_KEY="):
                    s["api_key"] = ln.split("=", 1)[1].strip()
        except Exception:
            pass
    return s


# ------------------------------------------------------------------ gọi LUO-API
class ApiError(RuntimeError):
    def __init__(self, msg, account=""):
        super().__init__(msg)
        self.account = account


def api(method, path, body=None, timeout=60, raw=False):
    s = settings()
    url = s["api_url"].rstrip("/") + path
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if s.get("api_key"):
        req.add_header("Authorization", "Bearer " + s["api_key"])
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read()
            return b if raw else json.loads(b.decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8", "replace"))
            msg = msg.get("detail") or msg.get("error") or msg
        except Exception:
            msg = e.reason
        raise ApiError(f"LUO-API {e.code}: {msg}")
    except (urllib.error.URLError, OSError) as e:
        raise ApiError(f"Không nối được LUO-API ({s['api_url']}): {e}")


def api_alive():
    try:
        api("GET", "/healthz", timeout=3)
        return True
    except Exception:
        return False


def download(url, dest):
    s = settings()
    if url.startswith("/"):
        url = s["api_url"].rstrip("/") + url
    else:   # API có thể trả địa chỉ công khai khác: luôn lấy từ máy chủ cục bộ qua /v1/media/<tên>
        m = re.search(r"/v1/media/([^/?#]+)$", url.split("?")[0])
        if m:
            url = s["api_url"].rstrip("/") + "/v1/media/" + m.group(1)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + s.get("api_key", "")} if s.get("api_key") else {})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


# ------------------------------------------------------------------ cuộc trò chuyện / tin nhắn
def new_chat(title="Cuộc trò chuyện mới", account=""):
    c = {"id": uid("c"), "title": title, "created": now(), "updated": now(), "account": account, "messages": []}
    with LOCK:
        CHATS[c["id"]] = c
    save_soon()
    return c


def find_msg(mid):
    for c in CHATS.values():
        for m in c["messages"]:
            if m["id"] == mid:
                return c, m
    return None, None


def summary(c):
    ms = c["messages"]
    cnt = {"queued": 0, "running": 0, "draft": 0, "error": 0, "done": 0}
    media = 0
    for m in ms:
        if m.get("role") != "user":
            continue
        cnt[m.get("status", "done")] = cnt.get(m.get("status", "done"), 0) + 1
        media += len(m.get("media") or [])
    last = next((m for m in reversed(ms) if m.get("text")), None)
    return {"id": c["id"], "title": c["title"], "updated": c["updated"], "account": c.get("account", ""), "count": len(ms),
            "counts": cnt, "media": media, "preview": (last or {}).get("text", "")[:90]}


def add_message(chat, text, kind="video", aspect="9:16", duration=None, files=None, by="user", draft=False, extra=None):
    """Thêm một yêu cầu. kind: video | image | chat. Mỗi yêu cầu = một tin nhắn (người dùng) mang trạng thái + kết quả."""
    files = files or []
    m = {"id": uid("m"), "role": "user", "by": by, "kind": kind, "text": text.strip(), "aspect": aspect, "duration": duration,
         "files": files, "status": "draft" if draft else "queued", "progress": 0, "media": [], "reply": "", "error": "",
         "attempts": 0, "account": "", "created": now(), "log": []}
    if extra:
        m["extra"] = extra
    with LOCK:
        chat["messages"].append(m)
        chat["updated"] = now()
        if chat["title"] == "Cuộc trò chuyện mới" and text:
            chat["title"] = text.strip().split("\n")[0][:48]
    save_soon()
    schedule()
    return m


def log(m, msg):
    m["log"].append({"t": now(), "msg": msg})
    m["log"] = m["log"][-30:]


def file_ref(f):
    """Đường dẫn cục bộ của tệp đính kèm (LUO-API đọc trực tiếp trên cùng máy)."""
    return f["path"]


# ------------------------------------------------------------------ chạy việc
def run_video(m, chat, ev):
    s = settings()
    imgs = [file_ref(f) for f in m["files"] if f["type"] == "image"]
    vids = [file_ref(f) for f in m["files"] if f["type"] == "video"]
    auds = [file_ref(f) for f in m["files"] if f["type"] == "audio"]
    body = {"prompt": m["text"], "aspect_ratio": m["aspect"], "timeout": int(s["timeout"]), "raw_prompt": bool(s.get("raw_prompt"))}
    if m.get("duration"):
        body["duration"] = int(m["duration"])
    if imgs:
        body["reference_images"] = imgs
    if vids:
        body["reference_videos"] = vids
    if auds:
        body["reference_audios"] = auds
    acc = m.get("pin_account") or chat.get("account")
    if acc:
        body["pin_account"] = acc
        body["pin"] = "chat-" + m["id"]
    if m.get("avoid"):
        body["pin_avoid"] = m["avoid"]
    t = api("POST", "/v1/videos", body)
    tid = t.get("task_id") or t.get("id")
    m["task_id"] = tid
    log(m, f"Đã gửi Muse, task {tid}")
    return poll_task(m, ev, f"/v1/videos/{tid}", s["timeout"]), "video"


def run_image(m, chat, ev):
    s = settings()
    imgs = [file_ref(f) for f in m["files"] if f["type"] == "image"]
    body = {"prompt": m["text"], "aspect_ratio": m["aspect"], "async": True, "timeout": min(int(s["timeout"]), 600), "raw_prompt": bool(s.get("raw_prompt"))}
    if imgs:
        body["reference_images"] = imgs
    acc = m.get("pin_account") or chat.get("account")
    if acc:
        body["pin_account"] = acc
        body["pin"] = "chat-" + m["id"]
    if m.get("avoid"):
        body["pin_avoid"] = m["avoid"]
    t = api("POST", "/v1/images/tasks", body)
    tid = t.get("task_id") or t.get("id")
    m["task_id"] = tid
    log(m, f"Đã gửi Muse, task {tid}")
    return poll_task(m, ev, f"/v1/images/tasks/{tid}", min(int(s["timeout"]), 600)), "image"


def poll_task(m, ev, path, timeout):
    t0 = now()
    while True:
        if ev.is_set():
            raise InterruptedError()
        t = api("GET", path)
        st = t.get("status")
        m["progress"] = int(t.get("progress") or m.get("progress") or 0)
        m["account"] = t.get("account_label") or t.get("account") or m.get("account", "")
        m["account_id"] = t.get("account") or m.get("account_id", "")
        if st in ("completed", "succeeded", "success", "done"):
            return t
        if st in ("failed", "error", "cancelled"):
            raise ApiError(t.get("error") or f"Muse báo lỗi ({t.get('error_kind') or st})", m.get("account_id", ""))
        if now() - t0 > timeout + 60:
            raise ApiError("Quá thời gian chờ")
        save_soon()
        time.sleep(3)


def result_url(t):
    d = (t.get("data") or [{}])[0] if t.get("data") else {}
    return t.get("url") or (t.get("video") or {}).get("url") or (t.get("result") or {}).get("url") or d.get("url")


def run_chat(m, chat, ev):
    s = settings()
    hist = []
    for x in chat["messages"]:
        if x["id"] == m["id"]:
            break
        if x.get("kind") == "chat" and x.get("text") and x.get("reply"):
            hist += [{"role": "user", "content": x["text"]}, {"role": "assistant", "content": x["reply"]}]
    r = api("POST", "/v1/chat/completions", {"model": "muse-chat", "messages": hist + [{"role": "user", "content": m["text"]}], "session": chat["id"],
                                             "stream": False}, timeout=int(s["timeout"]))
    return r


def execute(mid):
    chat, m = find_msg(mid)
    if not m:
        return
    ev = STOP.setdefault(mid, threading.Event())
    ev.clear()
    try:
        m["attempts"] += 1
        m["error"] = ""
        log(m, f"Bắt đầu (lần {m['attempts']})")
        save_soon()
        if m["kind"] == "chat":
            r = run_chat(m, chat, ev)
            m["reply"] = (((r.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
            m["status"], m["progress"] = "done", 100
        else:
            t, kind = (run_video if m["kind"] == "video" else run_image)(m, chat, ev)
            url = result_url(t)
            if not url:
                raise ApiError("Muse xong nhưng không trả về tệp")
            ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or (".mp4" if kind == "video" else ".png")
            name = f"{m['id']}{ext}"
            download(url, os.path.join(MEDIA, name))
            m["media"] = [{"file": name, "type": kind}]
            m["status"], m["progress"], m["error"] = "done", 100, ""
            log(m, "Xong")
    except InterruptedError:
        m["status"] = "stopped"
        log(m, "Đã dừng")
    except Exception as e:  # noqa: BLE001
        acc = getattr(e, "account", "") or m.get("account_id", "")
        m["error"] = str(e)
        log(m, "Lỗi: " + str(e))
        if m["attempts"] <= int(settings()["retries"]) and not ev.is_set() and m["kind"] != "chat":
            if acc:
                m["avoid"] = list({*(m.get("avoid") or []), acc})
            m["status"] = "queued"
            m["progress"] = 0
            log(m, "Tự thử lại, đổi tài khoản")
        else:
            m["status"] = "error"
    finally:
        m["ended"] = now()
        with LOCK:
            WORKING.discard(mid)
        chat["updated"] = now()
        save_soon()
        schedule()


def schedule():
    with LOCK:
        free = int(settings()["parallel"]) - len(WORKING)
        if free <= 0:
            return
        todo = [m for c in CHATS.values() for m in c["messages"] if m.get("status") == "queued" and m["id"] not in WORKING]
        todo.sort(key=lambda m: m["created"])
        for m in todo[:free]:
            WORKING.add(m["id"])
            m["status"] = "running"
            m["progress"] = max(m.get("progress", 0), 1)
            threading.Thread(target=execute, args=(m["id"],), daemon=True).start()
    save_soon()


def stop_msgs(ids):
    for mid in ids:
        chat, m = find_msg(mid)
        if not m:
            continue
        if m["status"] == "running":
            STOP.setdefault(mid, threading.Event()).set()
        elif m["status"] in ("queued", "draft"):
            m["status"] = "stopped"
    save_soon()


# ------------------------------------------------------------------ tệp tải lên
def kind_of(name, mime=""):
    ext = os.path.splitext(name)[1].lower()
    if ext in (".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v") or mime.startswith("video"):
        return "video"
    if ext in (".mp3", ".wav", ".m4a", ".aac", ".ogg") or mime.startswith("audio"):
        return "audio"
    return "image"


def save_upload(name, data):
    name = re.sub(r"[^\w.\- ]", "_", os.path.basename(name or "file")) or "file"
    fid = uid("f")
    path = os.path.join(UPLOADS, f"{fid}_{name}")
    with open(path, "wb") as f:
        f.write(data)
    return {"id": fid, "name": name, "path": path, "type": kind_of(name), "size": len(data)}


def import_path(p):
    p = os.path.abspath(os.path.expanduser(p))
    if not os.path.isfile(p):
        raise ValueError("Không thấy tệp: " + p)
    fid = uid("f")
    path = os.path.join(UPLOADS, f"{fid}_{os.path.basename(p)}")
    shutil.copy2(p, path)
    return {"id": fid, "name": os.path.basename(p), "path": path, "type": kind_of(p), "size": os.path.getsize(path)}


def ffmpeg():
    for p in (os.path.join(HERE, "bin", "ffmpeg.exe"),):
        if os.path.exists(p):
            return p
    return shutil.which("ffmpeg")


def concat(files):
    ff = ffmpeg()
    if not ff:
        raise ValueError("Không có ffmpeg")
    files = [os.path.join(MEDIA, os.path.basename(f)) for f in files]
    lst = os.path.join(DATA, "concat.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in files:
            f.write("file '" + p.replace("\\", "/").replace("'", "'\\''") + "'\n")
    out_name = f"ghep_{int(now())}.mp4"
    out = os.path.join(MEDIA, out_name)
    cf = 0x08000000 if os.name == "nt" else 0
    r = subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], capture_output=True, creationflags=cf)
    if r.returncode != 0:
        r = subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out],
                           capture_output=True, creationflags=cf)
        if r.returncode != 0:
            raise ValueError("ffmpeg lỗi: " + r.stderr.decode("utf-8", "replace")[-300:])
    return out_name


# ------------------------------------------------------------------ HTTP
def public_message(m):
    return m


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LUOChat"

    def log_message(self, *a):
        pass

    # ---- tiện ích
    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def json_body(self):
        try:
            return json.loads(self.body().decode("utf-8") or "{}")
        except Exception:
            return {}

    def send_file(self, path, download_name=None):
        if not os.path.isfile(path):
            return self.send_json({"error": "not found"}, 404)
        size = os.path.getsize(path)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        start, end, code = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            try:
                start = int(a) if a else max(0, size - int(b))
                end = int(b) if (a and b) else size - 1
                end = min(end, size - 1)
                code = 206
            except ValueError:
                start, end, code = 0, size - 1, 200
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download_name:
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(download_name))
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 16, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def proxy_muse(self, method, path, query=""):
        """Chuyển /api/muse/<x> -> LUO-API /admin/<x> (chỉ nhóm tài khoản)."""
        sub = path[len("/api/muse/"):]
        if not re.fullmatch(r"accounts(/[\w\-]+){0,3}", sub):
            return self.send_json({"error": "không cho phép"}, 403)
        body = self.json_body() if method in ("POST", "PATCH", "PUT") else None
        try:
            return self.send_json(api(method, "/admin/" + sub + (("?" + query) if query else ""), body, timeout=180))
        except ApiError as e:
            return self.send_json({"error": str(e)}, 400)

    # ---- định tuyến
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        p, q = u.path, {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if p.startswith("/api/muse/"):
            return self.proxy_muse("GET", p, u.query)
        try:
            if p in ("/", "/index.html"):
                return self.send_file(os.path.join(UI, "index.html"))
            if p.startswith("/ui/"):
                f = os.path.normpath(os.path.join(UI, p[4:]))
                return self.send_file(f) if f.startswith(UI) else self.send_json({"error": "forbidden"}, 403)
            if p == "/api/poll":
                return self.send_json({"rev": REV["n"], "changed": str(REV["n"]) != q.get("rev"), "running": len(WORKING),
                                       "queued": sum(1 for c in CHATS.values() for m in c["messages"] if m.get("status") == "queued")})
            if p == "/api/chats":
                with LOCK:
                    items = sorted((summary(c) for c in CHATS.values()), key=lambda x: -x["updated"])
                return self.send_json({"rev": REV["n"], "chats": items})
            m = re.fullmatch(r"/api/chats/([\w]+)", p)
            if m:
                c = CHATS.get(m.group(1))
                return self.send_json(c) if c else self.send_json({"error": "not found"}, 404)
            if p == "/api/media-all":
                out = []
                with LOCK:
                    for c in CHATS.values():
                        for x in c["messages"]:
                            for md in x.get("media") or []:
                                out.append({**md, "chat": c["id"], "chat_title": c["title"], "msg": x["id"], "text": x["text"], "created": x.get("ended") or x["created"]})
                out.sort(key=lambda x: -x["created"])
                return self.send_json({"media": out})
            if p == "/api/settings":
                s = settings()
                s["api_key_set"] = bool(s.get("api_key"))
                s.pop("api_key", None)
                return self.send_json(s)
            if p == "/api/health":
                return self.send_json({"api": api_alive(), "api_url": settings()["api_url"], "running": len(WORKING), "data": DATA})
            if p == "/api/accounts":
                try:
                    st = api("GET", "/admin/status", timeout=15)
                    accs = [{"id": a["id"], "label": a.get("label") or a["id"], "status": a.get("status"), "enabled": a.get("enabled", True), "ok": a.get("ok"),
                             "note": a.get("note", ""), "quota": a.get("quota"), "video_count": a.get("video_count", 0), "expires_at": a.get("expires_at"),
                             "checked_at": a.get("checked_at"), "mail_email": a.get("mail_email", "")} for a in st.get("accounts", [])]
                    return self.send_json({"accounts": accs, "tasks": st.get("tasks", [])[:10]})
                except ApiError as e:
                    return self.send_json({"accounts": [], "error": str(e)})
            if p.startswith("/media/"):
                return self.send_file(os.path.join(MEDIA, os.path.basename(p[7:])))
            if p.startswith("/upload/"):
                return self.send_file(os.path.join(UPLOADS, os.path.basename(p[8:])))
            if p == "/api/zip":
                names = [os.path.basename(x) for x in q.get("files", "").split(",") if x]
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
                    for n in names:
                        fp = os.path.join(MEDIA, n)
                        if os.path.isfile(fp):
                            z.write(fp, n)
                b = buf.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", "attachment; filename=luo-chat-media.zip")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            return self.send_json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            return self.send_json({"error": str(e)}, 500)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        p = u.path
        if p.startswith("/api/muse/"):
            return self.proxy_muse("POST", p, u.query)
        try:
            if p == "/api/upload":
                name = urllib.parse.unquote(self.headers.get("X-Filename", "file"))
                return self.send_json(save_upload(name, self.body()))
            b = self.json_body()
            if p == "/api/chats":
                return self.send_json(new_chat(b.get("title") or "Cuộc trò chuyện mới", b.get("account", "")))
            m = re.fullmatch(r"/api/chats/(\w+)/send", p)
            if m:
                c = CHATS.get(m.group(1))
                if not c:
                    return self.send_json({"error": "not found"}, 404)
                text = (b.get("text") or "").strip()
                if not text:
                    return self.send_json({"error": "Prompt trống"}, 400)
                msg = add_message(c, text, b.get("kind", "video"), b.get("aspect", "9:16"), b.get("duration"), b.get("files") or [], by=b.get("by", "user"))
                return self.send_json(msg)
            if p == "/api/attach":   # đính một tệp đã có (video thành phẩm...) vào chat như một kết quả đã xong
                c = CHATS.get(b.get("chat") or "")
                src = b.get("file") or ""
                if not c or not os.path.isfile(src):
                    return self.send_json({"error": "chat/tệp không hợp lệ"}, 400)
                kind = b.get("kind", "video")
                msg = add_message(c, b.get("text") or os.path.basename(src), kind, b.get("aspect", "9:16"), None, [], by=b.get("by", "claude"), draft=True)
                name = f"{msg['id']}{os.path.splitext(src)[1] or '.mp4'}"
                shutil.copy2(src, os.path.join(MEDIA, name))
                msg.update({"status": "done", "progress": 100, "media": [{"file": name, "type": kind}], "ended": now()})
                save_soon()
                return self.send_json({"id": msg["id"], "file": name})
            if p == "/api/batch":   # dành cho Claude / script
                return self.send_json(do_batch(b))
            m = re.fullmatch(r"/api/messages/(\w+)/(stop|retry|run)", p)
            if m:
                mid, act = m.groups()
                chat, msg = find_msg(mid)
                if not msg:
                    return self.send_json({"error": "not found"}, 404)
                if act == "stop":
                    stop_msgs([mid])
                else:
                    if msg["status"] == "running":
                        return self.send_json({"error": "đang chạy"}, 400)
                    msg.update({"status": "queued", "progress": 0, "error": "", "attempts": 0 if act == "retry" else msg["attempts"]})
                    if act == "retry":
                        msg["avoid"] = []
                    save_soon()
                    schedule()
                return self.send_json({"ok": True})
            if p == "/api/run-drafts":
                n = 0
                for c in CHATS.values():
                    if b.get("chat") and c["id"] != b["chat"]:
                        continue
                    for msg in c["messages"]:
                        if msg["status"] == "draft":
                            msg["status"] = "queued"
                            n += 1
                save_soon()
                schedule()
                return self.send_json({"started": n})
            if p == "/api/stop-all":
                stop_msgs([x["id"] for c in CHATS.values() for x in c["messages"] if x["status"] in ("running", "queued")])
                return self.send_json({"ok": True})
            if p == "/api/retry-failed":
                n = 0
                for c in CHATS.values():
                    if b.get("chat") and c["id"] != b["chat"]:
                        continue
                    for msg in c["messages"]:
                        if msg["status"] in ("error", "stopped"):
                            msg.update({"status": "queued", "progress": 0, "error": "", "attempts": 0, "avoid": []})
                            n += 1
                save_soon()
                schedule()
                return self.send_json({"started": n})
            if p == "/api/settings":
                allowed = set(DEFAULTS)
                with LOCK:
                    for k, v in b.items():
                        if k in allowed and not (k == "api_key" and v == ""):
                            SETTINGS[k] = v
                    jwrite(os.path.join(DATA, "settings.json"), {k: SETTINGS[k] for k in SETTINGS if SETTINGS[k] != DEFAULTS.get(k)})
                bump()
                schedule()
                return self.send_json({"ok": True})
            if p == "/api/concat":
                return self.send_json({"file": concat(b.get("files") or [])})
            if p == "/api/open-folder":
                folder = MEDIA
                if os.name == "nt":
                    os.startfile(folder)  # noqa: S606
                return self.send_json({"ok": True, "path": folder})
            return self.send_json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            return self.send_json({"error": str(e)}, 400)

    def do_PATCH(self):
        if self.path.startswith("/api/muse/"):
            return self.proxy_muse("PATCH", urllib.parse.urlparse(self.path).path)
        pm = re.fullmatch(r"/api/messages/(\w+)", urllib.parse.urlparse(self.path).path)
        if pm:
            chat, msg = find_msg(pm.group(1))
            if not msg:
                return self.send_json({"error": "not found"}, 404)
            b = self.json_body()
            if msg["status"] == "running":
                return self.send_json({"error": "đang chạy"}, 400)
            if (b.get("text") or "").strip():
                msg["text"] = b["text"].strip()
            save_soon()
            return self.send_json({"ok": True})
        m = re.fullmatch(r"/api/chats/(\w+)", urllib.parse.urlparse(self.path).path)
        if not m or m.group(1) not in CHATS:
            return self.send_json({"error": "not found"}, 404)
        b = self.json_body()
        c = CHATS[m.group(1)]
        for k in ("title", "account"):
            if k in b:
                c[k] = b[k]
        save_soon()
        return self.send_json({"ok": True})

    def do_DELETE(self):
        p = urllib.parse.urlparse(self.path).path
        if p.startswith("/api/muse/"):
            return self.proxy_muse("DELETE", p)
        m = re.fullmatch(r"/api/chats/(\w+)", p)
        if m and m.group(1) in CHATS:
            stop_msgs([x["id"] for x in CHATS[m.group(1)]["messages"]])
            with LOCK:
                CHATS.pop(m.group(1), None)
            save_soon()
            return self.send_json({"ok": True})
        m = re.fullmatch(r"/api/messages/(\w+)", p)
        if m:
            chat, msg = find_msg(m.group(1))
            if msg:
                stop_msgs([msg["id"]])
                with LOCK:
                    chat["messages"].remove(msg)
                save_soon()
            return self.send_json({"ok": True})
        return self.send_json({"error": "not found"}, 404)


def do_batch(b):
    """b = {chat: id|None, title: str, by: 'claude', draft: bool, items: [{text, kind, aspect, duration, files:[đường dẫn]|[{path}]}], defaults:{...}}"""
    items = b.get("items") or []
    if not items:
        raise ValueError("Không có mục nào")
    d = b.get("defaults") or {}
    shared = [import_path(x["path"] if isinstance(x, dict) else x) for x in (b.get("files") or d.get("files") or [])]   # lỗi tệp thì dừng trước khi tạo cuộc trò chuyện
    chat = CHATS.get(b.get("chat") or "")
    if not chat:
        title = b.get("title") or "Lô tự động"
        chat = next((c for c in CHATS.values() if c["title"] == title and b.get("reuse", True)), None) or new_chat(title, b.get("account", ""))
    draft = bool(b.get("draft", SETTINGS.get("review_claude") if b.get("by") == "claude" else False))
    ids = []
    for it in items:
        if isinstance(it, str):
            it = {"text": it}
        files = shared + [import_path(x["path"] if isinstance(x, dict) else x) for x in (it.get("files") or [])]
        m = add_message(chat, it["text"], it.get("kind", d.get("kind", "video")), it.get("aspect", d.get("aspect", "9:16")),
                        it.get("duration", d.get("duration")), files, by=b.get("by", "claude"), draft=draft)
        ids.append(m["id"])
    return {"chat": chat["id"], "title": chat["title"], "added": len(ids), "draft": draft, "ids": ids}


def make_server(port=0):
    load()
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.daemon_threads = True
    threading.Thread(target=lambda: (time.sleep(1), schedule()), daemon=True).start()
    return srv


if __name__ == "__main__":
    s = make_server(int(os.environ.get("LUO_CHAT_PORT", "18620")))
    print("LUO Chat:", f"http://127.0.0.1:{s.server_address[1]}/", flush=True)
    s.serve_forever()
