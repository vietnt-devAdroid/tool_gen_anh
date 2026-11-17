"use strict";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const IC = {
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="1.6"/><path d="m21 15-5-5L5 21"/>',
  video: '<rect x="2" y="6" width="14" height="12" rx="2"/><path d="m16 10 6-3v10l-6-3"/>',
  film: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4M3 12h4M3 16h4M17 8h4M17 12h4M17 16h4"/>',
  chat: '<path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 9h8M8 13h5"/>',
  user: '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0M19 8v6M16 11h6"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  id: '<rect x="2" y="4" width="20" height="16" rx="2"/><circle cx="8" cy="11" r="2.2"/><path d="M5 17c.6-2 4.4-2 6 0M14 9h5M14 13h5"/>',
  book: '<path d="M3 5h7a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H3zM21 5h-7a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h7z"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5h0a1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', x: '<path d="M18 6 6 18M6 6l12 12"/>', send: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  clip: '<path d="m21 12-8.5 8.5a5 5 0 0 1-7-7L14 5a3.3 3.3 0 0 1 5 5l-8.5 8.5a1.7 1.7 0 0 1-2.5-2.5L15 9"/>',
  wand: '<path d="m15 4 1 2 2 1-2 1-1 2-1-2-2-1 2-1zM3 21l11-11M18 14l.7 1.3L20 16l-1.3.7L18 18l-.7-1.3L16 16l1.3-.7z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>', refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5"/>',
  dl: '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>', play: '<path d="M7 4v16l13-8z" fill="currentColor"/>', check: '<path d="m5 12 5 5 9-10"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>', stop: '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/>', folder: '<path d="M3 6a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  redo: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5"/>', bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
};
const ico = n => `<svg class="i" viewBox="0 0 24 24">${IC[n] || ""}</svg>`;
const S = { view: "chat", chats: [], chat: null, chatId: localStorage.getItem("lc.chat") || "", settings: {}, health: {}, rev: "", mode: "video", aspect: "9:16", duration: "",
  files: [], sel: new Set(), mediaFilter: "all", search: "", accounts: [], poll: { running: 0, queued: 0 }, all: [] };

