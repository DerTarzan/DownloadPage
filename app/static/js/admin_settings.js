"use strict";
(() => {
  const mm = $("mm"), state = $("mm-state"), message = $("mmsg"), save = $("maint-save");
  let saved = null;
  const paint = () => {
    const on = mm.checked;
    state.textContent = on ? "Gesperrt" : "Website ist online";
    state.className = "badge " + (on ? "off" : "on");
  };
  async function load() {
    try {
      saved = await api("GET", "/api/admin/settings");
      mm.checked = saved.maintenance_mode; message.value = saved.maintenance_message; paint();
    } catch (e) { toast(e.message, "err"); }
  }
  mm.addEventListener("change", paint);
  $("maint").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (mm.checked && !saved?.maintenance_mode) {
      const ok = await confirmAction({
        title: "Website sperren?", message: "Besucher sehen ab sofort nur noch die Wartungsseite. Die Verwaltung bleibt erreichbar.",
        confirmLabel: "Website sperren", danger: true,
      });
      if (!ok) { mm.checked = false; paint(); return; }
    }
    save.disabled = true;
    try {
      saved = await api("PUT", "/api/admin/settings", {maintenance_mode: mm.checked, maintenance_message: message.value});
      toast("Einstellungen gespeichert.");
    } catch (err) { toast(err.message, "err"); }
    save.disabled = false;
  });
  load();
})();

/* Chatbot an-/ausschalten: wirkt sofort, ohne Speichern-Knopf */
(() => {
  const cb = $("cb"), state = $("cb-state"), note = $("cb-note");
  const paint = (s) => {
    cb.checked = s.enabled;
    cb.disabled = false;
    if (!s.available) {
      state.textContent = "Serverseitig gesperrt";
      state.className = "badge off";
      note.textContent = "Der Chatbot ist in der Server-Konfiguration abgeschaltet (CHAT_ENABLED=false in der .env). Der Schalter wirkt erst, wenn das dort geändert wurde.";
      note.hidden = false;
    } else {
      state.textContent = s.enabled ? "Aktiv" : "Deaktiviert";
      state.className = "badge " + (s.enabled ? "on" : "off");
      note.hidden = true;
    }
  };
  cb.addEventListener("change", async () => {
    const want = cb.checked;
    if (!want) {
      const ok = await confirmAction({
        title: "Chatbot deaktivieren?", message: "Der Chat-Button verschwindet sofort für alle Besucher. Sie können ihn jederzeit wieder aktivieren.",
        confirmLabel: "Chatbot deaktivieren", danger: true,
      });
      if (!ok) { cb.checked = true; return; }
    }
    cb.disabled = true;
    try {
      paint(await api("PUT", "/api/admin/chatbot", {enabled: want}));
      toast(want ? "Chatbot aktiviert." : "Chatbot deaktiviert.");
    } catch (e) { cb.checked = !want; cb.disabled = false; toast(e.message, "err"); }
  });
  api("GET", "/api/admin/chatbot").then(paint).catch(e => toast(e.message, "err"));
})();
