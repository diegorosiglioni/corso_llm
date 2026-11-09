import pytest

from assistant.catalog import Catalog


def test_search_by_word():
    r = Catalog.load().search("python")
    assert r == {"query": "python", "total": 2, "results": [
        {"code": "PY-101", "title": "Python per l'analisi dei dati", "location": "Trieste"},
        {"code": "PY-201", "title": "Python avanzato: test e packaging", "location": "Online"},
    ]}


def test_search_all_words_must_match():
    assert [i["code"] for i in Catalog.load().search("deep UDINE")["results"]] == ["DL-201"]


def test_search_by_code_and_location():
    assert Catalog.load().search("net-101")["total"] == 1
    assert Catalog.load().search("pordenone")["total"] == 2


def test_max_results_limits_results_not_total():
    r = Catalog.load().search("python", max_results=1)
    assert (len(r["results"]), r["total"]) == (1, 2)


def test_no_results_is_declared_empty():
    assert Catalog.load().search("astrologia") == {"query": "astrologia", "results": [], "total": 0}


def test_empty_query():
    with pytest.raises(ValueError, match=r"^Il testo di ricerca è vuoto\.$"):
        Catalog.load().search("  ")


@pytest.mark.parametrize("n", [0, 11])
def test_max_results_out_of_range(n):
    with pytest.raises(ValueError, match=rf"^max_results deve essere tra 1 e 10, ricevuto {n}\.$"):
        Catalog.load().search("python", max_results=n)


def test_get_item_full_record():
    item = Catalog.load().get_item("LLM-101")
    assert (item["title"], item["location"], item["duration_hours"]) == (
        "LLM: costruire chatbot e agenti", "Pordenone", 48
    )
    assert item["description"]


def test_get_item_ignores_case_and_spaces():
    assert Catalog.load().get_item(" dl-101 ")["code"] == "DL-101"


def test_get_item_unknown():
    with pytest.raises(
        ValueError,
        match=r"^Nessun corso con codice 'XX-999'\. Usa search_catalog per trovare il codice\.$",
    ):
        Catalog.load().get_item("XX-999")


def test_duplicate_codes_rejected():
    item = {"code": "A-1", "title": "t", "location": "l", "duration_hours": 1, "description": "d"}
    with pytest.raises(ValueError, match="duplicato"):
        Catalog([item, dict(item)])


def test_missing_field_rejected():
    with pytest.raises(ValueError, match="title"):
        Catalog([{"code": "A-1"}])
