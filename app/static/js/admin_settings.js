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
