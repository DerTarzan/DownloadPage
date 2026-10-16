from tests.conftest import make_category, make_product, upload_pdf


def test_create_category_generates_slug_from_name(admin):
    cat = make_category(admin, "Rollstühle")
    assert cat["slug"] == "rollstuehle" and cat["active"] is True


def test_auto_slug_conflict_gets_suffix_but_explicit_conflict_is_409(admin):
    a = make_category(admin, "Treppenlift")
    b = make_category(admin, "Treppenlift")
    assert (a["slug"], b["slug"]) == ("treppenlift", "treppenlift-2")
    r = admin.post("/api/admin/categories", json={"name": "Anders", "slug": "treppenlift"})
    assert r.status_code == 409


def test_reserved_slugs_cannot_be_used(admin):
    assert admin.post("/api/admin/categories", json={"name": "Admin", "slug": "admin"}).status_code == 409
    assert make_category(admin, "Admin")["slug"] == "admin-2"


def test_create_product_and_per_category_slug_uniqueness(admin):
    c1, c2 = make_category(admin, "Eins"), make_category(admin, "Zwei")
    p1 = make_product(admin, c1["id"], "Modell X")
    p2 = make_product(admin, c1["id"], "Modell X")
    p3 = make_product(admin, c2["id"], "Modell X")  # gleicher Slug in anderer Kategorie ist erlaubt
    assert (p1["slug"], p2["slug"], p3["slug"]) == ("modell-x", "modell-x-2", "modell-x")


def test_product_requires_existing_category(admin):
    assert admin.post("/api/admin/products", json={"category_id": 9999, "name": "X"}).status_code == 422


def test_public_hierarchy(admin, anon):
    cat = make_category(admin, "Rollstühle")
    make_product(admin, cat["id"], "Produkt A")
    make_product(admin, cat["id"], "Produkt B", active=False)
    assert [c["slug"] for c in anon.get("/").json()["categories"]] == ["rollstuehle"]
    detail = anon.get("/rollstuehle").json()
    assert [p["slug"] for p in detail["products"]] == ["produkt-a"]
    assert anon.get("/rollstuehle/produkt-a").json()["product"]["name"] == "Produkt A"
    assert anon.get("/rollstuehle/produkt-b").status_code == 404
    assert anon.get("/gibt-es-nicht").status_code == 404


def test_html_for_browsers(admin, anon):
    cat = make_category(admin, "Rollstühle")
    make_product(admin, cat["id"], "Produkt A")
    r = anon.get("/rollstuehle", headers={"accept": "text/html,application/xhtml+xml"})
    assert r.status_code == 200 and "text/html" in r.headers["content-type"] and "Produkt A" in r.text


def test_public_pages_do_not_link_to_admin(admin, anon):
    category = make_category(admin, "Rollstühle")
    make_product(admin, category["id"], "Produkt A")
    headers = {"accept": "text/html"}
    pages = [anon.get("/", headers=headers), anon.get("/rollstuehle", headers=headers),
             anon.get("/rollstuehle/produkt-a", headers=headers)]
    assert all(response.status_code == 200 and "/admin" not in response.text for response in pages)


def test_inactive_category_hides_everything(admin, anon, document):
    cat_id = admin.get("/api/admin/categories").json()[0]["id"]
    admin.put(f"/api/admin/categories/{cat_id}", json={"active": False})
    assert anon.get("/").json()["categories"] == []
    assert anon.get("/rollstuehle").status_code == 404
    assert anon.get("/rollstuehle/produkt-a").status_code == 404
    assert anon.get(f"/documents/{document['id']}/download").status_code == 404


def test_html_is_escaped(admin, anon):
    make_category(admin, '<script>alert(1)</script>')
    r = anon.get("/", headers={"accept": "text/html"})
    assert "<script>alert(1)</script>" not in r.text and "&lt;script&gt;" in r.text


