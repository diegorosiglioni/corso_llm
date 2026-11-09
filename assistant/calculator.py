"""Safe arithmetic calculator: parses with ast and evaluates a closed set of nodes, no eval."""

import ast
import operator
import re

CALCULATOR_DESCRIPTION = (
    "Calcola un'espressione aritmetica. Ammessi: numeri, + - * / // % **, parentesi. "
    "Per i decimali usa il punto."
)

MAX_LENGTH = 200
MAX_EXPONENT = 100
MAX_MAGNITUDE = 1e100

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

# Symbols of the operators that are not allowed, for the error message.
_SYMBOLS = {
    ast.LShift: "<<", ast.RShift: ">>", ast.BitOr: "|", ast.BitAnd: "&", ast.BitXor: "^",
    ast.MatMult: "@", ast.Invert: "~", ast.Not: "not",
}


def _rejected(what: str) -> ValueError:
    return ValueError(f"Elemento non ammesso: {what}.")


def _checked(value):
    if isinstance(value, complex):
        raise ValueError("Risultato non reale: potenza frazionaria di un numero negativo.")
    if abs(value) > MAX_MAGNITUDE:
        raise ValueError("Numero troppo grande: oltre 1e100.")
    return value


def _evaluate(node: ast.AST):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise _rejected(f"valore {node.value!r}")
        return _checked(node.value)
    if isinstance(node, ast.BinOp):
        function = _BINARY.get(type(node.op))
        if function is None:
            raise _rejected(f"operatore '{_SYMBOLS.get(type(node.op), type(node.op).__name__)}'")
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise ValueError(
                f"Esponente troppo grande: massimo {MAX_EXPONENT} in valore assoluto."
            )
        try:
            return _checked(function(left, right))
        except ZeroDivisionError:
            raise ValueError("Divisione per zero.") from None
        except OverflowError:
            raise ValueError("Numero troppo grande: oltre 1e100.") from None
    if isinstance(node, ast.UnaryOp):
        function = _UNARY.get(type(node.op))
        if function is None:
            raise _rejected(f"operatore '{_SYMBOLS.get(type(node.op), type(node.op).__name__)}'")
        return _checked(function(_evaluate(node.operand)))
    if isinstance(node, ast.Name):
        raise _rejected(f"nome '{node.id}'")
    if isinstance(node, ast.Call):
        raise _rejected("chiamata di funzione")
    if isinstance(node, ast.Attribute):
        raise _rejected("attributo")
    if isinstance(node, ast.Compare):
        raise _rejected("confronto")
    raise _rejected(f"costrutto '{type(node).__name__}'")


def calculate(expression: str) -> dict:
    """Evaluates an arithmetic expression; raises ValueError with an Italian message otherwise."""
    text = expression.strip()
    if not text:
        raise ValueError("Espressione vuota.")
    if len(text) > MAX_LENGTH:
        raise ValueError(f"Espressione troppo lunga: massimo {MAX_LENGTH} caratteri.")
    if "^" in text:
        raise ValueError("Espressione non valida: usa ** per le potenze.")
    if re.search(r"\d,\d", text):
        raise ValueError("Espressione non valida: usa il punto per i decimali.")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        raise ValueError("Espressione non valida: controlla parentesi e operatori.") from None
    result = _evaluate(tree)
    if isinstance(result, float):
        result = float(f"{result:.12g}")
    return {"expression": text, "result": result}
