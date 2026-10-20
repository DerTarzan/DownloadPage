"""Orchestrierung: Anfrage → Suchbegriffe → Suche → Antworttext + Karten. Links entstehen ausschließlich aus echten Slugs/IDs."""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import ChatCategory, ChatContext, ChatDocument, ChatProduct, ChatResponse
from app.services.chat import search as srch
from app.services.chat.i18n import msg, normalize_lang
from app.services.chat.llm import get_term_extractor
from app.services.chat.text import token_similarity, tokenize
from app.services.chat.vocabulary import GREETINGS, REFERENCES, DOC_WORDS, STOPWORDS

logger = logging.getLogger("app.chat")  # loggt nie den Nachrichtentext

MAX_DOCS_PER_CARD = 5
MAX_CATEGORY_RESULTS = 8
DESCRIPTION_LIMIT = 160
_TAGS = re.compile(r"<[^>]*>")


def _snippet(text: str | None) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= DESCRIPTION_LIMIT else text[: DESCRIPTION_LIMIT - 1].rstrip() + "…"


def category_url(slug: str) -> str:
    return f"/{quote(slug, safe='')}"


def product_url(p: srch.ProductEntry) -> str:
    return f"/{quote(p.category.slug, safe='')}/{quote(p.slug, safe='')}"


