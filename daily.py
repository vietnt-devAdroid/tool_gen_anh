"""daily - đọc tab kế hoạch trong Google Sheet, lấy các hàng của ngày hôm nay, tìm video mẫu (Sample) để làm biến thể.

Cấu trúc sheet (tab "Plan test_AI Photo", MỘT tab chung, cột nhận theo tên tiêu đề, không phân biệt hoa thường/dấu):
  Ngày order      = ngày cần làm (vd 17/11)          Mã order    = mã video làm (vd Z00126)
  Tên video       = tên video                         Sample      = video mẫu (tên file, vd Z00126.mp4)
  Yêu cầu biến thể= kiểu biến thể (vd "Thay đổi nhân vật")   Nhân vật = mô tả nhân vật cần dùng
  Ảnh before      = nguồn ảnh before (tự gen / ...)  Hook / Ngôn ngữ = hook, ngôn ngữ lồng tiếng mới
  Số lượng dự kiến= SỐ VIDEO cần tạo                  Status / Link hoàn thành / ... (chỉ đọc)
Tên file kết quả: <Mã order>_<Tên video>_<số thứ tự>.mp4 (không có Tên video thì dùng Mã order + tên Sample).

  python daily.py check    [--date 2026-11-17]   -> JSON: các hàng của ngày, hàng nào sẵn sàng (có Mã order + Sample), đã xử lý chưa
  python daily.py download [--date ...]          -> tìm/tải video mẫu của các hàng sẵn sàng vào <out_root>/<dd-mm>/<mã>_<tên>/source.mp4
  python daily.py done  <YYYY-MM-DD> <mã order> [ghi chú]    -> đánh dấu đã xong (lần sau không làm lại)
  python daily.py fail  <YYYY-MM-DD> <mã order> <lý do>      -> ghi lỗi (vẫn cho chạy lại)
  python daily.py config
Cấu hình daily_config.json: sheet_url, tab_name, default_variants, out_root, sample_dir (thư mục máy chứa video mẫu) / sample_drive_folder (link thư mục Drive),
                           upload_url, upload_token, upload_folder_id.
"""
import argparse, csv, datetime, io, json, os, re, shutil, sys, unicodedata, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(ROOT, "daily_config.json")
STATE_PATH = os.path.join(ROOT, "userdata", "daily_state.json")
UA = {"User-Agent": "Mozilla/5.0"}
DEFAULT_CFG = {"sheet_url": "", "tab_name": "Plan test_AI Photo", "default_variants": 10, "out_root": "D:/ketqua", "sample_dir": "", "sample_drive_folder": "",
               "upload_url": "", "upload_token": "", "upload_folder_id": ""}
# khoá logic -> các cụm từ (đã bỏ dấu, chữ thường) nhận diện tiêu đề cột
COLS = {"date": ["ngay order"], "code": ["ma order"], "concept": ["concept"], "angle": ["angle"], "insight": ["insight"], "name": ["ten video"], "sample": ["sample"],
        "level": ["level"], "request": ["yeu cau bien the", "yeu cau"], "character": ["nhan vat"], "hook": ["hook"], "language": ["ngon ngu"], "before": ["anh before"],
        "after": ["anh after"], "qty": ["so luong du kien"], "qty_done": ["so luong thuc dat"], "status": ["status"], "link_done": ["link hoan thanh"]}


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


def fetch_tab(sid, tab):
    """CSV của tab. gviz âm thầm trả tab đầu khi tên sai: nếu nội dung trùng tab 'mặc định' thì coi như tab không tồn tại (trừ khi tab đó thật sự là tab đầu)."""
    q = lambda name: f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(name)}"
    try:
        body = get(q(tab)).read().decode("utf-8-sig", "replace")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Không đọc được sheet (HTTP {e.code}). Kiểm tra sheet đã chia sẻ 'bất kỳ ai có link' chưa.")
    if "<html" in body[:200].lower():
        raise SystemExit("Sheet trả về trang đăng nhập: chưa chia sẻ công khai (bất kỳ ai có link đều xem được).")
    fallback = get(q("__khong_ton_tai__")).read().decode("utf-8-sig", "replace")
    return None if body == fallback and body.strip() else body


def parse_date(text, default_year):
    """'17/11', '17/11/2026', '17-11' -> (ngày, tháng) hoặc None."""
    m = re.match(r"\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})(?:\s*[/\-.]\s*(\d{2,4}))?\s*$", str(text or ""))
    if not m:
        return None
    d, mo = int(m[1]), int(m[2])
    return (d, mo) if 1 <= d <= 31 and 1 <= mo <= 12 else None


def clean_request(req):
    """Cột 'Yêu cầu biến thể / Nguồn' đôi khi chứa ghi chú nguồn ('Lấy từ Social Peta...'): khi đó yêu cầu mặc định là thay đổi nhân vật."""
    r = (req or "").strip()
    if not r or re.match(r"(?i)\s*(l[aấ]y|social|ngu[oồ]n)", r):
        return "Thay đổi nhân vật"
    return r


