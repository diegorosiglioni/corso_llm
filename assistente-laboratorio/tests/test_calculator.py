from pathlib import Path

import pytest

from assistant import calculator
from assistant.calculator import CALCULATOR_DESCRIPTION, calculate


@pytest.mark.parametrize("expr,expected", [
    ("17 * 23", 391), ("2 + 3 * 4", 14), ("(2 + 3) * 4", 20), ("-3 ** 2", -9), ("+5 - -2", 7),
    ("7 // 2", 3), ("7 % 3", 1), ("2 ** 10", 1024), ("0.1 + 0.2", 0.3), ("1 / 4", 0.25),
])
def test_valid(expr, expected):
    assert calculate(expr) == {"expression": expr, "result": expected}


def test_integer_result_stays_int():
    assert type(calculate("6 * 7")["result"]) is int


def test_expression_is_stripped():
    assert calculate("  1 + 1 ")["expression"] == "1 + 1"


@pytest.mark.parametrize("expr,message", [
    ("", r"^Espressione vuota\.$"),
    ("1+" * 101 + "1", r"^Espressione troppo lunga: massimo 200 caratteri\.$"),
    ("2 ^ 3", r"usa \*\* per le potenze"),
    ("3,5 + 1", r"usa il punto per i decimali"),
    ("(1 + 2", r"^Espressione non valida"),
    ("x + 1", r"^Elemento non ammesso: nome 'x'\.$"),
    ("__import__('os')", r"^Elemento non ammesso: chiamata di funzione\.$"),
    ("(1).real", r"^Elemento non ammesso: attributo\.$"),
    ("'a' * 3", r"^Elemento non ammesso: valore 'a'\.$"),
    ("True + 1", r"^Elemento non ammesso: valore True\.$"),
    ("1 << 3", r"^Elemento non ammesso: operatore '<<'\.$"),
    ("1 < 2", r"^Elemento non ammesso: confronto\.$"),
    ("1 / 0", r"^Divisione per zero\.$"),
    ("5 % 0", r"^Divisione per zero\.$"),
    ("2 ** 101", r"^Esponente troppo grande: massimo 100 in valore assoluto\.$"),
    ("9 ** 9 ** 9", r"^Esponente troppo grande"),
    ("10 ** 100 * 10", r"^Numero troppo grande: oltre 1e100\.$"),
])
def test_rejected(expr, message):
    with pytest.raises(ValueError, match=message):
        calculate(expr)


def test_float_overflow_is_too_large():
    with pytest.raises(ValueError, match=r"^Numero troppo grande: oltre 1e100\.$"):
        calculate("1e99 ** 100")


def test_fractional_power_of_negative_is_rejected():
    with pytest.raises(ValueError, match=r"^Risultato non reale"):
        calculate("(-8) ** 0.5")


def test_no_eval_in_module():
    source = Path(calculator.__file__).read_text(encoding="utf-8")
    assert "eval(" not in source.replace('mode="eval"', "") and "exec(" not in source


def test_description_mentions_operators():
    assert "**" in CALCULATOR_DESCRIPTION and "punto" in CALCULATOR_DESCRIPTION