def test_update_and_reorder_categories(admin):
    a, b, c = (make_category(admin, n) for n in ("A", "B", "C"))
    r = admin.put("/api/admin/categories/reorder", json={"ids": [c["id"], a["id"], b["id"]]})
    assert r.status_code == 200 and [x["name"] for x in r.json()] == ["C", "A", "B"]
    assert admin.put("/api/admin/categories/reorder", json={"ids": [a["id"]]}).status_code == 422
    r = admin.put(f"/api/admin/categories/{a['id']}", json={"name": "Neu", "description": "Text"})
    assert r.json()["name"] == "Neu" and r.json()["slug"] == "a"  # Slug bleibt stabil


def test_move_product_to_other_category(admin):
    c1, c2 = make_category(admin, "Eins"), make_category(admin, "Zwei")
    p = make_product(admin, c1["id"], "Teil")
    make_product(admin, c2["id"], "Teil")  # Slug "teil" existiert im Ziel bereits
    assert admin.put(f"/api/admin/products/{p['id']}", json={"category_id": c2["id"]}).status_code == 409
    r = admin.put(f"/api/admin/products/{p['id']}", json={"category_id": c2["id"], "slug": "teil-neu"})
    assert r.status_code == 200 and r.json()["category_id"] == c2["id"]


def test_reorder_products(admin):
    cat = make_category(admin)
    p1, p2 = make_product(admin, cat["id"], "P1"), make_product(admin, cat["id"], "P2")
    r = admin.put("/api/admin/products/reorder", json={"category_id": cat["id"], "ids": [p2["id"], p1["id"]]})
    assert [p["name"] for p in r.json()] == ["P2", "P1"]


def test_delete_category_with_products_requires_cascade(admin, storage_root):
    cat = make_category(admin)
    prod = make_product(admin, cat["id"])
    doc = upload_pdf(admin, prod["id"]).json()
    r = admin.delete(f"/api/admin/categories/{cat['id']}")
    assert r.status_code == 409
    assert admin.delete(f"/api/admin/products/{prod['id']}").status_code == 409  # hat noch ein Dokument
    assert len(list((storage_root / "documents").rglob("*.pdf"))) == 1
    assert admin.delete(f"/api/admin/categories/{cat['id']}?cascade=true").status_code == 204
    assert admin.get(f"/api/admin/documents/{doc['id']}").status_code == 404
    assert list((storage_root / "documents").rglob("*")) == []  # keine verwaisten Dateien/Ordner


def test_delete_empty_category_and_product(admin):
    cat = make_category(admin)
    prod = make_product(admin, cat["id"])
    assert admin.delete(f"/api/admin/products/{prod['id']}").status_code == 204
    assert admin.delete(f"/api/admin/categories/{cat['id']}").status_code == 204
    assert admin.get(f"/api/admin/categories/{cat['id']}").status_code == 404


def test_id_out_of_range_is_not_a_server_error(admin):
    assert admin.get("/api/admin/categories/99999999999999").status_code == 422


