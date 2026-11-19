"""Rule `has_doses`: a paragraph of two or more lines with at least one quantity (spec §3)."""

import pytest

from rag.doses import has_doses


@pytest.mark.parametrize("text", [
    "Patate, grammi 400.\nFarina, grammi 150.\n\nCuocete le patate nell'acqua.",
    "Uova, N. 3.\nSale, quanto basta.",
    "Zucchero, gr. 100.\nAcqua, mezzo bicchiere.",
])
def test_list_with_quantities(text):
    assert has_doses(text) is True


def test_list_with_one_quantity_line_is_enough():
    assert has_doses("Riso, mezzo chilo.\nBrodo, decilitri 2.\nUn pizzico di pepe.") is True


def test_list_without_units():
    assert has_doses("Mezzo petto di cappone.\nUn fegatino di pollo.") is False


def test_verses():
    assert has_doses("Se il maiale volasse\nNon ci saria danar che lo pagasse,") is False


def test_illustration_caption():
    assert has_doses("[Illustrazione: Disco — grammi 10\nnell'illustrazione]") is False


def test_dose_inside_prose():
    text = "Prendete grammi 300 di farina e fatene una pasta con le uova, lavorandola a lungo."
    assert has_doses(text) is False


@pytest.mark.parametrize("text", [
    "Farina, grammi 200.",
    "Farina, grammi 200.\n\nImpastate con le uova e lasciate riposare la pasta.",
])
def test_single_dose_line(text):
    assert has_doses(text) is False


def test_list_in_a_later_paragraph():
    text = "Questa è una minestra assai delicata.\n\nBrodo, litri 1.\nSemolino, grammi 80."
    assert has_doses(text) is True


def test_unit_is_a_word():
    assert has_doses("Rettore della chiesa.\nAltro verso.") is False