async function api(path, opt = {}) {
  const o = { method: opt.method || (opt.body ? "POST" : "GET"), headers: {}, body: undefined };
  if (opt.body !== undefined) { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(opt.body); }
  if (opt.raw) { o.body = opt.raw; o.headers = opt.headers || {}; }
  const r = await fetch(path, o);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function toast(msg, err) { const d = document.createElement("div"); d.textContent = msg; if (err) d.className = "e"; $("#toast").appendChild(d); setTimeout(() => d.remove(), err ? 6000 : 3000); }
const openModal = h => { $("#modal").innerHTML = h; $("#modal").classList.remove("hidden"); };
const closeModal = () => { $("#modal").classList.add("hidden"); $("#modal").innerHTML = ""; };
$("#modal").addEventListener("mousedown", e => { if (e.target.id === "modal") closeModal(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

// ------------------------------------------------------------ khung chung
const NAV = [["chat", "chat", "Trò chuyện"], ["lib", "grid", "Thư viện"], ["acc", "id", "Tài khoản"], ["guide", "book", "Hướng dẫn"], ["set", "gear", "Cài đặt"]];
function renderNav() {
  $("#nav").innerHTML = `<div class="logo">LC</div>` + NAV.map(([k, i, l]) => `<button data-nav="${k}" class="${S.view === k ? "on" : ""}">${ico(i)}<span>${l}</span></button>`).join("") + `<div class="ver">LUO Chat</div>`;
}
$("#nav").addEventListener("click", e => { const b = e.target.closest("[data-nav]"); if (b) go(b.dataset.nav); });
function go(v) { S.view = v; renderNav(); renderTop(); renderView(); }
const TITLES = { chat: "Cuộc trò chuyện", lib: "Thư viện", acc: "Tài khoản", guide: "Hướng dẫn", set: "Cài đặt" };
function renderTop() {
  const h = S.health, p = S.poll;
  $("#top").innerHTML = `<h1><b>LUO Chat</b><span>/</span>${TITLES[S.view]}</h1><div class="sp"></div>
  <span class="chip ${h.api ? "ok" : "err"}"><i class="d"></i>${h.api ? "LUO-API sẵn sàng" : "LUO-API chưa chạy"}</span>
  <span class="chip ${p.running ? "run" : ""}"><i class="d"></i>${p.running ? `Đang chạy ${p.running}` : "Đang nghỉ"}${p.queued ? ` · chờ ${p.queued}` : ""}</span>
  <button class="btn" id="retryAll" title="Chạy lại các video lỗi/đã dừng">${ico("redo")}Chạy lại lỗi</button>
  <button class="btn danger" id="stopAll">${ico("stop")}Dừng</button>`;
  $("#stopAll").onclick = async () => { await api("/api/stop-all", { body: {} }); toast("Đã dừng toàn bộ"); refresh(); };
  $("#retryAll").onclick = async () => { const r = await api("/api/retry-failed", { body: {} }); toast(`Xếp hàng lại ${r.started} mục`); refresh(); };
}

// ------------------------------------------------------------ danh sách / chat
function dayLabel(t) {
  const d = new Date(t * 1000), n = new Date(); const a = new Date(d.getFullYear(), d.getMonth(), d.getDate()), b = new Date(n.getFullYear(), n.getMonth(), n.getDate());
  const k = Math.round((b - a) / 864e5); return k <= 0 ? "Hôm nay" : k === 1 ? "Hôm qua" : `${k} ngày trước`;
}
function renderList() {
  const el = $("#clist"); if (!el) return;
  const q = S.search.toLowerCase(); let last = "", h = "";
  for (const c of S.chats) {
    if (q && !(c.title + " " + c.preview).toLowerCase().includes(q)) continue;
    const g = dayLabel(c.updated); if (g !== last) { h += `<div class="grp">${g}</div>`; last = g; }
    const n = c.counts, b = [];
    if (n.running) b.push(`<span class="tag run">${n.running} chạy</span>`); if (n.queued) b.push(`<span class="tag">${n.queued} chờ</span>`);
    if (n.draft) b.push(`<span class="tag draft">${n.draft} chờ duyệt</span>`); if (n.error) b.push(`<span class="tag err">${n.error} lỗi</span>`);
    if (c.media) b.push(`<span class="tag ok">${c.media} file</span>`);
    h += `<div class="ci ${c.id === S.chatId ? "on" : ""}" data-chat="${c.id}"><div class="t">${esc(c.title)}</div><div class="p">${esc(c.preview || "Chưa có tin nhắn")}</div><div class="bd">${b.join("")}</div><button class="ib x" data-delchat="${c.id}" title="Xoá cuộc trò chuyện">${ico("trash")}</button></div>`;
  }
  el.innerHTML = h || `<div class="grp">Chưa có cuộc trò chuyện</div>`;
  const cnt = $("#ccount"); if (cnt) cnt.textContent = S.chats.length;
}
async function openChat(id) {
  S.chatId = id; localStorage.setItem("lc.chat", id); S.sel.clear();
  S.chat = id ? await api("/api/chats/" + id).catch(() => null) : null;
  if (!S.chat) { S.chatId = ""; }
  renderList(); renderThread(true); renderMedia(); syncAccountSel();
}
async function newChat() {
  const c = await api("/api/chats", { body: { title: "Cuộc trò chuyện mới", account: $("#accSel")?.value || "" } });
  await refreshChats(); await openChat(c.id); $("#prompt")?.focus();
}

// --- tin nhắn: dựng DOM theo khoá để video không bị tải lại mỗi lần cập nhật
const NODES = new Map();
function sig(m) { return [m.status, m.progress, m.error, m.text, m.reply, (m.media || []).map(x => x.file).join(), m.account, m.attempts].join("|"); }
const KIND = { video: "Tạo video", image: "Tạo ảnh", chat: "Chat AI" };
function fileChip(f) {
  const u = "/upload/" + encodeURIComponent(f.path.split(/[\\/]/).pop());
  const th = f.type === "image" ? `<img src="${u}" alt="">` : f.type === "video" ? `<video src="${u}#t=0.1" preload="metadata" muted></video>` : `<span>♪</span>`;
  return `<div class="fc">${th}<span title="${esc(f.name)}">${esc(f.name)}</span></div>`;
}
function resHTML(m) {
  const st = m.status, acc = m.account ? ` · <b>${esc(m.account)}</b>` : "";
  let h = "";
  if (st === "draft") h = `<div class="st"><span class="tag draft">Chờ duyệt</span> Xem prompt rồi bấm Chạy.</div><div class="acts"><button class="btn pri sm" data-act="run">${ico("bolt")}Chạy</button><button class="btn sm" data-act="edit">Sửa prompt</button><button class="btn sm danger" data-act="del">${ico("trash")}Xoá</button></div>`;
  else if (st === "queued") h = `<div class="st"><i class="spin"></i>Đang xếp hàng${m.attempts ? ` · thử lại lần ${m.attempts + 1}` : ""}</div>${m.error ? `<div class="err-t">Lần trước: ${esc(m.error)}</div>` : ""}<div class="acts"><button class="btn sm" data-act="stop">${ico("stop")}Dừng</button></div>`;
  else if (st === "running") h = `<div class="st"><i class="spin"></i><b>Đang tạo ${KIND[m.kind].toLowerCase()}…</b> ${m.progress || 0}%${acc}</div><div class="bar"><i style="width:${m.progress || 3}%"></i></div><div class="acts"><button class="btn sm" data-act="stop">${ico("stop")}Dừng</button></div>`;
  else if (st === "error") h = `<div class="st"><span class="tag err">Lỗi</span>${acc}</div><div class="err-t">${esc(m.error || "Không rõ")}</div><div class="acts"><button class="btn pri sm" data-act="retry">${ico("redo")}Thử lại</button><button class="btn sm danger" data-act="del">${ico("trash")}Xoá</button></div>`;
  else if (st === "stopped") h = `<div class="st"><span class="tag">Đã dừng</span></div><div class="acts"><button class="btn sm" data-act="retry">${ico("redo")}Chạy lại</button><button class="btn sm danger" data-act="del">${ico("trash")}Xoá</button></div>`;
  else if (st === "done") {
    const md = (m.media || [])[0];
    if (m.kind === "chat") h = `<div class="txt">${esc(m.reply)}</div><div class="acts"><button class="btn sm danger" data-act="del">${ico("trash")}Xoá</button></div>`;
    else if (md) {
      const url = "/media/" + encodeURIComponent(md.file), port = m.aspect === "9:16";
      h = (md.type === "video" ? `<video class="vid ${port ? "v" : ""}" src="${url}" controls preload="metadata"></video>` : `<img class="vid v" src="${url}" alt="" style="cursor:zoom-in" data-zoom="${url}">`) +
        `<div class="acts"><a class="btn sm" href="${url}" download="${esc(md.file)}">${ico("dl")}Tải</a><button class="btn sm" data-act="retry">${ico("redo")}Tạo lại</button><button class="btn sm danger" data-act="del">${ico("trash")}Xoá</button>${m.account ? `<span class="st">${esc(m.account)}</span>` : ""}</div>`;
    }
  }
  return h;
}
function msgHTML(m) {
  const by = m.by === "claude" ? `<span class="tag cl">Claude</span>` : "Bạn";
  const meta = `${KIND[m.kind]}${m.kind !== "chat" ? ` · ${m.aspect}${m.duration ? ` · ${m.duration}s` : ""}` : ""}`;
  return `<div class="bub user"><div class="who">${by} · ${meta}</div><div class="txt">${esc(m.text)}</div>${m.files?.length ? `<div class="fl">${m.files.map(fileChip).join("")}</div>` : ""}</div><div class="bub res">${resHTML(m)}</div>`;
}
function renderThread(reset) {
  const th = $("#thread"); if (!th) return;
  const c = S.chat;
  if (reset) { NODES.clear(); th.innerHTML = ""; }
  if (!c) { th.innerHTML = `<div class="empty"><h3>Cuộc trò chuyện trên Muse</h3>Chọn một cuộc trò chuyện bên trái, hoặc nhập ý tưởng bên dưới để bắt đầu.<br>Bạn cũng có thể nhờ Claude tạo hàng loạt: các prompt sẽ hiện ở đây để bạn kiểm tra.</div>`; return; }
  const near = th.scrollHeight - th.scrollTop - th.clientHeight < 140;
  const ids = new Set(c.messages.map(m => m.id)); let added = false;
  th.querySelector(".empty")?.remove();
  for (const [id, o] of NODES) if (!ids.has(id)) { o.el.remove(); NODES.delete(id); }
  let prev = null;
  for (const m of c.messages) {
    let o = NODES.get(m.id); const s = sig(m);
    if (!o) { const el = document.createElement("div"); el.className = "msg"; el.dataset.id = m.id; el.innerHTML = msgHTML(m); o = { el, s }; NODES.set(m.id, o); added = true;
      th.insertBefore(el, prev ? prev.nextSibling : th.firstChild); }
    else if (o.s !== s) { const wasDone = o.s.startsWith("done"), nowDone = s.startsWith("done");
      if (!(wasDone && nowDone && (m.media || []).map(x => x.file).join() === o.s.split("|")[5])) { o.el.innerHTML = msgHTML(m); } else { $(".res", o.el).innerHTML = resHTML(m); }
      o.s = s; }
    prev = o.el;
  }
  if (!c.messages.length) th.innerHTML = `<div class="empty"><h3>${esc(c.title)}</h3>Chưa có yêu cầu nào. Nhập mô tả video ở khung bên dưới.</div>`;
  if (reset || (added && near)) th.scrollTop = th.scrollHeight;
}
$("#view").addEventListener("click", async e => {
  const t = e.target;
  let x;
  if ((x = t.closest("[data-delchat]"))) { e.stopPropagation(); if (confirm("Xoá cuộc trò chuyện này và các yêu cầu trong đó? (video đã tải vẫn còn trong thư mục)")) { await api("/api/chats/" + x.dataset.delchat, { method: "DELETE" }); if (S.chatId === x.dataset.delchat) await openChat(""); refresh(); } return; }
  if ((x = t.closest("[data-chat]"))) return openChat(x.dataset.chat);
  if ((x = t.closest("[data-act]"))) {
    const id = x.closest(".msg").dataset.id, a = x.dataset.act;
    if (a === "del") await api("/api/messages/" + id, { method: "DELETE" });
    else if (a === "edit") return editPrompt(id);
    else await api(`/api/messages/${id}/${a}`, { body: {} });
    return refresh();
  }
  if ((x = t.closest("[data-zoom]"))) return openModal(`<div class="mbox" style="width:min(900px,100%)"><h2>Xem ảnh<button class="ib" id="mx">${ico("x")}</button></h2><img src="${x.dataset.zoom}"></div>`), $("#mx").onclick = closeModal;
});
function editPrompt(id) {
  const m = S.chat.messages.find(x => x.id === id);
  openModal(`<div class="mbox"><h2>Sửa prompt<button class="ib" id="mx">${ico("x")}</button></h2><textarea class="inp" id="ed" rows="8">${esc(m.text)}</textarea><div class="acts"><button class="btn pri" id="eok">Lưu</button><button class="btn" id="eok2">Lưu và chạy</button></div></div>`);
  $("#mx").onclick = closeModal;
  const save = async run => { await api("/api/messages/" + id, { method: "PATCH", body: { text: $("#ed").value } }); if (run) await api(`/api/messages/${id}/run`, { body: {} }); closeModal(); refresh(); };
  $("#eok").onclick = () => save(false); $("#eok2").onclick = () => save(true);
}

// ------------------------------------------------------------ cột media
function chatMedia() {
  const out = []; for (const m of S.chat?.messages || []) for (const md of m.media || []) out.push({ ...md, text: m.text, aspect: m.aspect, id: m.id });
  return out;
}
function renderMedia() {
  const el = $("#mpanel"); if (!el) return;
  const all = chatMedia(), vi = all.filter(x => x.type === "video"), im = all.filter(x => x.type === "image");
  const list = S.mediaFilter === "video" ? vi : S.mediaFilter === "image" ? im : all;
  const valid = new Set(all.map(x => x.file)); for (const f of [...S.sel]) if (!valid.has(f)) S.sel.delete(f);
  const grid = list.map(x => `<div class="mc ${x.aspect === "16:9" ? "land" : ""} ${S.sel.has(x.file) ? "sel" : ""}" data-m="${esc(x.file)}">${x.type === "video" ? `<video src="/media/${encodeURIComponent(x.file)}#t=0.1" preload="metadata" muted></video><div class="pl">${ico("play")}</div>` : `<img loading="lazy" src="/media/${encodeURIComponent(x.file)}" alt="">`}<div class="ck">${S.sel.has(x.file) ? ico("check") : ""}</div><div class="ca">${esc(x.text)}</div></div>`).join("");
  const sel = S.sel.size;
  el.innerHTML = `<div class="ph">${ico("grid")}Media<span class="sp"></span><button class="btn sm" id="selAll" style="background:none;border:0;color:var(--mu)">${sel === list.length && list.length ? "Bỏ chọn" : "Chọn tất cả"}</button></div>
  <div class="media-tabs">${[["all", "Tất cả", all.length], ["image", "Ảnh", im.length], ["video", "Video", vi.length]].map(([k, l, n]) => `<button class="pill ${S.mediaFilter === k ? "on" : ""}" data-mf="${k}">${l} ${n}</button>`).join("")}</div>
  <div class="mg">${grid || `<div class="empty" style="grid-column:span 2;font-size:13px">Chưa có ảnh/video trong cuộc trò chuyện này</div>`}</div>
  <div class="mfoot"><button class="btn" id="dlSel" ${sel ? "" : "disabled"}>${ico("dl")}Tải xuống (${sel})</button><button class="btn pri" id="joinSel" ${sel > 1 ? "" : "disabled"}>${ico("film")}Ghép (${sel})</button></div>`;
}
function playModal(file, type, text) {
  const url = "/media/" + encodeURIComponent(file);
  openModal(`<div class="mbox" style="width:min(520px,100%)"><h2>${esc((text || "").slice(0, 60))}<button class="ib" id="mx">${ico("x")}</button></h2>${type === "video" ? `<video src="${url}" controls autoplay></video>` : `<img src="${url}">`}<div class="acts"><a class="btn" href="${url}" download="${esc(file)}">${ico("dl")}Tải về</a></div></div>`);
  $("#mx").onclick = closeModal;
}
document.addEventListener("click", async e => {
  const t = e.target; let x;
  if ((x = t.closest("[data-mf]"))) { S.mediaFilter = x.dataset.mf; return renderMedia(); }
  if (t.closest("#selAll")) { const l = chatMedia().filter(m => S.mediaFilter === "all" || m.type === S.mediaFilter); if (S.sel.size === l.length) S.sel.clear(); else l.forEach(m => S.sel.add(m.file)); return renderMedia(); }
  if ((x = t.closest(".mc[data-m]"))) {
    const f = x.dataset.m;
    if (t.closest(".ck")) { S.sel.has(f) ? S.sel.delete(f) : S.sel.add(f); return S.view === "lib" ? renderView() : renderMedia(); }
    const md = (S.view === "lib" ? S.all : chatMedia()).find(m => m.file === f); return playModal(f, md?.type || "video", md?.text);
  }
  if (t.closest("#dlSel")) { location.href = "/api/zip?files=" + encodeURIComponent([...S.sel].join(",")); return; }
  if (t.closest("#joinSel")) {
    const order = chatMedia().filter(m => S.sel.has(m.file) && m.type === "video").map(m => m.file);
    if (order.length < 2) return toast("Chọn ít nhất 2 video", 1);
    toast("Đang ghép video…"); try { const r = await api("/api/concat", { body: { files: order } }); toast("Đã ghép: " + r.file); playModal(r.file, "video", "Video ghép"); } catch (er) { toast(er.message, 1); }
  }
});

// ------------------------------------------------------------ khung nhập
async function uploadFile(f) {
  const r = await fetch("/api/upload", { method: "POST", headers: { "X-Filename": encodeURIComponent(f.name) }, body: f });
  const j = await r.json(); if (!r.ok) throw new Error(j.error); return j;
}
async function addFiles(list) {
  for (const f of list) { try { toast("Đang tải " + f.name); S.files.push(await uploadFile(f)); } catch (e) { toast(e.message, 1); } }
  renderFiles();
}
function renderFiles() {
  const el = $("#attach"); if (!el) return;
  el.innerHTML = S.files.map((f, i) => `<div class="fc">${fileChip(f).replace(/^<div class="fc">/, "").replace(/<\/div>$/, "")}<button class="x" data-rmf="${i}">${ico("x")}</button></div>`).join("");
  el.style.display = S.files.length ? "flex" : "none";
}
async function send(textOverride) {
  const ta = $("#prompt"), text = (textOverride ?? ta.value).trim(); if (!text) return;
  if (!S.chat) { const c = await api("/api/chats", { body: { account: $("#accSel").value } }); S.chatId = c.id; localStorage.setItem("lc.chat", c.id); S.chat = c; }
  const body = { text, kind: S.mode, aspect: S.aspect, duration: S.mode === "video" && S.duration ? +S.duration : null, files: S.files };
  await api(`/api/chats/${S.chat.id}/send`, { body });
  if (textOverride === undefined) { ta.value = ""; ta.style.height = ""; }
  await refresh(true);
  const th = $("#thread"); if (th) th.scrollTop = th.scrollHeight;
}
function batchModal() {
  openModal(`<div class="mbox"><h2>Tạo hàng loạt<button class="ib" id="mx">${ico("x")}</button></h2>
  <p style="color:var(--mu);margin-bottom:8px">Mỗi dòng là một ${KIND[S.mode].toLowerCase()}. Dùng chế độ, tỷ lệ và tệp đính kèm hiện tại (${S.mode}, ${S.aspect}${S.files.length ? `, ${S.files.length} tệp` : ""}).</p>
  <textarea class="inp" id="bt" rows="10" placeholder="Ý tưởng 1&#10;Ý tưởng 2&#10;…"></textarea><div class="acts"><button class="btn pri" id="bok">${ico("bolt")}Thêm vào hàng đợi</button></div></div>`);
  $("#mx").onclick = closeModal;
  $("#bok").onclick = async () => { const lines = $("#bt").value.split("\n").map(s => s.trim()).filter(Boolean); if (!lines.length) return; closeModal(); for (const l of lines) await send(l); toast(`Đã thêm ${lines.length} mục`); };
}
function syncAccountSel() { const s = $("#accSel"); if (s) s.value = S.chat?.account || ""; }
function renderChatView() {
  $("#view").innerHTML = `<div class="cols">
  <div class="panel" id="lpanel"><div class="ph">${ico("chat")}Cuộc trò chuyện <span class="cnt" id="ccount">0</span><span class="sp"></span><button class="ib" id="rl" title="Làm mới">${ico("refresh")}</button></div>
    <div class="lp"><select class="inp" id="accSel"><option value="">Tự động (xoay vòng tài khoản)</option>${S.accounts.map(a => `<option value="${esc(a.id)}">${esc(a.label)}</option>`).join("")}</select>
    <button class="btn pri" id="nc">${ico("plus")}Cuộc trò chuyện mới</button>
    <div style="position:relative"><input class="inp" id="srch" placeholder="Tìm cuộc trò chuyện…" value="${esc(S.search)}" style="padding-left:36px"><span style="position:absolute;left:11px;top:10px;color:var(--mu)">${ico("search")}</span></div></div>
    <div class="list" id="clist"></div></div>
  <div class="panel center"><div class="ph" id="ctitle"></div><div class="thread" id="thread"></div>
    <div class="composer" id="comp"><div class="fl" id="attach" style="display:none;margin:0 0 6px"></div><textarea id="prompt" rows="2" placeholder="Mô tả ý tưởng ${S.mode === "chat" ? "bạn muốn hỏi" : S.mode === "image" ? "ảnh bạn muốn tạo" : "video bạn muốn tạo"}… (Enter để gửi, Shift+Enter xuống dòng)"></textarea>
    <div class="row"><div class="modes">${[["chat", "Chat AI"], ["image", "Tạo ảnh"], ["video", "Tạo video"]].map(([k, l]) => `<button data-mode="${k}" class="${S.mode === k ? "on" : ""}">${l}</button>`).join("")}</div>
    <select id="asp" title="Tỷ lệ"><option value="9:16">9:16 Dọc</option><option value="16:9">16:9 Ngang</option><option value="1:1">1:1 Vuông</option></select>
    <select id="dur" title="Thời lượng" ${S.mode === "video" ? "" : 'style="display:none"'}><option value="">Thời lượng tự động</option><option>5</option><option>6</option><option>8</option><option>10</option></select>
    <button class="ib" id="pImg" title="Đính kèm ảnh tham chiếu">${ico("clip")}</button><button class="ib" id="pVid" title="Đính kèm video tham chiếu">${ico("video")}</button><button class="ib" id="pBatch" title="Tạo hàng loạt (mỗi dòng một yêu cầu)">${ico("wand")}</button>
    <button class="send" id="sendBtn" title="Gửi">${ico("send")}</button></div></div></div>
  <div class="panel" id="mpanel"></div></div>
  <input type="file" id="fImg" accept="image/*" multiple hidden><input type="file" id="fVid" accept="video/*,audio/*" multiple hidden>`;
  $("#asp").value = S.aspect; $("#dur").value = S.duration;
  $("#asp").onchange = e => S.aspect = e.target.value; $("#dur").onchange = e => S.duration = e.target.value;
  $("#rl").onclick = () => refresh(true); $("#nc").onclick = newChat;
  $("#srch").oninput = e => { S.search = e.target.value; renderList(); };
  $("#accSel").onchange = async e => { if (S.chat) await api("/api/chats/" + S.chat.id, { method: "PATCH", body: { account: e.target.value } }); };
  $("#pImg").onclick = () => $("#fImg").click(); $("#pVid").onclick = () => $("#fVid").click(); $("#pBatch").onclick = batchModal;
  $("#fImg").onchange = async e => { await addFiles(e.target.files); e.target.value = ""; }; $("#fVid").onchange = async e => { await addFiles(e.target.files); e.target.value = ""; };
  $("#sendBtn").onclick = () => send();
  const ta = $("#prompt");
  ta.onkeydown = e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } };
  ta.oninput = () => { ta.style.height = "auto"; ta.style.height = Math.min(200, ta.scrollHeight) + "px"; };
  ta.onpaste = e => { const fs = [...(e.clipboardData?.files || [])]; if (fs.length) { e.preventDefault(); addFiles(fs); } };
  $("#comp").ondragover = e => e.preventDefault(); $("#comp").ondrop = e => { e.preventDefault(); addFiles([...e.dataTransfer.files]); };
  $("#comp").addEventListener("click", e => { const m = e.target.closest("[data-mode]"); if (m) { S.mode = m.dataset.mode; const v = ta.value; renderChatView(); $("#prompt").value = v; fill(); }
    const r = e.target.closest("[data-rmf]"); if (r) { S.files.splice(+r.dataset.rmf, 1); renderFiles(); } });
  fill();
}
function fill() { renderFiles(); renderList(); renderThread(true); renderMedia(); syncAccountSel(); const t = $("#ctitle"); if (t) t.innerHTML = `<span id="ct">${esc(S.chat?.title || "Cuộc trò chuyện mới")}</span><span class="sp"></span>${S.chat?.messages.some(m => m.status === "draft") ? `<button class="btn pri sm" id="runDr">${ico("bolt")}Chạy tất cả đã duyệt</button>` : ""}`;
  $("#runDr")?.addEventListener("click", async () => { const r = await api("/api/run-drafts", { body: { chat: S.chat.id } }); toast(`Bắt đầu ${r.started} mục`); refresh(); }); }

// ------------------------------------------------------------ các trang khác
async function renderView() {
  if (S.view === "chat") return renderChatView();
  if (S.view === "lib") {
    const r = await api("/api/media-all"); S.all = r.media;
    $("#view").innerHTML = `<div class="page"><div class="lib">${r.media.map(x => `<div class="mc ${S.sel.has(x.file) ? "sel" : ""}" data-m="${esc(x.file)}" title="${esc(x.chat_title)}">${x.type === "video" ? `<video src="/media/${encodeURIComponent(x.file)}#t=0.1" preload="metadata" muted></video><div class="pl">${ico("play")}</div>` : `<img loading="lazy" src="/media/${encodeURIComponent(x.file)}">`}<div class="ck">${S.sel.has(x.file) ? ico("check") : ""}</div><div class="ca">${esc(x.text)}</div></div>`).join("") || `<div class="empty">Chưa có media nào.</div>`}</div>
    <div class="acts" style="margin-top:14px"><button class="btn" id="dlSel">${ico("dl")}Tải xuống (${S.sel.size})</button><button class="btn" id="openF">${ico("folder")}Mở thư mục media</button></div></div>`;
    $("#openF").onclick = () => api("/api/open-folder", { body: {} });
    return;
  }
  if (S.view === "acc") return renderAccounts();
  if (S.view === "set") {
    const s = S.settings;
    $("#view").innerHTML = `<div class="page"><div class="card"><h3>Cài đặt</h3><div class="form">
    <label>Địa chỉ LUO-API</label><input class="inp" id="s_api_url" value="${esc(s.api_url)}">
    <label>Khoá API</label><input class="inp" id="s_api_key" type="password" placeholder="${s.api_key_set ? "Đã có (để trống = giữ nguyên)" : "Để trống = tự lấy từ userdata/api/.env"}">
    <label>Số video chạy song song</label><input class="inp" id="s_parallel" type="number" min="1" max="20" value="${s.parallel}"><span class="hint">Nên bằng số tài khoản Muse đang dùng.</span>
    <label>Số lần tự thử lại</label><input class="inp" id="s_retries" type="number" min="0" max="10" value="${s.retries}"><span class="hint">Mỗi lần thử lại đổi sang tài khoản khác.</span>
    <label>Thời gian chờ tối đa (giây)</label><input class="inp" id="s_timeout" type="number" value="${s.timeout}">
    <label>Duyệt prompt của Claude</label><span><input type="checkbox" id="s_review" ${s.review_claude ? "checked" : ""}> Prompt Claude thêm vào sẽ chờ bạn bấm Chạy</span>
    <label>Gửi nguyên văn prompt</label><span><input type="checkbox" id="s_raw" ${s.raw_prompt ? "checked" : ""}> Không để LUO-API bọc thêm mẫu câu</span>
    </div><div class="acts"><button class="btn pri" id="ssave">Lưu</button></div></div></div>`;
    $("#ssave").onclick = async () => { await api("/api/settings", { body: { api_url: $("#s_api_url").value.trim(), api_key: $("#s_api_key").value.trim(), parallel: +$("#s_parallel").value || 1, retries: +$("#s_retries").value || 0, timeout: +$("#s_timeout").value || 900, review_claude: $("#s_review").checked, raw_prompt: $("#s_raw").checked } }); toast("Đã lưu"); await loadSettings(); refresh(true); };
    return;
  }
  if (S.view === "guide") {
    $("#view").innerHTML = `<div class="page"><div class="card"><h3>Để Claude làm hàng loạt giúp bạn</h3><p>Giữ LUO Chat mở, rồi nói với Claude trong cửa sổ Claude Code, ví dụ: <i>“Làm 20 video 9:16 về quán cà phê, mỗi video một cảnh khác nhau.”</i></p><p style="margin-top:8px">Claude viết prompt và đưa vào hàng đợi. Chúng hiện ngay ở đây với nhãn <span class="tag cl">Claude</span>, tự chạy ngầm trên các tài khoản. Bạn chỉ việc xem prompt và video khi cần. Bật “Duyệt prompt của Claude” trong Cài đặt nếu muốn đọc trước khi chạy.</p></div>
    <div class="card"><h3>Lệnh Claude dùng (chatctl.py)</h3><pre>python app\\luo-chat\\chatctl.py add "mô tả video" --aspect 9:16 --video clip.mp4 --title "Lô cà phê"
python app\\luo-chat\\chatctl.py batch prompts.json
python app\\luo-chat\\chatctl.py status
python app\\luo-chat\\chatctl.py stop</pre></div>
    <div class="card"><h3>Mẹo</h3><p>• Đính kèm ảnh hoặc video tham chiếu bằng nút kẹp giấy / biểu tượng video.<br>• Nút đũa phép tạo hàng loạt: mỗi dòng một yêu cầu.<br>• Chọn nhiều video ở cột Media rồi bấm Ghép để nối thành một.</p></div></div>`;
  }
}

// ------------------------------------------------------------ vòng cập nhật
async function loadSettings() { S.settings = await api("/api/settings"); }
async function refreshChats() { const r = await api("/api/chats"); S.chats = r.chats; renderList(); }
async function refresh(force) {
  try {
    S.health = await api("/api/health").catch(() => ({ api: false }));
    await refreshChats();
    if (S.view === "chat") {
      if (S.chatId) { const c = await api("/api/chats/" + S.chatId).catch(() => null); if (c) { S.chat = c; renderThread(false); renderMedia(); const t = $("#ct"); if (t) t.textContent = c.title; fillDraftBtn(); } }
    }
    renderTop();
  } catch (e) { /* mất kết nối tạm thời */ }
}
function fillDraftBtn() {
  const t = $("#ctitle"); if (!t || !S.chat) return; const has = S.chat.messages.some(m => m.status === "draft"), cur = !!$("#runDr");
  if (has !== cur) fill();
}
let lastRev = "";
setInterval(async () => {
  try {
    const p = await api("/api/poll?rev=" + lastRev); S.poll = p; const chg = p.changed; lastRev = p.rev;
    if (chg) await refresh(); else renderTop();
  } catch (e) { S.health = { api: false }; renderTop(); }
}, 2000);

(async function init() {
  renderNav(); renderTop();
  await loadSettings();
  S.accounts = (await api("/api/accounts").catch(() => ({ accounts: [] }))).accounts;
  S.health = await api("/api/health").catch(() => ({ api: false }));
  await refreshChats();
  if (!S.chats.find(c => c.id === S.chatId)) S.chatId = S.chats[0]?.id || "";
  if (S.chatId) S.chat = await api("/api/chats/" + S.chatId).catch(() => null);
  renderTop(); renderView();
})();
