"""Katalogmodell und Relevanzbewertung. Alles läuft auf den öffentlich sichtbaren Daten
(aktive Kategorie-Kette, aktive Produkte, aktive Dokumente); nichts wird erfunden oder geraten."""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.repositories.chat_repository import ChatRepository
from app.services.chat.text import compact, fold, token_similarity, tokenize

# Gewichte der Fundstellen: Produktname zählt am meisten, Beschreibung/Dokumente weniger
W_NAME, W_CATEGORY, W_DESCRIPTION, W_DOCUMENT = 1.0, 0.7, 0.6, 0.6
MIN_SCORE = 0.45  # darunter kein Treffer
RELATIVE_CUTOFF = 0.6  # Treffer müssen mindestens so gut sein wie dieser Anteil des besten
CATEGORY_THRESHOLD = 0.85


@dataclass(frozen=True)
class DocEntry:
    id: int
    title: str
    filename: str
    version: str
    size: int
    tokens: frozenset[str]


@dataclass
class CategoryEntry:
    id: int
    name: str
    slug: str
    parent_id: int | None
    path: tuple[str, ...] = ()
    tokens: frozenset[str] = frozenset()
    ancestors: frozenset[int] = frozenset()  # IDs der Elternkategorien


@dataclass
class ProductEntry:
    id: int
    name: str
    slug: str
    description: str | None
    image_path: str | None
    category: CategoryEntry
    docs: list[DocEntry] = field(default_factory=list)
    name_tokens: frozenset[str] = frozenset()
    name_compact: str = ""
    category_tokens: frozenset[str] = frozenset()
    description_tokens: frozenset[str] = frozenset()
    doc_tokens: frozenset[str] = frozenset()


@dataclass
class Catalog:
    categories: dict[int, CategoryEntry]
    products: list[ProductEntry]

    def roots(self) -> list[CategoryEntry]:
        return [c for c in self.categories.values() if c.parent_id is None]

    def products_in(self, category: CategoryEntry) -> list[ProductEntry]:
        return [p for p in self.products if p.category.id == category.id or category.id in p.category.ancestors]

    def find_product(self, category_slug: str, product_slug: str) -> ProductEntry | None:
        return next((p for p in self.products if p.slug == product_slug and p.category.slug == category_slug), None)


def build_catalog(repo: ChatRepository) -> Catalog:
    """Drei begrenzte Abfragen; sichtbar sind nur Produkte, deren komplette Kategorie-Kette aktiv ist."""
    rows = {r.id: r for r in repo.categories()}
    entries: dict[int, CategoryEntry] = {}
    for row in rows.values():
        chain, seen, current, visible = [], set(), row, True
        while current is not None:
            if current.id in seen:  # Zyklus in den Daten: Kategorie nicht anzeigen
                visible = False
                break
            seen.add(current.id)
            visible = visible and current.active
            chain.append(current)
            current = rows.get(current.parent_id) if current.parent_id is not None else None
        if not visible:
            continue
        chain.reverse()
        entries[row.id] = CategoryEntry(
            id=row.id,
            name=row.name,
            slug=row.slug,
            parent_id=row.parent_id,
            path=tuple(c.name for c in chain),
            tokens=frozenset(t for c in chain for t in tokenize(c.name)),
            ancestors=frozenset(c.id for c in chain[:-1]),
        )
    docs: dict[int, list[DocEntry]] = {}
    for d in repo.active_documents():
        docs.setdefault(d.product_id, []).append(
            DocEntry(d.id, d.title, d.original_filename, d.version, d.file_size, frozenset(tokenize(f"{d.title} {d.original_filename}")))
        )
    products = []
    for p in repo.active_products():
        category = entries.get(p.category_id)
        if category is None:
            continue
        product_docs = docs.get(p.id, [])
        products.append(
            ProductEntry(
                id=p.id,
                name=p.name,
                slug=p.slug,
                description=p.description,
                image_path=p.image_path,
                category=category,
                docs=product_docs,
                name_tokens=frozenset(tokenize(p.name)),
                name_compact=compact(p.name),
                category_tokens=category.tokens,
                description_tokens=frozenset(tokenize(p.description or "")),
                doc_tokens=frozenset(t for d in product_docs for t in d.tokens),
            )
        )
    return Catalog(entries, products)


