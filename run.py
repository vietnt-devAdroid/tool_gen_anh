"""LUO Chat (bản độc lập) - bật LUO-API kèm theo + máy chủ LUO Chat + cửa sổ ứng dụng.

Chạy:  python run.py [--no-window]
Mọi thứ nằm trong thư mục này: luo-muse-api/ (API Muse), ui/, server.py, bin/ffmpeg.exe, userdata/ (dữ liệu: tài khoản, chat, media).
"""
import json, os, shutil, socket, subprocess, sys, threading, time, urllib.request, secrets

ROOT = os.path.dirname(os.path.abspath(__file__))
API_DIR = os.path.join(ROOT, "luo-muse-api")
USER = os.path.join(ROOT, "userdata")
API_HOME, CHAT_DATA, LOGS = os.path.join(USER, "api"), os.path.join(USER, "chat"), os.path.join(USER, "logs")
CNW = 0x08000000 if os.name == "nt" else 0


def say(m):
    try:
        print(m, flush=True)
    except Exception:
        pass


def port_free(p):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", p)) != 0


def pick_port(pref):
    for p in range(pref, pref + 40):
        if port_free(p):
            return p
    raise RuntimeError("Không tìm được cổng trống cho LUO-API")


def http_ok(url, t=3):
    try:
        with urllib.request.urlopen(url, timeout=t) as r:
            return r.status == 200
    except Exception:
        return False


def write_env(port):
    """userdata/api/.env: khoá API sinh một lần, giữ nguyên các lần sau; cổng cập nhật mỗi lần chạy."""
    os.makedirs(API_HOME, exist_ok=True)
    path, lines, key = os.path.join(API_HOME, ".env"), [], ""
    if os.path.exists(path):
        for ln in open(path, encoding="utf-8").read().splitlines():
            if ln.startswith("MUSE2API_KEY="):
                key = ln.split("=", 1)[1].strip()
            if ln.split("=", 1)[0] not in ("MUSE2API_PORT", "MUSE2API_HOST") and ln.strip():
                lines.append(ln)
    if not key:
        key = secrets.token_hex(16)
        lines = [ln for ln in lines if not ln.startswith("MUSE2API_KEY=")] + [f"MUSE2API_KEY={key}"]
    lines += ["MUSE2API_HOST=127.0.0.1", f"MUSE2API_PORT={port}"]
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return key


def kill_tree(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, creationflags=CNW)
        else:
            proc.terminate()
    except Exception:
        pass


def reap_stale(profile_root):
    """Tắt trình duyệt con / LUO-API sót lại của lần chạy trước (nếu không, chúng giữ hồ sơ và cổng)."""
    if os.name != "nt":
        return
    script = ("$p=$env:LC_PROFILE; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.Name -match 'chrome|chromium|msedge' "
              "-and $_.CommandLine.Contains($p) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, timeout=30, creationflags=CNW,
                       env=dict(os.environ, LC_PROFILE=profile_root))
    except Exception:
        pass


def find_browser():
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if os.path.exists(p):
            return p
    return shutil.which("msedge") or shutil.which("chrome")


def open_window(url):
    exe = find_browser()
    if not exe:
        import webbrowser
        webbrowser.open(url)
        input("Đã mở trình duyệt. Nhấn Enter để thoát… ")
        return
    subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={os.path.join(CHAT_DATA, 'window-profile')}", "--start-maximized", "--no-first-run", "--disable-sync",
                      "--lang=vi", "--disable-features=Translate,TranslateUI,EdgeTranslate,msEdgeTranslate"]).wait()


def running_chat():
    try:
        d = json.load(open(os.path.join(CHAT_DATA, "running.json"), encoding="utf-8"))
        if http_ok(d["url"] + "api/health", 5):
            return d["url"]
    except Exception:
        pass
    return None


def main():
    os.makedirs(CHAT_DATA, exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)
    again = running_chat()
    if again:
        say(f"LUO Chat đang chạy: {again}")
        open_window(again)
        return 0
    os.environ["PATH"] = os.path.join(ROOT, "bin") + os.pathsep + os.environ.get("PATH", "")
    profiles = os.path.join(USER, "profiles")
    os.environ.setdefault("MUSE2API_PROFILE_ROOT", profiles)
    os.environ["MUSE2API_HOME"] = API_HOME
    os.environ.setdefault("MUSE2API_ACCOUNT_PARALLEL", "6")   # số việc cùng lúc trên MỖI tài khoản (mặc định của API là 2)
    os.environ.setdefault("MUSE2API_CONCURRENCY", "60")        # trần tổng số việc của mọi tài khoản
    os.environ["MUSE2API_ENV_FILE"] = os.path.join(API_HOME, ".env")
    os.environ["LUO_CHAT_DATA"] = CHAT_DATA
    reap_stale(profiles)
    for p in range(19210, 19250):
        if port_free(p):
            os.environ.setdefault("MUSE2API_CDP_PORT", str(p))
            break
    port = pick_port(int(os.environ.get("LUO_API_PORT", "18610")))
    os.environ["MUSE2API_KEY"] = write_env(port)
    api_url = f"http://127.0.0.1:{port}"
    py = sys.executable
    if os.name == "nt" and py.lower().endswith("pythonw.exe"):
        py = py[:-len("pythonw.exe")] + "python.exe"
    log = open(os.path.join(LOGS, "api.log"), "ab")
    api = subprocess.Popen([py, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"], cwd=API_DIR, stdout=log,
                           stderr=log, creationflags=CNW, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    try:
        say(f"Đang bật LUO-API (cổng {port})…")
        for _ in range(120):
            if api.poll() is not None:
                raise RuntimeError("LUO-API tắt ngay khi khởi động. Xem userdata/logs/api.log (đã chạy setup.bat chưa?)")
            if http_ok(api_url + "/healthz"):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("LUO-API không phản hồi sau 60 giây. Xem userdata/logs/api.log")
        os.environ["LUO_API_URL"] = api_url
        sys.path.insert(0, ROOT)
        import server  # noqa: E402
        cport = int(os.environ.get("LUO_CHAT_PORT", "18620"))
        srv = server.make_server(cport if port_free(cport) else 0)
        url = f"http://127.0.0.1:{srv.server_address[1]}/"
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        json.dump({"url": url, "api_url": api_url, "pid": os.getpid()}, open(os.path.join(CHAT_DATA, "running.json"), "w", encoding="utf-8"))
        say(f"LUO Chat: {url}")
        if "--no-window" in sys.argv:
            while True:
                time.sleep(3600)
        open_window(url)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            os.remove(os.path.join(CHAT_DATA, "running.json"))
        except OSError:
            pass
        try:
            sys.modules["server"]._save_now()
        except Exception:
            pass
        kill_tree(api)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        msg = f"LUO Chat không khởi động được: {e}"
        say(msg)
        try:
            os.makedirs(LOGS, exist_ok=True)
            open(os.path.join(LOGS, "launcher-error.txt"), "w", encoding="utf-8").write(msg + "\n")
            if os.name == "nt":
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, msg, "LUO Chat", 0x10)
        except Exception:
            pass
        sys.exit(1)
