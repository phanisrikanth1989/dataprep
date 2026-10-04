"""Tests for schema type mappings."""
import polars as pl
from src.v2.components.file.schema_types import TYPE_MAPPING, DATE_TYPES


class TestTypeMapping:
    def test_date_maps_to_pl_date(self):
        assert TYPE_MAPPING['date'] == pl.Date

    def test_datetime_maps_to_pl_datetime(self):
        assert TYPE_MAPPING['datetime'] == pl.Datetime

    def test_id_date_maps_to_pl_date(self):
        assert TYPE_MAPPING['id_Date'] == pl.Date

    def test_integer_unchanged(self):
        assert TYPE_MAPPING['integer'] == pl.Int64

    def test_decimal_stays_utf8(self):
        assert TYPE_MAPPING['decimal'] == pl.Utf8


class TestDateTypes:
    def test_date_in_date_types(self):
        assert 'date' in DATE_TYPES

    def test_datetime_in_date_types(self):
        assert 'datetime' in DATE_TYPES

    def test_id_date_in_date_types(self):
        assert 'id_Date' in DATE_TYPES

    def test_integer_not_in_date_types(self):
        assert 'integer' not in DATE_TYPES