def _weight(token: str) -> float:
    return 2.0 if any(c.isdigit() for c in token) else 1.0  # Modellnummern sind das stärkste Signal


def _best(token: str, targets: frozenset[str], *, fuzzy: bool = True) -> float:
    return max((token_similarity(token, t, fuzzy=fuzzy) for t in targets), default=0.0)


def token_scores(tokens: list[str], p: ProductEntry) -> list[tuple[float, float]]:
    """(Gewicht, bester Treffer über alle Fundstellen) je Suchwort."""
    out = []
    for t in tokens:
        s = max(
            _best(t, p.name_tokens) * W_NAME,
            _best(t, p.category_tokens) * W_CATEGORY,
            _best(t, p.description_tokens, fuzzy=False) * W_DESCRIPTION,
            _best(t, p.doc_tokens, fuzzy=False) * W_DOCUMENT,
        )
        out.append((_weight(t), s))
    return out


def score_product(tokens: list[str], p: ProductEntry) -> float:
    """Relevanz 0..~1,4. Exakter Name > Name-Treffer > Kategorie > Beschreibung/Dokumente; fehlende Zahlen werten stark ab."""
    if not tokens:
        return 0.0
    scored = token_scores(tokens, p)
    total = sum(w for w, _ in scored)
    score = sum(w * s for w, s in scored) / total
    if any(w > 1 and s == 0 for w, s in scored):
        score *= 0.5  # eine angefragte Modellnummer fehlt: eher „ähnlich“ als Treffer
    if all(_best(t, p.name_tokens) >= 0.95 for t in tokens):
        score += 0.1
    if "".join(tokens) == p.name_compact:
        score += 0.3
    return score


def score_category(tokens: list[str], c: CategoryEntry) -> float:
    own = frozenset(tokenize(c.name))
    if not tokens:
        return 0.0
    scored = [(_weight(t), _best(t, own)) for t in tokens]
    coverage = sum(w * s for w, s in scored) / sum(w for w, _ in scored)
    # „Rollatoren“ soll vor „Indoor-Rollatoren“ gewinnen, wenn nur „Rollatoren“ gefragt ist: überzählige Namensteile werten ab
    matched = sum(1 for o in own if any(token_similarity(t, o) >= 0.85 for t in tokens))
    return coverage * (0.5 + 0.5 * matched / len(own)) if own else 0.0


@dataclass
class SearchResult:
    products: list[tuple[ProductEntry, float]]  # absteigend, gekappt
    total: int  # Treffer vor dem Kappen
    category: CategoryEntry | None  # eindeutig gemeinte Kategorie
    similar: list[ProductEntry]  # nur gefüllt, wenn es keinen Treffer gibt
    similar_categories: list[CategoryEntry]


def search(catalog: Catalog, tokens: list[str], limit: int) -> SearchResult:
    scored = sorted(((score_product(tokens, p), p) for p in catalog.products), key=lambda x: (-x[0], len(x[1].name), x[1].name))
    hits = [(p, s) for s, p in scored if s >= MIN_SCORE]
    if hits:
        top = hits[0][1]
        hits = [(p, s) for p, s in hits if s >= top * RELATIVE_CUTOFF]

    cats = sorted(((score_category(tokens, c), c) for c in catalog.categories.values()), key=lambda x: (-x[0], x[1].name))
    category = cats[0][1] if cats and cats[0][0] >= CATEGORY_THRESHOLD else None

    similar: list[ProductEntry] = []
    similar_categories: list[CategoryEntry] = []
    if not hits and category is None:
        similar = [p for s, p in scored[:3] if s >= 0.2]
        if not similar:
            joined = "".join(tokens)
            close = sorted(
                ((SequenceMatcher(None, joined, p.name_compact).ratio(), p) for p in catalog.products), key=lambda x: -x[0]
            )
            similar = [p for r, p in close[:3] if r >= 0.6]
        if not similar:
            similar_categories = catalog.roots()[:5]
    return SearchResult(hits[:limit], len(hits), category, similar, similar_categories)
