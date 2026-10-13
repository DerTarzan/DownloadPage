from tests.conftest import PDF_BYTES, PNG_BYTES, make_category, make_product, upload_pdf


def test_upload_document_detects_metadata(admin, product, storage_root):
    r = upload_pdf(admin, product["id"], title="Handbuch", version="2.1")
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["title"] == "Handbuch" and d["version"] == "2.1"
    assert d["original_filename"] == "manual.pdf"
    assert d["mime_type"] == "application/pdf" and d["file_size"] == len(PDF_BYTES)
    assert "storage_path" not in d  # interner Pfad wird nicht ausgeliefert
    files = list((storage_root / "documents").rglob("*.pdf"))
    assert len(files) == 1 and files[0].name != "manual.pdf"  # UUID statt Benutzer-Dateiname


def test_title_defaults_to_filename(admin, product):
    assert upload_pdf(admin, product["id"], filename="Anleitung Größe.pdf").json()["title"] == "Anleitung Größe"


def test_download_via_both_routes(admin, anon, document):
    for url in (f"/documents/{document['id']}/download", f"/rollstuehle/produkt-a/dokument/{document['id']}/download"):
        r = anon.get(url)
        assert r.status_code == 200, url
        assert r.headers["content-type"] == "application/pdf"
        assert 'filename="manual.pdf"' in r.headers["content-disposition"]
        assert r.headers["content-disposition"].startswith("attachment")
        assert r.content == PDF_BYTES
    assert anon.get(f"/rollstuehle/falsches-produkt/dokument/{document['id']}/download").status_code == 404
    assert anon.get(f"/falsch/produkt-a/dokument/{document['id']}/download").status_code == 404


def test_product_page_lists_active_documents_only(admin, anon, product, document):
    second = upload_pdf(admin, product["id"], title="Versteckt", active="false").json()
    docs = anon.get("/rollstuehle/produkt-a").json()["documents"]
    assert [d["id"] for d in docs] == [document["id"]]
    assert second["id"] not in [d["id"] for d in docs]


def test_deactivated_document_is_not_accessible(admin, anon, document):
    assert anon.get(f"/documents/{document['id']}/download").status_code == 200
    assert admin.put(f"/api/admin/documents/{document['id']}", json={"active": False}).status_code == 200
    assert anon.get(f"/documents/{document['id']}/download").status_code == 404
    assert anon.get(f"/rollstuehle/produkt-a/dokument/{document['id']}/download").status_code == 404
    admin.put(f"/api/admin/documents/{document['id']}", json={"active": True})
    assert anon.get(f"/documents/{document['id']}/download").status_code == 200


def test_inactive_product_blocks_download(admin, anon, product, document):
    admin.put(f"/api/admin/products/{product['id']}", json={"active": False})
    assert anon.get(f"/documents/{document['id']}/download").status_code == 404


def test_delete_document_removes_row_and_file(admin, anon, document, storage_root):
    assert len(list((storage_root / "documents").rglob("*.pdf"))) == 1
    assert admin.delete(f"/api/admin/documents/{document['id']}").status_code == 204
    assert list((storage_root / "documents").rglob("*")) == []
    assert anon.get(f"/documents/{document['id']}/download").status_code == 404
    assert admin.get(f"/api/admin/documents/{document['id']}").status_code == 404


def test_replace_pdf_removes_old_file(admin, anon, document, storage_root):
    new = PDF_BYTES + b"% neue Version\n"
    r = admin.put(
        f"/api/admin/documents/{document['id']}/file",
        files={"file": ("neu.pdf", new, "application/pdf")},
        data={"version": "1.1"},
    )
    assert r.status_code == 200 and r.json()["version"] == "1.1" and r.json()["file_size"] == len(new)
    assert len(list((storage_root / "documents").rglob("*.pdf"))) == 1
    assert anon.get(f"/documents/{document['id']}/download").content == new


def test_upload_to_missing_product(admin):
    assert upload_pdf(admin, 4242).status_code == 404


def test_upload_requires_authentication(anon, product):
    assert upload_pdf(anon, product["id"]).status_code == 401


# ---- ungültige Uploads ----
def test_rejects_wrong_extension(admin, product, storage_root):
    r = upload_pdf(admin, product["id"], filename="evil.exe")
    assert r.status_code == 415
    r = upload_pdf(admin, product["id"], filename="evil.pdf.exe")
    assert r.status_code == 415
    assert list((storage_root / "documents").rglob("*")) == []


def test_rejects_wrong_content_type(admin, product):
    assert upload_pdf(admin, product["id"], content_type="text/plain").status_code == 415
    assert upload_pdf(admin, product["id"], content_type="application/octet-stream").status_code == 415


def test_rejects_fake_pdf_without_magic_bytes(admin, product, storage_root):
    r = upload_pdf(admin, product["id"], content=b"MZ\x90\x00 das ist keine PDF-Datei")
    assert r.status_code == 415
    assert list((storage_root / "documents").rglob("*")) == []  # nichts liegen geblieben (auch keine .part)


