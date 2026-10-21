"use strict";
/* Live-Log-Ansicht: lädt den Rückblick per API und hängt sich dann an den SSE-Stream (EventSource).
   Alle Inhalte werden per textContent gesetzt, nie als HTML. */
(() => {
  const view = $("log-view"), statusBadge = $("log-status"), empty = $("log-empty"), count = $("log-count");
  const search = $("log-search"), levelSel = $("log-level"), sourceSel = $("log-source");
  const pauseBtn = $("log-pause"), clearBtn = $("log-clear"), latestBtn = $("log-latest");

  const MAX_ROWS = 1500;
  const LEVELS = {DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40, CRITICAL: 50};
  const SOURCE_LABEL = {access: "Zugriff", audit: "Admin", chat: "Chat", app: "App", server: "Server", system: "System"};
  const entries = [];          // alle empfangenen Einträge (neueste zuletzt)
  const queue = [];            // während der Pause gesammelt
  let paused = false, lastId = 0, source = null, reconnectTimer = null, firstConnect = true;

  const time = (iso) => {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString("de-DE", {hour12: false}) + "." + String(d.getMilliseconds()).padStart(3, "0");
  };
  const atBottom = () => view.scrollHeight - view.scrollTop - view.clientHeight < 40;

  function matches(e) {
    if ((LEVELS[e.level] || 0) < LEVELS[levelSel.value]) return false;
    if (sourceSel.value && e.source !== sourceSel.value) return false;
    const q = search.value.trim().toLowerCase();
    return !q || (e.message + " " + e.logger + " " + (e.exc || "")).toLowerCase().includes(q);
  }

  function row(e) {
    const r = el("div", undefined, {className: `log-row lvl-${e.level.toLowerCase()}`});
    r.append(
      el("time", time(e.ts), {className: "log-time", dateTime: e.ts}),
      el("span", e.level, {className: "log-level"}),
      el("span", SOURCE_LABEL[e.source] || e.source, {className: `log-source src-${e.source}`}),
      el("span", e.message, {className: "log-msg"}),
    );
    if (e.exc) r.append(el("pre", e.exc, {className: "log-exc"}));
    return r;
  }

  function updateInfo() {
    const shown = view.children.length;
    count.textContent = entries.length ? `${shown} von ${entries.length} Einträgen` : "";
    const none = shown === 0;
    empty.hidden = !none;
    if (none) empty.textContent = entries.length ? "Keine Einträge für diese Filter." : "Noch keine Einträge. Sobald auf der Website etwas passiert, erscheint es hier.";
  }

  function addToView(batch) {
    const stick = atBottom();
    const frag = document.createDocumentFragment();
    batch.filter(matches).forEach(e => frag.append(row(e)));
    view.append(frag);
    while (view.children.length > MAX_ROWS) view.firstElementChild.remove();
    if (stick) view.scrollTop = view.scrollHeight; else latestBtn.hidden = false;
    updateInfo();
  }

  function receive(e) {
    lastId = Math.max(lastId, e.id);
    entries.push(e);
    if (entries.length > MAX_ROWS) entries.shift();
    if (paused) { queue.push(e); pauseBtn.textContent = `Fortsetzen (${queue.length} neu)`; } else addToView([e]);
  }

  function rebuild() {
    view.replaceChildren();
    addToView(entries);
    view.scrollTop = view.scrollHeight;
    latestBtn.hidden = true;
  }

  function setStatus(text, cls) { statusBadge.textContent = text; statusBadge.className = "badge " + cls; }

  function connect() {
    clearTimeout(reconnectTimer);
    if (source) source.close();
    source = new EventSource(`/api/admin/logs/stream?after=${lastId}`);
    source.addEventListener("open", () => setStatus("Live", "on"));
    source.addEventListener("log", (ev) => { try { receive(JSON.parse(ev.data)); } catch (_) { /* defekte Zeile überspringen */ } });
    source.addEventListener("error", async () => {
      // EventSource verbindet bei Netzfehlern selbst neu. Bei Abbruch durch den Server (z. B. 401) prüfen wir die Sitzung.
      if (source.readyState === EventSource.CONNECTING) { setStatus("Verbindung wird neu aufgebaut …", "off"); return; }
      source.close();
      setStatus("Getrennt", "off");
      const me = await fetch("/auth/me").catch(() => null);
      if (me && me.status === 401) { location.href = "/admin/login"; return; }
      reconnectTimer = setTimeout(connect, 3000);
    });
  }

  pauseBtn.addEventListener("click", () => {
    paused = !paused;
    pauseBtn.setAttribute("aria-pressed", String(paused));
    if (paused) { setStatus("Pausiert", "off"); pauseBtn.textContent = "Fortsetzen"; return; }
    pauseBtn.textContent = "Pausieren";
    setStatus(source && source.readyState === EventSource.OPEN ? "Live" : "Verbinde …", source && source.readyState === EventSource.OPEN ? "on" : "off");
    const batch = queue.splice(0);
    addToView(batch);
  });
  clearBtn.addEventListener("click", () => { entries.length = 0; queue.length = 0; rebuild(); if (paused) pauseBtn.textContent = "Fortsetzen"; });
  latestBtn.addEventListener("click", () => { view.scrollTop = view.scrollHeight; latestBtn.hidden = true; });
  view.addEventListener("scroll", () => { if (atBottom()) latestBtn.hidden = true; });
  [levelSel, sourceSel].forEach(c => c.addEventListener("change", rebuild));
  search.addEventListener("input", rebuild);

  updateInfo();
  connect();
})();
