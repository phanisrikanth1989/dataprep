"""Python-Java Bridge using Py4J and Apache Arrow.

Schema-driven DataFrame serialization with automatic context/globalMap
synchronization after every Java call. Zero print() statements -- all
output goes through the logging module.
"""

import calendar
import collections
import datetime
import io
import logging
import math
import os
import subprocess
import threading
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from attr import field
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.ipc as ipc
from py4j.java_gateway import JavaClass, JavaGateway, GatewayParameters
from py4j.protocol import register_input_converter

from .type_mapping import (
    PYTHON_TO_JAVA,
    build_arrow_schema,
    extract_precision_map,
    validate_schema_types,
)

logger = logging.getLogger(__name__)

# Py4J Base64-encodes byte[] arguments and stores the encoded length as a
# signed 32-bit Java int (max ~2.14 GB). Encoded size = ceil(raw / 3) * 4.
# We cap the *raw* Arrow payload at ~1.5 GB so that after Base64 expansion
# (~2.0 GB) we stay safely below the 2 GB int limit and avoid
# java.lang.NegativeArraySizeException at py4j.Base64.decode().
_PY4J_BYTE_ARG_SAFE_LIMIT = 1_500_000_000

# Sentinel used by the D-09 (Plan 05.4-06) reject_mode context-flag wrap:
# distinguishes "key not present prior to this call" from "key explicitly
# present and set to None" so the wrap can restore exactly the prior state.
_MISSING = object()


def _coerce_global_map_for_java(d: dict[str, Any]) -> dict[str, Any]:
    """Coerce string values representing numbers to Python int/float.

    Py4J maps Python ``int`` -> Java ``Long`` and ``float`` -> Java ``Double``,
    but ``str`` -> Java ``String``.  GlobalMap values stored from Python config
    (e.g. tSetGlobalVar reading ``"5000"`` from JSON) arrive as strings.
    Groovy explicit casts such as ``(Integer) globalMap.get("key")`` then fail
    with ``GroovyCastException``.  Coercing here ensures Java receives typed
    numeric values without changing what Python components observe in GlobalMap.
    """
    result: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str):
            try:
                result[k] = int(v)
                continue
            except ValueError:
                pass
            try:
                result[k] = float(v)
                continue
            except ValueError:
                pass
        result[k] = v
    return result


def _coerce_to_decimal_or_none(v: Any) -> Optional[Decimal]:
    """Normalize a single cell value for a ``Decimal``-typed Arrow column.

    PyArrow's ``decimal128`` builder only accepts ``decimal.Decimal`` (or
    ``None`` for null). Real-world DataFrames feeding the bridge may carry:

    - Python ``Decimal`` -- pass through.
    - ``None`` / ``pd.NA`` / ``float('nan')`` / ``np.nan`` -- become ``None``.
    - ``""`` or whitespace-only strings -- become ``None`` (Talend null
      convention for delimited files).
    - ``int`` / ``float`` / numpy numeric scalars -- happens when the CSV
      reader infers ``float64`` for a ``Decimal``-typed column, or when
      ``pd.merge(how="left")`` promotes unmatched rows to ``NaN`` and flips
      the column dtype. Convert via ``str(v)`` to avoid binary-float drift.
    - Numeric strings (e.g. ``"123.45"``) -- parsed via ``Decimal``.

    Anything else falls back to ``Decimal(str(v))``; if that fails the value
    is treated as null rather than crashing the entire batch serialization.
    """
    # Fast path: already a Decimal.
    if isinstance(v, Decimal):
        return v
    # Null-likes. ``v is pd.NA`` must come before any comparison that would
    # raise on pd.NA (e.g. ``v != v`` works, but be explicit).
    if v is None or v is pd.NA:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return Decimal(str(v))
    if isinstance(v, (int, np.integer)):
        return Decimal(int(v))
    if isinstance(v, np.floating):
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return Decimal(str(f))
    if isinstance(v, str):
        s = v.strip()
        if s == "":
            return None
        try:
            return Decimal(s)
        except InvalidOperation:
            return None
#Unknown types -- best effort string conversion else null.
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None


# Python logging level -> Java JUL level string
_PYTHON_TO_JAVA_LOG_LEVEL: dict[int, str] = {
    logging.DEBUG: "FINE",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "SEVERE",
    logging.CRITICAL: "SEVERE",
}


# ----------------------------------------------------------------------
# Py4J input converters for datetime.date / datetime.datetime
# ----------------------------------------------------------------------
#
# Pattern reference: pyspark.sql.types DatetimeConverter / DateConverter
# (see Phase 05.5 RESEARCH.md L69-97). Registration is process-global per
# py4j docs -- one register_input_converter call at JavaBridge.start()
# covers every subsequent gateway client started in the same Python
# process. Subclass (DatetimeConverter) is registered FIRST so it takes
# precedence over DateConverter for datetime.datetime instances.

