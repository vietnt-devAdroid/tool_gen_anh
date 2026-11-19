"""characters - bộ nhân vật dùng làm ảnh BEFORE (danh tính + trang phục) khi tạo ảnh after cho loại IMAGE TO IMAGE.

Thư mục bộ nhân vật (mặc định D:/180 nhan vat Photo, đổi bằng "characters_dir" trong daily_config.json hoặc biến môi trường LUO_CHARACTERS_DIR):
  mỗi thư mục con = MỘT MÃ, tên dạng  V04_Au-My_Nu_20-35  (mã = phần trước dấu _ đầu tiên: V01..V18)
  trong đó 10 ảnh nhân vật (ảnh toàn thân do Muse tạo, nền trắng).  Khu vực: Au-My / Latin / India; Nam / Nu; nhóm tuổi 20-35 / 40-60 / 5-6.
Sau mỗi video người dùng cho MÃ nhân vật (vd V04): dùng các ảnh trong thư mục đó làm ảnh BEFORE cho các biến thể.

  python characters.py list                 liệt kê các mã
  python characters.py show V04             mô tả mã + danh sách ảnh
  python characters.py pick V04 20          chọn 20 ảnh luân phiên (JSON), mỗi nhân vật dùng lại khi vượt 10
Nhóm tuổi 5-6 là TRẺ EM: theo quy tắc nội dung KHÔNG dùng làm chủ thể; pick sẽ từ chối.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
REGION = {"au-my": "Western (European / North American)", "latin": "Latin American", "india": "Indian"}
GENDER = {"nam": "male", "nu": "female"}


def characters_dir():
    d = os.environ.get("LUO_CHARACTERS_DIR")
    if not d:
        try:
            d = json.load(open(os.path.join(ROOT, "daily_config.json"), encoding="utf-8")).get("characters_dir")
        except Exception:
            d = None
    return d or r"D:\180 nhan vat Photo"


def codes():
    base, out = characters_dir(), {}
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        m = re.match(r"^(V\d+)_(.+?)_(Nam|Nu)_(\d+)-(\d+)$", name, flags=re.I)
        p = os.path.join(base, name)
        if not m or not os.path.isdir(p):
            continue
        code, region, gender, a0, a1 = m.group(1).upper(), m.group(2), m.group(3), int(m.group(4)), int(m.group(5))
        files = sorted(os.path.join(p, f) for f in os.listdir(p) if f.lower().endswith((".webp", ".png", ".jpg", ".jpeg")))
        out[code] = {"code": code, "folder": p, "region": region, "gender": gender, "age": [a0, a1], "child": a1 < 18, "files": files,
                     "describe": f"{REGION.get(region.lower(), region)} {GENDER.get(gender.lower(), gender)}, aged {a0}-{a1}"}
    return out


def pick(code, n, offset=0, allow_child=False):
    """n ảnh nhân vật của mã 'code', luân phiên theo thứ tự (nhân vật 1,2,...,10,1,2,...)."""
    c = codes().get(code.upper())
    if not c:
        raise SystemExit(f"Không thấy mã nhân vật '{code}' trong {characters_dir()}. Các mã có: {', '.join(codes()) or '(thư mục trống)'}")
    if c["child"] and not allow_child:
        raise SystemExit(f"Mã {c['code']} là nhóm trẻ em ({c['age'][0]}-{c['age'][1]} tuổi): theo quy tắc nội dung không dùng trẻ em làm chủ thể. Hãy chọn mã người trưởng thành.")
    if not c["files"]:
        raise SystemExit(f"Thư mục {c['folder']} không có ảnh.")
    return [c["files"][(offset + i) % len(c["files"])] for i in range(n)]


def main():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    a = sys.argv[1:]
    if not a or a[0] == "list":
        for c in codes().values():
            print(f"{c['code']}  {c['describe']:55}  {len(c['files'])} ảnh{'  [TRẺ EM - không dùng]' if c['child'] else ''}")
    elif a[0] == "show" and len(a) > 1:
        c = codes().get(a[1].upper())
        print(json.dumps(c, ensure_ascii=False, indent=1) if c else "không thấy mã")
    elif a[0] == "pick" and len(a) > 2:
        print(json.dumps(pick(a[1], int(a[2]), int(a[3]) if len(a) > 3 else 0), ensure_ascii=False, indent=1))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
