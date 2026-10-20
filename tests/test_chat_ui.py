"""Chat-Oberfläche: Einbindung in öffentliche Seiten, Übersetzungsvollständigkeit, Textfunktionen."""
import re
from pathlib import Path

import pytest

from app.services.chat.i18n import MESSAGES
from app.services.chat.text import compact, edit_distance, fold, token_similarity, tokenize
from tests.conftest import make_category, make_product

HTML = {"accept": "text/html"}
JS = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "chat.js"


def test_widget_is_mounted_on_public_pages_only(admin, anon):
    cat = make_category(admin, "Rollatoren")
    make_product(admin, cat["id"], "Rollator STF 300")
    for url in ("/", "/rollatoren", "/rollatoren/rollator-stf-300", "/gibt-es-nicht"):
        page = anon.get(url, headers=HTML)
        assert 'id="chat-root"' in page.text and "/static/js/chat.js" in page.text and "/static/css/chat.css" in page.text, url
    for url in ("/admin", "/admin/catalog", "/admin/login"):
        assert "chat-root" not in admin.get(url, headers=HTML).text, url


def test_widget_not_shown_in_maintenance_page(admin, anon):
    admin.put("/api/admin/settings", json={"maintenance_mode": True, "maintenance_message": "Wartung"})
    page = anon.get("/", headers=HTML)
    assert page.status_code == 503 and "chat-root" not in page.text


def test_static_assets_are_served(anon):
    js, css = anon.get("/static/js/chat.js"), anon.get("/static/css/chat.css")
    assert js.status_code == 200 and css.status_code == 200
    assert "prefers-reduced-motion" in css.text


def test_frontend_translations_are_complete_and_safe():
    """DE und EN im Frontend haben exakt dieselben Schlüssel; Inhalte werden nie per innerHTML gesetzt."""
    source = JS.read_text(encoding="utf-8")
    blocks = re.findall(r"\n    (de|en): \{(.*?)\n    \}", source, re.S)
    keys = {lang: set(re.findall(r"(\w+):", body)) for lang, body in blocks}
    assert set(keys) == {"de", "en"} and keys["de"] == keys["en"] and len(keys["de"]) > 20
    assert "innerHTML" not in source and "outerHTML" not in source and "insertAdjacentHTML" not in source


def test_backend_translations_have_same_keys_and_placeholders():
    assert set(MESSAGES["de"]) == set(MESSAGES["en"])
    for key in MESSAGES["de"]:
        assert set(re.findall(r"{(\w+)}", MESSAGES["de"][key])) == set(re.findall(r"{(\w+)}", MESSAGES["en"][key])), key


@pytest.mark.parametrize("text,expected", [("Rollstühle", "rollstuehle"), ("Größe", "groesse"), ("Café", "cafe")])
def test_fold(text, expected):
    assert fold(text) == expected


def test_tokenize_and_compact():
    assert tokenize("STF300") == tokenize("STF-300") == tokenize("stf 300") == ["stf", "300"]
    assert compact("STF-300") == compact("stf 300") == "stf300"


def test_similarity_rules():
    assert token_similarity("rolator", "rollator") >= 0.7  # Tippfehler
    assert token_similarity("rollstuhl", "rollstuhls") > 0.8
    assert token_similarity("300", "3000") == 0.0  # Zahlen exakt
    assert token_similarity("abc", "abd") == 0.0  # kurze Wörter ohne Toleranz
    assert token_similarity("trainer", "bewegungstrainer") == 0.6  # Teilwort schwächer als Name
    assert edit_distance("stf", "sft", 1) == 1  # Vertauschung zählt einfach


def test_existing_public_api_still_works(admin, anon):
    cat = make_category(admin, "Rollatoren")
    make_product(admin, cat["id"], "Rollator STF 300")
    assert anon.get("/").json()["categories"][0]["slug"] == "rollatoren"
    assert anon.get("/rollatoren/rollator-stf-300").json()["product"]["name"] == "Rollator STF 300"
    assert anon.get("/health").json() == {"status": "ok"}
