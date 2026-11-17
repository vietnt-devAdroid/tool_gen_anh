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

import sheetx

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(ROOT, "daily_config.json")
STATE_PATH = os.path.join(ROOT, "userdata", "daily_state.json")
UA = {"User-Agent": "Mozilla/5.0"}
DEFAULT_CFG = {"sheet_url": "", "tab_name": "Plan test_AI Photo", "tab_gid": "", "default_variants": 10, "out_root": "D:/ketqua", "sample_dir": "", "sample_drive_folder": "",
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


def drive_id(url):
    for pat in (r"/file/d/([\w-]+)", r"[?&]id=([\w-]+)"):
        m = re.search(pat, url or "")
        if m:
            return m.group(1)
    return None


def fetch_url(url, dest_base):
    """Tải file từ link Drive (file công khai) hoặc link ảnh/video trực tiếp; trả đường dẫn file (có đuôi theo loại nội dung)."""
    fid = drive_id(url)
    real = f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t" if fid else url
    resp = get(real, timeout=300)
    ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if "html" in ctype:
        raise RuntimeError("Drive trả về trang web thay vì file: file chưa chia sẻ công khai (ai có link đều xem được) hoặc link sai")
    ext = {"video/mp4": ".mp4", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif", "video/quicktime": ".mov", "video/webm": ".webm"}.get(ctype)
    if not ext:
        ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or (".mp4" if "video" in ctype else ".bin")
    dest = dest_base + ext
    with open(dest, "wb") as f:
        while True:
            b = resp.read(1 << 20)
            if not b:
                break
            f.write(b)
    return dest


def sheet_links(c):
    """Link ẩn sau chữ trong ô (Sample...), công thức IMAGE()/HYPERLINK(), ảnh thả nổi (Ảnh after): đọc từ XLSX xuất của sheet. Trả (cells, images, header_row)."""
    sid = sheet_id(c["sheet_url"])
    url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=xlsx" + (f"&gid={c['tab_gid']}" if c.get("tab_gid") else "")
    data = get(url, timeout=120).read()
    cells, images = sheetx.load(data, None if c.get("tab_gid") else c["tab_name"])
    header_row = next((int(re.sub(r"\D", "", k)) for k, v in cells.items() if norm(v["text"]) == "ma order"), 1)
    return cells, images, header_row


def row_of_code(cells, code_col, code, header_row):
    """Số dòng trong XLSX của hàng có Mã order = code (tìm theo mã, không phụ thuộc lệch dòng giữa CSV và XLSX)."""
    for n in range(header_row + 1, header_row + 1000):
        v = cells.get(f"{sheetx.col_letter(code_col)}{n}")
        if v and v["text"].strip() == code:
            return n
    return None


def cell_ref(col_idx, row):
    return f"{sheetx.col_letter(col_idx)}{row}"


def download(date):
    res = check(date)
    if not res["tab_exists"] or not res["ready"]:
        return res
    c = cfg()
    try:
        cells, images, header_row = sheet_links(c)
    except Exception as e:  # noqa: BLE001
        cells, images, header_row = {}, {}, 1
        res["warning"] = f"không đọc được link ẩn trong ô (xlsx): {e}"
    head = [norm(x) for x in next(csv.reader(io.StringIO(fetch_tab(sheet_id(c["sheet_url"]), c["tab_name"]))))]
    col = {k: next((i for i, h in enumerate(head) if any(p in h for p in pats)), None) for k, pats in COLS.items()}
    res["downloads"] = []
    for r in res["rows"]:
        if not r["ready"] or r["processed"]:
            continue
        row_no = row_of_code(cells, col["code"], r["code"], header_row) or (header_row + r["row"] - 1)
        folder = os.path.join(c["out_root"], f"{date.day:02d}-{date.month:02d}", r["folder_name"])
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, "source.mp4")
        item = {"code": r["code"], "name": r["name"], "sample": r["sample"], "folder": folder.replace("\\", "/"), "request": r["request_clean"], "request_raw": r["request"],
                "variants": r["variants"], "character": r["character"], "hook": r["hook"], "language": r["language"], "before": r["before"], "angle": r["angle"], "concept": r["concept"]}
        # --- video mẫu: file có sẵn -> thư mục máy (sample_dir) -> link Drive ẩn sau ô Sample
        try:
            if os.path.exists(dest) and os.path.getsize(dest) > 1000:
                item.update(ok=True, path=dest.replace("\\", "/"))
            else:
                local = None
                d = c.get("sample_dir")
                if d and os.path.isdir(d):
                    for root, _, files in os.walk(d):
                        for f in files:
                            if f.lower() == r["sample"].lower():
                                local = os.path.join(root, f)
                if local:
                    shutil.copy2(local, dest)
                    item.update(ok=True, path=dest.replace("\\", "/"), from_=local.replace("\\", "/"))
                else:
                    link = sheetx.find_url(cells.get(cell_ref(col["sample"], row_no))) if col.get("sample") is not None else ""
                    if not link:
                        raise RuntimeError(f"ô Sample '{r['sample']}' không có link (cần link Drive hoặc cấu hình sample_dir)")
                    if not drive_id(link):
                        raise RuntimeError(f"Sample là link ngoài Drive ({link[:60]}): chưa hỗ trợ tải tự động, cần file video trên Drive")
                    p = fetch_url(link, os.path.join(folder, "source"))
                    if p != dest:
                        shutil.move(p, dest)
                    item.update(ok=True, path=dest.replace("\\", "/"), sample_link=link)
        except Exception as e:  # noqa: BLE001
            item.update(ok=False, error=str(e)[:200])
        # --- ảnh AFTER mẫu: cột "Ảnh after" (link ẩn / URL / =IMAGE() / ảnh thả nổi trên ô)
        item["after_sample"] = None
        if col.get("after") is not None:
            ref = cell_ref(col["after"], row_no)
            try:
                img = images.get((sheetx.col_letter(col["after"]), row_no))
                if img:
                    p = os.path.join(folder, "after_sample" + img[1])
                    open(p, "wb").write(img[0])
                    item["after_sample"] = p.replace("\\", "/")
                else:
                    link = sheetx.find_url(cells.get(ref))
                    if link:
                        item["after_sample"] = fetch_url(link, os.path.join(folder, "after_sample")).replace("\\", "/")
                        item["after_link"] = link
                    elif r["after"]:
                        item["after_note"] = f"ô Ảnh after có chữ '{r['after'][:40]}' nhưng không có link/ảnh đọc được"
            except Exception as e:  # noqa: BLE001
                item["after_error"] = str(e)[:200]
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