def parse_plan(body):
    rows = list(csv.reader(io.StringIO(body)))
    if not rows:
        return []
    head = [norm(c) for c in rows[0]]
    idx = {}
    for key, pats in COLS.items():
        for p in pats:
            i = next((n for n, h in enumerate(head) if p in h), None)
            if i is not None:
                idx[key] = i
                break
    if "date" not in idx or "code" not in idx or "sample" not in idx:
        raise SystemExit("Không tìm thấy các cột Ngày order / Mã order / Sample trong tab (đổi tiêu đề cột?)")
    out = []
    for n, r in enumerate(rows[1:], start=2):
        cell = lambda k: (r[idx[k]].strip().replace("\n", " ") if k in idx and idx[k] < len(r) else "")
        rec = {k: cell(k) for k in COLS}
        rec["row"] = n
        out.append(rec)
    return out


def variants_of(rec, default):
    m = re.search(r"\d+", rec.get("qty", "") or "")
    return int(m.group(0)) if m else default


def safe(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s).strip("_")


def check(date):
    c = cfg()
    if not c["sheet_url"]:
        raise SystemExit("Chưa có sheet_url trong daily_config.json")
    sid = sheet_id(c["sheet_url"])
    body = fetch_tab(sid, c["tab_name"])
    if body is None:
        return {"date": str(date), "tab": c["tab_name"], "tab_exists": False, "rows": [], "ready": False, "reason": f"không có tab '{c['tab_name']}'"}
    st = state().get(str(date), {})
    rows = []
    for rec in parse_plan(body):
        if parse_date(rec["date"], date.year) != (date.day, date.month) or not (rec["code"] or rec["sample"]):
            continue
        rec["variants"] = variants_of(rec, c["default_variants"])
        rec["request_clean"] = clean_request(rec["request"])
        rec["ready"] = bool(rec["code"] and rec["sample"])
        rec["processed"] = st.get(rec["code"], {}).get("status") == "done"
        rec["folder_name"] = safe(f"{rec['code']}_{rec['name']}" if rec["name"] else rec["code"])
        rows.append(rec)
    pending = [r for r in rows if r["ready"] and not r["processed"]]
    waiting = [r["code"] for r in rows if not r["ready"] and not r["processed"]]
    reason = "" if pending else ("hôm nay không có hàng nào" if not rows else "chưa hàng nào có Sample" if not any(r["ready"] for r in rows) else "tất cả hàng đã có Sample đều xử lý xong")
    return {"date": str(date), "tab": c["tab_name"], "tab_exists": True, "rows": rows, "pending": len(pending), "waiting_no_sample": waiting, "ready": bool(pending), "reason": reason}


def find_sample(name, c):
    d = c.get("sample_dir")
    if d and os.path.isdir(d):
        want = name.lower()
        for root, _, files in os.walk(d):
            for f in files:
                if f.lower() == want or os.path.splitext(f)[0].lower() == os.path.splitext(want)[0]:
                    return os.path.join(root, f)
    return None


def download(date):
    res = check(date)
    if not res["tab_exists"] or not res["ready"]:
        return res
    c = cfg()
    res["downloads"] = []
    for r in res["rows"]:
        if not r["ready"] or r["processed"]:
            continue
        folder = os.path.join(c["out_root"], f"{date.day:02d}-{date.month:02d}", r["folder_name"])
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, "source.mp4")
        item = {"code": r["code"], "name": r["name"], "sample": r["sample"], "folder": folder.replace("\\", "/"), "request": r["request_clean"], "request_raw": r["request"],
                "variants": r["variants"], "character": r["character"], "hook": r["hook"], "language": r["language"], "before": r["before"], "angle": r["angle"], "concept": r["concept"]}
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            item.update(ok=True, path=dest.replace("\\", "/"))
        else:
            src = find_sample(r["sample"], c)
            if src:
                shutil.copy2(src, dest)
                item.update(ok=True, path=dest.replace("\\", "/"), from_=src.replace("\\", "/"))
            elif re.match(r"https?://", r["sample"]):
                item.update(ok=False, error="Sample là URL (TikTok/Facebook...): chưa hỗ trợ tải tự động, cần file video")
            else:
                item.update(ok=False, error=f"không tìm thấy file '{r['sample']}' (cần cấu hình sample_dir hoặc sample_drive_folder)")
        res["downloads"].append(item)
    return res


def mark(date, code, status, note=""):
    st = state()
    st.setdefault(date, {})[code] = {"status": status, "note": note, "at": datetime.datetime.now().isoformat(timespec="seconds")}
    save_state(st)
    print(json.dumps({"ok": True, "code": code, "status": status}, ensure_ascii=False))


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