def test_rejects_empty_file(admin, product):
    assert upload_pdf(admin, product["id"], content=b"").status_code == 400


def test_rejects_oversized_file(admin, product, storage_root):
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)  # Limit im Test: 1 MB
    r = upload_pdf(admin, product["id"], content=big)
    assert r.status_code == 413
    assert list((storage_root / "documents").rglob("*")) == []


def test_path_traversal_in_filename_is_neutralised(admin, product, storage_root):
    r = upload_pdf(admin, product["id"], filename="../../../etc/passwd.pdf")
    assert r.status_code == 201
    d = r.json()
    assert d["original_filename"] == "passwd.pdf"
    stored = list(storage_root.rglob("*.pdf"))
    assert len(stored) == 1 and stored[0].is_relative_to(storage_root / "documents")
    r = upload_pdf(admin, product["id"], filename="..\\..\\windows\\system32\\x.pdf")
    assert r.status_code == 201 and r.json()["original_filename"] == "x.pdf"


def test_client_cannot_supply_storage_path(admin, product, document):
    r = admin.put(f"/api/admin/documents/{document['id']}", json={"storage_path": "../../etc/passwd"})
    assert r.status_code == 200  # unbekanntes Feld wird ignoriert ...
    assert "storage_path" not in r.json()  # ... und nie ausgegeben


# ---- Bilder ----
def test_category_and_product_images(admin, anon, product, storage_root):
    cat_id = product["category_id"]
    r = admin.post(f"/api/admin/categories/{cat_id}/image", files={"file": ("a.png", PNG_BYTES, "image/png")})
    assert r.status_code == 200
    url = r.json()["image_url"]
    assert url.startswith("/media/images/") and anon.get(url).content == PNG_BYTES
    r = admin.post(f"/api/admin/products/{product['id']}/image", files={"file": ("b.png", PNG_BYTES, "image/png")})
    assert r.status_code == 200
    assert len(list((storage_root / "images").iterdir())) == 2
    # Ersetzen löscht das alte Bild
    admin.post(f"/api/admin/categories/{cat_id}/image", files={"file": ("c.png", PNG_BYTES, "image/png")})
    admin.post(f"/api/admin/products/{product['id']}/image", files={"file": ("d.png", PNG_BYTES, "image/png")})
    assert len(list((storage_root / "images").iterdir())) == 2
    assert admin.delete(f"/api/admin/categories/{cat_id}/image").status_code == 204
    assert admin.delete(f"/api/admin/products/{product['id']}/image").status_code == 204
    assert list((storage_root / "images").iterdir()) == []


def test_admin_dashboard_has_image_upload_controls(admin):
    response = admin.get("/admin")
    assert response.status_code == 200
    assert 'id="cat-image"' in response.text
    assert 'id="prod-image"' in response.text
    assert "Bild hinzufügen" in response.text
    assert "Bild ändern" in response.text


def test_category_and_product_images_are_shown_in_public_pages(admin, anon, product):
    cat_id = product["category_id"]
    admin.post(f"/api/admin/categories/{cat_id}/image", files={"file": ("category.png", PNG_BYTES, "image/png")})
    admin.post(
        f"/api/admin/products/{product['id']}/image",
        files={"file": ("product.png", PNG_BYTES, "image/png")},
    )
    assert anon.get("/").json()["categories"][0]["image_url"].startswith("/media/images/")
    assert anon.get("/rollstuehle").json()["products"][0]["image_url"].startswith("/media/images/")
    assert anon.get("/rollstuehle/produkt-a").json()["product"]["image_url"].startswith("/media/images/")
    assert 'img src="/media/images/' in anon.get(
        "/", headers={"accept": "text/html"}
    ).text
    assert 'img src="/media/images/' in anon.get(
        "/rollstuehle", headers={"accept": "text/html"}
    ).text
    assert 'img src="/media/images/' in anon.get(
        "/rollstuehle/produkt-a", headers={"accept": "text/html"}
    ).text


def test_image_validation(admin, product):
    cat_id = product["category_id"]
    url = f"/api/admin/categories/{cat_id}/image"
    assert admin.post(url, files={"file": ("a.svg", b"<svg onload=alert(1)>", "image/svg+xml")}).status_code == 415
    assert admin.post(url, files={"file": ("a.png", b"kein png", "image/png")}).status_code == 415
    assert admin.post(url, files={"file": ("a.png", PNG_BYTES, "text/plain")}).status_code == 415
    assert admin.post(url, files={"file": ("a.jpg", PNG_BYTES, "image/jpeg")}).status_code == 415  # Endung != Inhalt
    big = PNG_BYTES + b"0" * (1024 * 1024 + 1)
    assert admin.post(url, files={"file": ("a.png", big, "image/png")}).status_code == 413
