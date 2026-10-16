"use strict";
/* Kategorien & Produkte: Baumansicht, Anlegen/Bearbeiten in Dialogen, Aktivieren/Löschen mit Rückfrage. */
(() => {
  const state = {cats: [], prods: [], docs: []};
  let byId = new Map(), childrenByParent = new Map(), productsByCategory = new Map(), docsByProduct = new Map();
  const expanded = {cats: new Set(), prods: new Set()};
  let firstLoad = true, query = "";
  let editingCategory = null, editingProduct = null;

  const catDlg = $("dlg-category"), catForm = $("category-form"), catError = $("category-error");
  const prodDlg = $("dlg-product"), prodForm = $("product-form"), prodError = $("product-error");
  const catImage = imageField("cat"), prodImage = imageField("prod");

  // ---------- Daten ----------
  async function load() {
    try {
      const [cats, prods, docs] = await Promise.all([api("GET", "/api/admin/categories"), api("GET", "/api/admin/products"), api("GET", "/api/admin/documents")]);
      Object.assign(state, {cats, prods, docs});
      byId = new Map(cats.map(c => [c.id, c]));
      childrenByParent = groupBy(cats, c => c.parent_id);
      productsByCategory = groupBy(prods, p => p.category_id);
      docsByProduct = groupBy(docs, d => d.product_id);
      if (firstLoad) { (childrenByParent.get(null) || []).forEach(c => expanded.cats.add(c.id)); firstLoad = false; }
      render();
    } catch (e) { toast(e.message, "err"); }
  }
  async function act(fn, okText) {
    try { await fn(); if (okText) toast(okText); await load(); }
    catch (e) { toast(e.message, "err"); }
  }

  // ---------- Darstellung ----------
  function render() {
    const tree = $("tree");
    tree.replaceChildren();
    tree.setAttribute("aria-busy", "false");
    const q = query;
    let hits = 0, visibleRoots = 0;

    const build = (c, depth) => {
      const selfMatch = !q || c.name.toLocaleLowerCase("de").includes(q);
      const allProducts = productsByCategory.get(c.id) || [];
      const matchingProducts = q ? allProducts.filter(p => p.name.toLocaleLowerCase("de").includes(q)) : allProducts;
      const products = selfMatch ? allProducts : matchingProducts;
      const childNodes = (childrenByParent.get(c.id) || []).map(ch => build(ch, depth + 1)).filter(Boolean);
      if (q && !selfMatch && !products.length && !childNodes.length) return null;
      if (q) hits += Number(selfMatch) + matchingProducts.length;
      const isOpen = expanded.cats.has(c.id) || Boolean(q && (matchingProducts.length || childNodes.length));
      return categoryNode(c, products, childNodes, isOpen, depth);
    };
    (childrenByParent.get(null) || []).forEach(root => { const n = build(root, 0); if (n) { tree.append(n); visibleRoots++; } });

    if (!state.cats.length) {
      tree.append(el("div", undefined, {className: "empty"}));
      tree.lastChild.append(el("p", "Noch keine Kategorien angelegt."), btn("Erste Kategorie anlegen", "", () => openCategoryDialog()));
    }
    $("category-search-status").textContent = q ? plural(hits, "Treffer", "Treffer") : "";
    $("category-search-empty").hidden = !q || visibleRoots > 0;
  }

  function categoryNode(c, products, childNodes, isOpen, depth) {
    const section = el("section", undefined, {className: "cat" + (depth ? " cat-nested" : "")});
    section.dataset.categoryId = c.id;
    const bodyId = `cat-body-${c.id}`;
    const head = el("div", undefined, {className: "cat-head"});
    const toggle = el("button", undefined, {type: "button", className: "chevron"});
    toggle.setAttribute("aria-expanded", String(isOpen));
    toggle.setAttribute("aria-controls", bodyId);
    toggle.setAttribute("aria-label", `${c.name} ${isOpen ? "zuklappen" : "aufklappen"}`);
    toggle.append(chevronIcon());
    toggle.addEventListener("click", () => { flip(expanded.cats, c.id); render(); focusToggle(`[data-category-id="${c.id}"] > .cat-head .chevron`); });

    const main = el("div", undefined, {className: "cat-main"});
    const title = el("h3", c.name, {className: "cat-name"});
    const meta = el("div", undefined, {className: "meta"});
    meta.append(el("span", `/${c.slug}`, {className: "slug"}));
    if (!c.active) meta.append(badge("inaktiv", "off"));
    const kids = (childrenByParent.get(c.id) || []).length, own = (productsByCategory.get(c.id) || []).length;
    meta.append(el("span", [kids ? plural(kids, "Unterkategorie", "Unterkategorien") : "", plural(own, "Produkt", "Produkte")].filter(Boolean).join(" · "), {className: "counts"}));
    main.append(title, meta);

    const actions = el("div", undefined, {className: "row-actions"});
    actions.append(btn("Bearbeiten", "btn-ghost", () => openCategoryDialog({category: c})), actionMenu(`Weitere Aktionen für ${c.name}`, [
      {label: c.active ? "Deaktivieren" : "Aktivieren", onClick: () => act(() => api("PUT", `/api/admin/categories/${c.id}`, {active: !c.active}), c.active ? "Kategorie deaktiviert." : "Kategorie aktiviert.")},
      "-",
      {label: "Löschen …", danger: true, onClick: () => deleteCategory(c)},
    ]));
    head.append(toggle, main, actions);
    section.append(head);

    const body = el("div", undefined, {className: "cat-body", id: bodyId});
    body.hidden = !isOpen;
    if (isOpen) {
      if (c.description) body.append(el("p", c.description, {className: "cat-desc"}));
      const list = el("ul", undefined, {className: "items"});
      products.forEach(p => list.append(productNode(p, c)));
      if (products.length) body.append(list);
      else if (!childNodes.length) body.append(el("p", "In dieser Kategorie gibt es noch nichts.", {className: "cat-empty"}));
      const add = el("div", undefined, {className: "cat-add"});
      add.append(btn("+ Produkt hinzufügen", "btn-ghost", () => openProductDialog({categoryId: c.id})),
        btn("+ Unterkategorie", "btn-ghost", () => openCategoryDialog({parentId: c.id})));
      body.append(add);
      if (childNodes.length) {
        const kidsBox = el("div", undefined, {className: "cat-children"});
        kidsBox.setAttribute("aria-label", `Unterkategorien von ${c.name}`);
        kidsBox.append(...childNodes);
        body.append(kidsBox);
      }
    }
    section.append(body);
    return section;
  }

  function productNode(p, c) {
    const li = el("li", undefined, {className: "item"});
    li.dataset.productId = p.id;
    const docs = docsByProduct.get(p.id) || [];
    const open = expanded.prods.has(p.id);
    const head = el("div", undefined, {className: "item-head"});
    const main = el("div", undefined, {className: "item-main"});
    main.append(el("b", p.name), el("span", `/${c.slug}/${p.slug}`, {className: "slug"}), ...(p.active ? [] : [badge("inaktiv", "off")]));
    const docToggle = el("button", plural(docs.length, "Dokument", "Dokumente"), {type: "button", className: "link-btn"});
    docToggle.disabled = !docs.length;
    docToggle.setAttribute("aria-expanded", String(open && docs.length > 0));
    docToggle.addEventListener("click", () => { flip(expanded.prods, p.id); render(); focusToggle(`[data-product-id="${p.id}"] .link-btn`); });
    const actions = el("div", undefined, {className: "row-actions"});
    actions.append(btn("Bearbeiten", "btn-ghost", () => openProductDialog({product: p})), actionMenu(`Weitere Aktionen für ${p.name}`, [
      {label: "PDF hochladen", href: `/admin/upload?product=${p.id}`},
      {label: p.active ? "Deaktivieren" : "Aktivieren", onClick: () => act(() => api("PUT", `/api/admin/products/${p.id}`, {active: !p.active}), p.active ? "Produkt deaktiviert." : "Produkt aktiviert.")},
      "-",
      {label: "Löschen …", danger: true, onClick: () => deleteProduct(p, docs.length)},
    ]));
    head.append(main, docToggle, actions);
    li.append(head);
    if (open && docs.length) {
      const list = el("ul", undefined, {className: "docs"});
      docs.forEach(d => {
        const row = el("li", undefined, {className: "doc"});
        const label = el("div", undefined, {className: "doc-main"});
        label.append(el("span", d.title), el("span", `Version ${d.version}`, {className: "slug"}), ...(d.active ? [] : [badge("inaktiv", "off")]));
        row.append(label, actionMenu(`Weitere Aktionen für ${d.title}`, [
          ...(d.active ? [{label: "PDF öffnen", href: d.download_url}, "-"] : []),
          {label: d.active ? "Deaktivieren" : "Aktivieren", onClick: () => act(() => api("PUT", `/api/admin/documents/${d.id}`, {active: !d.active}), d.active ? "Dokument deaktiviert." : "Dokument aktiviert.")},
          "-",
          {label: "Löschen …", danger: true, onClick: () => deleteDocument(d)},
        ]));
        list.append(row);
      });
      li.append(list);
    }
    return li;
  }

  const chevronIcon = () => {
    const ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg"), path = document.createElementNS(ns, "path");
    svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("aria-hidden", "true");
    path.setAttribute("d", "M9 6l6 6-6 6"); path.setAttribute("fill", "none"); path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "2"); path.setAttribute("stroke-linecap", "round"); path.setAttribute("stroke-linejoin", "round");
    svg.append(path);
    return svg;
  };
  const flip = (set, id) => set.has(id) ? set.delete(id) : set.add(id);
  const focusToggle = (selector) => document.querySelector(selector)?.focus();

  // ---------- Löschen mit Rückfrage ----------
  async function deleteCategory(c) {
    const ids = descendantIds(c.id, childrenByParent), all = [c.id, ...ids];
    const prods = all.flatMap(id => productsByCategory.get(id) || []);
    const docs = prods.flatMap(p => docsByProduct.get(p.id) || []);
    const details = [
      ids.size ? plural(ids.size, "Unterkategorie", "Unterkategorien") : "", prods.length ? plural(prods.length, "Produkt", "Produkte") : "",
      docs.length ? plural(docs.length, "Dokument", "Dokumente") + " (PDF-Dateien)" : "", "Alle zugehörigen Bilder und Dateien",
    ].filter(Boolean);
    const ok = await confirmAction({
      title: `Kategorie „${c.name}“ löschen?`, message: "Dieser Vorgang kann nicht rückgängig gemacht werden. Folgendes wird mitgelöscht:",
      details, confirmLabel: "Kategorie löschen", danger: true,
    });
    if (ok) act(() => api("DELETE", `/api/admin/categories/${c.id}?cascade=true`), "Kategorie gelöscht.");
  }
  async function deleteProduct(p, docCount) {
    const ok = await confirmAction({
      title: `Produkt „${p.name}“ löschen?`, message: "Dieser Vorgang kann nicht rückgängig gemacht werden.",
      details: [docCount ? plural(docCount, "Dokument", "Dokumente") + " (PDF-Dateien) werden mitgelöscht" : "Das Produkt hat keine Dokumente", "Das Produktbild wird ebenfalls gelöscht"],
      confirmLabel: "Produkt löschen", danger: true,
    });
    if (ok) act(() => api("DELETE", `/api/admin/products/${p.id}?cascade=true`), "Produkt gelöscht.");
  }
  async function deleteDocument(d) {
    const ok = await confirmAction({
      title: "Dokument löschen?", message: `„${d.title}“ (Version ${d.version}) wird endgültig gelöscht, einschließlich der PDF-Datei.`,
      confirmLabel: "Dokument löschen", danger: true,
    });
    if (ok) act(() => api("DELETE", `/api/admin/documents/${d.id}`), "Dokument gelöscht.");
  }

  // ---------- Dialog: Kategorie ----------
  function fillParentOptions(select, selectedId, excludeId) {
    select.replaceChildren(el("option", "Keine (Hauptkategorie)", {value: ""}));
    const excluded = excludeId == null ? new Set() : descendantIds(excludeId, childrenByParent).add(excludeId);
    const add = (parentId, depth) => (childrenByParent.get(parentId) || []).filter(c => !excluded.has(c.id)).forEach(c => {
      select.append(el("option", `${"— ".repeat(depth)}${c.name}`, {value: c.id}));
      add(c.id, depth + 1);
    });
    add(null, 0);
    select.value = selectedId == null ? "" : String(selectedId);
  }
  function openCategoryDialog({category = null, parentId = null} = {}) {
    editingCategory = category; catError.textContent = "";
    $("dlg-category-title").textContent = category ? "Kategorie bearbeiten" : "Kategorie anlegen";
    $("dlg-category-lead").textContent = category ? `Änderungen an „${category.name}“.` : "Kategorien gliedern Ihre Produkte. Sie können beliebig tief verschachtelt werden.";
    $("category-save").textContent = category ? "Speichern" : "Anlegen";
    $("cat-name").value = category?.name ?? "";
    $("cat-desc").value = category?.description ?? "";
    $("cat-sort").value = category?.sort_order ?? "";
    $("cat-sort-field").hidden = !category;
    $("cat-sort").required = Boolean(category);
    fillParentOptions($("cat-parent"), category ? category.parent_id : parentId, category?.id ?? null);
    catImage.reset(category?.image_url);
    openDialog(catDlg);
    $("cat-name").focus();
  }
  catForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!catForm.reportValidity()) return;
    const save = $("category-save"); save.disabled = true; catError.textContent = "";
    const name = $("cat-name").value.trim(), description = $("cat-desc").value.trim();
    const parent_id = $("cat-parent").value ? Number($("cat-parent").value) : null;
    let saved = null;
    try {
      if (editingCategory) {
        saved = await api("PUT", `/api/admin/categories/${editingCategory.id}`, {name, parent_id, description: description || null, sort_order: Number($("cat-sort").value)});
      } else {
        saved = await api("POST", "/api/admin/categories", {name, parent_id, ...(description ? {description} : {})});
        if (parent_id) expanded.cats.add(parent_id);
        expanded.cats.add(saved.id);
      }
    } catch (ex) { catError.textContent = ex.message; save.disabled = false; return; }
    try { await applyImage(catImage, `/api/admin/categories/${saved.id}/image`); toast(editingCategory ? "Kategorie gespeichert." : "Kategorie angelegt."); }
    catch (ex) { toast(`${editingCategory ? "Kategorie gespeichert" : "Kategorie angelegt"}, aber die Bild-Aktion ist fehlgeschlagen: ${ex.message}`, "err"); }
    closeDialog(catDlg); save.disabled = false;
    await load();
  });

  // ---------- Dialog: Produkt ----------
  function openProductDialog({product = null, categoryId = null} = {}) {
    if (!state.cats.length) { toast("Legen Sie zuerst eine Kategorie an.", "err"); openCategoryDialog(); return; }
    editingProduct = product; prodError.textContent = "";
    $("dlg-product-title").textContent = product ? "Produkt bearbeiten" : "Produkt anlegen";
    $("dlg-product-lead").textContent = product ? `Änderungen an „${product.name}“.` : "Dokumente laden Sie anschließend über „PDF hochladen“ hinzu.";
    $("product-save").textContent = product ? "Speichern" : "Anlegen";
    $("prod-name").value = product?.name ?? "";
    $("prod-desc").value = product?.description ?? "";
    const sel = $("prod-category"); sel.replaceChildren();
    const wanted = product ? product.category_id : categoryId;
    state.cats.forEach(c => { const o = el("option", categoryPath(c, byId), {value: c.id}); o.selected = c.id === wanted; sel.append(o); });
    prodImage.reset(product?.image_url);
    openDialog(prodDlg);
    $("prod-name").focus();
  }
  prodForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!prodForm.reportValidity()) return;
    const save = $("product-save"); save.disabled = true; prodError.textContent = "";
    const name = $("prod-name").value.trim(), description = $("prod-desc").value.trim(), category_id = Number($("prod-category").value);
    let saved = null;
    try {
      if (editingProduct) {
        saved = await api("PUT", `/api/admin/products/${editingProduct.id}`, {name, category_id, description: description || null});
      } else {
        saved = await api("POST", "/api/admin/products", {category_id, name, ...(description ? {description} : {})});
      }
      expanded.cats.add(category_id);
    } catch (ex) { prodError.textContent = ex.message; save.disabled = false; return; }
    try { await applyImage(prodImage, `/api/admin/products/${saved.id}/image`); toast(editingProduct ? "Produkt gespeichert." : "Produkt angelegt."); }
    catch (ex) { toast(`${editingProduct ? "Produkt gespeichert" : "Produkt angelegt"}, aber die Bild-Aktion ist fehlgeschlagen: ${ex.message}`, "err"); }
    closeDialog(prodDlg); save.disabled = false;
    await load();
  });

  // ---------- Bedienelemente ----------
  $("new-category").addEventListener("click", () => openCategoryDialog());
  $("new-product").addEventListener("click", () => openProductDialog());
  $("expand-all").addEventListener("click", () => { state.cats.forEach(c => expanded.cats.add(c.id)); render(); });
  $("collapse-all").addEventListener("click", () => { expanded.cats.clear(); expanded.prods.clear(); render(); });
  $("category-search").addEventListener("input", (e) => { query = e.target.value.trim().toLocaleLowerCase("de"); render(); });

  load().then(() => {
    const wanted = new URLSearchParams(location.search).get("new");
    if (wanted === "category") openCategoryDialog();
    if (wanted === "product") openProductDialog();
    if (wanted) history.replaceState(null, "", location.pathname);
  });
})();