class ChatService:
    def __init__(self, db: Session, max_results: int = 5):
        self.repo = ChatRepository(db)
        self.max_results = max_results

    # ---------- Karten ----------
    def _card(self, p: srch.ProductEntry, *, doc_terms: list[str] | None = None, with_docs: bool = True) -> ChatProduct:
        docs = []
        if with_docs:
            ranked = [(self._doc_match(d, doc_terms or []), d) for d in p.docs]
            ranked.sort(key=lambda x: (not x[0], x[1].id))
            docs = [
                ChatDocument(
                    title=d.title,
                    url=f"{product_url(p)}/dokument/{d.id}/download",
                    version=d.version,
                    file_size=d.size,
                    matched=m,
                )
                for m, d in ranked[:MAX_DOCS_PER_CARD]
            ]
        return ChatProduct(
            name=p.name,
            url=product_url(p),
            description=_snippet(p.description),
            image_url=f"/media/{p.image_path}" if p.image_path else None,
            category_name=p.category.name,
            category_url=category_url(p.category.slug),
            category_path=list(p.category.path),
            documents=docs,
        )

    @staticmethod
    def _doc_match(d: srch.DocEntry, doc_terms: list[str]) -> bool:
        return any(token_similarity(t, dt, fuzzy=False) >= 0.85 for t in doc_terms for dt in d.tokens)

    def _category_card(self, catalog: srch.Catalog, c: srch.CategoryEntry) -> ChatCategory:
        return ChatCategory(name=c.name, url=category_url(c.slug), product_count=len(catalog.products_in(c)))

    # ---------- Hauptlogik ----------
    def reply(self, message: str, lang: str, context: ChatContext | None = None) -> ChatResponse:
        lang = normalize_lang(lang)
        message = _TAGS.sub(" ", message)  # HTML ist hier nur Text; Tags tragen nichts zur Suche bei
        catalog = srch.build_catalog(self.repo)

        def respond(kind, key, **kw):
            params = kw.pop("params", {})
            return ChatResponse(reply=msg(lang, key, **params), kind=kind, lang=lang, **kw)

        raw = tokenize(message)
        if not catalog.products and not catalog.categories:
            return respond("none", "empty_catalog")
        if raw and all(t in GREETINGS or t in STOPWORDS for t in raw) and any(t in GREETINGS for t in raw):
            return respond("greeting", "greeting")

        text = message
        extractor = get_term_extractor()
        if extractor is not None:  # optionales lokales Modell: nur Begriffe, nie Treffer
            try:
                text = extractor.extract_terms(message, lang) or message
            except Exception:  # Modellfehler dürfen die Basisfunktion nie stören
                logger.warning("Term-Extraktor fehlgeschlagen, nutze Standardlogik", exc_info=True)
        tokens_all = tokenize(text)
        wants_docs = any(t in DOC_WORDS for t in tokens_all)
        doc_terms = [t for t in tokens_all if t in DOC_WORDS]
        has_reference = any(t in REFERENCES for t in raw)
        terms = [t for t in tokens_all if t not in STOPWORDS and t not in DOC_WORDS]

        context_product = None
        if context is not None:
            context_product = catalog.find_product(context.category_slug, context.product_slug)

        # Keine eigenen Suchbegriffe: „Wo finde ich die PDF zu diesem Produkt?“ bezieht sich auf den Kontext
        if not terms:
            if wants_docs and context_product is not None:
                return self._documents(respond, lang, catalog, context_product, doc_terms)
            if wants_docs:
                return respond("clarify", "clarify_product", categories=self._root_cards(catalog))
            return respond("clarify", "clarify_categories", categories=self._root_cards(catalog))

        result = srch.search(catalog, terms, self.max_results)

        # Nur Dokument-Stichwörter plus Verweis („…zu diesem Produkt“) mit Treffer-losem Rest: Kontext nutzen
        if not result.products and wants_docs and has_reference and context_product is not None:
            return self._documents(respond, lang, catalog, context_product, doc_terms)

        if result.products:
            exact_name = [p for p, s in result.products if s >= 0.95]
            category_listing = result.category is not None and (len(exact_name) != 1)
            if category_listing:
                return self._category(respond, lang, catalog, result.category, terms)
            top_score = result.products[0][1]
            single = len(result.products) == 1 or (top_score >= 0.85 and top_score - result.products[1][1] >= 0.2)
            if wants_docs and single:
                return self._documents(respond, lang, catalog, result.products[0][0], doc_terms)
            if single:
                p = result.products[0][0]
                key = "found_one" if p.docs else "found_one_nodocs"
                return respond("found", key, params={"name": p.name}, results=[self._card(p, doc_terms=doc_terms)])
            cards = [self._card(p, doc_terms=doc_terms, with_docs=wants_docs) for p, _ in result.products]
            n, total = len(cards), result.total
            if total > n:
                return respond("multiple", "found_many_more", params={"n": n, "total": total}, results=cards)
            return respond("multiple", "found_many", params={"n": n}, results=cards)

        if result.category is not None:
            return self._category(respond, lang, catalog, result.category, terms)

        similar = [self._card(p, with_docs=False) for p in result.similar]
        if similar:
            return respond("none", "none_similar", similar=similar)
        cats = [self._category_card(catalog, c) for c in result.similar_categories]
        return respond("none", "none_categories" if cats else "none", categories=cats)

    def _root_cards(self, catalog: srch.Catalog) -> list[ChatCategory]:
        return [self._category_card(catalog, c) for c in catalog.roots()[:5]]

    def _category(self, respond, lang, catalog, category, terms):
        members = catalog.products_in(category)
        card = self._category_card(catalog, category)
        if not members:
            return respond("category", "category_empty", params={"name": category.name}, categories=[card])
        ranked = sorted(members, key=lambda p: -srch.score_product(terms, p))
        shown = ranked[: min(self.max_results, MAX_CATEGORY_RESULTS)]
        cards = [self._card(p, with_docs=False) for p in shown]
        if len(members) > len(cards):
            params, key = {"name": category.name, "n": len(cards), "total": len(members)}, "category_more"
        else:
            params, key = {"name": category.name, "n": len(members)}, "category"
        return respond("category", key, params=params, results=cards, categories=[card])

    def _documents(self, respond, lang, catalog, product, doc_terms):
        card = self._card(product, doc_terms=doc_terms)
        if not card.documents:
            return respond("documents", "docs_none", params={"name": product.name}, results=[card])
        specific = [t for t in doc_terms if t not in {"pdf", "pdfs", "download", "downloads", "dokument", "dokumente", "document", "documents", "datei", "dateien", "file", "files"}]
        if specific and not any(d.matched for d in card.documents):
            return respond("documents", "docs_unmatched", params={"what": " ".join(specific), "name": product.name}, results=[card])
        return respond("documents", "docs_one", params={"name": product.name, "n": len(card.documents)}, results=[card])
