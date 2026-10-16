"use strict";
(async () => {
  const msg = $("msg"), form = $("f"), sel = $("prod"), button = $("upload-btn");
  const show = (text, kind) => { msg.className = "alert " + kind; msg.textContent = text; };
  try {
    const [cats, prods] = await Promise.all([api("GET", "/api/admin/categories"), api("GET", "/api/admin/products")]);
    const byId = new Map(cats.map(c => [c.id, c]));
    prods.forEach(p => sel.append(el("option", `${categoryPath(byId.get(p.category_id), byId)} / ${p.name}`, {value: p.id})));
    const wanted = new URLSearchParams(location.search).get("product");
    if (wanted && prods.some(p => String(p.id) === wanted)) sel.value = wanted;
    if (!prods.length) {
      show("Es gibt noch kein Produkt. Legen Sie zuerst unter „Kategorien & Produkte“ eine Kategorie und ein Produkt an.", "err");
      button.disabled = true;
    }
  } catch (e) { show(e.message, "err"); }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(), file = form.elements.file.files[0], title = form.elements.title.value.trim();
    fd.append("file", file);
    if (title) fd.append("title", title);
    fd.append("version", form.elements.version.value || "1.0");
    button.disabled = true;
    try {
      const d = await api("POST", `/api/admin/products/${sel.value}/documents`, fd);
      show(`Hochgeladen: ${d.title} (Version ${d.version})`, "ok");
      form.elements.file.value = ""; form.elements.title.value = "";
      toast("Dokument hochgeladen.");
    } catch (err) { show(err.message, "err"); }
    button.disabled = false;
    msg.scrollIntoView({block: "nearest"});
  });
})();
