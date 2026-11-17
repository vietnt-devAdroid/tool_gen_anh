"""chatctl - điều khiển LUO Chat từ dòng lệnh (dành cho Claude hoặc script).

  chatctl.py add "mô tả video" [--kind video|image|chat] [--aspect 9:16] [--duration 6] [--video a.mp4] [--image b.png] [--title "Tên lô"] [--draft]
  chatctl.py batch prompts.json|-   JSON: {"title":"...", "defaults":{"aspect":"9:16"}, "files":["ref.mp4"], "items":["prompt 1", {"text":"prompt 2","files":["x.png"]}]}
                                     hoặc chỉ là mảng ["prompt 1", ...]
  chatctl.py status                  tổng quan hàng đợi và các cuộc trò chuyện
  chatctl.py chat <id|tiêu đề>       chi tiết từng yêu cầu (trạng thái, lỗi, tệp kết quả)
  chatctl.py run-drafts | retry-failed | stop
Địa chỉ máy chủ: lấy từ userdata/chat/running.json, hoặc biến LUO_CHAT_URL.
"""
import argparse, json, os, sys, urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = os.path.dirname(os.path.abspath(__file__))


def base():
    if os.environ.get("LUO_CHAT_URL"):
        return os.environ["LUO_CHAT_URL"].rstrip("/")
    try:
        return json.load(open(os.path.join(ROOT, "userdata", "chat", "running.json"), encoding="utf-8"))["url"].rstrip("/")
    except Exception:
        sys.exit("LUO Chat chưa chạy. Mở 'LUO Chat.bat' trước (hoặc đặt LUO_CHAT_URL).")


def call(path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base() + path, data=data, method=method or ("POST" if body is not None else "GET"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit("Lỗi: " + e.read().decode("utf-8", "replace"))


def find_chat(key):
    for c in call("/api/chats")["chats"]:
        if c["id"] == key or c["title"] == key:
            return c["id"]
    sys.exit("Không thấy cuộc trò chuyện: " + key)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("add")
    a.add_argument("text")
    a.add_argument("--kind", default="video")
    a.add_argument("--aspect", default="9:16")
    a.add_argument("--duration", type=int)
    a.add_argument("--video", action="append", default=[])
    a.add_argument("--image", action="append", default=[])
    a.add_argument("--title", default="Lô tự động")
    a.add_argument("--draft", action="store_true")
    b = sp.add_parser("batch")
    b.add_argument("file")
    b.add_argument("--draft", action="store_true")
    sp.add_parser("status")
    c = sp.add_parser("chat")
    c.add_argument("key")
    for n in ("run-drafts", "retry-failed", "stop"):
        sp.add_parser(n)
    x = ap.parse_args()
    if x.cmd == "add":
        body = {"title": x.title, "by": "claude", "defaults": {"kind": x.kind, "aspect": x.aspect, "duration": x.duration},
                "items": [{"text": x.text, "files": [os.path.abspath(f) for f in x.video + x.image]}]}
        if x.draft:
            body["draft"] = True
        print(json.dumps(call("/api/batch", body), ensure_ascii=False))
    elif x.cmd == "batch":
        raw = sys.stdin.read() if x.file == "-" else open(x.file, encoding="utf-8").read()
        data = json.loads(raw)
        body = {"items": data} if isinstance(data, list) else data
        body["by"] = "claude"
        if x.draft:
            body["draft"] = True
        print(json.dumps(call("/api/batch", body), ensure_ascii=False))
    elif x.cmd == "status":
        p = call("/api/poll")
        print(f"Đang chạy: {p['running']} · chờ: {p['queued']}")
        for c in call("/api/chats")["chats"]:
            n = c["counts"]
            print(f"{c['id']}  {c['title'][:40]:40}  chạy {n['running']} · chờ {n['queued']} · duyệt {n['draft']} · lỗi {n['error']} · xong {n['done']}")
    elif x.cmd == "chat":
        c = call("/api/chats/" + find_chat(x.key))
        for m in c["messages"]:
            print(f"{m['id']} [{m['status']:7}] {m['kind']} {m['aspect']} {m['text'][:70]!r} {m['error'][:80] if m['error'] else ''} {','.join(i['file'] for i in m['media'])}")
    elif x.cmd == "run-drafts":
        print(call("/api/run-drafts", {}))
    elif x.cmd == "retry-failed":
        print(call("/api/retry-failed", {}))
    elif x.cmd == "stop":
        print(call("/api/stop-all", {}))


if __name__ == "__main__":
    main()
