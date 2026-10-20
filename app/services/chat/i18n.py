"""Antworttexte des Bots (Deutsch/Englisch). Die UI-Beschriftungen stehen in static/js/chat.js; die Suche selbst ist sprachunabhängig."""
SUPPORTED = ("de", "en")
DEFAULT_LANG = "de"

MESSAGES: dict[str, dict[str, str]] = {
    "de": {
        "greeting": "Hallo! Ich helfe dir dabei, Produkte, Kategorien und Dokumente zu finden. Was suchst du?",
        "clarify": "Wonach genau suchst du? Nenne mir einen Produktnamen, eine Modellnummer oder eine Kategorie.",
        "clarify_categories": "Wonach genau suchst du? Nenne mir einen Produktnamen, eine Modellnummer oder stöbere in diesen Kategorien:",
        "clarify_product": "Zu welchem Produkt suchst du die Dokumente? Nenne mir bitte den Produktnamen oder die Modellnummer.",
        "found_one": "Ich habe einen passenden Treffer gefunden: {name}. Hier findest du die Produktseite und die verfügbaren Dokumente.",
        "found_one_nodocs": "Ich habe einen passenden Treffer gefunden: {name}. Dokumente sind zu diesem Produkt aktuell nicht hinterlegt.",
        "found_many": "Ich habe {n} passende Produkte gefunden. Welches meinst du?",
        "found_many_more": "Ich habe {total} passende Produkte gefunden und zeige die {n} besten. Nenne mir gern mehr Details, um die Suche einzugrenzen.",
        "category": "In der Kategorie „{name}“ gibt es {n} Produkt(e).",
        "category_more": "In der Kategorie „{name}“ gibt es {total} Produkte. Hier sind {n} davon; alle findest du auf der Kategorieseite.",
        "category_empty": "Die Kategorie „{name}“ gibt es, aktuell sind dort aber noch keine Produkte hinterlegt.",
        "docs_one": "Für {name} habe ich {n} Dokument(e) gefunden:",
        "docs_none": "Zu {name} sind aktuell keine Dokumente hinterlegt. Auf der Produktseite findest du alle Informationen.",
        "docs_unmatched": "Eine passende Datei zu „{what}“ gibt es nicht. Das sind die vorhandenen Dokumente zu {name}:",
        "none": "Ich habe keinen passenden Eintrag gefunden. Prüfe bitte die Schreibweise oder versuche einen anderen Begriff.",
        "none_similar": "Ich habe keinen passenden Eintrag gefunden. Meintest du vielleicht eines dieser Produkte?",
        "none_categories": "Ich habe keinen passenden Eintrag gefunden. Du kannst aber in diesen Kategorien stöbern:",
        "empty_catalog": "Aktuell sind noch keine Produkte hinterlegt.",
    },
    "en": {
        "greeting": "Hello! I can help you find products, categories and documents. What are you looking for?",
        "clarify": "What exactly are you looking for? Tell me a product name, a model number or a category.",
        "clarify_categories": "What exactly are you looking for? Tell me a product name, a model number, or browse these categories:",
        "clarify_product": "Which product do you need the documents for? Please tell me the product name or model number.",
        "found_one": "I found a matching result: {name}. Here you can find the product page and the available documents.",
        "found_one_nodocs": "I found a matching result: {name}. There are currently no documents available for this product.",
        "found_many": "I found {n} matching products. Which one do you mean?",
        "found_many_more": "I found {total} matching products and I'm showing the best {n}. Feel free to give me more details to narrow it down.",
        "category": "The category “{name}” contains {n} product(s).",
        "category_more": "The category “{name}” contains {total} products. Here are {n} of them; you can see all of them on the category page.",
        "category_empty": "The category “{name}” exists, but it has no products yet.",
        "docs_one": "I found {n} document(s) for {name}:",
        "docs_none": "There are currently no documents for {name}. The product page has all available information.",
        "docs_unmatched": "There is no file matching “{what}”. These are the available documents for {name}:",
        "none": "I couldn't find a matching entry. Please check the spelling or try a different term.",
        "none_similar": "I couldn't find a matching entry. Did you perhaps mean one of these products?",
        "none_categories": "I couldn't find a matching entry, but you can browse these categories:",
        "empty_catalog": "There are no products available yet.",
    },
}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in SUPPORTED else DEFAULT_LANG


def msg(lang: str, key: str, **params: object) -> str:
    return MESSAGES[normalize_lang(lang)][key].format(**params)
