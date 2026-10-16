"use strict";
(async () => {
  try {
    const [cats, prods, docs, settings] = await Promise.all([
      api("GET", "/api/admin/categories"), api("GET", "/api/admin/products"),
      api("GET", "/api/admin/documents"), api("GET", "/api/admin/settings"),
    ]);
    $("s-c").textContent = cats.length; $("s-p").textContent = prods.length; $("s-d").textContent = docs.length;
    if (settings.maintenance_mode) {
      $("maintenance-banner").hidden = false;
      $("maint-state").textContent = "Aktuell aktiv – Website ist für Besucher gesperrt";
    }
    const productsById = new Map(prods.map(p => [p.id, p]));
    const recent = [...docs].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
    const list = $("recent");
    if (!recent.length) list.append(el("li", "Noch keine Dokumente hochgeladen.", {className: "recent-empty"}));
    recent.forEach(d => {
      const li = el("li"), text = el("div");
      text.append(el("b", d.title), el("span", `${productsById.get(d.product_id)?.name ?? "Unbekanntes Produkt"} · Version ${d.version}`));
      li.append(text, el("time", fmtDate(d.created_at)));
      list.append(li);
    });
  } catch (e) { toast(e.message, "err"); }
})();
