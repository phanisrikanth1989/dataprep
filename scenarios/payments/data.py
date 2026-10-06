"""Made-up data for the payments scenario: one big payments file and its small reference files.

Every value is worked out from the row's number, so a row count always
gives the same files, on any machine. The files are written with a header
line and ``;`` between fields, and hold plain ASCII.

The file runs on its own and needs only Python and polars:

    python data.py --rows 100000 --out data

It writes ``payments.csv`` (45 columns, about 470 bytes a row) and the four
small files the job reads beside it: ``branches.csv``, ``customers.csv``,
``purposes.csv`` and ``settings.csv``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

import polars as pl

BRANCHES = 5_000
CUSTOMERS = 200_000
PURPOSES = 300
# Payments name a few purpose codes the reference file does not hold.
PURPOSES_USED = 320
UNKNOWN_BRANCH = "BR99999"
BUSINESS_DATE = "2024-03-31"
HIGH_VALUE_LIMIT = 250_000

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "INR", "SGD", "AUD", "CAD", "HKD"]
RATES = ["1.0000", "1.0842", "1.2715", "0.0067", "1.1230", "0.0120", "0.7410", "0.6605", "0.7325", "0.1281"]
COUNTRIES = ["GB", "DE", "FR", "US", "IN", "SG", "CH", "NL"]
BANKS = ["NWBK", "DEUT", "BNPA", "CITI", "HDFC", "DBSS", "UBSW", "INGB", "BARC", "HSBC", "SOGE", "ICIC"]
CHANNELS = ["ONLINE", "BRANCH", "API", "FILE", "MOBILE"]
STATUSES = ["BOOKED", "PENDING", "SETTLED", "RETURNED"]
BEARERS = ["SHA", "OUR", "BEN"]
METHODS = ["INDA", "INGA", "COVE", "CLRG"]
SYSTEMS = ["TARGET2", "CHAPS", "FEDWIRE", "SEPA", "CHIPS"]
PARTY_TYPES = ["CORP", "IND", "GOV"]
TAX_CODES = ["STD", "EXM", "ZER", "RED"]
SOURCES = ["CORE", "SWIFT", "ACH", "CARDS"]
REGIONS = ["EMEA-N", "EMEA-S", "AMER-N", "AMER-S", "APAC-N", "APAC-S", "MEA", "UKI"]
SEGMENTS = ["RETAIL", "SME", "CORP", "PRIVATE"]
RATINGS = ["LOW", "MEDIUM", "HIGH"]
CATEGORIES = ["TRADE", "SALARY", "TAX", "TREASURY", "LOAN", "OTHER"]

_CHUNK = 500_000
_OPTIONS = {"separator": ";", "line_terminator": "\n"}


def purpose_code(number: int) -> str:
    """The four capitals that stand for one purpose; no two numbers below 676 share them."""
    letters = [number % 26, (number // 26) % 26, (number * 7) % 26, (number * 11) % 26]
    return "".join(chr(65 + letter) for letter in letters)


def generate(folder: Path, rows: int) -> None:
    """Write the scenario's input files into a folder.

    Args:
        folder: Where the files go; made when it is not there.
        rows: How many payments to write.
    """
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "settings.csv").write_text(
        f"key;value\nbusiness_date;{BUSINESS_DATE}\nhigh_value_limit;{HIGH_VALUE_LIMIT}\n", encoding="ascii"
    )
    _branches().write_csv(folder / "branches.csv", **_OPTIONS)
    _customers().write_csv(folder / "customers.csv", **_OPTIONS)
    _purposes().write_csv(folder / "purposes.csv", **_OPTIONS)
    with open(folder / "payments.csv", "wb") as handle:
        for start in range(0, rows, _CHUNK):
            frame = _payments(start, min(start + _CHUNK, rows))
            frame.write_csv(handle, include_header=start == 0, **_OPTIONS)


# ------------------------------------------------------------------
# Reference files
# ------------------------------------------------------------------

def _branches() -> pl.DataFrame:
    number = pl.int_range(BRANCHES)
    return pl.select(
        pl.format("BR{}", _digits(number, 5)).alias("branch_code"),
        pl.format("BRANCH {}", _digits(number, 5)).alias("branch_name"),
        _pick(number % 8, REGIONS).alias("region"),
        pl.format("CC{}", _digits(number % 300, 4)).alias("cost_centre"),
    )


def _customers() -> pl.DataFrame:
    number = pl.int_range(1, CUSTOMERS + 1)
    status = (
        pl.when(number % 20 == 3).then(pl.lit("CLOSED"))
        .when(number % 20 == 13).then(pl.lit("SUSPENDED"))
        .otherwise(pl.lit("ACTIVE"))
    )
    return pl.select(
        number.alias("customer_id"),
        pl.format("CUSTOMER {}", _digits(number, 6)).alias("customer_name"),
        _pick(number % 4, SEGMENTS).alias("segment"),
        status.alias("status"),
        _pick(number % 3, RATINGS).alias("risk_rating"),
        _pick(number % 8, COUNTRIES).alias("home_country"),
    )


def _purposes() -> pl.DataFrame:
    return pl.DataFrame({
        "purpose_code": [purpose_code(number) for number in range(PURPOSES)],
        "purpose_name": [f"PURPOSE {number:03d}" for number in range(PURPOSES)],
        "category": [CATEGORIES[number % len(CATEGORIES)] for number in range(PURPOSES)],
    })


# ------------------------------------------------------------------
# Payments
# ------------------------------------------------------------------

def _payments(start: int, end: int) -> pl.DataFrame:
    """The payments numbered from ``start`` up to ``end``, one row each, every field as text."""
    i = pl.col("i")
    kind = i % 100
    day = pl.date(2024, 1, 1) + pl.duration(days=i % 90)
    debit = i % 8
    credit = pl.when(i % 4 == 0).then((i // 4 + 3) % 8).otherwise(debit)
    currency = (i * 7) % 10
    dollars = (i * 7919) % 100_000 + 1 + pl.when(i % 40 == 0).then(900_000).otherwise(0)
    amount = pl.format("{}.{}", dollars, _digits(i % 100, 2))
    debit_account = pl.format(
        "{}{}{}{}", _pick(debit, COUNTRIES), _digits(i % 97, 2), _pick((i * 3) % 12, BANKS), _digits((i * 104_729) % 10**14, 14)
    )
    credit_account = pl.format(
        "{}{}{}{}", _pick(credit, COUNTRIES), _digits((i * 5) % 97, 2), _pick((i * 5) % 12, BANKS),
        _digits((i * 15_485_863) % 10**14, 14),
    )
    invoice = pl.format(
        "PAYMENT  FOR   INV-{}-{}  SUPPLIER {}", 2020 + i % 5, _digits((i * 37) % 1_000_000, 6), (i * 3) % 9_000
    )
    codes = [purpose_code(number) for number in range(PURPOSES_USED)]
    columns = {
        "txn_id": i + 1,
        # One payment in a hundred carries the reference of the one before it.
        "txn_ref": pl.format("TX{}", _digits(pl.when(kind == 57).then(i).otherwise(i + 1), 12)),
        "batch_id": i // 10_000,
        "seq_no": i % 10_000,
        "value_date": day.dt.strftime("%Y-%m-%d"),
        "booking_date": (day - pl.duration(days=i % 3)).dt.strftime("%Y-%m-%d"),
        "created_ts": (pl.datetime(2024, 1, 1) + pl.duration(seconds=i % 7_776_000)).dt.strftime("%Y-%m-%d %H:%M:%S"),
        "amount": amount,
        "fee": pl.format("{}.{}", i % 5, _digits((i * 3) % 100, 2)),
        "instructed_amount": amount,
        "fx_rate": _pick(currency, RATES),
        # One in a hundred has a currency that is not three capitals...
        "currency": pl.when(kind == 23).then(_pick(currency, CURRENCIES).str.to_lowercase()).otherwise(_pick(currency, CURRENCIES)),
        "instructed_currency": _pick((i * 3) % 10, CURRENCIES),
        # ...and one in a hundred an account number that does not look like an IBAN.
        "debit_account": pl.when(kind == 7).then(debit_account.str.to_lowercase()).otherwise(debit_account),
        "credit_account": credit_account,
        "debit_bic": pl.format("{}{}2L", _pick((i * 3) % 12, BANKS), _pick(debit, COUNTRIES)),
        "credit_bic": pl.format("{}{}2L", _pick((i * 5) % 12, BANKS), _pick(credit, COUNTRIES)),
        "debit_country": _pick(debit, COUNTRIES),
        "credit_country": _pick(credit, COUNTRIES),
        # One in a hundred names a branch the reference file does not hold.
        "branch_code": pl.when(kind == 41).then(pl.lit(UNKNOWN_BRANCH)).otherwise(pl.format("BR{}", _digits((i * 13) % BRANCHES, 5))),
        "customer_id": (i * 31) % CUSTOMERS + 1,
        "channel": _pick(i % 5, CHANNELS),
        "product_code": pl.format("P{}", _digits(i % 40, 3)),
        "status": _pick(i % 4, STATUSES),
        "priority": i % 5,
        "charge_bearer": _pick(i % 3, BEARERS),
        "settlement_method": _pick(i % 4, METHODS),
        "clearing_system": _pick(i % 5, SYSTEMS),
        "narrative": pl.when(i % 5 == 0).then(pl.format("SALARY   TRANSFER  MONTH {}", i % 12 + 1)).otherwise(invoice),
        "remittance_info": pl.format("/PURP/{}/REF/{}", _pick((i * 17) % PURPOSES_USED, codes), _digits((i * 11) % 10**8, 8)),
        "end_to_end_id": pl.format("E2E{}", _digits(i, 15)),
        "uetr": pl.format(
            "{}-{}-4{}-8{}-{}", _digits((i * 2_654_435_761) % 10**8, 8), _digits(i % 10**4, 4), _digits((i * 7) % 10**3, 3),
            _digits((i * 13) % 10**3, 3), _digits((i * 48_271) % 10**12, 12),
        ),
        "ordering_name": pl.format("ORDERING PARTY {}", (i * 7) % 50_000),
        "beneficiary_name": pl.format("BENEFICIARY {} LTD", (i * 13) % 80_000),
        "beneficiary_type": _pick(i % 3, PARTY_TYPES),
        "mandate_id": pl.format("MND{}", _digits(i % 250_000, 8)),
        "cost_code": pl.format("CC{}", _digits(i % 300, 4)),
        "tax_code": _pick(i % 4, TAX_CODES),
        "is_urgent": pl.when(i % 10 == 0).then(pl.lit("true")).otherwise(pl.lit("false")),
        "is_recurring": pl.when(i % 6 == 0).then(pl.lit("true")).otherwise(pl.lit("false")),
        "risk_score": pl.format("{}.{}", i % 100, _digits((i * 7) % 100, 2)),
        "source_system": _pick(i % 4, SOURCES),
        "file_name": pl.format("payments_{}.dat", i // 100_000),
        "operator_id": pl.format("OP{}", _digits(i % 500, 4)),
        "comment": pl.when(i % 9 == 0).then(pl.lit("manual review")).otherwise(pl.lit("")),
    }
    numbers = pl.select(pl.int_range(start, end, dtype=pl.Int64).alias("i"))
    return numbers.select([value.alias(name) for name, value in columns.items()])


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Make the files from the command line and say what was written."""
    parser = argparse.ArgumentParser(description="Make the input files of the payments scenario.")
    parser.add_argument("--rows", type=int, default=100_000, help="How many payments to write (default 100000).")
    parser.add_argument("--out", default="data", help="The folder to write into (default: data).")
    args = parser.parse_args(argv)
    if args.rows < 1:
        parser.error("--rows must be at least 1")
    folder = Path(args.out)
    generate(folder, args.rows)
    print(f"{args.rows:,} payments written to {folder}/")
    for path in sorted(folder.glob("*.csv")):
        print(f"  {path.name:14} {path.stat().st_size / 1e6:10.1f} MB")
    return 0


def _digits(number: pl.Expr, width: int) -> pl.Expr:
    return number.cast(pl.String).str.zfill(width)


def _pick(index: pl.Expr, values: Sequence[str]) -> pl.Expr:
    """The value at a place in a short list."""
    places: List[int] = list(range(len(values)))
    return index.replace_strict(places, list(values), return_dtype=pl.String)


if __name__ == "__main__":
    sys.exit(main())
