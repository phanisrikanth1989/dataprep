"""id_Date context vars must store as datetime.date / datetime.datetime, not str."""
import datetime

from src.v1.engine.context_manager import ContextManager


def test_id_date_stores_as_date_object_iso():
    cm = ContextManager()
    cm.set("batch_date", "2025-06-01", "id_Date")
    val = cm.get("batch_date")
    assert isinstance(val, (datetime.date, datetime.datetime))
    assert val.year == 2025 and val.month == 6 and val.day == 1


def test_id_date_stores_as_datetime_object_iso_with_time():
    cm = ContextManager()
    cm.set("batch_dt", "2025-06-01 14:30:00", "id_Date")
    val = cm.get("batch_dt")
    assert isinstance(val, datetime.datetime)
    assert val.hour == 14 and val.minute == 30


def test_id_date_already_date_object_passes_through():
    cm = ContextManager()
    cm.set("batch_date", datetime.date(2025, 6, 1), "id_Date")
    val = cm.get("batch_date")
    assert val == datetime.date(2025, 6, 1)