def test_nested_categories_support_direct_products_and_document_downloads(admin, anon):
    root = make_category(admin, "Rollstühle")
    middle = make_category(admin, "Elektrorollstühle", parent_id=root["id"])
    leaf = make_category(admin, "Reiserollstühle", parent_id=middle["id"])
    root_product = make_product(admin, root["id"], "Direktprodukt")
    leaf_product = make_product(admin, leaf["id"], "Modell X")
    document = upload_pdf(admin, leaf_product["id"], title="Anleitung").json()

    assert root["parent_id"] is None
    assert middle["parent_id"] == root["id"]
    assert leaf["parent_id"] == middle["id"]
    assert [item["slug"] for item in anon.get("/").json()["categories"]] == ["rollstuehle"]
    root_detail = anon.get("/rollstuehle").json()
    assert [item["slug"] for item in root_detail["children"]] == ["elektrorollstuehle"]
    assert [item["slug"] for item in root_detail["products"]] == ["direktprodukt"]
    middle_detail = anon.get("/elektrorollstuehle").json()
    assert [item["slug"] for item in middle_detail["children"]] == ["reiserollstuehle"]
    assert anon.get("/reiserollstuehle").json()["products"][0]["slug"] == "modell-x"

    headers = {"accept": "text/html"}
    leaf_page = anon.get("/reiserollstuehle", headers=headers)
    assert all(part in leaf_page.text for part in ("Rollstühle", "Elektrorollstühle", "Modell X"))
    product_page = anon.get("/reiserollstuehle/modell-x", headers=headers)
    assert all(part in product_page.text for part in ("Rollstühle", "Elektrorollstühle", "Reiserollstühle"))
    downloaded = anon.get(f"/reiserollstuehle/modell-x/dokument/{document['id']}/download")
    assert downloaded.status_code == 200 and downloaded.content.startswith(b"%PDF-")
    assert root_product["category_id"] == root["id"]


def test_empty_nested_category_has_an_empty_state(admin, anon):
    root = make_category(admin, "Badartikel")
    child = make_category(admin, "Toilettenstühle", parent_id=root["id"])
    assert anon.get(f"/{child['slug']}").status_code == 200
    response = anon.get(f"/{child['slug']}", headers={"accept": "text/html"})
    assert "Keine Inhalte" in response.text


def test_category_move_rejects_self_and_descendant_cycles(admin):
    root = make_category(admin, "Lifter")
    child = make_category(admin, "Patientenlifter", parent_id=root["id"])
    grandchild = make_category(admin, "Foldy", parent_id=child["id"])

    assert admin.put(f"/api/admin/categories/{root['id']}", json={"parent_id": root["id"]}).status_code == 422
    assert admin.put(f"/api/admin/categories/{root['id']}", json={"parent_id": grandchild["id"]}).status_code == 422
    assert admin.post("/api/admin/categories", json={"name": "Unbekannt", "parent_id": 9999}).status_code == 422

    moved = admin.put(f"/api/admin/categories/{grandchild['id']}", json={"parent_id": None})
    assert moved.status_code == 200 and moved.json()["parent_id"] is None


def test_deleting_category_with_descendants_requires_explicit_cascade(admin, storage_root):
    root = make_category(admin, "Badartikel")
    child = make_category(admin, "Badewannenlifter", parent_id=root["id"])
    leaf = make_category(admin, "Bellavita", parent_id=child["id"])
    product = make_product(admin, leaf["id"], "Bellavita")
    document = upload_pdf(admin, product["id"]).json()

    assert admin.delete(f"/api/admin/categories/{root['id']}").status_code == 409
    assert admin.get(f"/api/admin/documents/{document['id']}").status_code == 200
    assert admin.delete(f"/api/admin/categories/{root['id']}?cascade=true").status_code == 204
    assert admin.get(f"/api/admin/categories/{leaf['id']}").status_code == 404
    assert admin.get(f"/api/admin/products/{product['id']}").status_code == 404
    assert admin.get(f"/api/admin/documents/{document['id']}").status_code == 404
    assert list((storage_root / "documents").rglob("*")) == []


def test_inactive_ancestor_hides_nested_categories_products_and_downloads(admin, anon, document):
    category = admin.get("/api/admin/categories").json()[0]
    child = make_category(admin, "Unterkategorie", parent_id=category["id"])
    admin.put(f"/api/admin/categories/{category['id']}", json={"active": False})

    assert anon.get(f"/{child['slug']}").status_code == 404
    assert anon.get(f"/documents/{document['id']}/download").status_code == 404


def test_admin_dashboard_contains_nested_category_and_product_editing(admin):
    response = admin.get("/admin")
    assert response.status_code == 200
    assert 'id="newcat-parent"' in response.text
    assert "Übergeordnete Kategorie" in response.text
    assert "category_id: Number(category.value)" in response.text