class DatetimeConverter:
    """Py4J input converter: datetime.datetime -> java.util.Date.

    Registered before DateConverter so the subclass branch wins for
    datetime instances. Aware datetimes use UTC; naive datetimes use
    the host's local timezone via time.mktime (mirrors PySpark).

    Uses ``JavaClass("java.util.Date", gateway_client)`` rather than
    ``gateway_client.jvm.java.util.Date`` because Py4J passes a
    ``GatewayClient`` (no ``.jvm`` attribute) to converter.convert().
    The ``JavaClass`` API works with the low-level GatewayClient directly.
    """

    def can_convert(self, obj):
        return isinstance(obj, datetime.datetime)

    def convert(self, obj, gateway_client):
        if obj.tzinfo is not None:
            seconds = calendar.timegm(obj.utctimetuple())
        else:
            seconds = time.mktime(obj.timetuple())
        millis = int(seconds * 1000 + obj.microsecond // 1000)
        return JavaClass("java.util.Date", gateway_client)(millis)


class DateConverter:
    """Py4J input converter: datetime.date -> java.util.Date at midnight UTC.

    Excludes datetime.datetime (handled by DatetimeConverter).

    Uses ``JavaClass("java.util.Date", gateway_client)`` rather than
    ``gateway_client.jvm.java.util.Date`` because Py4J passes a
    ``GatewayClient`` (no ``.jvm`` attribute) to converter.convert().
    The ``JavaClass`` API works with the low-level GatewayClient directly.
    """

    def can_convert(self, obj):
        return (
            isinstance(obj, datetime.date)
            and not isinstance(obj, datetime.datetime)
        )

    def convert(self, obj, gateway_client):
        seconds = calendar.timegm(obj.timetuple())
        return JavaClass("java.util.Date", gateway_client)(int(seconds * 1000))


class JavaBridge:
    """Bridge between Python and Java using Py4J with Arrow for data transfer.

    All public methods that modify Java state automatically synchronize
    context and globalMap back to Python via ``_sync_from_java()``.

    Arrow schemas are built from explicit type mappings (via type_mapping.py),
    never inferred from DataFrame data.
    """

    # Class-level flag -- Py4J input-converter registration is process-global,
    # so we register exactly once across all JavaBridge instances in the same
    # Python process. Flipped to True after the first successful start().
    _converters_registered: bool = False

    def __init__(self) -> None:
        """Initialize the bridge. Call ``start()`` to launch the JVM."""
        self.gateway: Optional[JavaGateway] = None
        self.java_bridge: Any = None
        self.process: Optional[subprocess.Popen] = None
        self.context: dict[str, Any] = {}
        self.global_map: dict[str, Any] = {}
        self._started: bool = False
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_buffer: collections.deque = collections.deque(maxlen=200)
        self._stderr_lock: threading.Lock = threading.Lock()
        self._stderr_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, port: int | None = None, routine_jars: list[str] | None = None) -> None:
        """Start the JVM subprocess and connect via Py4J.

        Uses retry with exponential backoff (max 5 attempts starting at 0.5s).
        Captures Java stderr for diagnostics.

        Args:
            port: Py4J gateway port. Defaults to 25333 if not specified.
            routine_jars: Optional list of JAR file paths or directories to add
                to the JVM classpath. Directories are scanned for *.jar files.

        Raises:
            JavaBridgeError: If the JVM fails to start or connect.
        """
        from src.v1.engine.exceptions import JavaBridgeError

        if port is None:
            port = 25333

        logger.info("[OK] Starting Java gateway on port %d", port)

        jar_path = self._find_jar_path()

        # Build classpath from bridge JAR plus optional routine JARs
        classpath_entries = [jar_path]
        if routine_jars:
            for jar in routine_jars:
                jar_resolved = str(Path(jar).resolve())
                if os.path.isfile(jar_resolved):
                    classpath_entries.append(jar_resolved)
                    logger.info("[OK] Added routine JAR to classpath: %s", jar_resolved)
                elif os.path.isdir(jar_resolved):
                    # Directory mode: add all .jar files within
                    dir_jars = sorted(Path(jar_resolved).glob("*.jar"))
                    for dj in dir_jars:
                        classpath_entries.append(str(dj))
                        logger.info("[OK] Added routine JAR to classpath: %s", dj)
                    if not dir_jars:
                        logger.warning("[WARN] No JAR files found in directory: %s", jar_resolved)
                else:
                    logger.warning("[WARN] Routine JAR path not found: %s", jar)
        classpath = os.pathsep.join(classpath_entries)

        cmd = [
            "java",
            "--add-opens=java.base/java.nio=ALL-UNNAMED",
            "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED",
            "--add-opens=java.base/java.lang=ALL-UNNAMED",
            "-Duser.timezone=UTC",
            f"-Dpy4j.port={port}",
            "-cp", classpath,
            "com.citi.gru.etl.JavaBridge",
        ]

        java_dir = os.path.dirname(jar_path)

        self.process = subprocess.Popen(
            cmd,
            cwd=java_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )

        # Forward JVM stdout to Python logger so System.out.println() output
        # from user Java/Groovy code is visible in the engine log.
        self._stdout_thread = threading.Thread(
            target=self._drain_java_stdout,
            daemon=True,
            name="java-stdout-forwarder",
        )
        self._stdout_thread.start()

        self._stderr_thread = threading.Thread(
            target=self._drain_java_stderr,
            daemon=True,
            name="java-stderr-drainer",
        )
        self._stderr_thread.start()

        # Retry connection with exponential backoff
        max_attempts = 5
        delay = 0.5

        for attempt in range(1, max_attempts + 1):
            time.sleep(delay)

            if self.process.poll() is not None:
                java_stderr = self._capture_java_stderr()
                raise JavaBridgeError(
                    f"Java process exited during startup (exit code {self.process.returncode})"
                    f"\n--- Java stderr (last 20 lines) ---\n{java_stderr}"
                )

            try:
                self.gateway = JavaGateway(
                    gateway_parameters=GatewayParameters(
                        port=port,
                        auto_convert=True,
                    )
                )
                self.java_bridge = self.gateway.entry_point
                # Test connection
                _ = self.java_bridge.getContext()

                # Register Py4J input converters for datetime.date /
                # datetime.datetime exactly once per Python process. Order
                # matters: DatetimeConverter (subclass match) is registered
                # FIRST so it wins over DateConverter for datetime instances.
                if not JavaBridge._converters_registered:
                    register_input_converter(DatetimeConverter())
                    register_input_converter(DateConverter())
                    JavaBridge._converters_registered = True
                    logger.info(
                        "[OK] Registered Py4J date/datetime input converters"
                    )

                self._started = True

                # Sync log level
                java_level = _PYTHON_TO_JAVA_LOG_LEVEL.get(
                    logger.getEffectiveLevel(), "INFO"
                )
                try:
                    self.java_bridge.setLogLevel(java_level)
                except Exception:
                    logger.debug("setLogLevel not available on Java side -- skipping")

                logger.info(
                    "[OK] Java gateway started on port %d (attempt %d/%d)",
                    port,
                    attempt,
                    max_attempts,
                )
                return

            except Exception:
                if attempt < max_attempts:
                    logger.debug(
                        "Connection attempt %d/%d failed, retrying in %.1fs",
                        attempt,
                        max_attempts,
                        delay,
                    )
                    delay *= 2
                else:
                    java_stderr = self._capture_java_stderr()
                    if self.process:
                        self.process.kill()
                    raise JavaBridgeError(
                        f"Timeout connecting to Java gateway on port {port} "
                        f"after {max_attempts} attempts"
                        f"\n--- Java stderr (last 20 lines) ---\n{java_stderr}"
                    )

    def stop(self) -> None:
        """Shutdown the Py4J gateway and kill the JVM subprocess."""
        if not self._started:
            return

        if self.gateway:
            try:
                self.gateway.shutdown()
            except Exception:
                pass

        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

        self._started = False
        self.gateway = None
        self.java_bridge = None
        self.process = None
        logger.info("[OK] Java gateway stopped")

    # ------------------------------------------------------------------
    # Public API -- Data execution methods
    # ------------------------------------------------------------------

    def execute_java_row(
        self,
        df: pd.DataFrame,
        java_code: str,
        output_schema: dict[str, str],
        input_columns: list[str] | None = None,
        output_columns: list[str] | None = None,
        schema_columns: list[dict] | None = None,
        input_schema: dict[str, str] | None = None,
        chunk_size: int = 50_000,
    ) -> pd.DataFrame:
        """Execute tJavaRow-style code on a DataFrame, chunking across Py4J.

        The DataFrame is split into ``chunk_size`` row ranges and each chunk
        is sent to the Java side as its own Arrow byte[] payload. This
        mirrors the proven pattern in ``execute_compiled_tmap_chunked``
        (line 690) and is REQUIRED to avoid Py4J's signed-int Base64
        length-field overflow.

        - Py4J Base64-encodes byte[] arguments.
        - Encoded length is stored as a Java signed 32-bit int (max ~2.14 GB).
        - Encoded size = ceil(raw / 3) * 4, so raw payload over ~1.5 GB
        (``_PY4J_BYTE_ARG_SAFE_LIMIT``) overflows the int and the Java
        side raises ``java.lang.NegativeArraySizeException`` at
        ``py4j.Base64.decode()``.

        Without chunking, a wide DataFrame with a few hundred thousand
        rows can exceed this limit -- e.g. a 330,936-row, 6 KB/row frame
        serializes to ~2.0 GB and crashes the bridge call.

        Inter-chunk semantics:
            - ``_call_java_with_sync`` runs after every chunk, so any
            ``context`` / ``globalMap`` mutations made by the user's row
            body in chunk N are visible to chunk N+1. This matches the
            tMap chunker's contract.

        Recovery:
            If the Arrow payload pre-flight check finds a chunk over the
            safe limit, the range is split in half and retried. If the
            Java side raises ``NegativeArraySizeException`` (the runtime
            backstop) the same halve-and-retry is applied. A single row
            that is itself too large is unrecoverable and the original
            error is re-raised so the user sees a clear message.

        Args:
            df: Input DataFrame.
            java_code: Java/Groovy code block.
            output_schema: Column name -> Python type string mapping for output.
            input_columns: Input column names (optional).
            output_columns: Output column names (optional).
            schema_columns: Full schema column list for precision extraction.
            input_schema: Optional column -> Python type mapping for input
                columns. Used as the authoritative source for input-side
                Arrow types when a column is NOT present in ``output_schema``
                (Talend parity for tJavaRow input-only columns such as a
                tMap-synthesized ``incremental_value`` int that the row body
                reads but does not re-emit). Without this hint the bridge
                falls back to pandas dtype inference, which silently
                degrades object/float64 NaN-promoted columns to Arrow
                VarChar/Float64 -- breaking ``int x = input_row.col``
                primitive coercion in the row body.
            chunk_size: Rows per chunk (default 50,000). Single-chunk jobs
                (df rows <= chunk_size) make exactly one Java call -- no
                behavior change vs the pre-chunking implementation. Auto
                halves at runtime if a chunk's Arrow payload would
                overflow the Py4J Base64 limit, so this default is a
                safe upper bound and rarely needs tuning per job.

        Returns:
            Output DataFrame (per-chunk results concatenated in original
            row order).
        """
        total_rows = len(df)
        # Diagnostic: log effective chunk_size + frame shape so we can tell
        # whether a caller's chunk_size override actually reached us, and
        # how wide each row is before serialization. Mirrors
        # execute_compiled_tmap_chunked (line 727-741).
        try:
            mem_mb = df.memory_usage(deep=True).sum() / 1e6
        except Exception:
            mem_mb = -1.0
        logger.info(
            "[execute_java_row] rows=%d cols=%d code_len=%d chunk_size=%d "
            "in-memory=%.1f MB (~%.0f KB/row)",
            total_rows,
            len(df.columns),
            len(java_code),
            chunk_size,
            mem_mb,
            (mem_mb * 1000 / max(total_rows, 1)) if mem_mb > 0 else -1,
        )

        # Empty input : short-circuit. the Java side has no rows to process
        # and the chunked output concat below would receive zero frames.
       # Returning an empty DataFrame with the declared output columns
        # matches what _arrow_bytes_to_df would yield for an empty result.
        if total_rows == 0:
            return pd.DataFrame({col: [] for col in output_schema.keys()})

        # Build schema dict ONCE (df-level): chunked Arrow serialization
        # reuses the same schema for every slice -- no per-chunk recomputation.
        schema_dict = self._schema_dict_from_df_and_output(
            df, output_schema, input_schema=input_schema,
        )
        java_output_schema = self._convert_schema_to_java(output_schema)

        # Build the initial list of (start, end) row ranges. Ranges may be
        # split further at runtime if a chunk's Arrow payload would exceed
        # the Py4J Base64 byte[] limit (see _PY4J_BYTE_ARG_SAFE_LIMIT).
        pending_ranges: list[tuple[int, int]] = []
        for chunk_idx in range((total_rows + chunk_size - 1) // chunk_size):
            start_idx = chunk_idx * chunk_size
            end_idx = min(start_idx + chunk_size, total_rows)
            pending_ranges.append((start_idx, end_idx))

        # Per-chunk output frames, accumulated and concatenated at the end
        # in the order they were processed (which equals original row order
        # because pending_ranges is processed FIFO with halve-on-failure
        # inserting halves at the front).
        output_chunks: list[pd.DataFrame] = []
        processed = 0

        while pending_ranges:
            start_idx, end_idx = pending_ranges.pop(0)
            chunk_df = df.iloc[start_idx:end_idx]
            arrow_bytes = self._df_to_arrow_bytes(chunk_df, schema_dict, schema_columns)

            # Pre-flight guard: if the raw Arrow payload alone would overflow
            # Py4J's Base64 length field, split the range in half and retry.
            # Refuse to split below 1 row -- a single row exceeding the limit
            # is unrecoverable and must surface as a clear error.
            if len(arrow_bytes) > _PY4J_BYTE_ARG_SAFE_LIMIT and (end_idx - start_idx) > 1:
                mid = start_idx + (end_idx - start_idx) // 2
                logger.warning(
                    "[execute_java_row] chunk rows %d-%d Arrow size %.2f GB "
                    "exceeds Py4J safe limit %.2f GB; splitting in half",
                    start_idx, end_idx,
                    len(arrow_bytes) / 1e9,
                    _PY4J_BYTE_ARG_SAFE_LIMIT / 1e9,
                )
                pending_ranges.insert(0, (mid, end_idx))
                pending_ranges.insert(0, (start_idx, mid))
                continue

            logger.debug(
                "[execute_java_row] chunk rows %d-%d (%d rows, %.1f MB Arrow)",
                start_idx, end_idx, end_idx - start_idx,
                len(arrow_bytes) / 1e6,
            )

            def _call(ab=arrow_bytes):
                return self.java_bridge.executeJavaRow(
                    ab,
                    java_code,
                    java_output_schema,
                    self.context,
                    _coerce_global_map_for_java(self.global_map),
                )

            try:
                result_bytes = self._call_java_with_sync(_call)
            except Exception as e:
                # Recovery: if Java raised NegativeArraySizeException (or any
                # error mentioning Base64), the row-count heuristic was too
                # optimistic for this chunk's actual byte width. Halve the
                # range and retry, unless we are already at 1 row.
                msg = str(e)
                is_base64_overflow = (
                    "NegativeArraySizeException" in msg
                    or "py4j.Base64" in msg
                )
                if is_base64_overflow and (end_idx - start_idx) > 1:
                    mid = start_idx + (end_idx - start_idx) // 2
                    logger.warning(
                        "[execute_java_row] Py4J Base64 overflow on rows %d-%d; "
                        "halving and retrying",
                        start_idx, end_idx,
                    )
                    pending_ranges.insert(0, (mid, end_idx))
                    pending_ranges.insert(0, (start_idx, mid))
                    continue
                raise

            chunk_output_df = self._arrow_bytes_to_df(result_bytes, output_schema)
            output_chunks.append(chunk_output_df)
            processed += end_idx - start_idx
            logger.debug(
                "[execute_java_row] processed %d / %d rows", processed, total_rows
            )

        # Single-chunk path: avoid an unnecessary concat (the pre-chunking
        # behavior was a single bridge call returning a single DF). For
        # multi-chunk, concat preserves row order because halve-on-failure
        # inserts halves at the front of the queue, so pop(0) processes
        # ranges in start_idx-ascending order.
        if len(output_chunks) == 1:
            return output_chunks[0]
        return pd.concat(output_chunks, ignore_index=True)

    def execute_java_flex(
        self,
        df: pd.DataFrame,
        *,
        script: str,
        output_schema: dict[str, str],
        input_schema: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        """Execute a tJavaFlex Groovy script ONCE over the whole DataFrame.

        Unlike :meth:`execute_java_row`, the entire script runs a single time
        on the Java side: START locals, the row loop, and END all share one
        scope (Talend tJavaFlex parity). The row loop lives inside the Groovy
        body (built by ``java_flex_script.build_script``), so a START variable
        such as ``int totalCount = 0`` persists across rows and into END.

        Single-call only -- this method does NOT chunk. Chunking would split
        the input across separate ``script.run()`` calls and break cross-row
        START/END state, so an over-large payload raises a clear error instead
        (see ``_PY4J_BYTE_ARG_SAFE_LIMIT``).

        Empty input still calls the bridge: START and END must execute exactly
        once even when there are zero rows. An empty DataFrame with the
        declared ``output_schema`` columns is returned in that case (the Java
        side produces a zero-row Arrow batch with those columns).

        Args:
            df: Input DataFrame (one bridge call, no chunking).
            script: Pre-assembled Groovy unit (START + row loop + END).
            output_schema: Output column name -> Python type string mapping.
            input_schema: Optional input column name -> Python type string
                mapping. Used as the authoritative type source when an input
                column is not echoed to ``output_schema`` (same role as in
                :meth:`execute_java_row`), so an upstream ``object``/``float64``
                column is not silently downgraded from its declared ``int``.

        Returns:
            Output DataFrame with the ``output_schema`` columns.

        Raises:
            JavaBridgeError: On any Java-side failure (via
                ``_call_java_with_sync``).
            ValueError: If the serialized Arrow payload exceeds the Py4J
                Base64 byte[] safe limit (single-call cannot be chunked).
        """
        total_rows = len(df)
        logger.debug(
            "[execute_java_flex] rows=%d cols=%d script_len=%d",
            total_rows,
            len(df.columns),
            len(script),
        )

        # The Java side passes ``output_schema`` straight to
        # ``ArrowSerializer.createOutputRootFromData``, which keys off the
        # PYTHON type strings (str/int/float/bool/datetime/Decimal/object) --
        # NOT the Java type names. So forward the Python-string schemas as-is.
        # ``input_schema`` is informational on the Java side (input values
        # come from the Arrow vectors), but keep it in the same form.
        java_output_schema = dict(output_schema)
        java_input_schema = dict(input_schema or {})

        # Build the input schema for Arrow serialization with the same
        # type-resolution precedence as execute_java_row (output > input >
        # pandas inference). Even for empty input we serialize the frame so
        # the Java side sees the declared columns/types.
        schema_dict = self._schema_dict_from_df_and_output(
            df, output_schema, input_schema=input_schema,
        )
        arrow_bytes = self._df_to_arrow_bytes(df, schema_dict)

        # Single-call guard: tJavaFlex cannot be chunked (cross-row START
        # state would break). Refuse an over-large payload with a clear error
        # instead of silently truncating or splitting.
        if len(arrow_bytes) > _PY4J_BYTE_ARG_SAFE_LIMIT:
            raise ValueError(
                f"[execute_java_flex] Arrow payload {len(arrow_bytes) / 1e9:.2f} GB "
                f"exceeds the Py4J safe limit {_PY4J_BYTE_ARG_SAFE_LIMIT / 1e9:.2f} GB. "
                f"tJavaFlex runs as a single bridge call (START/END share one "
                f"scope across all rows) and cannot be chunked."
            )

        def _call():
            return self.java_bridge.executeJavaFlex(
                arrow_bytes,
                script,
                java_output_schema,
                java_input_schema,
                self.context,
                _coerce_global_map_for_java(self.global_map),
            )

        result_bytes = self._call_java_with_sync(_call)
        out_df = self._arrow_bytes_to_df(result_bytes, output_schema)

        # Guarantee the declared output columns even on an empty result so
        # callers always see a stable shape (Java emits a zero-row batch with
        # these columns, but normalize defensively).
        if total_rows == 0 and list(out_df.columns) != list(output_schema.keys()):
            return pd.DataFrame({col: [] for col in output_schema.keys()})
        return out_df

    def execute_one_time_expression(self, expression: str) -> Any:
        """Execute a single Java expression.

        Args:
            expression: Java expression string with context access.

        Returns:
            Expression result value.
        """
        logger.debug("[execute_one_time_expression] expr=%s", expression[:80])

        def _call():
            return self.java_bridge.executeOneTimeExpression(
                expression,
                self.context,
                _coerce_global_map_for_java(self.global_map),
            )

        return self._call_java_with_sync(_call)

    def execute_batch_one_time_expressions(
        self,
        expressions: dict[str, str],
    ) -> dict[str, Any]:
        """Execute multiple Java expressions in batch.

        Uses executeBatchOneTimeExpressionsWithGlobalMap (the only batch method
        with full state access).

        Args:
            expressions: Mapping of param_name -> java_expression.

        Returns:
            Mapping of param_name -> resolved_value. Errors prefixed with {{ERROR}}.
        """
        logger.debug(
            "[execute_batch_one_time_expressions] %d expression(s)", len(expressions)
        )

        def _call():
            return self.java_bridge.executeBatchOneTimeExpressionsWithGlobalMap(
                expressions,
                self.context,
                _coerce_global_map_for_java(self.global_map),
            )

        return self._call_java_with_sync(_call)

    def execute_tmap_preprocessing(
        self,
        df: pd.DataFrame,
        expressions: dict[str, str],
        main_table_name: str,
        lookup_table_names: list[str] | None = None,
        schema: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute tMap preprocessing -- batch evaluate expressions on all rows.

        Args:
            df: Input DataFrame.
            expressions: Mapping of expr_id -> expression_string.
            main_table_name: Main table name for row variable binding.
            lookup_table_names: Lookup table names already joined.
            schema: Column name -> type string mapping for Arrow serialization.

        Returns:
            Mapping of expr_id -> numpy_array of per-row results.
        """
        import numpy as np
        from py4j.java_collections import ListConverter

        logger.debug(
            "[execute_tmap_preprocessing] rows=%d, exprs=%d", len(df), len(expressions)
        )

        schema_dict = schema if schema else self._infer_schema_dict(df)
        arrow_bytes = self._df_to_arrow_bytes(df, schema_dict)

        assert self.gateway is not None
        java_lookup_names = ListConverter().convert(
            lookup_table_names or [], self.gateway._gateway_client
        )

        def _call():
            return self.java_bridge.executeTMapPreprocessing(
                arrow_bytes,
                expressions,
                main_table_name,
                java_lookup_names,
                self.context,
                _coerce_global_map_for_java(self.global_map),
            )

        result_map = self._call_java_with_sync(_call)

        results: dict[str, Any] = {}
        for expr_id, java_array in result_map.items():
            python_list = list(java_array) if java_array else []
            results[expr_id] = np.array(python_list)

        return results

    def execute_tmap_compiled(
        self,
        java_script: str,
        df: pd.DataFrame,
        output_schemas: dict[str, list],
        output_types: dict[str, str],
        main_table_name: str | None = None,
        lookup_names: list[str] | None = None,
        input_columns: list[str] | None = None,
        output_columns: list[str] | None = None,
        schema: dict[str, str] | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Execute tMap outputs using a compiled Groovy script.

        Args:
            java_script: Pre-generated Java/Groovy script.
            df: Joined DataFrame.
            output_schemas: Mapping of output_name -> [column_names].
            output_types: Mapping of output_name_columnName -> type_string.
            main_table_name: Main input table name.
            lookup_names: Lookup table names.
            input_columns: Input column names (optional).
            output_columns: Output column names (optional).
            schema: Column name -> type string mapping for Arrow serialization.

        Returns:
            Mapping of output_name -> DataFrame.
        """
        from py4j.java_collections import ListConverter

        logger.debug(
            "[execute_tmap_compiled] rows=%d, outputs=%d",
            len(df),
            len(output_schemas),
        )

        schema_dict = schema if schema else self._infer_schema_dict(df)
        arrow_bytes = self._df_to_arrow_bytes(df, schema_dict)

        if lookup_names is None:
            lookup_names = []

        assert self.gateway is not None
        java_output_schemas = {}
        for output_name, col_list in output_schemas.items():
            java_output_schemas[output_name] = ListConverter().convert(
                col_list, self.gateway._gateway_client
            )
        java_lookup_names = ListConverter().convert(
            lookup_names, self.gateway._gateway_client
        )

        def _call():
            return self.java_bridge.executeTMapCompiled(
                java_script,
                arrow_bytes,
                java_output_schemas,
                output_types,
                main_table_name or "row1",
                java_lookup_names,
                self.context,
                _coerce_global_map_for_java(self.global_map),
            )

        result_map = self._call_java_with_sync(_call)

        return self._parse_output_map(result_map)

    def compile_tmap_script(
        self,
        component_id: str,
        java_script: str,
        output_schemas: dict[str, list],
        output_types: dict[str, str],
        main_table_name: str | None = None,
        lookup_names: list[str] | None = None,
        input_columns: list[str] | None = None,
        output_columns: list[str] | None = None,
        schema: dict[str, str] | None = None,
    ) -> str:
        """Compile a tMap Groovy script and cache it. No sync needed.

        Args:
            component_id: Unique component ID for cache key.
            java_script: Groovy script to compile.
            output_schemas: Mapping of output_name -> [column_names].
            output_types: Mapping of output_name_columnName -> type_string.
            main_table_name: Main input table name.
            lookup_names: Lookup table names.
            input_columns: Input column names (optional).
            output_columns: Output column names (optional).
            schema: Schema dict (unused here, for API consistency).

        Returns:
            component_id confirming compilation.
        """
        from py4j.java_collections import ListConverter

        logger.debug("[compile_tmap_script] component=%s", component_id)

        if lookup_names is None:
            lookup_names = []

        assert self.gateway is not None
        java_output_schemas = {}
        for output_name, col_list in output_schemas.items():
            java_output_schemas[output_name] = ListConverter().convert(
                col_list, self.gateway._gateway_client
            )
        java_lookup_names = ListConverter().convert(
            lookup_names, self.gateway._gateway_client
        )

        # No sync needed -- compilation doesn't change Java state
        return self.java_bridge.compileTMapScript(
            component_id,
            java_script,
            java_output_schemas,
            output_types,
            main_table_name or "row1",
            java_lookup_names,
        )

    def execute_compiled_tmap_chunked(
        self,
        component_id: str,
        df: pd.DataFrame,
        chunk_size: int = 50000,
        input_columns: list[str] | None = None,
        output_columns: list[str] | None = None,
        schema: dict[str, str] | None = None,
        reject_mode: bool = False,
    ) -> dict[str, pd.DataFrame]:
        """Execute a pre-compiled tMap script with chunking.

        Args:
            component_id: Component ID used during compilation.
            df: Joined DataFrame.
            chunk_size: Rows per chunk (default 50000).
            input_columns: Input column names (optional).
            output_columns: Output column names (optional).
            schema: Column name -> type string for Arrow serialization.
            reject_mode: D-09 (Plan 05.4-06) dual-invocation flag. False (the
                default) invokes the compiled script in active-output mode
                over ``df`` as the matched row source. True invokes the same
                compiled script in reject-output mode over ``df`` as the
                reject row source. The flag is propagated to Groovy via the
                ``__rejectMode__`` entry in the ``context`` binding so the
                generated script's row loop dispatches to active vs reject
                helpers (see ``Map._build_compiled_script``). The entry is
                inserted before the call and removed afterwards so it never
                leaks into subsequent calls or unrelated bridge consumers.

        Returns:
            Mapping of output_name -> DataFrame (combined from all chunks).
        """
        total_rows = len(df)
        # Diagnostic: log effective chunk_size + frame shape so we can tell
        # whether the caller's `output_chunk_size` override actually reached
        # us, and how wide each row is before serialization.
        try:
            mem_mb = df.memory_usage(deep=True).sum() / 1e6
        except Exception:
            mem_mb = -1.0
        logger.info(
            "[execute_compiled_tmap_chunked] component=%s rows=%d cols=%d "
            "chunk_size=%d in-memory=%.1f MB (~%.0f KB/row)",
            component_id,
            total_rows,
            len(df.columns),
            chunk_size,
            mem_mb,
            (mem_mb * 1000 / max(total_rows, 1)) if mem_mb > 0 else -1,
        )

        schema_dict = schema if schema else self._infer_schema_dict(df)
        output_dfs_list: dict[str, list[pd.DataFrame]] = {}

        # D-09 (Plan 05.4-06): propagate reject_mode to Groovy via the
        # context binding. The generated script reads
        # ``context.get("__rejectMode__")`` to decide whether the row loop
        # dispatches to active or reject helpers. Stash a prior value (if
        # any) so the entry can be restored after the call -- it never
        # leaks into unrelated consumers of the bridge.
        _prior_reject_flag = self.context.get("__rejectMode__", _MISSING)
        self.context["__rejectMode__"] = bool(reject_mode)
        try:
            return self._execute_compiled_tmap_chunked_body(
                component_id=component_id,
                df=df,
                chunk_size=chunk_size,
                schema_dict=schema_dict,
                total_rows=total_rows,
                output_dfs_list=output_dfs_list,
            )
        finally:
            if _prior_reject_flag is _MISSING:
                self.context.pop("__rejectMode__", None)
            else:
                self.context["__rejectMode__"] = _prior_reject_flag

    def _execute_compiled_tmap_chunked_body(
        self,
        component_id: str,
        df: pd.DataFrame,
        chunk_size: int,
        schema_dict: dict[str, str],
        total_rows: int,
        output_dfs_list: dict[str, list[pd.DataFrame]],
    ) -> dict[str, pd.DataFrame]:
        """Inner body of execute_compiled_tmap_chunked.

        Extracted into a separate method so the public entry point can
        wrap the call in a try/finally that scopes the
        ``context["__rejectMode__"]`` mutation to a single invocation
        (D-09, Plan 05.4-06).
        """
        # Build the initial list of (start, end) row ranges. Ranges may be
        # split further at runtime if a chunk's Arrow payload would exceed
        # the Py4J Base64 byte[] limit (see _PY4J_BYTE_ARG_SAFE_LIMIT).
        pending_ranges: list[tuple[int, int]] = []
        for chunk_idx in range((total_rows + chunk_size - 1) // chunk_size):
            start_idx = chunk_idx * chunk_size
            end_idx = min(start_idx + chunk_size, total_rows)
            pending_ranges.append((start_idx, end_idx))

        processed = 0
        while pending_ranges:
            start_idx, end_idx = pending_ranges.pop(0)
            chunk_df = df.iloc[start_idx:end_idx]

            arrow_bytes = self._df_to_arrow_bytes(chunk_df, schema_dict)

            # Pre-flight guard: if the raw Arrow payload alone would overflow
            # Py4J's Base64 length field, split the range in half and retry.
            # Refuse to split below 1 row -- a single row exceeding the limit
            # is unrecoverable and must surface as a clear error.
            if len(arrow_bytes) > _PY4J_BYTE_ARG_SAFE_LIMIT and (end_idx - start_idx) > 1:
                mid = start_idx + (end_idx - start_idx) // 2
                logger.warning(
                    "[execute_compiled_tmap_chunked] chunk rows %d-%d Arrow size "
                    "%.2f GB exceeds Py4J safe limit %.2f GB; splitting in half",
                    start_idx, end_idx,
                    len(arrow_bytes) / 1e9,
                    _PY4J_BYTE_ARG_SAFE_LIMIT / 1e9,
                )
                pending_ranges.insert(0, (mid, end_idx))
                pending_ranges.insert(0, (start_idx, mid))
                continue

            logger.debug(
                "  Chunk rows %d-%d (%d rows, %.1f MB Arrow)",
                start_idx, end_idx, end_idx - start_idx,
                len(arrow_bytes) / 1e6,
            )

            def _call(ab=arrow_bytes):
                return self.java_bridge.executeCompiledTMap(
                    component_id,
                    ab,
                    self.context,
                    _coerce_global_map_for_java(self.global_map),
                )

            try:
                result_map = self._call_java_with_sync(_call)
            except Exception as e:
                # Recovery: if Java raised NegativeArraySizeException (or any
                # error mentioning Base64), the row-count heuristic was too
                # optimistic for this chunk's actual byte width. Halve the
                # range and retry, unless we are already at 1 row.
                msg = str(e)
                is_base64_overflow = (
                    "NegativeArraySizeException" in msg
                    or "py4j.Base64" in msg
                )
                if is_base64_overflow and (end_idx - start_idx) > 1:
                    mid = start_idx + (end_idx - start_idx) // 2
                    logger.warning(
                        "[execute_compiled_tmap_chunked] Py4J Base64 overflow on "
                        "rows %d-%d; halving and retrying",
                        start_idx, end_idx,
                    )
                    pending_ranges.insert(0, (mid, end_idx))
                    pending_ranges.insert(0, (start_idx, mid))
                    continue
                raise

            for output_name, output_bytes in result_map.items():
                if output_name not in output_dfs_list:
                    output_dfs_list[output_name] = []
                if output_bytes and len(output_bytes) > 0:
                    reader = ipc.open_stream(pa.py_buffer(output_bytes))
                    result_table = reader.read_all()
                    chunk_output_df = result_table.to_pandas()
                    # decimal128 null ? "" so callers never see pandas <NA>.
                    # Keep non-null values as Python Decimal (not str) so that
                    # if this DF is fed back as input it can still be serialized.
                    for field in result_table.schema:
                        if pa.types.is_decimal(field.type) and field.name in chunk_output_df.columns:
                            chunk_output_df[field.name] = chunk_output_df[field.name].apply(  # type: ignore[arg-type]
                                lambda v: "" if v is None or v is pd.NA or (isinstance(v, float) and pd.isna(v)) else v
                            )
                    output_dfs_list[output_name].append(chunk_output_df)

            processed += end_idx - start_idx
            logger.debug(
                "[execute_compiled_tmap_chunked] processed %d / %d rows",
                processed, total_rows,
            )

        output_dfs: dict[str, pd.DataFrame] = {}
        for output_name, df_list in output_dfs_list.items():
            if df_list:
                output_dfs[output_name] = pd.concat(df_list, ignore_index=True)
                logger.info(
                    "  Output '%s': %d total rows",
                    output_name,
                    len(output_dfs[output_name]),
                )
            else:
                output_dfs[output_name] = pd.DataFrame()

        return output_dfs

    def load_routine(self, routine_class: str) -> None:
        """Load a custom routine class into the Java context.

        Args:
            routine_class: Fully qualified class name.
        """
        logger.debug("[load_routine] %s", routine_class)

        def _call():
            return self.java_bridge.loadRoutine(routine_class)

        self._call_java_with_sync(_call)

    def validate_libraries(self, libraries: list[str]) -> list[str]:
        """Validate that required libraries are on the classpath.

        No sync needed -- this is a read-only operation.

        Args:
            libraries: List of JAR filenames to validate.

        Returns:
            List of missing libraries (empty if all available).
        """
        if not libraries:
            return []

        from py4j.java_collections import ListConverter

        assert self.gateway is not None
        java_list = ListConverter().convert(libraries, self.gateway._gateway_client)
        missing = self.java_bridge.validateLibraries(java_list)
        return list(missing) if missing else []

    # ------------------------------------------------------------------
    # Public API -- State accessors
    # ------------------------------------------------------------------

    def set_context(self, key: str, value: Any) -> None:
        """Set a context variable on both Python and Java sides.

        Value type is preserved end-to-end. Py4J's native typed protocol
        handles int / bool / Decimal / str / None directly. datetime.date and
        datetime.datetime are converted via the registered Py4J input
        converters (registered in start()). Java setContext signature is
        Object so all types pass through unchanged.
        """
        self.context[key] = value
        if self.java_bridge:
            self.java_bridge.setContext(key, value)

    def set_global_map(self, key: str, value: Any) -> None:
        """Set a globalMap variable on both Python and Java sides.

        Value type is preserved end-to-end. Same type-fidelity contract as
        set_context.
        """
        self.global_map[key] = value
        if self.java_bridge:
            self.java_bridge.setGlobalMap(key, value)

    def get_context(self) -> dict[str, Any]:
        """Return a copy of the current context dict."""
        return dict(self.context)

    def get_global_map(self) -> dict[str, Any]:
        """Return a copy of the current globalMap dict."""
        return dict(self.global_map)

    def set_log_level(self, level: int) -> None:
        """Map Python log level to Java JUL level and set on Java side.

        Args:
            level: Python logging level (e.g. logging.DEBUG).
        """
        java_level = _PYTHON_TO_JAVA_LOG_LEVEL.get(level, "INFO")
        if self.java_bridge:
            try:
                self.java_bridge.setLogLevel(java_level)
                logger.debug("Java log level set to %s", java_level)
            except Exception as e:
                logger.warning("Failed to set Java log level: %s", e)

    # ------------------------------------------------------------------
    # Private -- Java call wrapper with sync
    # ------------------------------------------------------------------

    def _call_java_with_sync(self, java_method_call: Any) -> Any:
        """Call a Java method and always sync context/globalMap afterward.

        On Java exception, captures stderr and includes it in the error.

        Args:
            java_method_call: A callable that invokes the Java method.

        Returns:
            Result from the Java method call.

        Raises:
            JavaBridgeError: On any Java-side failure.
        """
        from src.v1.engine.exceptions import JavaBridgeError

        try:
            result = java_method_call()
            return result
        except JavaBridgeError:
            raise
        except Exception as e:
            java_stderr = self._capture_java_stderr()
            error_msg = str(e)
            if java_stderr:
                error_msg = (
                    f"Bridge operation failed: {error_msg}"
                    f"\n--- Java stderr (last 20 lines) ---\n{java_stderr}"
                )
            raise JavaBridgeError(error_msg) from e
        finally:
            self._sync_from_java()

    def _sync_from_java(self) -> None:
        """Sync context and globalMap back from Java side.

        Wraps Java calls in try/except -- sync failure should not mask
        the original operation's result.
        """
        if not self.java_bridge:
            return

        try:
            java_context = self.java_bridge.getContext()
            java_globalmap = self.java_bridge.getGlobalMap()
            self.context.update(java_context)
            self.global_map.update(java_globalmap)
        except Exception as e:
            logger.warning("[WARN] Failed to sync state from Java: %s", e)

    # ------------------------------------------------------------------
    # Private -- Arrow serialization
    # ------------------------------------------------------------------

    def _df_to_arrow_bytes(
        self,
        df: pd.DataFrame,
        schema_dict: dict[str, str],
        schema_columns: list[dict] | None = None,
    ) -> bytes:
        """Convert DataFrame to Arrow IPC bytes using schema-driven types.

        Args:
            df: DataFrame to serialize.
            schema_dict: Column name -> Python type string mapping.
            schema_columns: Full schema column list for Decimal precision extraction.

        Returns:
            Arrow IPC stream bytes.
        """
        schema_dict = self._reconcile_schema_to_df(df, schema_dict)
        validate_schema_types(schema_dict)

        precision_map = None
        if schema_columns:
            precision_map = extract_precision_map(schema_columns)

        arrow_schema = build_arrow_schema(schema_dict, precision_map)

        # Coerce DataFrame columns to match expected Arrow types
        coerced_df = df.copy()
        for col_name in coerced_df.columns:
            if col_name not in schema_dict:
                continue
            col_type = schema_dict[col_name]
            try:
                if col_type == "str" or col_type == "object":
                    null_mask = coerced_df[col_name].isna()
                    coerced_df[col_name] = coerced_df[col_name].astype(str)
                    coerced_df.loc[null_mask, col_name] = None
                elif col_type == "int":
                    coerced_df[col_name] = pd.to_numeric(coerced_df[col_name], errors="coerce")
                elif col_type == "float":
                    coerced_df[col_name] = pd.to_numeric(coerced_df[col_name], errors="coerce")
                elif col_type == "bool":
                    coerced_df[col_name] = coerced_df[col_name].astype(bool)
                elif col_type == "datetime":
                    coerced_df[col_name] = pd.to_datetime(coerced_df[col_name], errors="coerce")
                elif col_type == "Decimal":
                    # PyArrow's decimal128 column requires Python Decimal
                    # values (or None for null). The DataFrame may arrive
                    # with float64 dtype (e.g. from CSV inference or from
                    # pd.merge(how="left") NaN promotion) -- passing those
                    # raw triggers "Got bytestring of length 8 (expected
                    # 16), Conversion failed for column ... with type
                    # float64". Normalize every value to either Decimal or
                    # None here.
                    coerced_df[col_name] = coerced_df[col_name].apply(
                        _coerce_to_decimal_or_none  # type: ignore[arg-type]
                    )
            except Exception as e:
                logger.warning(
                    "[WARN] Column '%s' coercion to '%s' failed: %s",
                    col_name,
                    col_type,
                    e,
                )
                
        arrow_table = pa.Table.from_pandas(coerced_df, schema=arrow_schema, safe=False)
        # pandas 3.0 StringDtype columns produce chunked arrays that PyArrow
        # serializes as multiple record batches. The Java bridge reads only the
        # first batch (one loadNextBatch() call), so combine_chunks() is needed
        # to guarantee a single-batch IPC stream regardless of column dtype.
        arrow_table = arrow_table.combine_chunks()
        sink = pa.BufferOutputStream()
        writer = ipc.new_stream(sink, arrow_table.schema)
        writer.write_table(arrow_table)
        writer.close()
        return sink.getvalue().to_pybytes()

    def _arrow_bytes_to_df(
        self,
        arrow_bytes: bytes,
        schema_dict: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        """Deserialize Arrow IPC bytes back to a DataFrame.

        Args:
            arrow_bytes: Arrow IPC stream bytes.
            schema_dict: Optional schema for post-conversion type mapping.

        Returns:
            Deserialized DataFrame.
        """
        reader = ipc.open_stream(pa.py_buffer(arrow_bytes))
        result_table = reader.read_all()
        return result_table.to_pandas()

    def _reconcile_schema_to_df(
        self,
        df: pd.DataFrame,
        schema_dict: dict[str, str],
    ) -> dict[str, str]:
        """Reconcile schema dict against actual DataFrame columns.

        Strict: any DataFrame column not declared in schema_dict raises
        ConfigurationError. Schema columns not present in the DataFrame
        are pruned silently (DEBUG log) -- this is a normal case
        (schema_dict may carry entries from a wider input frame).

        Args:
            df: The DataFrame being serialized.
            schema_dict: Column name -> type string mapping.

        Returns:
            Reconciled schema dict with only columns present in df.

        Raises:
            ConfigurationError: if any column in df.columns lacks an
                entry in schema_dict. Type fidelity end-to-end requires
                every column crossing the Python/Java boundary to have
                a declared type; a missing entry indicates an upstream
                bug we want to fail loudly on.
        """
        from src.v1.engine.exceptions import ConfigurationError

        reconciled = dict(schema_dict)

        missing = [col for col in df.columns if col not in reconciled]
        if missing:
            raise ConfigurationError(
                f"DataFrame columns lack declared types in schema: {missing!r}. "
                f"Every column crossing the Python/Java boundary must have a "
                f"declared type. Schema keys: {list(reconciled.keys())!r}"
            )

        for col_name in list(reconciled.keys()):
            if col_name not in df.columns:
                logger.debug(
                    "Schema column '%s' not present in DataFrame -- skipping",
                    col_name,
                )
                del reconciled[col_name]

        return reconciled

    # ------------------------------------------------------------------
    # Private -- Schema conversion helpers
    # ------------------------------------------------------------------

    def _convert_schema_to_java(self, schema_dict: dict[str, str]) -> dict[str, str]:
        """Convert Python schema dict to Java HashMap with Java type names.

        Args:
            schema_dict: Column name -> Python type string mapping.

        Returns:
            Column name -> Java type name mapping.
        """
        return {
            col: PYTHON_TO_JAVA.get(col_type, "String")
            for col, col_type in schema_dict.items()
        }

    def _schema_dict_from_df_and_output(
        self,
        df: pd.DataFrame,
        output_schema: dict[str, str],
        input_schema: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build a schema dict for input DF serialization.

        Type-resolution precedence (highest first):
            1. ``output_schema[col]`` -- column is echoed to output, must
            keep the declared output type for round-trip parity.
            2. ``input_schema[col]`` -- column is declared in the upstream
            flow's schema (e.g. tJavaRow ``schema.inputs.<flow>``) but
            NOT echoed to output. This is the authoritative type the
            component author wrote in the JSON; the engine must trust
            it before falling back to pandas dtype guessing. Without
            this rung, an upstream component that returns a column as
            pandas ``object`` (mixed strings) or ``float64``
            (NaN-promoted from a left join) would silently downgrade
            an ``int`` declaration to Arrow VarChar/Float64, breaking
            ``int x = input_row.col`` primitive coercion in the row
            body. Talend has no analogous degradation because it uses
            the input flow's metadata directly.
            3. pandas dtype inference -- last-resort fallback.

        Args:
            df: Input DataFrame.
            output_schema: Output column name -> type mapping.
            input_schema: Optional input flow column name -> type mapping
                (e.g. derived from ``component.schema_inputs_map``).

        Returns:
            Schema dict covering all DataFrame columns.
        """
        input_schema = input_schema or {}
        schema_dict: dict[str, str] = {}
        for col in df.columns:
            if col in output_schema:
                schema_dict[col] = output_schema[col]
                continue
            if col in input_schema:
                schema_dict[col] = input_schema[col]
                continue
            pandas_dtype = str(df[col].dtype)
            if pandas_dtype.startswith("int"):
                schema_dict[col] = "int"
            elif pandas_dtype.startswith("float"):
                schema_dict[col] = "float"
            elif pandas_dtype == "bool":
                schema_dict[col] = "bool"
            elif pandas_dtype.startswith("datetime64"):
                schema_dict[col] = "datetime"
            else:
                schema_dict[col] = "str"
        return schema_dict

    def _infer_schema_dict(self, df: pd.DataFrame) -> dict[str, str]:
        """Infer a schema dict from DataFrame dtypes.

        Used as fallback when no explicit schema is provided.
        Maps pandas dtypes to the 7 Python type strings.

        Args:
            df: DataFrame to inspect.

        Returns:
            Column name -> Python type string mapping.
        """
        schema_dict: dict[str, str] = {}
        for col_name in df.columns:
            pandas_dtype = str(df[col_name].dtype)
            if pandas_dtype.startswith("int"):
                schema_dict[col_name] = "int"
            elif pandas_dtype.startswith("float"):
                schema_dict[col_name] = "float"
            elif pandas_dtype == "bool":
                schema_dict[col_name] = "bool"
            elif pandas_dtype.startswith("datetime64"):
                schema_dict[col_name] = "datetime"
            else:
                schema_dict[col_name] = "str"
        return schema_dict

    # ------------------------------------------------------------------
    # Private -- Output parsing
    # ------------------------------------------------------------------

    def _parse_output_map(
        self,
        result_map: Any,
    ) -> dict[str, pd.DataFrame]:
        """Parse a Java Map<String, byte[]> into output DataFrames.

        Args:
            result_map: Java map of output_name -> Arrow IPC bytes.

        Returns:
            Mapping of output_name -> DataFrame.
        """
        output_dfs: dict[str, pd.DataFrame] = {}
        for output_name, output_bytes in result_map.items():
            if output_bytes and len(output_bytes) > 0:
                reader = ipc.open_stream(pa.py_buffer(output_bytes))
                result_table = reader.read_all()
                output_df = result_table.to_pandas()
                # decimal128 null ? "" so callers never see pandas <NA>.
                # Keep non-null values as Python Decimal (not str) so that
                # if this DF is fed back as input it can still be serialized.
                for field in result_table.schema:
                    if pa.types.is_decimal(field.type) and field.name in output_df.columns:
                        output_df[field.name] = output_df[field.name].apply(
                            lambda v: "" if v is None or v is pd.NA or (isinstance(v, float) and pd.isna(v)) else v
                        )

                output_dfs[output_name] = output_df
            else:
                output_dfs[output_name] = pd.DataFrame()
        return output_dfs

    # ------------------------------------------------------------------
    # Private -- Utility
    # ------------------------------------------------------------------

    def _find_jar_path(self) -> str:
        """Locate the Java bridge JAR file.

        Returns:
            Absolute path to the JAR.

        Raises:
            JavaBridgeError: If the JAR is not found.
        """
        from src.v1.engine.exceptions import JavaBridgeError

        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        jar_path = os.path.join(
            base_path, "java_bridge", "java", "target",
            "java-bridge-with-dependencies.jar",
        )
        if not os.path.exists(jar_path):
            raise JavaBridgeError(
                f"Java bridge JAR not found at: {jar_path}. "
                f"Build with: cd src/v1/java_bridge/java && mvn package"
            )
        return jar_path

    def _drain_java_stdout(self) -> None:
        """Background thread: read JVM stdout line-by-line and emit via logger.

        Runs until the JVM process exits. Each non-empty line from
        ``System.out.println()`` (or any other Java/Groovy stdout write) is
        forwarded as ``logger.info("[Java] <line>")`` so it appears in the
        engine log alongside Python output.
        """
        if not self.process or not self.process.stdout:
            return
        try:
            for raw_line in self.process.stdout:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if line:
                    logger.info("[Java] %s", line)
        except Exception:
            pass

    def _drain_java_stderr(self) -> None:
        """Background thread: read JVM stderr line-by-line into bounded deque.

        Runs until the JVM process exits.  Keeps the OS pipe buffer empty so
        the JVM never blocks on a stderr write (prevents pipe-buffer deadlock
        on tFlowToIterate and other high-verbosity jobs).

        Each non-empty line is appended to ``self._stderr_buffer`` (capped at
        200 lines) for the ``_capture_java_stderr`` error-context API.

        For visibility in the Python log, the line is re-emitted at the
        Python log level that matches the Java ``java.util.logging`` (JUL)
        level prefix on the line:

          - ``INFO: <msg>``     -> ``logger.info("[Java] <msg>")``
          - ``WARNING: <msg>``  -> ``logger.warning("[Java] <msg>")``
          - ``SEVERE: <msg>``   -> ``logger.error("[Java] <msg>")``
          - ``FINE: <msg>``     -> ``logger.debug("[Java] <msg>")``
          - metadata lines (timestamp + class + method that JUL emits ahead
            of each message) and any unrecognised lines -> ``logger.debug``

        This avoids the prior behaviour of logging every stderr line at
        WARNING regardless of its actual severity, which buried real
        warnings under a flood of routine-load and class-init INFO noise.
        Real errors from the JVM (stack traces and lines without a JUL
        prefix that contain "Exception", "Error", etc.) continue to be
        captured into ``self._stderr_buffer`` and surfaced through
        ``_capture_java_stderr`` at the call boundary.
        """
        if not self.process or not self.process.stderr:
            return
        try:
            for raw_line in self.process.stderr:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line:
                    continue
                with self._stderr_lock:
                    self._stderr_buffer.append(line)
                self._log_jvm_stderr_line(line)
        except Exception:
            pass

    @staticmethod
    def _log_jvm_stderr_line(line: str) -> None:
        """Emit a single JVM stderr line at the matching Python log level.

        See ``_drain_java_stderr`` for the level-mapping rules.
        """
        # Strip the JUL level prefix and re-emit at the matching Python
        # level.  Order matters: SEVERE before WARNING before INFO is
        # unnecessary (no prefix is a substring of another), but a stable
        # mapping table makes the intent obvious.
        for jul_prefix, py_log in (
            ("SEVERE:",  logger.error),
            ("WARNING:", logger.warning),
            ("INFO:",    logger.info),
            ("FINE:",    logger.debug),
            ("FINER:",   logger.debug),
            ("FINEST:",  logger.debug),
        ):
            if line.startswith(jul_prefix):
                py_log("[Java] %s", line[len(jul_prefix):].strip())
                return
        # Not a JUL message-level line.  Could be (a) a JUL metadata line
        # (timestamp + class + method), (b) a JVM-emitted stack trace
        # ("\tat com.foo.Bar.method(...)"), or (c) an uncategorised line.
        # All three go to DEBUG -- stack traces are still surfaced via
        # _capture_java_stderr at the bridge call boundary on Exception.
        logger.debug("[Java stderr] %s", line)

    def _capture_java_stderr(self) -> str:
        """Return the last 20 lines of JVM stderr captured by the drainer thread.

        The stderr pipe is continuously drained by ``_drain_java_stderr``; this
        method reads from the in-memory deque so it never blocks.

        Returns:
            String of up to 20 most-recent stderr lines, or empty string.
        """
        with self._stderr_lock:
            lines = list(self._stderr_buffer)[-20:]
        return "\n".join(lines)
