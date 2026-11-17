"""upload - tải file kết quả lên thư mục Google Drive của bạn qua Apps Script (xem drive_upload.gs để cài).

  python upload.py <file> [<file> ...] --path 17-11/Z0200
Cấu hình trong daily_config.json: upload_url, upload_token, upload_folder_id. Thiếu cấu hình thì bỏ qua và báo "skipped".
"""
import argparse, base64, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))


def cfg():
    try:
        return json.load(open(os.path.join(ROOT, "daily_config.json"), encoding="utf-8"))
    except Exception:
        return {}


def upload(path, subpath):
    c = cfg()
    if not (c.get("upload_url") and c.get("upload_token") and c.get("upload_folder_id")):
        return {"ok": False, "skipped": True, "error": "chưa cấu hình upload_url / upload_token / upload_folder_id"}
    size = os.path.getsize(path)
    if size > 30 * 1024 * 1024:
        return {"ok": False, "error": f"file {size >> 20} MB vượt giới hạn 30 MB của Apps Script"}
    body = json.dumps({"token": c["upload_token"], "folderId": c["upload_folder_id"], "path": subpath, "name": os.path.basename(path),
                       "mime": "video/mp4" if path.lower().endswith(".mp4") else "application/octet-stream", "data": base64.b64encode(open(path, "rb").read()).decode()}).encode()
    req = urllib.request.Request(c["upload_url"], data=body, method="POST", headers={"Content-Type": "text/plain;charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:300]}


def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--path", default="")
    a = ap.parse_args()
    ok = True
    for f in a.files:
        r = upload(f, a.path)
        ok = ok and bool(r.get("ok"))
        print(json.dumps({"file": os.path.basename(f), **r}, ensure_ascii=False))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
