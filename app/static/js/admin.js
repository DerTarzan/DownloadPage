"use strict";
/* Gemeinsame Helfer der Admin-Oberfläche (API, Dialoge, Menüs, Navigation).
   Daten aus der API niemals als HTML-String einfügen – immer el()/textContent verwenden. */

// ---- API: Cookie-Session + CSRF-Header ----
let CSRF = null;
async function api(method, url, body) {
  if (!CSRF) {
    const me = await fetch("/auth/me");
    if (!me.ok) { location.href = "/admin/login"; throw new Error("not logged in"); }
    CSRF = (await me.json()).csrf_token;
  }
  const opts = {method, headers: {"X-CSRF-Token": CSRF}};
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const r = await fetch(url, opts);
  if (r.status === 401) { location.href = "/admin/login"; throw new Error("unauthorized"); }
  const data = r.status === 204 ? null : await r.json().catch(() => null);
  if (!r.ok) throw new Error(typeof data?.detail === "string" ? data.detail : JSON.stringify(data?.detail ?? r.status));
  return data;
}

// ---- DOM-Helfer ----
const $ = (id) => document.getElementById(id);
const el = (tag, text, attrs) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; return Object.assign(e, attrs || {}); };
const badge = (t, cls) => el("span", t, {className: "badge " + (cls || "")});
const btn = (t, cls, fn) => el("button", t, {className: "btn btn-sm " + cls, type: "button", onclick: fn});

