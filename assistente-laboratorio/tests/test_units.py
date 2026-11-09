import pytest

from assistant.units import UNITS_DESCRIPTION, convert_units


def test_length():
    assert convert_units(10, "km", "mi") == {
        "value": 10, "from_unit": "km", "to_unit": "mi", "quantity": "lunghezza", "result": 6.21371
    }


@pytest.mark.parametrize("v,a,b,expected", [
    (1, "ft", "cm", 30.48), (2.5, "kg", "lb", 5.51156), (1, "gal", "l", 3.78541),
    (100, "C", "F", 212), (32, "F", "C", 0), (0, "K", "C", -273.15), (1500, "mg", "g", 1.5),
])
def test_known_conversions(v, a, b, expected):
    assert convert_units(v, a, b)["result"] == pytest.approx(expected)


def test_units_ignore_case_spaces_and_degree():
    r = convert_units(20, " °c ", "f")
    assert (r["from_unit"], r["to_unit"], r["result"]) == ("C", "F", 68)


def test_unknown_unit():
    with pytest.raises(
        ValueError,
        match=r"^Unità sconosciuta: 'xyz'\. Unità ammesse: mm, cm, m, km, in, ft, yd, mi, "
        r"mg, g, kg, t, oz, lb, C, F, K, ml, l, gal\.$",
    ):
        convert_units(1, "xyz", "m")


def test_incompatible_quantities():
    with pytest.raises(
        ValueError, match=r"^Conversione impossibile: 'km' è una lunghezza, 'kg' è una massa\.$"
    ):
        convert_units(1, "km", "kg")


@pytest.mark.parametrize("v", [float("nan"), float("inf")])
def test_non_finite_value(v):
    with pytest.raises(ValueError, match=r"^Il valore deve essere un numero finito\.$"):
        convert_units(v, "m", "km")


def test_below_absolute_zero():
    with pytest.raises(ValueError, match=r"^Temperatura sotto lo zero assoluto: -500 C\.$"):
        convert_units(-500, "C", "F")


def test_description_lists_the_units():
    assert "mm, cm, m, km" in UNITS_DESCRIPTION and "C, F, K" in UNITS_DESCRIPTION
