"""Pagination component - statement pagination with per-page balance carry-forward.

Faithful in-memory port of a standalone bank-statement script. Operates on the
input DataFrame and emits two output flows:

- ``main``   : one row per (account, page) with summed debits/credits and the
               opening / closing balance carried forward across pages.
- ``detail`` : every input row, in sorted order, with the page number assigned.

The logic runs in three passes (mirroring the original three temp-file passes):

1. Paginate + split -- sort rows by ``(int(account), dc_flag)``; assign a page
   number that increments every ``page_size`` rows *within* an account; split the
   amount into debit / credit columns by the D/C flag.
2. Aggregate per page -- group by ``(account, page)``; compute ``SUM`` of debit /
   credit and ``MIN`` of opening balance.
3. Running balance -- walk pages in ``(account, page)`` order; reset the running
   balance to the page opening balance on account change or ``page == 1``;
   ``closing = running - debit + credit`` and carry ``closing`` forward.

All money is handled as :class:`decimal.Decimal` and output columns stay string
dtype, preserving the original's ``0 -> "0"`` formatting quirk and two-decimal
rounding exactly (no float coercion).

Config keys (all optional, defaults match the original hardcoded names):
    page_size               -- rows per page per account (int, default 10000)
    account_column          -- grouping / sort / account key (default "SUBACC")
    dc_flag_column          -- debit/credit flag column (default "IDRORCR")
    amount_column           -- source amount column (default "IAMOUNT")
    page_column             -- page-number output column (default "STMTPG")
    opening_balance_column  -- opening balance column (default "OPBAL")
    closing_balance_column  -- closing balance output column (default "CLBAL")
    debit_column            -- derived debit column (default "AMT_D")
    credit_column           -- derived credit column (default "AMT_C")
    debit_flag_value        -- flag value meaning debit (default "D")
    credit_flag_value       -- flag value meaning credit (default "C")
    null_token              -- amount value treated as empty (default "NULL")
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)

_DECIMAL_ZERO = Decimal(0)
_ACCT_SORT_KEY = "__pagination_acct_int__"

# Config keys that hold a column / token name -- must resolve to a non-empty str.
_NAME_KEYS = (
    "account_column",
    "dc_flag_column",
    "amount_column",
    "page_column",
    "opening_balance_column",
    "closing_balance_column",
    "debit_column",
    "credit_column",
    "debit_flag_value",
    "credit_flag_value",
    "null_token",
)


@REGISTRY.register("Pagination", "tPagination")
class Pagination(BaseComponent):
    """Paginate statement rows and carry opening/closing balances across pages."""

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_config(self) -> None:
        """Validate structural config (key types only)."""
        page_size = self.config.get("page_size", 10000)
        if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size <= 0:
            raise ConfigurationError(
                f"[{self.id}] 'page_size' must be a positive integer, got {page_size!r}"
            )
        for key in _NAME_KEYS:
            if key in self.config:
                value = self.config[key]
                if not isinstance(value, str) or not value:
                    raise ConfigurationError(
                        f"[{self.id}] '{key}' must be a non-empty string, got {value!r}"
                    )

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------
    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Paginate and aggregate; return main (summary) and detail flows."""
        if input_data is None or input_data.empty:
            logger.info(f"[{self.id}] No input data; emitting empty main/detail flows")
            return {"main": input_data, "detail": input_data}

        # ---- Resolve config ----
        page_size = self.config.get("page_size", 10000)
        account_col = self.config.get("account_column", "SUBACC")
        flag_col = self.config.get("dc_flag_column", "IDRORCR")
        amount_col = self.config.get("amount_column", "IAMOUNT")
        page_col = self.config.get("page_column", "STMTPG")
        opening_col = self.config.get("opening_balance_column", "OPBAL")
        closing_col = self.config.get("closing_balance_column", "CLBAL")
        debit_col = self.config.get("debit_column", "AMT_D")
        credit_col = self.config.get("credit_column", "AMT_C")
        debit_flag = self.config.get("debit_flag_value", "D")
        credit_flag = self.config.get("credit_flag_value", "C")
        null_token = self.config.get("null_token", "NULL")

        for required in (account_col, flag_col, amount_col):
            if required not in input_data.columns:
                raise ConfigurationError(
                    f"[{self.id}] Required column '{required}' not present in input data"
                )

        logger.info(
            f"[{self.id}] Paginating {len(input_data)} rows "
            f"(page_size={page_size}, account='{account_col}')"
        )

        # ---- Stage 1: sort + page number + detail flow ----
        df, page = self._stage1_sort_and_paginate(input_data, account_col, flag_col, page_size)
        detail_df = df.drop(columns=[_ACCT_SORT_KEY]).reset_index(drop=True)
        detail_df[page_col] = page.to_numpy()

        # ---- Stage 2: aggregate per (account, page) ----
        groups = self._stage2_aggregate(
            df, page, account_col, flag_col, amount_col, opening_col,
            debit_flag, credit_flag, null_token,
        )

        # ---- Stage 3: running balance carry-forward ----
        summary_columns = self._build_summary_columns(
            input_data, debit_col, credit_col, account_col, page_col, opening_col, closing_col
        )
        summary_df = self._stage3_running_balance(
            groups, summary_columns,
            account_col, page_col, opening_col, closing_col, debit_col, credit_col,
        )

        self._update_stats(rows_read=len(input_data), rows_ok=len(summary_df), rows_reject=0)
        logger.info(
            f"[{self.id}] Produced {len(summary_df)} summary rows, "
            f"{len(detail_df)} detail rows"
        )
        return {"main": summary_df, "detail": detail_df}

    # ------------------------------------------------------------------
    # Stage helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _stage1_sort_and_paginate(
        input_data: pd.DataFrame, account_col: str, flag_col: str, page_size: int
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Stable-sort by (int(account), flag) and compute the per-account page."""
        df = input_data.copy()
        df[_ACCT_SORT_KEY] = df[account_col].map(lambda v: int(str(v).strip()))
        df = df.sort_values(
            by=[_ACCT_SORT_KEY, flag_col], kind="stable"
        ).reset_index(drop=True)
        cumcount = df.groupby(_ACCT_SORT_KEY, sort=False).cumcount()
        page = (cumcount // page_size) + 1
        return df, page

    def _stage2_aggregate(
        self, df: pd.DataFrame, page: pd.Series, account_col: str, flag_col: str,
        amount_col: str, opening_col: str, debit_flag: str, credit_flag: str,
        null_token: str,
    ) -> Dict[tuple, Dict[str, Any]]:
        """Group rows by (account, page); sum debit/credit and min opening balance."""
        acct_vals = df[account_col].tolist()
        flag_vals = df[flag_col].tolist()
        amount_vals = df[amount_col].tolist()
        page_vals = page.tolist()
        opbal_vals = (
            df[opening_col].tolist() if opening_col in df.columns else [""] * len(df)
        )

        groups: Dict[tuple, Dict[str, Any]] = {}
        for i in range(len(df)):
            key = (str(acct_vals[i]), int(page_vals[i]))
            amt = self._to_decimal_amount(amount_vals[i], null_token)
            amt_d = _DECIMAL_ZERO
            amt_c = _DECIMAL_ZERO
            if amt is not None:
                if flag_vals[i] == debit_flag:
                    amt_d = amt
                elif flag_vals[i] == credit_flag:
                    amt_c = amt

            grp = groups.get(key)
            if grp is None:
                grp = {"sum_d": _DECIMAL_ZERO, "sum_c": _DECIMAL_ZERO, "min_opbal": None}
                groups[key] = grp
            grp["sum_d"] += amt_d
            grp["sum_c"] += amt_c

            ob_str = str(opbal_vals[i]).strip()
            if ob_str:
                ob_dec = Decimal(ob_str)
                if grp["min_opbal"] is None or ob_dec < grp["min_opbal"]:
                    grp["min_opbal"] = ob_dec
        return groups

    def _stage3_running_balance(
        self, groups: Dict[tuple, Dict[str, Any]], summary_columns: List[str],
        account_col: str, page_col: str, opening_col: str, closing_col: str,
        debit_col: str, credit_col: str,
    ) -> pd.DataFrame:
        """Walk pages in (account, page) order, carrying the running balance."""
        sorted_keys = sorted(groups.keys(), key=lambda k: (int(k[0]), k[1]))

        summary_rows: List[Dict[str, Any]] = []
        prev_acc: Optional[int] = None
        running_bal = _DECIMAL_ZERO

        for acct_str, pg in sorted_keys:
            grp = groups[(acct_str, pg)]
            min_opbal = grp["min_opbal"] if grp["min_opbal"] is not None else _DECIMAL_ZERO

            # Stage-2 formatting (rounds debit/credit to 2dp before stage-3 reuse).
            amt_d_str = self._fmt_amount(grp["sum_d"])
            amt_c_str = self._fmt_amount(grp["sum_c"])
            opbal_str = self._fmt_opbal(min_opbal)

            curr_acc = int(acct_str)
            op_clean = opbal_str.strip()
            input_op_bal = Decimal(op_clean) if op_clean else _DECIMAL_ZERO
            if prev_acc is None or curr_acc != prev_acc or pg == 1:
                running_bal = input_op_bal
            page_op_bal = running_bal

            sum_d = Decimal(amt_d_str) if amt_d_str.strip() else _DECIMAL_ZERO
            sum_c = Decimal(amt_c_str) if amt_c_str.strip() else _DECIMAL_ZERO
            cl_bal = running_bal - sum_d + sum_c
            running_bal = cl_bal
            prev_acc = curr_acc

            row = {col: "" for col in summary_columns}
            row[account_col] = acct_str
            row[page_col] = str(pg)
            row[debit_col] = amt_d_str
            row[credit_col] = amt_c_str
            row[opening_col] = f"{page_op_bal}"
            row[closing_col] = f"{cl_bal}"
            summary_rows.append(row)

        return pd.DataFrame(summary_rows, columns=summary_columns)

    # ------------------------------------------------------------------
    # Pure utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _build_summary_columns(
        input_data: pd.DataFrame, debit_col: str, credit_col: str,
        account_col: str, page_col: str, opening_col: str, closing_col: str,
    ) -> List[str]:
        """Summary schema = input columns + AMT_D/AMT_C, plus any missing role columns."""
        columns = list(input_data.columns)
        for col in (debit_col, credit_col, account_col, page_col, opening_col, closing_col):
            if col not in columns:
                columns.append(col)
        return columns

    @staticmethod
    def _to_decimal_amount(raw: Any, null_token: str) -> Optional[Decimal]:
        """Parse an amount cell to Decimal, or None for null/blank values."""
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return None
        if raw == null_token:
            return None
        text = str(raw).strip()
        if not text:
            return None
        return Decimal(text)

    @staticmethod
    def _fmt_amount(value: Decimal) -> str:
        """Format a summed amount: exact zero -> '0', else two decimals."""
        return "0" if value == 0 else f"{value:.2f}"

    @staticmethod
    def _fmt_opbal(value: Decimal) -> str:
        """Format an opening balance: exact zero -> '0', else its plain string."""
        return "0" if value == 0 else str(value)
