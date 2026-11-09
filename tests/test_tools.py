from datetime import datetime, timezone

import pytest

from assistant.tools import create_current_time_tool
from conftest import FIXED_NOW


def current_time(tz, now=FIXED_NOW):
    return create_current_time_tool(lambda: now).invoke({"timezone": tz})


def test_tokyo():
    assert current_time("Asia/Tokyo") == {
        "timezone": "Asia/Tokyo", "datetime": "2026-10-27T00:47:12+09:00"
    }


def test_rome_winter():
    assert current_time("Europe/Rome")["datetime"] == "2026-10-26T16:47:12+01:00"


def test_rome_summer():
    summer = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    assert current_time("Europe/Rome", summer)["datetime"] == "2026-07-01T12:00:00+02:00"


@pytest.mark.parametrize("tz", ["Tokio", "", "../x", "asia/tokyo"])
def test_invalid_timezone(tz):
    assert current_time(tz) == {
        "error": f"Fuso orario sconosciuto: '{tz}'. Usa un nome IANA, es. 'Asia/Tokyo'."
    }


def test_parameter_names_and_description():
    t = create_current_time_tool()
    assert t.name == "get_current_time"
    assert t.tool_call_schema.model_json_schema()["required"] == ["timezone"]
    assert set(t.args) == {"timezone"}
    assert "Europe/Rome" in t.description and "Asia/Tokyo" in t.description


def test_real_clock_by_default():
    real = create_current_time_tool().invoke({"timezone": "UTC"})
    assert real["datetime"].endswith("+00:00")