// ---- Formatierung ----
const fmtBytes = (n) => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1).replace(".", ",")} MB`;
const fmtDate = (iso) => {
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("de-DE", {day: "2-digit", month: "2-digit", year: "numeric"});
};
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

// ---- Rückmeldungen ----
function toast(text, kind = "ok") {
  const box = $("toasts");
  const item = el("div", text, {className: `toast toast-${kind}`});
  if (kind === "err") item.setAttribute("role", "alert");
  const close = el("button", "×", {className: "toast-close", type: "button", title: "Schließen"});
  close.setAttribute("aria-label", "Meldung schließen");
  close.addEventListener("click", () => item.remove());
  item.append(close);
  box.append(item);
  setTimeout(() => item.remove(), kind === "err" ? 9000 : 4500);
}

// ---- Dialoge ----
function openDialog(dialog) { if (!dialog.open) dialog.showModal(); }
function closeDialog(dialog) { if (dialog.open) dialog.close(); }
document.addEventListener("click", (e) => {
  const dialog = e.target instanceof HTMLDialogElement ? e.target : null;
  if (dialog && dialog.classList.contains("dialog-sm")) {         // Klick auf den Hintergrund (nur Rückfragen, Formulare behalten Eingaben)
    const r = dialog.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close();
  }
  const closer = e.target.closest?.("[data-close]");
  if (closer) closeDialog(closer.closest("dialog"));
});

/* Bestätigungsdialog. Liefert true, wenn bestätigt wurde. */
function confirmAction({title, message, details = [], confirmLabel = "Bestätigen", danger = false}) {
  const dialog = $("confirm-dialog"), ok = $("confirm-ok"), list = $("confirm-details");
  $("confirm-title").textContent = title;
  $("confirm-text").textContent = message;
  list.replaceChildren(...details.map(d => el("li", d)));
  list.hidden = !details.length;
  ok.textContent = confirmLabel;
  ok.className = "btn" + (danger ? " btn-danger-solid" : "");
  dialog.returnValue = "";
  return new Promise(resolve => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "ok"), {once: true});
    openDialog(dialog);
  });
}

// ---- Aktionsmenü (⋯) ----
/* items: [{label, onClick, href, danger}] oder "-" als Trenner */
function actionMenu(label, items) {
  const menu = el("details", undefined, {className: "menu"});
  const summary = el("summary", undefined, {className: "btn btn-ghost btn-sm menu-btn"});
  summary.setAttribute("aria-label", label);
  summary.title = label;
  summary.append(el("span", "⋯", {className: "menu-dots"}));
  const list = el("div", undefined, {className: "menu-list"});
  items.forEach(item => {
    if (item === "-") { list.append(el("hr")); return; }
    const node = item.href
      ? el("a", item.label, {href: item.href, className: "menu-item"})
      : el("button", item.label, {type: "button", className: "menu-item" + (item.danger ? " is-danger" : ""),
          onclick: () => { menu.open = false; item.onClick(); }});
    list.append(node);
  });
  menu.append(summary, list);
  return menu;
}
const closeMenus = (except) => document.querySelectorAll("details.menu[open]").forEach(m => { if (m !== except) m.open = false; });
document.addEventListener("click", (e) => closeMenus(e.target.closest?.("details.menu")));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenus(); });

// ---- Kategorien-Helfer ----
function categoryPath(category, byId) {
  const parts = [], seen = new Set();
  let current = category;
  while (current) {
    if (seen.has(current.id)) throw new Error("Zyklus in der Kategorienstruktur.");
    seen.add(current.id);
    parts.push(current.name);
    current = current.parent_id == null ? null : byId.get(current.parent_id);
  }
  return parts.reverse().join(" / ");
}
function descendantIds(categoryId, childrenByParent) {
  const found = new Set(), pending = [categoryId];
  while (pending.length) {
    (childrenByParent.get(pending.pop()) || []).forEach(c => {
      if (!found.has(c.id)) { found.add(c.id); pending.push(c.id); }
    });
  }
  return found;
}
function groupBy(list, keyOf) {
  const map = new Map();
  list.forEach(item => { const k = keyOf(item); if (!map.has(k)) map.set(k, []); map.get(k).push(item); });
  return map;
}

/* Bildfeld eines Dialogs (Vorschau, Auswahl, „entfernen“). IDs: <p>-image, <p>-preview, <p>-image-remove, <p>-remove-wrap, <p>-image-label */
function imageField(p) {
  const input = $(`${p}-image`), preview = $(`${p}-preview`), remove = $(`${p}-image-remove`), wrap = $(`${p}-remove-wrap`), label = $(`${p}-image-label`);
  let current = "", objectUrl = "";
  const show = () => {
    const url = objectUrl || (remove.checked ? "" : current);
    preview.hidden = !url;
    if (url) preview.src = url; else preview.removeAttribute("src");
  };
  const dropObjectUrl = () => { if (objectUrl) URL.revokeObjectURL(objectUrl); objectUrl = ""; };
  input.addEventListener("change", () => {
    dropObjectUrl();
    if (input.files[0]) { objectUrl = URL.createObjectURL(input.files[0]); remove.checked = false; }
    show();
  });
  remove.addEventListener("change", () => { if (remove.checked) { input.value = ""; dropObjectUrl(); } show(); });
  return {
    reset(url) {
      dropObjectUrl(); current = url || ""; input.value = ""; remove.checked = false;
      wrap.hidden = !current;
      label.firstChild.textContent = current ? "Bild ersetzen " : "Bild auswählen ";
      show();
    },
    file: () => input.files[0] || null,
    removeRequested: () => remove.checked,
  };
}
/* Lädt ein Bild hoch bzw. entfernt es, je nach Auswahl im Bildfeld. */
async function applyImage(field, endpoint) {
  if (field.file()) {
    const form = new FormData();
    form.append("file", field.file());
    await api("POST", endpoint, form);
  } else if (field.removeRequested()) {
    await api("DELETE", endpoint);
  }
}

// ---- Seitenrahmen: Navigation (mobil als Drawer), Abmelden ----
(() => {
  const toggle = $("nav-toggle"), scrim = $("nav-scrim");
  const setOpen = (open) => {
    document.body.classList.toggle("nav-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Navigation schließen" : "Navigation öffnen");
    scrim.hidden = !open;
  };
  toggle.addEventListener("click", () => setOpen(!document.body.classList.contains("nav-open")));
  scrim.addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && document.body.classList.contains("nav-open")) { setOpen(false); toggle.focus(); } });
  matchMedia("(min-width: 901px)").addEventListener("change", (m) => { if (m.matches) setOpen(false); });
  document.querySelectorAll("#logout, #logout-2").forEach(b => b.addEventListener("click", async () => {
    try { await api("POST", "/auth/logout"); } finally { location.href = "/admin/login"; }
  }));
})();
