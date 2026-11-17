"""analyze - chuẩn bị tư liệu để Claude xem cấu trúc video mẫu (cảnh, mốc chuyển cảnh, chữ trên màn hình).

  python analyze.py video.mp4 [--out thư_mục] [--fps 2.5] [--window 5.4 6.2 --fps 15]
In ra: thời lượng, kích thước, có âm thanh không, các mốc đổi cảnh (ffmpeg scene) và đường dẫn các ảnh contact sheet có đóng dấu thời gian.
Claude mở ảnh bằng công cụ Read để nhìn rồi viết spec (xem specrun.py).
"""
import argparse, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FF = os.path.join(ROOT, "bin", "ffmpeg.exe")
FONT = "C\\:/Windows/Fonts/arialbd.ttf"
CNW = 0x08000000 if os.name == "nt" else 0


def info(path):
    r = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True, creationflags=CNW).stderr.decode("utf-8", "replace")
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r)
    dur = int(d[1]) * 3600 + int(d[2]) * 60 + float(d[3])
    sz = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", r)
    return dur, (int(sz[1]), int(sz[2])), "Audio:" in r


def scenes(path, thr):
    r = subprocess.run([FF, "-hide_banner", "-i", path, "-vf", f"select='gt(scene,{thr})',showinfo", "-an", "-f", "null", "-"], capture_output=True, creationflags=CNW).stderr.decode("utf-8", "replace")
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", r)]


def sheet(path, out, fps, cols, tile_w, ss=None, to=None):
    rows = 3
    pre = (["-ss", str(ss)] if ss is not None else []) + (["-to", str(to - ss)] if (to is not None and ss is not None) else [])
    base = ss or 0
    vf = f"fps={fps},scale={tile_w}:-1,drawtext=fontfile='{FONT}':text='%{{pts\\:hms\\:{base}}}':x=4:y=4:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6"
    # in nhiều trang, mỗi trang cols x rows ảnh
    pat = out + "_%02d.jpg"
    subprocess.run([FF, "-y", "-loglevel", "error", *pre, "-i", path, "-vf", vf + f",tile={cols}x{rows}", pat], check=True, creationflags=CNW)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default=None)
    ap.add_argument("--fps", type=float, default=2.5)
    ap.add_argument("--window", nargs=2, type=float, default=None, help="chỉ xem đoạn từ..đến (giây), dùng với --fps cao để soi chuyển cảnh")
    ap.add_argument("--cols", type=int, default=12)
    ap.add_argument("--tile", type=int, default=170)
    a = ap.parse_args()
    out = a.out or os.path.splitext(a.video)[0] + "_phantich"
    os.makedirs(out, exist_ok=True)
    dur, (w, h), has_a = info(a.video)
    print(f"video: {a.video}\nthời lượng: {dur:.2f}s  kích thước: {w}x{h}  âm thanh: {'có' if has_a else 'không'}")
    cuts = scenes(a.video, 0.1)
    print("mốc đổi cảnh (scene>0.1):", " ".join(f"{c:.2f}" for c in cuts) or "(không có)")
    name = "win" if a.window else "all"
    for f in os.listdir(out):
        if f.startswith(name + "_"):
            os.remove(os.path.join(out, f))
    sheet(a.video, os.path.join(out, name), a.fps, a.cols, a.tile, *(a.window or (None, None)))
    print("ảnh contact sheet:")
    for f in sorted(os.listdir(out)):
        if f.startswith(name + "_"):
            print("  ", os.path.join(out, f))


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
