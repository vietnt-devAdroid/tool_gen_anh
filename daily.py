"""daily - đọc Google Sheet (mỗi ngày một tab, ví dụ "17-11"), kiểm tra đã điền chưa, tải video mẫu về máy.

Sheet phải đặt chế độ "Bất kỳ ai có đường liên kết đều xem được"; file video trên Drive cũng vậy.
Cột (nhận theo tên tiêu đề, không phân biệt hoa thường/dấu): tên video | link | yêu cầu. Nếu không có hàng tiêu đề thì lấy 3 cột đầu.

  python daily.py check    [--date 2026-11-17]    -> JSON: tab có không, các hàng, hàng nào đã đủ 3 cột, hàng nào đã xử lý
  python daily.py download [--date ...]           -> tải video của các hàng ĐỦ + CHƯA xử lý vào <out_root>/<ngày>/<tên>/source.mp4, in JSON
  python daily.py done  <ngày> <tên> [ghi chú]    -> đánh dấu hàng đã xử lý xong (để lần sau không chạy lại)
  python daily.py fail  <ngày> <tên> <lý do>      -> ghi lỗi (vẫn cho chạy lại lần sau)
  python daily.py config                          -> in cấu hình
Cấu hình: daily_config.json cạnh file này (sheet_url, tab_format, default_variants, out_root, upload_url, upload_token).
"""
import argparse, csv, datetime, hashlib, io, json, os, re, sys, urllib.error, urllib.parse, urllib.request, unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(ROOT, "daily_config.json")
STATE_PATH = os.path.join(ROOT, "userdata", "daily_state.json")
UA = {"User-Agent": "Mozilla/5.0"}
DEFAULT_CFG = {"sheet_url": "", "tab_format": "%d-%m", "default_variants": 10, "out_root": "D:/ketqua", "upload_url": "", "upload_token": ""}


def cfg():
    c = dict(DEFAULT_CFG)
    try:
        c.update(json.load(open(CFG_PATH, encoding="utf-8")))
    except Exception:
        pass
    return c


def state():
    try:
        return json.load(open(STATE_PATH, encoding="utf-8"))
    except Exception:
        return {}


