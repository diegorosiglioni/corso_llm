"""Strumenti che il modello può richiedere tramite tool calling."""

from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones

from langchain_core.tools import BaseTool, tool

DESCRIZIONE_ORA_CORRENTE = (
    "Restituisce data e ora correnti nel fuso orario indicato. `fuso` è un nome IANA, "
    'per esempio "Europe/Rome" o "Asia/Tokyo".'
)

# Confronto esatto con l'elenco IANA: copre nomi sconosciuti, vuoti o malformati (es. "../x")
# e non dipende da come il sistema operativo cerca i file dei fusi.
_FUSI_VALIDI = available_timezones()


def crea_ora_corrente(
    adesso: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> BaseTool:
    """Crea lo strumento ora_corrente; `adesso` permette di fissare l'istante nei test."""

    @tool("ora_corrente", description=DESCRIZIONE_ORA_CORRENTE)
    def ora_corrente(fuso: str) -> dict:
        if fuso not in _FUSI_VALIDI:
            return {
                "errore": f"Fuso orario sconosciuto: '{fuso}'. Usa un nome IANA, es. 'Asia/Tokyo'."
            }
        data_ora = adesso().astimezone(ZoneInfo(fuso)).isoformat(timespec="seconds")
        return {"fuso": fuso, "data_ora": data_ora}

    return ora_corrente
