"""Unit tests for Py4J input converters DateConverter / DatetimeConverter.

Pure-Python unit suite (no JVM required). Mocks ``py4j.java_gateway.JavaClass``
so that ``JavaClass("java.util.Date", gateway_client)(millis)`` is interceptable
without a real JVM. Asserts that converter ``convert()`` calls the Java Date
constructor with the expected epoch-millis integer.

Test expected-millis formulas mirror RESEARCH.md L74-91 exactly:
    DateConverter:          int(calendar.timegm(d.timetuple()) * 1000)
    DatetimeConverter aware: int(calendar.timegm(dt.utctimetuple()) * 1000
                                  + dt.microsecond // 1000)
    DatetimeConverter naive: int(time.mktime(dt.timetuple()) * 1000
                                  + dt.microsecond // 1000)

Note on converter API change (Task 0.4)
---------------------------------------
Originally the converters used ``gateway_client.jvm.java.util.Date(millis)``.
This was incorrect: Py4J passes a ``GatewayClient`` (not ``JavaGateway``) to
input-converter ``convert()`` calls, so ``gateway_client.jvm`` raises
``AttributeError``. The converters now use
``JavaClass("java.util.Date", gateway_client)(millis)`` which works with the
low-level ``GatewayClient`` API. Tests mock ``JavaClass`` accordingly.
"""

import calendar
import datetime
import time
from unittest.mock import MagicMock, patch

import pytest  # noqa: F401  -- imported for pytest test discovery / fixtures if needed

from src.v1.java_bridge.bridge import DateConverter, DatetimeConverter


class TestDateConverter:
    """can_convert truth-table + convert() epoch-millis output for DateConverter."""

    def test_can_convert_true_for_date(self):
        assert DateConverter().can_convert(datetime.date(2026, 5, 15)) is True

    def test_can_convert_false_for_datetime(self):
        # datetime.datetime is a subclass of datetime.date but DateConverter
        # must exclude it -- DatetimeConverter handles datetimes.
        dt = datetime.datetime(2026, 5, 15, 12, 30, 45)
        assert DateConverter().can_convert(dt) is False

    def test_can_convert_false_for_str(self):
        assert DateConverter().can_convert("2026-05-15") is False

    def test_can_convert_false_for_none(self):
        assert DateConverter().can_convert(None) is False

    def test_convert_produces_java_date_with_midnight_utc_millis(self):
        d = datetime.date(2026, 5, 15)
        expected_ms = int(calendar.timegm(d.timetuple()) * 1000)

        gateway_client = MagicMock()
        java_date_constructor = MagicMock()
        java_date_instance = MagicMock()
        java_date_constructor.return_value = java_date_instance

        with patch("src.v1.java_bridge.bridge.JavaClass", return_value=java_date_constructor) as mock_java_class:
            result = DateConverter().convert(d, gateway_client)

        # JavaClass should be called with the java.util.Date class name and the gateway_client
        mock_java_class.assert_called_once_with("java.util.Date", gateway_client)
        # The constructor should be called with the epoch millis
        java_date_constructor.assert_called_once_with(expected_ms)
        # The converter returns the constructed Date instance unchanged.
        assert result is java_date_instance


class TestDatetimeConverter:
    """can_convert truth-table + convert() epoch-millis output for DatetimeConverter."""

    def test_can_convert_true_for_datetime(self):
        dt = datetime.datetime(2026, 5, 15, 12, 30, 45)
        assert DatetimeConverter().can_convert(dt) is True

    def test_can_convert_false_for_date(self):
        # Concrete date (NOT datetime) -- DatetimeConverter must skip it.
        assert DatetimeConverter().can_convert(datetime.date(2026, 5, 15)) is False

    def test_convert_aware_uses_utctimetuple(self):
        dt = datetime.datetime(2026, 5, 15, 12, 30, 45, tzinfo=datetime.timezone.utc)
        expected_ms = int(
            calendar.timegm(dt.utctimetuple()) * 1000 + dt.microsecond // 1000
        )

        gateway_client = MagicMock()
        java_date_constructor = MagicMock()

        with patch("src.v1.java_bridge.bridge.JavaClass", return_value=java_date_constructor) as mock_java_class:
            DatetimeConverter().convert(dt, gateway_client)

        mock_java_class.assert_called_once_with("java.util.Date", gateway_client)
        java_date_constructor.assert_called_once_with(expected_ms)

    def test_convert_naive_uses_mktime(self):
        dt = datetime.datetime(2026, 5, 15, 12, 30, 45)  # naive, no tzinfo
        expected_ms = int(time.mktime(dt.timetuple()) * 1000 + dt.microsecond // 1000)

        gateway_client = MagicMock()
        java_date_constructor = MagicMock()

        with patch("src.v1.java_bridge.bridge.JavaClass", return_value=java_date_constructor) as mock_java_class:
            DatetimeConverter().convert(dt, gateway_client)

        mock_java_class.assert_called_once_with("java.util.Date", gateway_client)
        java_date_constructor.assert_called_once_with(expected_ms)

    def test_convert_preserves_microseconds_floored_to_millis(self):
        # microsecond=123456 should add floor(123456/1000) = 123 millis.
        dt = datetime.datetime(
            2026, 5, 15, 12, 30, 45, 123456, tzinfo=datetime.timezone.utc
        )
        seconds = calendar.timegm(dt.utctimetuple())
        expected_ms = int(seconds * 1000 + 123)  # 123456 // 1000 == 123
        assert expected_ms == int(seconds * 1000 + dt.microsecond // 1000)

        gateway_client = MagicMock()
        java_date_constructor = MagicMock()

        with patch("src.v1.java_bridge.bridge.JavaClass", return_value=java_date_constructor) as mock_java_class:
            DatetimeConverter().convert(dt, gateway_client)

        mock_java_class.assert_called_once_with("java.util.Date", gateway_client)
        java_date_constructor.assert_called_once_with(expected_ms)
