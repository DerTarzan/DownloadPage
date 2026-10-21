"""Seitenweite Sprachwahl: Lesezeichen im Footer (Cookie), übersetzte Seiten, Chat ohne eigenes Sprach-Dropdown."""
import re
from pathlib import Path

import pytest

from app.i18n import ERROR_DETAILS_EN, TEXTS, safe_next_path
from tests.conftest import make_category, make_product

HTML = {"accept": "text/html"}
STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
CHAT_JS = STATIC / "js" / "chat.js"
CHAT_CSS = STATIC / "css" / "chat.css"


def choose(client, lang, next_url="/"):
    return client.post("/api/language", data={"lang": lang, "next": next_url}, follow_redirects=False)


def test_default_language_is_german(anon):
    page = anon.get("/", headers=HTML).text
    assert '<html lang="de">' in page
    assert "Produkte &amp; Dokumente" in page
    assert "Zum Inhalt springen" in page


def test_choosing_english_sets_cookie_and_translates_the_whole_site(admin, anon):
    cat = make_category(admin, "Rollatoren")
    make_product(admin, cat["id"], "Rollator STF 300")

    r = choose(anon, "en", "/rollatoren")
    assert r.status_code == 303 and r.headers["location"] == "/rollatoren"
    cookie = r.headers["set-cookie"].lower()
    assert "lang=en" in cookie and "samesite=lax" in cookie and "max-age=" in cookie and "path=/" in cookie

    home = anon.get("/", headers=HTML).text
    assert '<html lang="en">' in home and "Products &amp; documents" in home and "Skip to content" in home
    assert "Produkte &amp; Dokumente" not in home

    category = anon.get("/rollatoren", headers=HTML).text
    assert "Details &amp; documents" in category and 'aria-label="Breadcrumbs"' in category and ">Home<" in category

    product = anon.get("/rollatoren/rollator-stf-300", headers=HTML).text
    assert "Documents &amp; downloads" in product and "There are no documents available" in product

    missing = anon.get("/gibt-es-nicht", headers=HTML)
    assert missing.status_code == 404
    assert "Page not found" in missing.text and "Category not found" in missing.text and "Back to home page" in missing.text


def test_switching_back_to_german(anon):
    choose(anon, "en")
    choose(anon, "de")
    assert '<html lang="de">' in anon.get("/", headers=HTML).text


def test_json_api_is_not_translated(anon):
    choose(anon, "en")
    assert anon.get("/gibt-es-nicht").json() == {"detail": "Kategorie nicht gefunden"}


def test_footer_contains_the_language_bookmark_on_public_pages(anon):
    page = anon.get("/", headers=HTML).text
    assert 'class="lang-details"' in page and 'action="/api/language"' in page and "/static/js/lang.js" in page
    assert 'value="de"' in page and 'value="en"' in page and "Deutsch" in page and "English" in page
    assert page.index('class="site-footer"') < page.index('class="lang-details"') < page.index("</footer>")
    assert 'aria-current="true"' in page


def test_current_language_is_marked_in_the_menu(anon):
    choose(anon, "en")
    page = anon.get("/", headers=HTML).text
    assert re.search(r'value="en" lang="en" aria-current="true"', page)
    assert 'value="de" lang="de" aria-current' not in page


def test_unknown_language_is_ignored(anon):
    r = choose(anon, "fr", "/")
    assert r.status_code == 303 and "set-cookie" not in r.headers
    assert '<html lang="de">' in anon.get("/", headers=HTML).text
    anon.cookies.set("lang", "xx")  # manipuliertes Cookie fällt auf Deutsch zurück
    assert '<html lang="de">' in anon.get("/", headers=HTML).text


@pytest.mark.parametrize("target", ["https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)", "", "/a\nb"])
def test_redirect_target_cannot_leave_the_site(anon, target):
    r = choose(anon, "en", target)
    assert r.status_code == 303 and r.headers["location"] == "/"


def test_safe_next_path():
    assert safe_next_path("/rollatoren/rollator") == "/rollatoren/rollator"
    assert safe_next_path(None) == "/"


def test_language_can_be_switched_in_maintenance_mode(admin, anon):
    admin.put("/api/admin/settings", json={"maintenance_mode": True, "maintenance_message": "Wartung"})
    assert "Wir sind gleich wieder da" in anon.get("/", headers=HTML).text
    r = choose(anon, "en", "/")
    assert r.status_code == 303
    page = anon.get("/", headers=HTML)
    assert page.status_code == 503 and "We&#39;ll be right back" in page.text and "Wartung" in page.text
    assert 'class="lang-details"' in page.text


def test_login_page_is_translated(anon):
    choose(anon, "en")
    page = anon.get("/admin/login", headers=HTML).text
    assert "Admin sign-in" in page and "Username" in page and "Sign-in failed" in page


def test_chat_has_no_language_dropdown_and_follows_page_language(anon):
    js, css = CHAT_JS.read_text(encoding="utf-8"), CHAT_CSS.read_text(encoding="utf-8")
    assert 'el("select")' not in js and "langSel" not in js and "select" not in css
    assert "document.documentElement.lang" in js
    choose(anon, "en")
    assert '<html lang="en">' in anon.get("/", headers=HTML).text  # chat.js liest genau dieses Attribut


def test_chat_api_still_accepts_both_languages(anon):
    for lang in ("de", "en"):
        assert anon.post("/api/chat", json={"message": "Hallo", "lang": lang}).json()["lang"] == lang


def test_site_translations_have_same_keys_and_placeholders():
    assert set(TEXTS["de"]) == set(TEXTS["en"])
    for key in TEXTS["de"]:
        assert set(re.findall(r"{(\w+)}", TEXTS["de"][key])) == set(re.findall(r"{(\w+)}", TEXTS["en"][key])), key


def test_every_default_error_message_has_an_english_text():
    from app.core import exceptions

    defaults = {
        cls.default_detail
        for cls in vars(exceptions).values()
        if isinstance(cls, type) and issubclass(cls, exceptions.AppError)
    }
    assert defaults <= set(ERROR_DETAILS_EN)
