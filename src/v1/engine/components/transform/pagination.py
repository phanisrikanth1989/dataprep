"""Pagination component - statement pagination with a configurable ASCENDING sort.

Talend equivalent: tPagination. Key characteristics:

  * Rows are sorted by ``sort_columns`` -- a list of column names compared as
    PLAIN STRINGS, ascending. There is no ``int()`` cast on the account, so
    accounts order lexically ("10" before "2").
  * The debit/credit flag column (``dc_flag_column``) is NOT a sort key. It is
    used only to split amounts into debit / credit during aggregation.
  * The ``main`` flow is NOT aggregated -- it keeps EVERY input row (1:1 with
    the input) and broadcasts each row's PAGE-level values onto it. So every
    row of a page carries that page's ``AMT_D`` / ``AMT_C`` totals and the
    computed opening / closing balance (``OPBAL`` / ``CLBAL`` are overwritten
    with the carried page open/close).

The logic runs in three passes:

1. Paginate + split -- stable-sort by ``sort_columns`` (string ascending);
   assign a page number that increments every ``page_size`` rows *within* an
   account.
2. Aggregate per page -- group by ``(account, page)``; ``SUM`` of debit / credit
   (split by the D/C flag) and ``MIN`` of opening balance.
3. Running balance -- walk pages in ``(account, page)`` order; reset the running
   balance to the page opening balance on account change or ``page == 1``;
   ``closing = running - debit + credit`` and carry ``closing`` forward. The
   resulting per-page values are then broadcast back onto every detail row.

Output flows:
    main    -- every input row (sorted, page assigned) + its page's AMT_D/AMT_C
               and the computed OPBAL/CLBAL (page values repeat across the page).
    detail  -- every input row (sorted) with only the page number filled; the
               raw OPBAL passes through and no AMT_D/AMT_C/closing is computed.

Optional derived columns on the main flow (all config-gated, off by default):
    * absolute_balance -- emit OPBAL/CLBAL as absolute values.
    * opening_sign_column / closing_sign_column -- write the D/C sign of the
      SIGNED balance (negative -> debit_flag_value, else credit_flag_value),
      derived before any absolute conversion.
    * multipage_column -- write multipage_value when the account spans more than
      one page, else multipage_single_value.

Config keys (all optional; defaults match the original hardcoded names):
    page_size               -- rows per page per account (int, default 10000)
    sort_columns            -- ascending sort keys, string compare
                               (list[str], default [account_column])
    account_column          -- grouping / account key (default "SUBACC")
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
    absolute_balance        -- abs OPBAL/CLBAL on the main flow (bool, default False)
    opening_sign_column     -- column for the opening-balance D/C sign (default "")
    closing_sign_column     -- column for the closing-balance D/C sign (default "")
    multipage_column        -- column for the multi-page flag (default "")
    multipage_value         -- value when account spans >1 page (default "M")
    multipage_single_value  -- value when account fits in one page (default "")
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

# Optional derived-column config keys -- may be empty ("" = feature off), so they
# are validated as plain strings rather than non-empty names.
_OPTIONAL_NAME_KEYS = (
    "opening_sign_column",
    "closing_sign_column",
    "multipage_column",
    "multipage_value",
    "multipage_single_value",
)


@REGISTRY.register("Pagination", "tPagination")
class Pagination(BaseComponent):
    """Paginate statement rows using a configurable ascending multi-column sort."""

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
        if "sort_columns" in self.config:
            sort_columns = self.config["sort_columns"]
            if not isinstance(sort_columns, list) or not sort_columns:
                raise ConfigurationError(
                    f"[{self.id}] 'sort_columns' must be a non-empty list, got {sort_columns!r}"
                )
            for col in sort_columns:
                if not isinstance(col, str) or not col:
                    raise ConfigurationError(
                        f"[{self.id}] 'sort_columns' entries must be non-empty strings, "
                        f"got {col!r}"
                    )
        for key in _NAME_KEYS:
            if key in self.config:
                value = self.config[key]
                if not isinstance(value, str) or not value:
                    raise ConfigurationError(
                        f"[{self.id}] '{key}' must be a non-empty string, got {value!r}"
                    )
        if "absolute_balance" in self.config and not isinstance(
            self.config["absolute_balance"], bool
        ):
            raise ConfigurationError(
                f"[{self.id}] 'absolute_balance' must be a bool, "
                f"got {self.config['absolute_balance']!r}"
            )
        for key in _OPTIONAL_NAME_KEYS:
            if key in self.config and not isinstance(self.config[key], str):
                raise ConfigurationError(
                    f"[{self.id}] '{key}' must be a string, got {self.config[key]!r}"
                )

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------
    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Paginate; broadcast per-page balances onto every row. main + detail."""
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
        sort_columns = self.config.get("sort_columns") or [account_col]
        absolute_balance = self.config.get("absolute_balance", False)
        opening_sign_col = self.config.get("opening_sign_column", "")
        closing_sign_col = self.config.get("closing_sign_column", "")
        multipage_col = self.config.get("multipage_column", "")
        multipage_value = self.config.get("multipage_value", "M")
        multipage_single_value = self.config.get("multipage_single_value", "")

        for required in (account_col, flag_col, amount_col):
            if required not in input_data.columns:
                raise ConfigurationError(
                    f"[{self.id}] Required column '{required}' not present in input data"
                )
        for sort_col in sort_columns:
            if sort_col not in input_data.columns:
                raise ConfigurationError(
                    f"[{self.id}] Sort column '{sort_col}' not present in input data"
                )

        logger.info(
            f"[{self.id}] Paginating {len(input_data)} rows "
            f"(page_size={page_size}, account='{account_col}', sort={sort_columns})"
        )

        # ---- Stage 1: sort + page number + detail flow ----
        df, page = self._stage1_sort_and_paginate(
            input_data, sort_columns, account_col, page_size
        )
        detail_df = df.reset_index(drop=True)
        detail_df[page_col] = page.to_numpy()

        # ---- Stage 2: aggregate per (account, page) ----
        groups = self._stage2_aggregate(
            df, page, account_col, flag_col, amount_col, opening_col,
            debit_flag, credit_flag, null_token,
        )

        # ---- Stage 3: running balance -> per-page values ----
        page_values = self._compute_page_balances(
            groups, account_col, opening_col, closing_col, debit_col, credit_col,
        )

        # ---- Optional derived columns (abs balance / sign / multi-page flag) ----
        page_values = self._apply_derived_columns(
            page_values, opening_col, closing_col, debit_flag, credit_flag,
            absolute_balance, opening_sign_col, closing_sign_col,
            multipage_col, multipage_value, multipage_single_value,
        )

        # ---- Broadcast page values onto every detail row -> main flow ----
        main_df = self._broadcast_page_values(detail_df, page_values, account_col, page_col)

        self._update_stats(rows_read=len(input_data), rows_ok=len(main_df), rows_reject=0)
        logger.info(
            f"[{self.id}] Produced {len(main_df)} main rows (1:1 with input), "
            f"{len(detail_df)} detail rows"
        )
        return {"main": main_df, "detail": detail_df}

    # ------------------------------------------------------------------
    # Stage helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _stage1_sort_and_paginate(
        input_data: pd.DataFrame, sort_columns: List[str], account_col: str, page_size: int
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Stable-sort by sort_columns (string ascending); compute per-account page."""
        df = input_data.copy()
        # Compare every sort key as a plain string -- no numeric cast on the account.
        sort_keys = {f"__pgs_sort_{i}__": df[col].map(lambda v: str(v))
                     for i, col in enumerate(sort_columns)}
        for name, series in sort_keys.items():
            df[name] = series
        df = df.sort_values(
            by=list(sort_keys.keys()), kind="stable"
        ).reset_index(drop=True)
        df = df.drop(columns=list(sort_keys.keys()))
        cumcount = df.groupby(account_col, sort=False).cumcount()
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

    def _compute_page_balances(
        self, groups: Dict[tuple, Dict[str, Any]],
        account_col: str, opening_col: str, closing_col: str,
        debit_col: str, credit_col: str,
    ) -> Dict[tuple, Dict[str, str]]:
        """Walk pages in (account, page) order; return per-page formatted values.

        Account is ordered as a plain string (ascending) to match the stage-1 sort.
        The running balance resets on account change or page 1 and carries forward.
        """
        sorted_keys = sorted(groups.keys(), key=lambda k: (k[0], k[1]))

        page_values: Dict[tuple, Dict[str, str]] = {}
        prev_acc: Optional[str] = None
        running_bal = _DECIMAL_ZERO

        for acct_str, pg in sorted_keys:
            grp = groups[(acct_str, pg)]
            min_opbal = grp["min_opbal"] if grp["min_opbal"] is not None else _DECIMAL_ZERO

            amt_d_str = self._fmt_amount(grp["sum_d"])
            amt_c_str = self._fmt_amount(grp["sum_c"])
            opbal_str = self._fmt_opbal(min_opbal)

            op_clean = opbal_str.strip()
            input_op_bal = Decimal(op_clean) if op_clean else _DECIMAL_ZERO
            if prev_acc is None or acct_str != prev_acc or pg == 1:
                running_bal = input_op_bal
            page_op_bal = running_bal

            sum_d = Decimal(amt_d_str) if amt_d_str.strip() else _DECIMAL_ZERO
            sum_c = Decimal(amt_c_str) if amt_c_str.strip() else _DECIMAL_ZERO
            cl_bal = running_bal - sum_d + sum_c
            running_bal = cl_bal
            prev_acc = acct_str

            page_values[(acct_str, pg)] = {
                debit_col: amt_d_str,
                credit_col: amt_c_str,
                opening_col: f"{page_op_bal}",
                closing_col: f"{cl_bal}",
            }
        return page_values

    def _apply_derived_columns(
        self, page_values: Dict[tuple, Dict[str, str]],
        opening_col: str, closing_col: str, debit_flag: str, credit_flag: str,
        absolute_balance: bool, opening_sign_col: str, closing_sign_col: str,
        multipage_col: str, multipage_value: str, multipage_single_value: str,
    ) -> Dict[tuple, Dict[str, str]]:
        """Augment each page's value dict with optional derived columns.

        All features are config-gated (off by default). Signs are taken from the
        SIGNED balance before any absolute conversion; ``multipage`` reflects
        whether the account spans more than one page.
        """
        if not (absolute_balance or opening_sign_col or closing_sign_col or multipage_col):
            return page_values

        acct_pages: Dict[str, set] = {}
        for acct, pg in page_values:
            acct_pages.setdefault(acct, set()).add(pg)

        for (acct, pg), vals in page_values.items():
            ob = self._parse_decimal(vals[opening_col])
            cb = self._parse_decimal(vals[closing_col])
            if opening_sign_col:
                vals[opening_sign_col] = debit_flag if ob < 0 else credit_flag
            if closing_sign_col:
                vals[closing_sign_col] = debit_flag if cb < 0 else credit_flag
            if absolute_balance:
                vals[opening_col] = f"{abs(ob)}"
                vals[closing_col] = f"{abs(cb)}"
            if multipage_col:
                vals[multipage_col] = (
                    multipage_value if len(acct_pages[acct]) > 1 else multipage_single_value
                )
        return page_values

    @staticmethod
    def _broadcast_page_values(
        detail_df: pd.DataFrame, page_values: Dict[tuple, Dict[str, str]],
        account_col: str, page_col: str,
    ) -> pd.DataFrame:
        """Stamp each row with its page's values (main flow, 1:1 with input).

        New columns (AMT_D / AMT_C and any derived columns) are appended; columns
        that already exist (OPBAL / CLBAL / sign / type) are overwritten in place.
        Page values repeat across all rows of a page.
        """
        main_df = detail_df.copy()
        acct_vals = detail_df[account_col].tolist()
        page_vals = detail_df[page_col].tolist()

        # Stamp the union of keys present across the per-page dicts (stable order).
        target_cols: List[str] = []
        seen = set()
        for vals in page_values.values():
            for col in vals:
                if col not in seen:
                    seen.add(col)
                    target_cols.append(col)

        collected: Dict[str, List[str]] = {col: [] for col in target_cols}
        for i in range(len(detail_df)):
            pv = page_values[(str(acct_vals[i]), int(page_vals[i]))]
            for col in target_cols:
                collected[col].append(pv.get(col, ""))
        for col in target_cols:
            main_df[col] = collected[col]
        return main_df

    # ------------------------------------------------------------------
    # Pure utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_decimal(text: str) -> Decimal:
        """Parse a formatted balance string back to Decimal (blank -> 0)."""
        stripped = str(text).strip()
        return Decimal(stripped) if stripped else _DECIMAL_ZERO

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
