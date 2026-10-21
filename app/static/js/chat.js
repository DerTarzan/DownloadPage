/* Chat-Widget der öffentlichen Seiten: Produkt-/Dokumentensuche in natürlicher Sprache (Deutsch/Englisch).
   Die Sprache wählt der Besucher seitenweit über das Lesezeichen im Footer; der Chat übernimmt <html lang>.
   Alle Inhalte werden per textContent gesetzt (kein HTML-Einfügen); Links nur zu relativen Pfaden der eigenen Seite. */
(function () {
  "use strict";
  var root = document.getElementById("chat-root");
  if (!root) return;

  var ENDPOINT = root.dataset.endpoint || "/api/chat";
  var MAX_LEN = parseInt(root.dataset.maxLength, 10) || 300;
  var STORE_KEY = "chat.session.v1";
  var MAX_STORED = 40;
  var TIMEOUT_MS = 15000;

  var I18N = {
    de: {
      title: "Produktsuche", open: "Chat öffnen", close: "Chat schließen", newChat: "Neue Unterhaltung",
      placeholder: "Frage eingeben, z. B. ein Produktname …", send: "Senden",
      searching: "Suche läuft …", you: "Du", bot: "Assistent",
      greeting: "Hallo! Ich helfe dir dabei, Produkte, Kategorien und Dokumente zu finden. Was suchst du?",
      productPage: "Zur Produktseite", categoryPage: "Zur Kategorie", documents: "Dokumente",
      similar: "Ähnliche Produkte", categories: "Kategorien", products: "Produkte", download: "Herunterladen",
      errNetwork: "Keine Verbindung zum Server. Bitte prüfe deine Internetverbindung und versuche es erneut.",
      errServer: "Die Suche ist gerade nicht verfügbar. Bitte versuche es später noch einmal.",
      errRate: "Das waren sehr viele Anfragen. Bitte warte einen Moment.",
      errLong: "Deine Nachricht ist zu lang. Bitte fasse dich kürzer.",
      errMaint: "Die Seite befindet sich gerade in Wartung.",
      errOff: "Die Chat-Suche ist derzeit nicht aktiviert.",
      errTimeout: "Die Suche hat zu lange gedauert. Bitte versuche es erneut."
    },
    en: {
      title: "Product search", open: "Open chat", close: "Close chat", newChat: "New conversation",
      placeholder: "Type a question, e.g. a product name …", send: "Send",
      searching: "Searching …", you: "You", bot: "Assistant",
      greeting: "Hello! I can help you find products, categories and documents. What are you looking for?",
      productPage: "Open product page", categoryPage: "Open category", documents: "Documents",
      similar: "Similar products", categories: "Categories", products: "Products", download: "Download",
      errNetwork: "Can't reach the server. Please check your connection and try again.",
      errServer: "Search is currently unavailable. Please try again later.",
      errRate: "That was a lot of requests. Please wait a moment.",
      errLong: "Your message is too long. Please shorten it.",
      errMaint: "The site is currently under maintenance.",
      errOff: "Chat search is currently disabled.",
      errTimeout: "The search took too long. Please try again."
    }
  };

  /* ---------- Zustand (nur diese Browser-Sitzung) ---------- */
  var pageLang = (document.documentElement.lang || "de").slice(0, 2).toLowerCase();
  var state = { lang: pageLang === "en" ? "en" : "de", messages: [], context: null };
  try {
    var saved = JSON.parse(sessionStorage.getItem(STORE_KEY) || "null");
    if (saved && Array.isArray(saved.messages)) {
      state.messages = saved.messages.slice(-MAX_STORED);
      state.context = saved.context || null;
    }
  } catch (e) { /* Speicher gesperrt: Chat funktioniert trotzdem */ }

  function persist() {
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify({ messages: state.messages.slice(-MAX_STORED), context: state.context }));
    } catch (e) { /* ignorieren */ }
  }
  function t(key) { return I18N[state.lang][key]; }

  /* ---------- DOM-Helfer ---------- */
  var SVG_NS = "http://www.w3.org/2000/svg";
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function icon(paths, fill) {
    var s = document.createElementNS(SVG_NS, "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("fill", fill ? "currentColor" : "none");
    s.setAttribute("stroke", "currentColor");
    s.setAttribute("stroke-width", "2");
    s.setAttribute("stroke-linecap", "round");
    s.setAttribute("stroke-linejoin", "round");
    s.setAttribute("aria-hidden", "true");
    s.setAttribute("focusable", "false");
    paths.forEach(function (d) {
      var p = document.createElementNS(SVG_NS, "path");
      p.setAttribute("d", d);
      s.appendChild(p);
    });
    return s;
  }
  var ICON_CHAT = ["M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-3.6-.8L3 21l1.9-5.1A8.4 8.4 0 1 1 21 11.5z"];
  var ICON_CLOSE = ["M6 6l12 12", "M18 6L6 18"];
  var ICON_SEND = ["M22 2L11 13", "M22 2l-7 20-4-9-9-4z"];
  var ICON_NEW = ["M12 5v14", "M5 12h14"];

  function safeHref(url) {
    return typeof url === "string" && url.charAt(0) === "/" && url.charAt(1) !== "/" && url.indexOf("\\") === -1 ? url : null;
  }
  function link(url, cls, label, small) {
    var href = safeHref(url);
    if (!href) return null;
    var a = el("a", "chat-link" + (cls ? " " + cls : ""));
    a.href = href;
    a.appendChild(el("span", null, label));
    if (small) a.appendChild(el("small", null, small));
    return a;
  }
  function fileSize(bytes) {
    if (typeof bytes !== "number") return "";
    return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  /* ---------- Aufbau ---------- */
  var fab = el("button", "chat-fab");
  fab.type = "button";
  fab.id = "chat-toggle";
  fab.setAttribute("aria-controls", "chat-panel");
  fab.setAttribute("aria-expanded", "false");
  fab.appendChild(icon(ICON_CHAT));

  var panel = el("section", "chat-panel");
  panel.id = "chat-panel";
  panel.hidden = true;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-labelledby", "chat-title");

  var head = el("div", "chat-head");
  var title = el("h2", null);
  title.id = "chat-title";
  var newBtn = el("button", "chat-icon-btn");
  newBtn.type = "button";
  newBtn.appendChild(icon(ICON_NEW));
  var closeBtn = el("button", "chat-icon-btn");
  closeBtn.type = "button";
  closeBtn.appendChild(icon(ICON_CLOSE));
  head.append(title, newBtn, closeBtn);

  var log = el("div", "chat-log");
  log.setAttribute("role", "log");
  log.setAttribute("aria-live", "polite");
  log.tabIndex = 0;

  var form = el("form", "chat-form");
  form.setAttribute("novalidate", "");
  var input = el("input");
  input.type = "text";
  input.name = "message";
  input.maxLength = MAX_LEN;
  input.autocomplete = "off";
  input.enterKeyHint = "send";
  var sendBtn = el("button", "chat-send");
  sendBtn.type = "submit";
  sendBtn.appendChild(icon(ICON_SEND));
  form.append(input, sendBtn);

  panel.append(head, log, form);
  root.append(panel, fab);

  /* ---------- Rendering ---------- */
  function renderProductCard(p, withDocs) {
    var card = el("article", "chat-card");
    var main = el("div", "chat-card-main");
    var img = safeHref(p.image_url);
    if (img) {
      var im = el("img");
      im.src = img;
      im.alt = "";
      im.loading = "lazy";
      im.width = 56;
      im.height = 56;
      main.appendChild(im);
    }
    var info = el("div");
    var name = link(p.url, "", p.name);
    var heading = el("div", "chat-card-title");
    if (name) { name.className = ""; heading.appendChild(name); } else { heading.textContent = p.name; }
    info.appendChild(heading);
    if (p.category_path && p.category_path.length) info.appendChild(el("p", "chat-card-meta", p.category_path.join(" › ")));
    if (p.description) info.appendChild(el("p", "chat-card-desc", p.description));
    main.appendChild(info);
    card.appendChild(main);
    var actions = el("div", "chat-card-actions");
    var page = link(p.url, "primary", t("productPage"));
    if (page) actions.appendChild(page);
    card.appendChild(actions);
    if (withDocs && p.documents && p.documents.length) {
      var docs = el("div", "chat-card-actions");
      docs.setAttribute("role", "group");
      docs.setAttribute("aria-label", t("documents"));
      p.documents.forEach(function (d) {
        var meta = [d.version ? "v" + d.version : "", fileSize(d.file_size)].filter(Boolean).join(" · ");
        var a = link(d.url, d.matched ? "matched" : "", "PDF · " + d.title, meta);
        if (a) { a.title = t("download"); docs.appendChild(a); }
      });
      card.appendChild(docs);
    }
    return card;
  }
  function renderCategoryCard(c) {
    var card = el("article", "chat-card");
    var a = link(c.url, "", c.name, typeof c.product_count === "number" ? c.product_count + " " + t("products") : "");
    if (a) card.appendChild(a); else card.appendChild(el("span", null, c.name));
    return card;
  }
  function section(label, children) {
    var wrap = el("div", "chat-cards");
    wrap.appendChild(el("p", "chat-label", label));
    children.forEach(function (c) { wrap.appendChild(c); });
    return wrap;
  }

  function appendMessage(m) {
    var bubble = el("div", "chat-msg " + (m.role === "user" ? "user" : "bot") + (m.error ? " error" : ""));
    var who = el("span", "chat-sr", (m.role === "user" ? t("you") : t("bot")) + ": ");
    bubble.append(who, document.createTextNode(m.text));
    log.appendChild(bubble);
    var d = m.data;
    if (d) {
      if (d.categories && d.categories.length) log.appendChild(section(t("categories"), d.categories.map(renderCategoryCard)));
      if (d.results && d.results.length) {
        log.appendChild(section(t("products"), d.results.map(function (p) { return renderProductCard(p, true); })));
      }
      if (d.similar && d.similar.length) log.appendChild(section(t("similar"), d.similar.map(function (p) { return renderProductCard(p, false); })));
    }
  }

  function render() {
    title.textContent = t("title");
    newBtn.setAttribute("aria-label", t("newChat"));
    newBtn.title = t("newChat");
    closeBtn.setAttribute("aria-label", t("close"));
    closeBtn.title = t("close");
    input.placeholder = t("placeholder");
    input.setAttribute("aria-label", t("placeholder"));
    sendBtn.setAttribute("aria-label", t("send"));
    sendBtn.title = t("send");
    fab.setAttribute("aria-label", isOpen() ? t("close") : t("open"));
    fab.title = isOpen() ? t("close") : t("open");
    panel.lang = state.lang;
    log.setAttribute("aria-label", t("title"));
    log.textContent = "";
    appendMessage({ role: "bot", text: t("greeting") });  // Begrüßung immer in der aktuellen Sprache, nicht gespeichert
    state.messages.forEach(appendMessage);
    scrollDown();
  }
  function scrollDown() { log.scrollTop = log.scrollHeight; }

  /* ---------- Öffnen / Schließen ---------- */
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var closeTimer = null;
  function isOpen() { return !panel.hidden && panel.classList.contains("is-open"); }

  function openChat() {
    clearTimeout(closeTimer);
    panel.hidden = false;
    void panel.offsetWidth;  // Reflow, damit die Übergänge starten
    panel.classList.add("is-open");
    fab.setAttribute("aria-expanded", "true");
    fab.setAttribute("aria-label", t("close"));
    fab.title = t("close");
    // Scoll Animation
    scrollDown();
    input.focus({ preventScroll: true });
  }
  function closeChat(returnFocus) {
    panel.classList.remove("is-open");
    fab.setAttribute("aria-expanded", "false");
    fab.setAttribute("aria-label", t("open"));
    fab.title = t("open");
    var done = function () { if (!panel.classList.contains("is-open")) panel.hidden = true; };
    if (reduceMotion) done(); else closeTimer = setTimeout(done, 220);
    if (returnFocus) fab.focus();
  }

  fab.addEventListener("click", function () { if (isOpen()) closeChat(false); else openChat(); });
  closeBtn.addEventListener("click", function () { closeChat(true); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && isOpen()) { closeChat(panel.contains(document.activeElement) || document.activeElement === fab); }
  });

  /* ---------- Neustart ---------- */
  newBtn.addEventListener("click", function () {
    if (busy) return;
    state.messages = [];
    state.context = null;
    persist();
    render();
    input.focus();
  });

  /* ---------- Senden ---------- */
  var busy = false;

  function currentPageContext() {
    var m = /^\/([a-z0-9-]+)\/([a-z0-9-]+)\/?$/.exec(location.pathname);
    return m ? { category_slug: m[1], product_slug: m[2] } : null;
  }
  function contextFrom(data) {
    if (!data || !data.results || data.results.length !== 1) return null;
    var m = /^\/([a-z0-9-]+)\/([a-z0-9-]+)$/.exec(data.results[0].url || "");
    return m ? { category_slug: m[1], product_slug: m[2] } : null;
  }
  function setBusy(on) {
    busy = on;
    input.readOnly = on;
    sendBtn.disabled = on;
    log.setAttribute("aria-busy", on ? "true" : "false");
  }
  function typingBubble() {
    var b = el("div", "chat-msg bot");
    var dots = el("span", "chat-typing");
    dots.setAttribute("role", "status");
    dots.setAttribute("aria-label", t("searching"));
    dots.append(el("i"), el("i"), el("i"));
    b.appendChild(dots);
    return b;
  }
  function errorKey(status) {
    if (status === 429) return "errRate";
    if (status === 503) return "errMaint";
    if (status === 404) return "errOff";
    if (status === 413 || status === 422) return "errLong";
    return "errServer";
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = input.value.replace(/\s+/g, " ").trim();
    if (!text || busy) return;
    if (text.length > MAX_LEN) text = text.slice(0, MAX_LEN);
    setBusy(true);
    input.value = "";
    var userMsg = { role: "user", text: text };
    state.messages.push(userMsg);
    appendMessage(userMsg);
    var wait = typingBubble();
    log.appendChild(wait);
    scrollDown();

    var ctrl = typeof AbortController === "function" ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, TIMEOUT_MS);
    var lang = state.lang;
    var body = { message: text, lang: lang };
    var ctx = state.context || currentPageContext();
    if (ctx) body.context = ctx;

    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(body),
      credentials: "same-origin",
      signal: ctrl ? ctrl.signal : undefined
    }).then(function (r) {
      if (!r.ok) { var err = new Error("http"); err.status = r.status; throw err; }
      return r.json();
    }).then(function (data) {
      var next = contextFrom(data);
      if (next) state.context = next;
      return { role: "bot", text: String(data.reply || ""), data: { results: data.results, similar: data.similar, categories: data.categories } };
    }).catch(function (err) {
      var key = err && err.name === "AbortError" ? "errTimeout" : err && err.status ? errorKey(err.status) : "errNetwork";
      return { role: "bot", text: t(key), error: true };
    }).then(function (botMsg) {
      clearTimeout(timer);
      wait.remove();
      state.messages.push(botMsg);
      appendMessage(botMsg);
      persist();
      setBusy(false);
      scrollDown();
      if (isOpen()) input.focus({ preventScroll: true });
    });
  });

  render();
  persist();
})();
