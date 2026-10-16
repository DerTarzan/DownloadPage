"use strict";
(() => {
  const state = {docs: [], prods: [], cats: []};
  let byProduct = new Map(), byCategory = new Map(), editing = null;
  const dlg = $("dlg-doc"), form = $("doc-form"), err = $("doc-error");
  const productName = (id) => { const p = byProduct.get(id); return p ? `${categoryPath(byCategory.get(p.category_id), byCategory)} / ${p.name}` : "Unbekanntes Produkt"; };

  async function load() {
    try {
      const [cats, prods, docs] = await Promise.all([api("GET", "/api/admin/categories"), api("GET", "/api/admin/products"), api("GET", "/api/admin/documents")]);
      Object.assign(state, {cats, prods, docs: [...docs].sort((a, b) => b.created_at.localeCompare(a.created_at))});
      byCategory = new Map(cats.map(c => [c.id, c])); byProduct = new Map(prods.map(p => [p.id, p]));
      render();
    } catch (e) { toast(e.message, "err"); }
  }

  function render() {
    const q = $("doc-search").value.trim().toLocaleLowerCase("de"), st = $("doc-status").value;
    const rows = state.docs.filter(d =>
      (!st || (st === "active") === d.active) &&
      (!q || [d.title, d.original_filename, productName(d.product_id)].some(t => t.toLocaleLowerCase("de").includes(q))));
    const body = $("doc-body"); body.replaceChildren();
    rows.forEach(d => body.append(row(d)));
    $("doc-table").hidden = !rows.length;
    const empty = $("doc-empty");
    empty.hidden = rows.length > 0;
    empty.textContent = state.docs.length ? "Keine passenden Dokumente gefunden." : "Noch keine Dokumente hochgeladen.";
    $("doc-count").textContent = state.docs.length ? `${rows.length} von ${plural(state.docs.length, "Dokument", "Dokumenten")}` : "";
  }

  function row(d) {
    const tr = el("tr");
    const cell = (label, ...nodes) => { const td = el("td"); td.dataset.label = label; td.append(...nodes); tr.append(td); return td; };
    const title = el("div", undefined, {className: "cell-title"});
    title.append(el("b", d.title), el("span", d.original_filename, {className: "slug"}));
    cell("Dokument", title);
    cell("Produkt", productName(d.product_id));
    cell("Version", `v${d.version}`);
    cell("Größe", fmtBytes(d.file_size));
    cell("Status", badge(d.active ? "aktiv" : "inaktiv", d.active ? "on" : "off"));
    cell("Hochgeladen", fmtDate(d.created_at));
    const actions = el("div", undefined, {className: "row-actions"});
    actions.append(btn("Bearbeiten", "btn-ghost", () => openEdit(d)), actionMenu(`Weitere Aktionen für ${d.title}`, [
      ...(d.active ? [{label: "PDF öffnen", href: d.download_url}, "-"] : []),
      {label: d.active ? "Deaktivieren" : "Aktivieren", onClick: () => toggle(d)},
      "-",
      {label: "Löschen …", danger: true, onClick: () => remove(d)},
    ]));
    cell("Aktionen", actions).className = "cell-actions";
    return tr;
  }

  async function toggle(d) {
    try { await api("PUT", `/api/admin/documents/${d.id}`, {active: !d.active}); toast(d.active ? "Dokument deaktiviert." : "Dokument aktiviert."); await load(); }
    catch (e) { toast(e.message, "err"); }
  }
  async function remove(d) {
    const ok = await confirmAction({
      title: "Dokument löschen?", message: `„${d.title}“ (Version ${d.version}) wird endgültig gelöscht, einschließlich der PDF-Datei.`,
      confirmLabel: "Dokument löschen", danger: true,
    });
    if (!ok) return;
    try { await api("DELETE", `/api/admin/documents/${d.id}`); toast("Dokument gelöscht."); await load(); }
    catch (e) { toast(e.message, "err"); }
  }

  function openEdit(d) {
    editing = d; err.textContent = "";
    $("doc-title").value = d.title; $("doc-version").value = d.version; $("doc-desc").value = d.description || "";
    const sel = $("doc-product"); sel.replaceChildren();
    state.prods.forEach(p => { const o = el("option", productName(p.id), {value: p.id}); o.selected = p.id === d.product_id; sel.append(o); });
    openDialog(dlg);
    $("doc-title").focus();
  }
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!form.reportValidity()) return;
    const save = $("doc-save"); save.disabled = true; err.textContent = "";
    const payload = {title: $("doc-title").value.trim(), version: $("doc-version").value.trim(), description: $("doc-desc").value.trim() || null};
    const product = Number($("doc-product").value);
    if (product !== editing.product_id) payload.product_id = product;
    try { await api("PUT", `/api/admin/documents/${editing.id}`, payload); closeDialog(dlg); toast("Änderungen gespeichert."); await load(); }
    catch (ex) { err.textContent = ex.message; }
    save.disabled = false;
  });
  $("doc-search").addEventListener("input", render);
  $("doc-status").addEventListener("change", render);
  load();
})();
