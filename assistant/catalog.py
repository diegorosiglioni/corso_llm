"""Local course catalog: reads the JSON file, searches by words and returns a single course."""

import json
from pathlib import Path

DEFAULT_CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"

FIELDS = ("code", "title", "location", "duration_hours", "description")
MAX_RESULTS_LIMIT = 10

SEARCH_DESCRIPTION = (
    "Cerca corsi nel catalogo per parole del titolo, del codice o della sede. Restituisce "
    "codice, titolo e sede; per durata e descrizione usa get_item."
)
GET_ITEM_DESCRIPTION = (
    "Restituisce tutti i dati di un corso del catalogo dato il suo codice esatto, ottenuto con "
    "search_catalog."
)


class Catalog:
    def __init__(self, items: list[dict]):
        codes = set()
        for item in items:
            for field in FIELDS:
                if field not in item:
                    raise ValueError(
                        f"Campo mancante nel catalogo: '{field}' (corso '{item.get('code', '?')}')."
                    )
            key = item["code"].casefold()
            if key in codes:
                raise ValueError(f"Codice duplicato nel catalogo: '{item['code']}'.")
            codes.add(key)
        self._items = [dict(item) for item in items]

    @classmethod
    def load(cls, path: Path = DEFAULT_CATALOG_PATH) -> "Catalog":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def search(self, query: str, max_results: int = 5) -> dict:
        """Courses whose code, title or location contain every word of `query`."""
        words = query.casefold().split()
        if not words:
            raise ValueError("Il testo di ricerca è vuoto.")
        if not 1 <= max_results <= MAX_RESULTS_LIMIT:
            raise ValueError(
                f"max_results deve essere tra 1 e {MAX_RESULTS_LIMIT}, ricevuto {max_results}."
            )
        matches = [
            {"code": item["code"], "title": item["title"], "location": item["location"]}
            for item in self._items
            if all(
                word in f"{item['code']} {item['title']} {item['location']}".casefold()
                for word in words
            )
        ]
        return {"query": query, "results": matches[:max_results], "total": len(matches)}

    def get_item(self, code: str) -> dict:
        """Full record of the course with the given code (case and outer spaces ignored)."""
        key = code.strip().casefold()
        for item in self._items:
            if item["code"].casefold() == key:
                return dict(item)
        raise ValueError(
            f"Nessun corso con codice '{code.strip()}'. Usa search_catalog per trovare il codice."
        )
