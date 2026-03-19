"""
Python-Java Bridge using Py4J and Apache Arrow
Handles DataFrame transfer and Java expression execution
"""

import pandas as pd
import pyarrow as pa
from py4j.java_gateway import JavaGateway, GatewayParameters
import subprocess
import time
import os
from typing import Dict, Any, Optional


class JavaBridge:
    """Bridge between Python and Java using Py4J with Arrow for data transfer"""

    def __init__(self):
        self.gateway = None
        self.java_bridge = None
        self.java_process = None
        self.port = None  # Will be set during start()
        self.context = {}
        self.global_map = {}
        self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def start(self, port: int = None):
        """
        Start the Java gateway process and initialize the bridge

        Args:
            port: Port number for Py4J gateway (default: 25333, None = use default)
        """
        if port is None:
            port = 25333  # Default Py4J port

        self.port = port
        print(f"Starting Java gateway on port {port}...")

        java_dir = os.path.join(self.base_path, "java_bridge", "java")
        classes_dir = os.path.join(java_dir, "target", "java-bridge-with-dependencies.jar")

        # Build full classpath: our classes + jar dependencies
        full_classpath = f"{classes_dir}"
        print(full_classpath)

        # Run with classpath and Arrow JVM arguments
        cmd = [
            "java",
            "--add-opens=java.base/java.nio=ALL-UNNAMED",
            "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED",
            "--add-opens=java.base/java.lang=ALL-UNNAMED",
            f"-Dpy4j.port={port}",  # Pass port to Java
            "-cp", full_classpath,
            "com.citi.gru.etl.JavaBridge"
        ]

        # Start Java process
        # stdout/stderr go directly to console for debugging
        self.java_process = subprocess.Popen(
            cmd,
            cwd=java_dir,
            stdout=None,  # Let Java stdout go to console
            stderr=None,  # Let Java stderr go to console
            text=True
        )

        # Wait for gateway to be ready (look for startup message or port)
        print("Waiting for Java gateway to start...")

        # Initial delay to allow Java process to initialize
        # This reduces connection refused errors during startup
        time.sleep(2)

        max_wait = 30  # seconds
        start_time = time.time()

        while time.time() - start_time < max_wait:
            # Check if process is still running
            if self.java_process.poll() is not None:
                raise RuntimeError(f"Java process died during startup (check console for errors)")

            # Try to connect
            try:
                self.gateway = JavaGateway(
                    gateway_parameters=GatewayParameters(
                        port=port,  # Connect to specific port
                        auto_convert=True
                    )
                )
                self.java_bridge = self.gateway.entry_point
                # Test the connection
                _ = self.java_bridge.getContext()
                print(f"Java gateway started successfully on port {port}")
                return
            except Exception:
                time.sleep(0.5)

        # Timeout
        self.java_process.kill()
        raise RuntimeError("Timeout waiting for Java gateway to start")

    def stop(self):
        """Stop the Java gateway process"""
        if self.gateway:
            try:
                self.gateway.shutdown()
            except Exception:
                pass

        if self.java_process:
            self.java_process.terminate()
            try:
                self.java_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.java_process.kill()
            print("Java gateway stopped")

    def execute_java_row(self, df: pd.DataFrame, java_code: str,
                        output_schema: Dict[str, str]) -> pd.DataFrame:
        """
        Execute tJavaRow-style code block on DataFrame

        Args:
            df: Input DataFrame (becomes input_row in Java)
            java_code: Multi-line Java code block
            output_schema: Dict of {column_name: type} for output

        Returns:
            Output DataFrame (from output_row in Java)
        """
        # Convert input to Arrow with Decimal-aware schema
        arrow_table = pa.Table.from_pandas(df, schema=self._build_arrow_schema(df))
        sink = pa.BufferOutputStream()
        writer = pa.ipc.new_stream(sink, arrow_table.schema)
        writer.write_table(arrow_table)
        writer.close()
        arrow_bytes = sink.getvalue().to_pybytes()

        # Send to Java
        result_bytes = self.java_bridge.executeJavaRow(
            arrow_bytes,
            java_code,
            self._convert_schema_to_java(output_schema),
            self._convert_context_to_java(),
            self._convert_globalmap_to_java()
        )

        # Sync back context and globalMap
        self._sync_from_java()

        # Convert result
        reader = pa.ipc.open_stream(pa.py_buffer(result_bytes))
        result_table = reader.read_all()
        return result_table.to_pandas()

    def execute_one_time_expression(self, expression: str) -> Any:
        """
        Execute a one-time Java expression (e.g., for component properties)

        Args:
            expression: Java expression with context access

        Returns:
            Result value
        """
        return self.java_bridge.executeOneTimeExpression(
            expression,
            self._convert_context_to_java()
        )

    def execute_batch_one_time_expressions(self, expressions: Dict[str, str]) -> Dict[str, Any]:
        """
        Execute multiple one-time Java expressions in batch (efficient)

        Args:
            expressions: Dict of {param_name: java_expression}
                         e.g., {"footer": "1 + context.count", "limit": "context.rows * 2"}

        Returns:
            Dict of {param_name: resolved_value}
                    Errors are returned as strings with {{ERROR}} prefix
        """
        # Pass both context and globalMap to Java
        return self.java_bridge.executeBatchOneTimeExpressionsWithGlobalMap(
            expressions,
            self._convert_context_to_java(),
            self.global_map  # Pass globalMap as well
        )

    def execute_tmap_preprocessing(self, df: pd.DataFrame, expressions: Dict[str, str],
                                   main_table_name: str, lookup_table_names: list = None) -> Dict[str, Any]:
        """
        Execute tMap preprocessing - batch evaluate expressions on all rows

        Used for evaluating filters and join key expressions during tMap preprocessing.
        Each expression is evaluated once per row, returning an array of results.

        Args:
            df: Input DataFrame to evaluate expressions on
            expressions: Dict of {expr_id: expression_string} to evaluate on each row
                         e.g., {"__main_filter__": "orders.status == 'COMPLETE'",
                                "__join_customers_0__": "orders.customer_id"}
            main_table_name: Name of the main table (for row variable binding, e.g., "orders")
            lookup_table_names: List of lookup table names already joined (e.g., ["customers", "products"])

        Returns:
            Dict of {expr_id: numpy_array} where array contains result for each row

        Example:
            Input: 3 rows, expressions: {"filter": "orders.status == 'COMPLETE'",
                                          "join_key": "orders.customer_id"}
            Output: {"filter": [True, False, True], "join_key": [101, 102, 103]}
        """
        import numpy as np

        # Convert input to Arrow with Decimal-aware schema
        arrow_table = pa.Table.from_pandas(df, schema=self._build_arrow_schema(df))
        sink = pa.BufferOutputStream()
        writer = pa.ipc.new_stream(sink, arrow_table.schema)
        writer.write_table(arrow_table)
        writer.close()
        arrow_bytes = sink.getvalue().to_pybytes()

        # Convert lookup_table_names to Java List
        from py4j.java_collections import ListConverter
        java_lookup_names = ListConverter().convert(
            lookup_table_names or [], self.gateway._gateway_client
        )

        # Send to Java
        result_map = self.java_bridge.executeTMapPreprocessing(
            arrow_bytes,
            expressions,
            main_table_name,
            java_lookup_names,
            self._convert_context_to_java(),
            self._convert_globalmap_to_java()
        )

        # Convert Java Object[] arrays to numpy arrays
        results = {}
        for expr_id, java_array in result_map.items():
            # Convert Java array to Python list, then to numpy array
            python_list = list(java_array) if java_array else []
            results[expr_id] = np.array(python_list)

        return results

    def execute_tmap_compiled(self, java_script: str, df: pd.DataFrame,
                              output_schemas: Dict[str, list],
                              output_types: Dict[str, str],
                              main_table_name: str = None,
                              lookup_names: list = None) -> Dict[str, pd.DataFrame]:
        """
        Execute tMap outputs using COMPILED script (OPTIMIZED)

        Generates and compiles entire tMap logic once, then executes in parallel.
        Achieves stellar performance to tJavaRow (~180x rows/sec).

        Args:
            java_script: Pre-generated Java/Groovy script containing all tMap logic
            df: Joined DataFrame (after all lookups are complete)
            output_schemas: Dict of {output_name: [column_names...]}
            output_types: Dict of {output_name_columnName: type_string}
            main_table_name: Name of the main input table (e.g., "orders")
            lookup_names: List of lookup table names (e.g., ["customers", "products"])

        Returns:
            Dict of {output_name: DataFrame} for each output
        """
        # Convert input to Arrow with Decimal-aware schema
        arrow_table = pa.Table.from_pandas(df, schema=self._build_arrow_schema(df))
        sink = pa.BufferOutputStream()
        writer = pa.ipc.new_stream(sink, arrow_table.schema)
        writer.write_table(arrow_table)
        writer.close()
        arrow_bytes = sink.getvalue().to_pybytes()

        # Convert Python collections to Java collections
        if lookup_names is None:
            lookup_names = []

        from py4j.java_collections import ListConverter, MapConverter

        # Convert output_schemas: Map<String, List<String>>
        java_output_schemas = {}
        for output_name, col_list in output_schemas.items():
            java_col_list = ListConverter().convert(col_list, self.gateway._gateway_client)
            java_output_schemas[output_name] = java_col_list

        # Convert output_types: Map<String, String>
        java_output_types = output_types

        # Convert lookup_names: List<String>
        java_lookup_names = ListConverter().convert(lookup_names, self.gateway._gateway_client)

        # Send to Java (returns Map<String, byte[]>)
        result_map = self.java_bridge.executeTMapCompiled(
            java_script,
            arrow_bytes,
            java_output_schemas,
            java_output_types,
            main_table_name or "row1",
            java_lookup_names,
            self._convert_context_to_java(),
            self._convert_globalmap_to_java()
        )

        # Convert each output's Arrow bytes back to DataFrame
        output_dfs = {}
        for output_name, output_bytes in result_map.items():
            if output_bytes and len(output_bytes) > 0:
                reader = pa.ipc.open_stream(pa.py_buffer(output_bytes))
                result_table = reader.read_all()
                output_dfs[output_name] = result_table.to_pandas()
            else:
                # Empty output
                output_dfs[output_name] = pd.DataFrame()

        return output_dfs

    def compile_tmap_script(self, component_id: str, java_script: str,
                            output_schemas: Dict[str, list],
                            output_types: Dict[str, str],
                            main_table_name: str = None,
                            lookup_names: list = None) -> str:
        """
        Compile tMap script ONCE and cache it (STEP 1 of 2)

        This method compiles the tMap script and caches it in Java bridge.
        The compiled script can then be executed multiple times on different chunks.

        Args:
            component_id: Unique component ID (e.g., "tMap_1", "tMap_2")
            java_script: Pre-generated Java/Groovy script containing all tMap logic
            output_schemas: Dict of {output_name: [column_names...]}
            output_types: Dict of {output_name_columnName: type_string}
            main_table_name: Name of the main input table (e.g., "orders")
            lookup_names: List of lookup table names (e.g., ["customers", "products"])

        Returns:
            component_id (for confirmation)
        """
        from py4j.java_collections import ListConverter

        # Convert Python collections to Java collections
        if lookup_names is None:
            lookup_names = []

        # Convert output_schemas: Map<String, List<String>>
        java_output_schemas = {}
        for output_name, col_list in output_schemas.items():
            java_col_list = ListConverter().convert(col_list, self.gateway._gateway_client)
            java_output_schemas[output_name] = java_col_list

        # Convert lookup_names: List<String>
        java_lookup_names = ListConverter().convert(lookup_names, self.gateway._gateway_client)

        # Call Java compilation method
        return self.java_bridge.compileTMapScript(
            component_id,
            java_script,
            java_output_schemas,
            output_types,
            main_table_name or "row1",
            java_lookup_names
        )

    def execute_compiled_tmap_chunked(self, component_id: str, df: pd.DataFrame,
                                      chunk_size: int = 50000) -> Dict[str, pd.DataFrame]:

        """
        Execute pre-compiled tMap script with CHUNKING (STEP 2 of 2)

        This method chunks the input DataFrame and executes the pre-compiled script
        on each chunk. This solves the 2GB Arrow byte array limit issue.

        Compile ONCE + Execute MANY chunks = Massive performance gain!

        Args:
            component_id: Component ID used during compilation
            df: Joined DataFrame (after all lookups are complete)
            chunk_size: Number of rows per chunk (default: 50000)

        Returns:
            Dict of {output_name: DataFrame} for each output (combined from all chunks)
        """
        total_rows = len(df)
        print(f"Processing {total_rows} rows in chunks of {chunk_size}...")

        # Dictionary to accumulate results from all chunks
        output_dfs_list = {}  # {output_name: [df_chunk1, df_chunk2, ...]}

        # Process in chunks
        num_chunks = (total_rows + chunk_size - 1) // chunk_size  # Ceiling division

        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min(start_idx + chunk_size, total_rows)
            chunk_df = df.iloc[start_idx:end_idx]

            print(f"  Chunk {chunk_idx + 1}/{num_chunks}: rows {start_idx} to {end_idx} ({len(chunk_df)} rows)")

            # Convert chunk to Arrow with Decimal-aware schema
            arrow_table = pa.Table.from_pandas(chunk_df, schema=self._build_arrow_schema(df))
            sink = pa.BufferOutputStream()
            writer = pa.ipc.new_stream(sink, arrow_table.schema)
            writer.write_table(arrow_table)
            writer.close()
            arrow_bytes = sink.getvalue().to_pybytes()

            # Execute on this chunk
            result_map = self.java_bridge.executeCompiledTMap(
                component_id,
                arrow_bytes,
                self._convert_context_to_java(),
                self._convert_globalmap_to_java()
            )

            # Convert each output's Arrow bytes back to DataFrame
            for output_name, output_bytes in result_map.items():
                if output_bytes and len(output_bytes) > 0:
                    reader = pa.ipc.open_stream(pa.py_buffer(output_bytes))
                    result_table = reader.read_all()
                    chunk_output_df = result_table.to_pandas()

                    # Accumulate this chunk's output
                    if output_name not in output_dfs_list:
                        output_dfs_list[output_name] = []
                    output_dfs_list[output_name].append(chunk_output_df)

        # Combine all chunks for each output
        output_dfs = {}
        for output_name, df_list in output_dfs_list.items():
            if df_list:
                output_dfs[output_name] = pd.concat(df_list, ignore_index=True)
                print(f"  Output '{output_name}': {len(output_dfs[output_name])} total rows")
            else:
                output_dfs[output_name] = pd.DataFrame()

        return output_dfs

    def load_routine(self, routine_class: str):
        """Load a custom routine class into the Java context"""
        self.java_bridge.loadRoutine(routine_class)

    def validate_libraries(self, libraries: list) -> list:
        """
        Validate that required libraries are available on classpath

        Args:
            libraries: List of JAR filenames to validate

        Returns:
            List of missing libraries (empty if all are available)
        """
        if not libraries:
            return []

        # Convert Python List to Java List
        from py4j.java_collections import ListConverter
        java_list = ListConverter().convert(libraries, self.gateway._gateway_client)

        # Call Java validation method
        missing = self.java_bridge.validateLibraries(java_list)

        # Convert back to Python List
        return list(missing) if missing else []

    def set_context(self, key: str, value: Any):
        """Set a context variable"""
        self.context[key] = value

    def get_context(self, key: str) -> Any:
        """Get a context variable"""
        return self.context.get(key)

    def set_global_map(self, key: str, value: Any):
        """Set a globalMap variable"""
        self.global_map[key] = value

    def get_global_map(self, key: str) -> Any:
        """Get a globalMap variable"""
        return self.global_map.get(key)

    def _convert_context_to_java(self) -> Dict:
        """Convert Python context to Java Map"""
        # Py4J handles basic type conversion
        return self.context

    def _convert_globalmap_to_java(self) -> Dict:
        """Convert Python globalMap to Java Map"""
        return self.global_map

    def _convert_schema_to_java(self, schema: Dict[str, str]) -> Dict:
        """Convert Python schema dict to Java Map"""
        return schema

    def _infer_decimal_precision_scale(self, series: pd.Series) -> tuple:
        """
        Infer Arrow decimal128 precision and scale from a pandas Series of Decimal values.

        Scans all non-null values to find max digits-before-decimal and max digits-after-decimal.
        Returns (precision, scale) capped at precision=38 (Arrow decimal128 limit).
        Falls back to (38, 18) if no valid Decimal values found.
        """
        from decimal import Decimal

        max_before = 0
        max_after = 0
        found = False

        for val in series:
            if pd.isna(val) or not isinstance(val, Decimal):
                continue
            found = True
            sign, digits, exponent = val.as_tuple()
            num_digits = len(digits)
            if exponent < 0:
                after = -exponent
                before = max(num_digits - after, 0)
            else:
                before = num_digits + exponent
                after = 0
            max_before = max(max_before, before)
            max_after = max(max_after, after)

        if not found:
            return (38, 18)

        precision = min(max_before + max_after, 38)
        scale = max_after
        # Ensure precision >= scale and at least 1
        precision = max(precision, scale, 1)
        return (precision, scale)

    def _build_arrow_schema(self, df: pd.DataFrame) -> pa.Schema:
        """
        Build an explicit Arrow schema from a pandas DataFrame, detecting Decimal columns.

        For 'object' dtype columns, inspects the first non-null value:
        - Decimal instance -> pa.decimal128(precision, scale) inferred from data
        - str instance -> pa.string()
        - other -> pa.string()
        """
        from decimal import Decimal

        fields = []
        for col_name in df.columns:
            pandas_dtype = str(df[col_name].dtype)

            if pandas_dtype == 'object':
                # Check first non-null value to determine actual type
                first_val = None
                for val in df[col_name]:
                    if pd.notna(val):
                        first_val = val
                        break

                if isinstance(first_val, Decimal):
                    precision, scale = self._infer_decimal_precision_scale(df[col_name])
                    arrow_type = pa.decimal128(precision, scale)
                else:
                    arrow_type = pa.string()

            elif pandas_dtype.startswith('int'):
                arrow_type = pa.int64()
            elif pandas_dtype.startswith('float'):
                arrow_type = pa.float64()
            elif pandas_dtype == 'bool':
                arrow_type = pa.bool_()
            elif pandas_dtype.startswith('datetime64'):
                arrow_type = pa.timestamp('ns')
            else:
                arrow_type = pa.string()

            fields.append(pa.field(col_name, arrow_type))

        return pa.schema(fields)

    def _sync_from_java(self):
        """Sync context and globalMap back from Java after execution"""
        # Get updated values from Java
        java_context = self.java_bridge.getContext()
        java_globalmap = self.java_bridge.getGlobalMap()

        # Update Python dictionaries
        self.context.update(java_context)
        self.global_map.update(java_globalmap)
