"""Admin-Oberfläche: Seiten, Navigation und eingebundene Assets."""
import re

import pytest

ADMIN_PAGES = {
    "/admin": ("overview", "Übersicht"),
    "/admin/catalog": ("catalog", "Kategorien &amp; Produkte"),
    "/admin/documents": ("documents", "Dokumente"),
    "/admin/upload": ("upload", "PDF hochladen"),
    "/admin/settings": ("settings", "Einstellungen"),
}


@pytest.mark.parametrize("path", ADMIN_PAGES)
def test_admin_pages_redirect_to_login_when_logged_out(anon, path):
    r = anon.get(path, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin/login"


@pytest.mark.parametrize("path", ADMIN_PAGES)
def test_admin_page_renders_with_heading_and_single_active_nav_item(admin, path):
    _, heading = ADMIN_PAGES[path]
    r = admin.get(path)
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert f"<h1>{heading}</h1>" in r.text
    assert r.text.count('aria-current="page"') == 1  # genau ein aktiver Menüpunkt


@pytest.mark.parametrize("path", ADMIN_PAGES)
def test_active_nav_item_matches_page(admin, path):
    key, _ = ADMIN_PAGES[path]
    html = admin.get(path).text
    active_href = re.search(r'<a class="nav-link" href="([^"]+)" aria-current="page"', html).group(1)
    assert active_href == path, key


@pytest.mark.parametrize("path", ADMIN_PAGES)
def test_admin_page_assets_exist(admin, path):
    html = admin.get(path).text
    assets = re.findall(r'(?:href|src)="(/static/[^"]+)"', html)
    assert "/static/css/admin.css" in assets and "/static/js/admin.js" in assets
    assert "/static/images/ihre-gesundheitspartner-logo-white.png" in assets
    for asset in assets:
        assert admin.get(asset).status_code == 200, asset


def test_admin_pages_show_logged_in_user_and_logout(admin):
    html = admin.get("/admin").text
    assert "testadmin" in html and 'id="logout"' in html


def test_api_docs_link_follows_docs_setting(admin):
    from app.core.config import get_settings

    html = admin.get("/admin").text
    assert ('href="/docs"' in html) == get_settings().docs_enabled


def test_admin_scripts_do_not_use_inner_html():
    """API-Daten dürfen nie per innerHTML in die Seite gelangen (XSS-Schutz)."""
    from pathlib import Path

    for js in (Path(__file__).resolve().parent.parent / "app/static/js").glob("*.js"):
        assert "innerHTML" not in js.read_text(encoding="utf-8"), js.name
