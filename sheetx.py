"""sheetx - đọc thêm từ file XLSX xuất của Google Sheet (công khai): link ẩn sau chữ, công thức =IMAGE("url")/=HYPERLINK(), ảnh thả nổi trên ô.
CSV không có các thứ này. Chỉ dùng thư viện chuẩn.

  cells, images = load(xlsx_bytes)           cells: {"O5": {"text":..., "formula":..., "link":...}}   images: {("O",5): (bytes, ".png")}
  find_url(cell)                             URL đầu tiên trong ô (link ẩn / IMAGE() / HYPERLINK() / chữ)
"""
import io, posixpath, re, zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing", "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
RID = "{%s}id" % NS["r"]
EMBED = "{%s}embed" % NS["r"]


def col_letter(i):
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _rels(z, path):
    d, f = posixpath.split(path)
    rp = posixpath.join(d, "_rels", f + ".rels")
    out = {}
    if rp in z.namelist():
        for rel in ET.fromstring(z.read(rp)).findall("rel:Relationship", NS):
            tgt = rel.get("Target")
            out[rel.get("Id")] = (tgt if rel.get("TargetMode") == "External" else posixpath.normpath(posixpath.join(d, tgt)) if not tgt.startswith("/") else tgt.lstrip("/"))
    return out


def load(data, sheet_name=None):
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    wrels = _rels(z, "xl/workbook.xml")
    sheets = wb.findall("m:sheets/m:sheet", NS)
    sheet = next((x for x in sheets if x.get("name") == sheet_name), sheets[0]) if sheet_name else sheets[0]
    spath = wrels[sheet.get(RID)]
    root = ET.fromstring(z.read(spath))
    srels = _rels(z, spath)
    cells = {}
    for c in root.iter("{%s}c" % NS["m"]):
        ref = c.get("r")
        v, f = c.find("m:v", NS), c.find("m:f", NS)
        text = ""
        if c.get("t") == "s" and v is not None:
            text = shared[int(v.text)]
        elif c.get("t") == "inlineStr":
            text = "".join(t.text or "" for t in c.iter("{%s}t" % NS["m"]))
        elif v is not None:
            text = v.text or ""
        cells[ref] = {"text": text, "formula": (f.text if f is not None else "") or "", "link": ""}
    for h in root.iter("{%s}hyperlink" % NS["m"]):
        link = srels.get(h.get(RID), "") or h.get("location", "")
        rng = h.get("ref", "")
        for ref in ([rng] if ":" not in rng else _expand(rng)):
            cells.setdefault(ref, {"text": "", "formula": "", "link": ""})["link"] = link
    images = {}
    dr = root.find("m:drawing", NS)
    if dr is not None and srels.get(dr.get(RID)):
        dpath = srels[dr.get(RID)]
        drels = _rels(z, dpath)
        for anc in ET.fromstring(z.read(dpath)):
            fr = anc.find("xdr:from", NS)
            blip = anc.find(".//a:blip", NS)
            if fr is None or blip is None or drels.get(blip.get(EMBED)) is None:
                continue
            col, row = int(fr.find("xdr:col", NS).text), int(fr.find("xdr:row", NS).text) + 1
            mp = drels[blip.get(EMBED)]
            if mp in z.namelist():
                images[(col_letter(col), row)] = (z.read(mp), posixpath.splitext(mp)[1] or ".png")
    return cells, images


def _expand(rng):
    a, b = rng.split(":")
    ma, mb = re.match(r"([A-Z]+)(\d+)", a), re.match(r"([A-Z]+)(\d+)", b)
    if ma and mb and ma[1] == mb[1]:
        return [f"{ma[1]}{n}" for n in range(int(ma[2]), int(mb[2]) + 1)]
    return [a]


def find_url(cell):
    """URL của ô: link ẩn sau chữ > =IMAGE("...") > =HYPERLINK("...") > URL ghi thẳng trong ô."""
    if not cell:
        return ""
    if cell.get("link", "").startswith("http"):
        return cell["link"]
    for src in (cell.get("formula", ""), cell.get("text", "")):
        m = re.search(r'(?:IMAGE|HYPERLINK)\(\s*"([^"]+)"', src, flags=re.I) or re.search(r"https?://[^\s\"'<>]+", src)
        if m:
            return m.group(1) if m.re.groups else m.group(0)
    return ""
