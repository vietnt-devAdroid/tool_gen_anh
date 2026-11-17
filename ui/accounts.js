// ------------------------------------------------------------ tài khoản (đổi / thêm / xoá)
const MA = (path, method, body) => api("/api/muse/" + path, { method: method || (body !== undefined ? "POST" : "GET"), body });
function quotaText(q) { if (!q || typeof q !== "object") return "—"; const bits = []; if (q.plan) bits.push(q.plan); if (q.weekly_used_pct != null) bits.push(`tuần ${q.weekly_used_pct}%`); if (q.extra_left) bits.push(q.extra_left); return bits.join(" · ") || "—"; }
function ago(t) { if (!t) return ""; const m = Math.round((Date.now() / 1000 - t) / 60); return m < 1 ? "vừa xong" : m < 60 ? `${m} phút trước` : m < 1440 ? `${Math.round(m / 60)} giờ trước` : `${Math.round(m / 1440)} ngày trước`; }
async function renderAccounts() {
  const view = $("#view"); if (!S.accRendered) view.innerHTML = `<div class="page"><div class="card">Đang tải…</div></div>`;
  let r; try { r = await api("/api/accounts"); } catch (e) { r = { accounts: [], error: e.message }; }
  S.accRendered = true; S.accounts = r.accounts;
  const cur = S.chat?.account || "";
  view.innerHTML = `<div class="page"><div class="card"><h3>Tài khoản Muse (${r.accounts.length})</h3>
  <div class="acts" style="margin:0 0 12px"><button class="btn pri" data-acc="login">${ico("plus")}Đăng nhập tài khoản mới</button><button class="btn" data-acc="batch">${ico("plus")}Thêm hàng loạt</button><button class="btn" data-acc="quotaAll">${ico("refresh")}Kiểm tra hạn mức tất cả</button><button class="btn" data-acc="auto">${ico("bolt")}Chat này: tự động xoay vòng</button></div>
  ${r.error ? `<div class="err-t">${esc(r.error)}</div>` : ""}
  <p class="hint" style="margin:0 0 10px">${S.chat ? `Cuộc trò chuyện đang mở: <b>${esc(S.chat.title)}</b> — ${cur ? "đang ghim vào một tài khoản" : "đang tự động xoay vòng tài khoản"}.` : "Mở một cuộc trò chuyện ở tab Trò chuyện để ghim tài khoản cho nó."}</p>
  <table class="t"><tr><th>Tài khoản</th><th>Trạng thái</th><th>Hạn mức</th><th>Hôm nay</th><th>Bật</th><th style="width:1%">Thao tác</th></tr>
  ${r.accounts.map(a => `<tr data-id="${esc(a.id)}"><td><b>${esc(a.label)}</b>${a.id === cur ? ` <span class="tag cl">Chat này dùng</span>` : ""}<div class="hint" style="margin:0">${esc(a.mail_email || "")}</div></td>
  <td>${a.ok === false ? `<span class="tag err">Lỗi</span> <span class="hint">${esc((a.note || "").slice(0, 70))}</span>` : a.ok ? `<span class="tag ok">Tốt</span>` : `<span class="tag">Chưa kiểm tra</span>`}<div class="hint" style="margin:0">${a.checked_at ? "kiểm tra " + ago(a.checked_at) : ""}</div></td>
  <td>${esc(quotaText(a.quota))}</td><td>${a.video_count || 0} video</td>
  <td><input type="checkbox" data-acc="toggle" ${a.enabled ? "checked" : ""}></td>
  <td><div class="acts" style="margin:0;flex-wrap:nowrap"><button class="btn sm ${a.id === cur ? "pri" : ""}" data-acc="use">${a.id === cur ? "Đang dùng" : "Dùng cho chat này"}</button><button class="btn sm" data-acc="test">Kiểm tra</button><button class="btn sm" data-acc="quota">Hạn mức</button><button class="btn sm" data-acc="relogin">Đăng nhập lại</button><button class="btn sm" data-acc="view">Mở Chrome</button><button class="btn sm" data-acc="rename">Đổi tên</button><button class="btn sm danger" data-acc="del">${ico("trash")}Xoá</button></div></td></tr>`).join("") || `<tr><td colspan="6" class="hint">Chưa có tài khoản. Bấm "Đăng nhập tài khoản mới".</td></tr>`}</table></div></div>`;
}
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-acc]"); if (!b || b.tagName === "INPUT") return;
  const act = b.dataset.acc, id = b.closest("tr")?.dataset.id, redo = () => S.view === "acc" && renderAccounts();
  try {
    if (act === "login") return loginModal();
    if (act === "batch") return batchLoginModal();
    if (act === "auto") { if (!S.chat) return toast("Chưa mở cuộc trò chuyện", 1); await api("/api/chats/" + S.chat.id, { method: "PATCH", body: { account: "" } }); S.chat.account = ""; toast("Chat này sẽ tự xoay vòng tài khoản"); return redo(); }
    if (act === "use") { if (!S.chat) return toast("Mở một cuộc trò chuyện ở tab Trò chuyện trước", 1); await api("/api/chats/" + S.chat.id, { method: "PATCH", body: { account: id } }); S.chat.account = id; toast("Chat này sẽ dùng tài khoản đã chọn"); return redo(); }
    if (act === "test") { b.disabled = true; toast("Đang kiểm tra…"); const r = await MA(`accounts/${id}/test`, "POST", {}); toast(r.ok === false ? "Lỗi: " + (r.error || r.message || "") : "Tài khoản hoạt động tốt", r.ok === false); return redo(); }
    if (act === "quota") { b.disabled = true; toast("Đang đọc hạn mức…"); await MA(`accounts/${id}/quota`, "POST", {}); toast("Đã cập nhật hạn mức"); return redo(); }
    if (act === "quotaAll") { toast("Đang đọc hạn mức từng tài khoản (có thể mất vài phút)…"); for (const a of S.accounts.filter(x => x.enabled)) { try { await MA(`accounts/${a.id}/quota`, "POST", {}); } catch (er) { /* bỏ qua tài khoản lỗi */ } } toast("Xong"); return redo(); }
    if (act === "relogin") return loginModal(id, S.accounts.find(a => a.id === id)?.label);
    if (act === "view") { await MA(`accounts/${id}/view`, "POST", {}); return toast("Đã mở Chrome của tài khoản"); }
    if (act === "rename") { const cur = S.accounts.find(a => a.id === id)?.label || ""; const n = prompt("Tên mới cho tài khoản:", cur); if (n && n.trim()) { await MA(`accounts/${id}`, "PATCH", { label: n.trim() }); } return redo(); }
    if (act === "del") { const a = S.accounts.find(x => x.id === id); if (!confirm(`Xoá tài khoản "${a?.label}"?\nKhông thể hoàn tác (phải đăng nhập lại nếu muốn dùng lại).`)) return; await MA(`accounts/${id}`, "DELETE"); if (S.chat?.account === id) { await api("/api/chats/" + S.chat.id, { method: "PATCH", body: { account: "" } }); S.chat.account = ""; } toast("Đã xoá tài khoản"); return redo(); }
  } catch (er) { toast(er.message, 1); }
});
document.addEventListener("change", async e => {
  if (e.target.dataset?.acc !== "toggle") return; const id = e.target.closest("tr").dataset.id;
  try { await MA(`accounts/${id}`, "PATCH", { enabled: e.target.checked }); toast(e.target.checked ? "Đã bật" : "Đã tắt (sẽ không dùng để tạo video)"); } catch (er) { toast(er.message, 1); e.target.checked = !e.target.checked; }
});
let LOGIN_T = null;
const LOGIN_END = ["done", "error", "cancelled", "closed"];
function loginModal(accountId, label) {
  openModal(`<div class="mbox"><h2>${accountId ? "Đăng nhập lại" : "Đăng nhập tài khoản mới"}<button class="ib" id="mx">${ico("x")}</button></h2>
  <p style="color:var(--mu);margin-bottom:10px">Bấm Bắt đầu, một cửa sổ Chrome mở ra: bạn đăng nhập Muse trong đó, LUO tự lấy phiên và lưu lại.</p>
  <div class="form" style="grid-template-columns:120px 1fr"><label>Tên gọi</label><input class="inp" id="lg_label" value="${esc(label || "")}" placeholder="(tuỳ chọn, mặc định theo email)">
  <label>Hộp thư (tuỳ chọn)</label><input class="inp" id="lg_mail" placeholder="email|password|refresh_token|client_id (tự điền email, lấy mã OTP)"></div>
  <div class="acts"><button class="btn pri" id="lg_go">Bắt đầu</button><button class="btn" id="lg_cancel" style="display:none">Huỷ</button></div><div id="lg_st" class="st" style="margin-top:10px"></div></div>`);
  $("#mx").onclick = () => { clearInterval(LOGIN_T); closeModal(); };
  $("#lg_go").onclick = async () => {
    const body = { label: $("#lg_label").value.trim() }; if (accountId) body.account_id = accountId; const m = $("#lg_mail").value.trim(); if (m) body.mail = m;
    $("#lg_go").disabled = true;
    try {
      let t = await MA("accounts/login", "POST", body); const tok = t.token; $("#lg_cancel").style.display = "";
      $("#lg_cancel").onclick = () => MA(`accounts/login/${tok}/cancel`, "POST", {});
      const show = x => { $("#lg_st").innerHTML = `${LOGIN_END.includes(x.state) ? "" : '<i class="spin"></i>'}<span class="${x.state === "error" ? "err-t" : ""}">${esc(x.message || x.state)}</span>`; };
      show(t); clearInterval(LOGIN_T);
      LOGIN_T = setInterval(async () => {
        try { t = await MA("accounts/login/" + tok); show(t); if (LOGIN_END.includes(t.state)) { clearInterval(LOGIN_T); $("#lg_go").disabled = false; if (t.state === "done") { toast("Đã lưu tài khoản"); S.view === "acc" && renderAccounts(); } } }
        catch (er) { clearInterval(LOGIN_T); }
      }, 2000);
    } catch (er) { toast(er.message, 1); $("#lg_go").disabled = false; }
  };
}
function batchLoginModal() {
  openModal(`<div class="mbox" style="width:min(720px,100%)"><h2>Thêm tài khoản hàng loạt<button class="ib" id="mx">${ico("x")}</button></h2>
  <p style="color:var(--mu);margin-bottom:8px">Mỗi dòng một tài khoản: <code>email|password|refresh_token|client_id</code>. LUO lần lượt mở Chrome, tự điền email và lấy mã OTP. Email đã có thì đăng nhập lại tài khoản đó.</p>
  <textarea class="inp" id="bt_text" rows="7" placeholder="a@outlook.com|mật_khẩu|refresh_token|client_id"></textarea>
  <div class="acts"><button class="btn pri" id="bt_go">Bắt đầu</button><button class="btn" id="bt_cancel" style="display:none">Huỷ lô</button></div><div id="bt_st" style="margin-top:10px"></div></div>`);
  $("#mx").onclick = () => { clearInterval(LOGIN_T); closeModal(); };
  const NM = { pending: "Chờ", running: "Đang chạy", done: "Xong", failed: "Lỗi", skipped: "Bỏ qua" };
  const draw = b => { $("#bt_st").innerHTML = `<div class="st">Lô: <b>${b.state}</b> · ${Object.entries(b.counts || {}).map(([k, v]) => `${NM[k]} ${v}`).join(" · ")}</div><table class="t">${b.items.map(i => `<tr><td>${i.line}</td><td>${esc(i.email)}</td><td><span class="tag ${i.state === "done" ? "ok" : i.state === "failed" ? "err" : i.state === "running" ? "run" : ""}">${NM[i.state] || i.state}</span></td><td class="hint">${esc(i.message || "")}</td></tr>`).join("")}</table>`; };
  $("#bt_go").onclick = async () => {
    const text = $("#bt_text").value.trim(); if (!text) return; $("#bt_go").disabled = true;
    try {
      let b = await MA("accounts/login-batch", "POST", { text }); const tok = b.token; draw(b); $("#bt_cancel").style.display = ""; $("#bt_cancel").onclick = () => MA(`accounts/login-batch/${tok}/cancel`, "POST", {});
      clearInterval(LOGIN_T);
      LOGIN_T = setInterval(async () => {
        try { b = await MA("accounts/login-batch/" + tok); draw(b); if (b.state !== "running") { clearInterval(LOGIN_T); $("#bt_go").disabled = false; toast("Lô đăng nhập đã xong"); S.view === "acc" && renderAccounts(); } }
        catch (er) { clearInterval(LOGIN_T); }
      }, 2500);
    } catch (er) { toast(er.message, 1); $("#bt_go").disabled = false; }
  };
}
