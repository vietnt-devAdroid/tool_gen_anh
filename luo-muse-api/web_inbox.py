"""Đọc mã OTP Muse từ trang hộp thư web (link dạng https://<trang>/?a=<địa chỉ hộp thư>).

API JSON của trang:
  GET /api/inbox?address=<địa chỉ>            -> {"address", "messages": [{id, sender, sender_name, subject, preview, received_at}]}
  GET /api/message?address=<địa chỉ>&id=<id>  -> thư đầy đủ (subject, text, html)
Chỉ nhận thư Muse/Meta đến SAU khi bấm gửi mã (snapshot -> ignore). Chỉ dùng thư viện chuẩn.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from outlook_otp import CODE_RE, SENDER_HINT, MailAuthError

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _split(url: str) -> tuple[str, str]:
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(u.query)
    return f"{u.scheme}://{u.netloc}", (q.get("a") or q.get("address") or [""])[0]


def _get(url: str) -> dict:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise MailAuthError(f"Trang hộp thư từ chối truy cập (HTTP {e.code}).") from None
        raise


def _inbox(mail: dict) -> tuple[str, str, list[dict]]:
    base, addr = _split(mail["inbox_url"])
    addr = addr or mail["email"]
    d = _get(f"{base}/api/inbox?address={urllib.parse.quote(addr)}")
    return base, addr, list(d.get("messages") or [])


def _code_of(base: str, addr: str, m: dict) -> str | None:
    head = f"{m.get('sender_name') or ''} {m.get('sender') or ''} {m.get('subject') or ''}"
    if not SENDER_HINT.search(head + " " + (m.get("preview") or "")):
        return None
    codes = CODE_RE.findall(f"{m.get('subject') or ''} {m.get('preview') or ''}")
    if codes:
        return codes[0]
    try:
        full = _get(f"{base}/api/message?address={urllib.parse.quote(addr)}&id={urllib.parse.quote(str(m.get('id')))}")
    except Exception:  # noqa: BLE001
        return None
    body = full.get("text") or re.sub(r"(?s)<[^>]+>", " ", full.get("html") or "")
    codes = CODE_RE.findall(f"{full.get('subject') or ''} {body}")
    return codes[0] if codes else None


def _ts(m: dict) -> float:
    try:
        t = float(m.get("received_at"))
        return t / 1000 if t > 1e11 else t
    except (TypeError, ValueError):
        return 0.0


def snapshot(mail: dict) -> set:
    return {str(m.get("id")) for m in _inbox(mail)[2]}


def wait_code(mail: dict, since: float, timeout: float = 180, cancel=None, ignore: set | None = None) -> str | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cancel is not None and cancel.is_set():
            return None
        try:
            base, addr, msgs = _inbox(mail)
        except MailAuthError:
            raise
        except Exception:  # noqa: BLE001
            msgs, base, addr = [], "", ""
        msgs.sort(key=_ts, reverse=True)
        for m in msgs:
            if ignore is not None and str(m.get("id")) in ignore:
                continue
            if ignore is None and _ts(m) and _ts(m) < since - 10:
                continue
            code = _code_of(base, addr, m)
            if code:
                return code
        time.sleep(4)
    return None


def check(mail: dict) -> dict:
    try:
        _, addr, msgs = _inbox(mail)
        return {"ok": True, "message": f"Đọc được hộp thư {addr} ({len(msgs)} thư)"}
    except MailAuthError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"Lỗi mạng khi đọc hộp thư: {exc}"[:300]}
