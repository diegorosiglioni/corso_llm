"""Reading and cleaning of Artusi's book: recipes, chapters, excluded parts, structural errors."""

from pathlib import Path

import pytest

from rag.corpus import CHAPTERS, Chapter, CorpusError, load_corpus, parse_corpus

TEST_CHAPTERS = (Chapter("ZUPPE", "Zuppe"), Chapter("DOLCI", "Dolci"))

SAMPLE = """\
The Project Gutenberg eBook of Libro di prova

*** START OF THE PROJECT GUTENBERG EBOOK LIBRO DI PROVA ***

PREFAZIONE

1. Non è una ricetta, ma una riga della prefazione.

MINESTRE

Testo che raggruppa i capitoli, prima del primo.


ZUPPE

Introduzione alle zuppe.

1. Zuppa di pane

Una zuppa con una riga spezzata
che continua sotto e una _parola_ in corsivo.

  Farina, grammi 150.
  Burro, grammi 50.

RICETTA DI PROVA

Ultima  riga\x0c della ricetta.

2. Zuppa lunga

Una zuppa che rimanda a un'altra.

7. rimando a una ricetta che non è questa.


MINESTRE

Introduzione al gruppo di minestre.


DOLCI

Introduzione ai dolci.

3. _Torta_

Una torta semplice.


APPENDICE

Appendice con 4. Ricetta che non conta.

*** END OF THE PROJECT GUTENBERG EBOOK LIBRO DI PROVA ***

Licenza del Project Gutenberg.
"""


def parse(text=SAMPLE):
    return parse_corpus(text, TEST_CHAPTERS, expected=3)


def test_recipes_titles_and_chapters():
    assert [(r.number, r.title, r.chapter) for r in parse()] == [
        (1, "Zuppa di pane", "Zuppe"), (2, "Zuppa lunga", "Zuppe"), (3, "Torta", "Dolci")]


def test_out_of_sequence_line_stays_in_the_text():
    assert "7. rimando" in parse()[1].text


def test_upper_case_line_that_is_not_a_chapter_stays_in_the_text():
    assert "RICETTA DI PROVA" in parse()[0].text


def test_cleaning_joins_wrapped_lines_and_keeps_doses_as_lines():
    text = parse()[0].text
    assert "Farina, grammi 150.\nBurro, grammi 50." in text      # doses: separate lines, no indent
    assert "riga spezzata che continua" in text                  # wrapped line joined
    assert "una parola in corsivo" in text
    assert "_" not in text and "  " not in text and "\x0c" not in text
    assert text.split("\n\n") == [
        "Una zuppa con una riga spezzata che continua sotto e una parola in corsivo.",
        "Farina, grammi 150.\nBurro, grammi 50.",
        "RICETTA DI PROVA",
        "Ultima riga della ricetta.",
    ]


def test_header_preface_chapter_intro_group_heading_and_appendix_are_excluded():
    texts = " ".join(r.text for r in parse())
    for excluded in ("Project Gutenberg", "Non è una ricetta", "Introduzione alle zuppe",
                     "Introduzione ai dolci", "raggruppa", "gruppo di minestre", "Appendice"):
        assert excluded not in texts


@pytest.mark.parametrize("broken, message", [
    (lambda s: s.replace("\n2. Zuppa lunga", "\n4. Zuppa lunga"), "2"),   # gap in the numbering
    (lambda s: s.replace("\nDOLCI\n", "\nDOLCETTI\n"), "DOLCI"),          # missing chapter
    (lambda s: s.replace("\nZUPPE\n", "\nZUPPETTE\n"), "ZUPPE"),          # missing first chapter
    (lambda s: s.replace("APPENDICE", "FINE"), "APPENDICE"),
])
def test_structural_errors(broken, message):
    with pytest.raises(CorpusError, match=message):
        parse(broken(SAMPLE))


def test_chapter_without_recipes_is_an_error():
    broken = SAMPLE.replace("3. _Torta_\n\nUna torta semplice.\n", "")
    with pytest.raises(CorpusError, match="Dolci"):
        parse_corpus(broken, TEST_CHAPTERS, expected=2)


def test_missing_file(tmp_path):
    with pytest.raises(CorpusError, match="assente.txt"):
        load_corpus(tmp_path / "assente.txt")


def test_file_not_in_utf8(tmp_path):
    path = tmp_path / "latino.txt"
    path.write_bytes("Città".encode("latin-1"))
    with pytest.raises(CorpusError, match="latino.txt.*UTF-8"):
        load_corpus(path)


def test_crlf_and_bom_are_read(tmp_path):
    path = tmp_path / "libro.txt"
    path.write_bytes(("﻿" + SAMPLE).replace("\n", "\r\n").encode("utf-8"))
    assert [r.number for r in load_corpus(path, TEST_CHAPTERS, expected=3)] == [1, 2, 3]


def test_the_23_chapters_of_the_book():
    assert len(CHAPTERS) == 23
    assert CHAPTERS[0] == Chapter("BRODI, GELATINA E SUGHI", "Brodi, gelatina e sughi")
    assert CHAPTERS[-1] == Chapter("COSE DIVERSE", "Cose diverse")


REAL = Path("data/Ricettario.txt")


@pytest.mark.skipif(not REAL.exists(), reason="data/Ricettario.txt non presente")
def test_real_book():
    recipes = load_corpus(REAL)
    assert [r.number for r in recipes] == list(range(1, 791))
    assert len({r.chapter for r in recipes}) == 23
    by_number = {r.number: r for r in recipes}
    assert (by_number[89].title, by_number[89].chapter) == ("Gnocchi di patate", "Minestre asciutte e di magro")
    assert "Patate grosse e gialle, grammi 400.\nFarina di grano, grammi 150." in by_number[89].text
    assert (by_number[208].title, by_number[208].chapter) == ("Pollo alla cacciatora", "Fritti")
    assert "cacciatora" not in by_number[208].text.lower()
    assert by_number[226].chapter == "Lesso"
    assert "biada dell'uomo" not in by_number[6].text          # introduction of MINESTRE
    assert "Spezie fini" == by_number[790].title and "APPENDICE" not in by_number[790].text
    assert all(r.title and r.text for r in recipes)