def save_state(s):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    json.dump(s, open(STATE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def norm(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn").replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)


def sheet_id(url):
    m = re.search(r"/spreadsheets/d/([\w-]+)", url)
    if not m:
        raise SystemExit("sheet_url không đúng dạng https://docs.google.com/spreadsheets/d/<ID>/...")
    return m.group(1)


def list_tabs(sid):
    """Tên các tab của sheet (đọc từ trang htmlview/edit). Trả [] nếu không đọc được."""
    names = []
    for suffix in ("/htmlview", "/edit"):
        try:
            html = get(f"https://docs.google.com/spreadsheets/d/{sid}{suffix}").read().decode("utf-8", "replace")
        except Exception:
            continue
        names += [re.sub(r"<[^>]+>", "", n).strip() for n in re.findall(r'id="sheet-button-\d+"[^>]*>\s*<a[^>]*>(.*?)</a>', html, flags=re.S)]
        names += re.findall(r'"name":"([^"]{1,60})","gid"', html)
        names += re.findall(r'\\"title\\":\\"([^"\\]{1,60})\\",\\"sheetId', html)
        if names:
            break
    seen, out = set(), []
    for n in names:
        n = n.encode().decode("unicode_escape", "ignore") if "\\u" in n else n
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def fetch_tab(sid, tab):
    """CSV của tab (None nếu tab không tồn tại). gviz âm thầm trả tab đầu khi tên sai, nên so với tab 'mặc định' để phát hiện."""
    q = lambda name: f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(name)}"
    try:
        body = get(q(tab)).read().decode("utf-8-sig", "replace")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Không đọc được sheet (HTTP {e.code}). Kiểm tra sheet đã chia sẻ 'bất kỳ ai có link' chưa.")
    if "<html" in body[:200].lower():
        raise SystemExit("Sheet trả về trang đăng nhập: chưa chia sẻ công khai (bất kỳ ai có link đều xem được).")
    tabs = list_tabs(sid)
    if tabs:
        return body if tab in tabs else None
    fallback = get(q("__khong_ton_tai__")).read().decode("utf-8-sig", "replace")   # tab sai -> gviz trả tab đầu tiên
    return None if body == fallback and body.strip() else body


def parse_rows(body):
    rows = [r for r in csv.reader(io.StringIO(body))]
    if not rows:
        return []
    head = [norm(c) for c in rows[0]]

    def col(*keys):
        for i, h in enumerate(head):
            if any(k in h for k in keys):
                return i
        return None
    ci = [col("ten video", "ten", "name", "video"), col("link", "url", "duong dan"), col("yeu cau", "request", "note", "mo ta")]
    if None in ci or len(set(ci)) < 3:
        ci, data = [0, 1, 2], rows           # không có tiêu đề: 3 cột đầu
    else:
        data = rows[1:]
    out = []
    for n, r in enumerate(data, start=2 if data is not rows else 1):
        cell = lambda k: (r[ci[k]].strip() if ci[k] < len(r) else "")
        name, link, req = cell(0), cell(1), cell(2)
        if not (name or link or req):
            continue
        out.append({"row": n, "name": name, "link": link, "request": req, "complete": bool(name and link and req)})
    return out


def file_id(link):
    for pat in (r"/file/d/([\w-]+)", r"[?&]id=([\w-]+)", r"/d/([\w-]+)"):
        m = re.search(pat, link)
        if m:
            return m.group(1)
    return None


def row_key(r):
    return hashlib.sha1(f"{r['name']}|{r['link']}|{r['request']}".encode()).hexdigest()[:12]


def variants_in(req, default):
    m = re.search(r"(\d{1,2})\s*(?:biến thể|bien the|variant|bản|ban)", req, flags=re.I)
    return int(m.group(1)) if m else default


def check(date):
    c = cfg()
    if not c["sheet_url"]:
        raise SystemExit("Chưa có sheet_url trong daily_config.json")
    sid, tab = sheet_id(c["sheet_url"]), date.strftime(c["tab_format"]).lstrip("0")
    cand = [date.strftime(c["tab_format"]), tab, date.strftime(c["tab_format"]).replace("-0", "-")]
    body = None
    for t in dict.fromkeys(cand):
        body = fetch_tab(sid, t)
        if body is not None:
            tab = t
            break
    if body is None:
        return {"date": str(date), "tab": tab, "tab_exists": False, "rows": [], "ready": False, "reason": f"chưa có tab '{tab}'"}
    rows = parse_rows(body)
    st = state()
    for r in rows:
        r["key"] = row_key(r)
        r["processed"] = st.get(str(date), {}).get(r["key"], {}).get("status") == "done"
        r["variants"] = variants_in(r["request"], c["default_variants"])
        r["file_id"] = file_id(r["link"]) if r["link"] else None
    complete = [r for r in rows if r["complete"]]
    partial = [r for r in rows if not r["complete"]]
    pending = [r for r in complete if not r["processed"]]
    ready = bool(pending) and not partial
    reason = "" if ready else ("tab trống" if not rows else "có hàng chưa điền đủ 3 cột" if partial else "tất cả đã xử lý")
    return {"date": str(date), "tab": tab, "tab_exists": True, "rows": rows, "pending": len(pending), "ready": ready, "reason": reason}


def download(date):
    res = check(date)
    if not res["tab_exists"] or not res.get("ready"):
        return res
    out_root = cfg()["out_root"]
    res["downloads"] = []
    for r in res["rows"]:
        if not r["complete"] or r["processed"]:
            continue
        folder = os.path.join(out_root, str(date), re.sub(r'[\\/:*?"<>|]+', "_", r["name"]))
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, "source.mp4")
        if not r["file_id"]:
            res["downloads"].append({"name": r["name"], "ok": False, "error": "link không phải link file Drive (cần dạng drive.google.com/file/d/<ID>/view, không phải link thư mục)"})
            continue
        if not os.path.exists(dest) or os.path.getsize(dest) < 1000:
            try:
                url = f"https://drive.usercontent.google.com/download?id={r['file_id']}&export=download&confirm=t"
                resp = get(url, timeout=300)
                ctype = resp.headers.get("Content-Type", "")
                if "html" in ctype:
                    raise RuntimeError("Drive trả về trang web thay vì video: file chưa chia sẻ công khai hoặc quá lớn")
                with open(dest, "wb") as f:
                    while True:
                        b = resp.read(1 << 20)
                        if not b:
                            break
                        f.write(b)
            except Exception as e:  # noqa: BLE001
                if os.path.exists(dest):
                    os.remove(dest)
                res["downloads"].append({"name": r["name"], "ok": False, "error": str(e)[:200]})
                continue
        res["downloads"].append({"name": r["name"], "ok": True, "path": dest.replace("\\", "/"), "folder": folder.replace("\\", "/"), "request": r["request"], "variants": r["variants"], "key": r["key"]})
    return res


def mark(date, name, status, note=""):
    res = check(datetime.date.fromisoformat(date))
    key = next((r["key"] for r in res["rows"] if r["name"] == name), None)
    if not key:
        raise SystemExit("Không thấy hàng tên: " + name)
    st = state()
    st.setdefault(date, {})[key] = {"name": name, "status": status, "note": note, "at": datetime.datetime.now().isoformat(timespec="seconds")}
    save_state(st)
    print(json.dumps({"ok": True, "key": key, "status": status}, ensure_ascii=False))


def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "download", "done", "fail", "config"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--date", default=None)
    a = ap.parse_args()
    date = datetime.date.fromisoformat(a.date) if a.date else datetime.date.today()
    if a.cmd == "config":
        print(json.dumps(cfg(), ensure_ascii=False, indent=1))
    elif a.cmd == "check":
        print(json.dumps(check(date), ensure_ascii=False, indent=1))
    elif a.cmd == "download":
        print(json.dumps(download(date), ensure_ascii=False, indent=1))
    elif a.cmd in ("done", "fail"):
        mark(a.args[0], a.args[1], "done" if a.cmd == "done" else "failed", " ".join(a.args[2:]))


if __name__ == "__main__":
    main()
