"""Tools the model can request through tool calling."""

from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, available_timezones

from langchain_core.tools import BaseTool, tool


class ToolUnavailableError(Exception):
    """Raised by a tool when the service behind it does not answer (connection error)."""

CURRENT_TIME_DESCRIPTION = (
    "Restituisce data e ora correnti nel fuso orario indicato. `timezone` è un nome IANA, "
    'per esempio "Europe/Rome" o "Asia/Tokyo".'
)

# Exact match against the IANA list: covers unknown, empty or malformed names (e.g. "../x")
# and does not depend on how the operating system looks up the timezone files.
_VALID_TIMEZONES = available_timezones()


def create_current_time_tool(
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> BaseTool:
    """Creates the get_current_time tool; `now` lets tests fix the instant."""

    @tool("get_current_time", description=CURRENT_TIME_DESCRIPTION)
    def get_current_time(timezone: str) -> dict:
        if timezone not in _VALID_TIMEZONES:
            return {
                "error": f"Fuso orario sconosciuto: '{timezone}'. Usa un nome IANA, es. 'Asia/Tokyo'."
            }
        current = now().astimezone(ZoneInfo(timezone)).isoformat(timespec="seconds")
        return {"timezone": timezone, "datetime": current}

    return get_current_time
