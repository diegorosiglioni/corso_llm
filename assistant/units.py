"""Unit converter over a closed list of units (pure logic, no MCP)."""

import math

# Factors towards the base unit of each quantity (m, kg, l).
_FACTORS = {
    "lunghezza": {
        "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
        "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344,
    },
    "massa": {
        "mg": 1e-6, "g": 0.001, "kg": 1.0, "t": 1000.0,
        "oz": 0.028349523125, "lb": 0.45359237,
    },
    "temperatura": {"C": None, "F": None, "K": None},  # converted with formulas through kelvin
    "volume": {"ml": 0.001, "l": 1.0, "gal": 3.785411784},  # US gallon
}

_ARTICLES = {
    "lunghezza": "una lunghezza",
    "massa": "una massa",
    "temperatura": "una temperatura",
    "volume": "un volume",
}

# Canonical unit → quantity, in the order used by the messages.
_QUANTITY_OF = {unit: quantity for quantity, units in _FACTORS.items() for unit in units}
_CANONICAL = {unit.lower(): unit for unit in _QUANTITY_OF}
_UNIT_LIST = ", ".join(_QUANTITY_OF)

UNITS_DESCRIPTION = (
    "Converte un valore tra unità della stessa grandezza. Unità ammesse — lunghezza: mm, cm, m, "
    "km, in, ft, yd, mi; massa: mg, g, kg, t, oz, lb; temperatura: C, F, K; volume: ml, l, gal."
)


def _canonical(unit: str) -> str:
    key = unit.strip().removeprefix("°").strip().lower()
    if key not in _CANONICAL:
        raise ValueError(f"Unità sconosciuta: '{unit.strip()}'. Unità ammesse: {_UNIT_LIST}.")
    return _CANONICAL[key]


def _to_kelvin(value: float, unit: str) -> float:
    if unit == "C":
        return value + 273.15
    if unit == "F":
        return (value - 32) * 5 / 9 + 273.15
    return value


def _from_kelvin(kelvin: float, unit: str) -> float:
    if unit == "C":
        return kelvin - 273.15
    if unit == "F":
        return (kelvin - 273.15) * 9 / 5 + 32
    return kelvin


def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    """Converts `value` between two units of the same quantity; raises ValueError otherwise."""
    if not math.isfinite(value):
        raise ValueError("Il valore deve essere un numero finito.")
    source, target = _canonical(from_unit), _canonical(to_unit)
    quantity = _QUANTITY_OF[source]
    if _QUANTITY_OF[target] != quantity:
        raise ValueError(
            f"Conversione impossibile: '{source}' è {_ARTICLES[quantity]}, "
            f"'{target}' è {_ARTICLES[_QUANTITY_OF[target]]}."
        )
    if quantity == "temperatura":
        kelvin = _to_kelvin(value, source)
        if kelvin < 0:
            raise ValueError(f"Temperatura sotto lo zero assoluto: {value:g} {source}.")
        result = _from_kelvin(kelvin, target)
    else:
        factors = _FACTORS[quantity]
        result = value * factors[source] / factors[target]
    if not math.isfinite(result):
        raise ValueError("Risultato troppo grande per essere rappresentato.")
    return {
        "value": value,
        "from_unit": source,
        "to_unit": target,
        "quantity": quantity,
        "result": float(f"{result:.6g}"),
    }
