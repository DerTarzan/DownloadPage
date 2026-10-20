"""Füllwörter und Dokument-Stichwörter (gefaltet). Gilt für beide Sprachen, damit die Suche nicht von der UI-Sprache abhängt."""
from app.services.chat.text import fold

_STOPWORDS = """
ich suche suchen such brauche brauch benoetige haette moechte moechten will wuerde finde finden zeig zeige zeigen gib gibt
es gibt gebe welche welcher welches welchen wo wie was wer ist sind hat haben kann kannst koennt koennen mir mich mein meine
dir du sie wir ein eine einen einem einer eines der die das den dem des und oder fuer von zu zum zur zur mit bei auf im in
am an aus nach ueber unter nur auch noch mal bitte hallo hi hey danke bitte diese dieser diesem diesen dieses
dazu dafuer darueber hierzu produkt produkte artikel
i am looking for look need want find show me give get is are there do does you have has the a an of for to with about
on in at by from please which what where how can could would like any some this that these those its it my our
product products item items
""".split()

_DOC_WORDS = """
bedienungsanleitung anleitung anleitungen handbuch handbuecher gebrauchsanweisung gebrauchsanleitung manual manuals
datenblatt datenblaetter pdf pdfs dokument dokumente dokumentation download downloads unterlagen broschuere prospekt
guide instructions instruction datasheet datasheets document documents documentation brochure leaflet file files
datei dateien
""".split()

STOPWORDS = frozenset(fold(w) for w in _STOPWORDS)
DOC_WORDS = frozenset(fold(w) for w in _DOC_WORDS)

GREETINGS = frozenset(fold(w) for w in "hallo hi hey moin servus guten tag morgen abend hello hey danke thanks thank thx bye tschuess".split())
REFERENCES = frozenset(fold(w) for w in "diesem diesen diesem dieses dieser dazu hierzu dafuer this that it its".split())
