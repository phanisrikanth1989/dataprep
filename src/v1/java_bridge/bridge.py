"""
Python-Java Bridge using Py43 and Apache Arroм
Handles DataFrame transfer and Java expression execution
"""

import pandas as pd
import pyarrow as pa
from py4j.java_gateway import JavaGateway, GatewayParameters
import subprocess
import time
import os
from typing import Dict, Any, Optional


class Javabridge:
    """Bridge between Python and Java using Py43 with Arrow for data transfer"""

    def __init__(self):
        self.gateway = None
        self.java_bridge = None
        self.java_process = None
        self.port = None #Will be set during start()
        self.context = {}
        self.global_map = {}
        self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def start(self, port: int = None):
        """
        Start the Java gateway process and initialize the bridge

        Args:
        port: Port number for Py43 gateway (default: 25333, None use default)
        """
        if port is None:
            port = 25333 # Default Py4J port

        self.port = port
        print("Starting Java gateway on port (port)...")

        java_dir = os.path.join(self.base_path, "java_bridge", "java") 
        classes_dir = os.path.join(java_dir, "target", "java-bridge-with-dependencies.jar")

        #Build full classpath: our classes + jar dependencies
        full_classpath =f"{classes_dir}"
        print(full_classpath)

        #Run with classpath and Arrow JVM arguments
        cmd = [
            "java",
            "--add-opens=java.base/java.nio=ALL-UNNAMED",
            "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED",
            "--add-opens=java.base/java.lang=ALL-UNNAMED",
            f"-Dpy4j.port={port}", # Pass port to Java
            "-cp", full_classpath,
            "com.citi.gru.etl.JavaBridge"
        ]

        #Start Java process
        #Stdout/stderr go directly to console for debugging
        self.java_process = subprocess.Popen(
            cmd,
            cwd=java_dir,
            stdout=None,
            stderr=None,
            text=True
        )

        #Wait for gateway to be ready (look for startup message or port)
        print("Waiting for Java gateway to start...")

        #Initial delay to allow Java process to initialize
        #This reduces connection refused errors during startup
        time.sleep(2)

        max_wait = 30 # seconds
        start_time = time.time()

        while time.time() - start_time < max_wait:
            #check if process is still running
            if self.java_process.poll() is not None:
                raise RuntimeError(f"Java pricess died during startup (check console for errors)")
            
            # try to connect
            try:
                self.gateway =JavaGateway(
                    gateway_parameters=GatewayParameters(
                        port=port,#Connect to specific port
                        auto_convert=True
                    )
                )
                self.java_bridge =  self.gateway.entry_point
                #Test the connection
                _ = self.java_bridge.getContext()
                print(f"Java gateway started successfully on port {port}")
                return
            except Exception:
                time.sleep(0.5) 

        #Timeout
        self.java_process.kill()
        raise RuntimeError("Timeout waiting for Java gateway to start")
    
    def stop(self):
        """ Stop the java gateway process   """
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
            df: Input DataFrame (become input_row in Java)
            java_code: Multi-line Java code block
            output_schema: Dict of {column_name: type} for output
        
        Returns:
            Output DataFrame (from output_row in Java)
        """
        # Convert input to Arrow
        arrow_table = pa.Table.from_pandas(df)
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

        #Sync back context and global map
        self._sync_from_java()

        # Convert result
        reader = pa.ipc.open_stream(pa.BufferReader(result_bytes))
        result_table = reader.read_all()
        return result_table.to_pandas()

    def execute_one_time_expression(self, expression: str) -> Any:
        """
        Execute a one-time Java expression

        Args:
            expression: Java expression to evaluate
        
        Returns:
            Result of the expression
        """
        result = self.java_bridge.executeOneTimeExpression(
            expression,
            self._convert_context_to_java()
        )

    def execute_batch_one_time_expressions(self, expressions: Dict[str, str]) -> Dict[str, Any]:
        """
        Execute multiple one-time Java expressions in batch

        Args:
            expressions: Dict of {param_name: Java expression}
                        e.g.,{"footer": "1 + context.count", "limit": "context.rows * 2" }
        
        Returns:
            Dict of {param_name: resolved_value}
                    Errors are returned as Strings with {{ERROR}} prefix
        """
        #Pass both context and globalMap toJava
        return self.java_bridge.executeBatchOneTimeExpressionsWithGlobalMap(
            expressions,
            self._convert_context_to_java(),
            self.global_map #Pass global map as well
        )
    
    def execute_tmap_preprocessing(self, df: pd.DataFrame, expressions: Dict[str, str],
                                   main_table_name: str, lookup_table_names: list = None) -> Dict[str, Any]:
        """
        Execute tMap preprocessing - batch evaluate expressions on all rows
        
        Used for evelauting filters and join key expressions during tMap preprocessing.
        Each expression is evaluated once per row, returning an array of results.
        
        Args:
            df: Input DataFrame to evaluate expressions on
            expressions: Dict of {expr_id: expression_string} to evaluate on each row
                        e.g.,{'__main__filter': 'orders.status == 'COMPLETE'", 
                                "__join_customers_0__": "orders.customer_id"}
            main_table_name: Name of the main table (for row variable binding, e.g., "orders")
            lookup_table_names: List of lookup table names (for row variable binding, e.g., ["customers"])

        Returns:
            Dict of {expr_id: numpy_array} where each array contains results for each row

        Example:
            Input: 3 rows, expressions: {"filter": "orders.status == 'COMPLETE'",
                                         "join_key": "orders.customer_id"}
            Output: {"filter": array([True, False, True]), "join_key": array([123, 456, 789])}
        """
        import numpy as np
        
        # **FIX: Preserver pandas dtypes when converting to Arrow**
        # Create Arrow schema that matches pandas DataFrame dtypes exactly
        # This prevents Arrow from automatically inferring types ( e,g., object -> int64)

        arrow_schema_fields = []
        for col_name in df.columns:
            pandas_dtype = str(df[col_name].dtype)

            #Map pandas dtypes to Arrow types, preserving string types
            if pandas_dtype == 'object':
                # Keep object columns as string in Arrow ( dont let Arrow infer numeric type)
                arrow_type = pa.string()
            elif pandas_dtype.startswith('int'):    
                arrow_type = pa.int64()
            elif pandas_dtype.startswith('float'):
                arrow_type = pa.float64()  
            elif pandas_dtype == 'bool':
                arrow_type = pa.bool_() 
            else:
                # Default to string for any unknown types
                arrow_type = pa.string()
            
            arrow_schema_fields.append(pa.field(col_name, arrow_type))

        #create explicit Arrow schema
        explicit_schema = pa.schema(arrow_schema_fields)
    
        #Convert input to Arrow WITH explicit schema (prevents type inference)
        arrow_table = pa.Table.from_pandas(df, schema=explicit_schema)
        sink = pa.BufferOutputStream()
        writer = pa.ipc.new_stream(sink, arrow_table.schema)
        writer.write_table(arrow_table)
        writer.close()  
        arrow_bytes = sink.getvalue().to_pybytes()
    
        # Convert lookup table bames to Java list
        from py4j.java_collections import ListConverter
        java_lookup_names = ListConverter().convert(
            lookup_table_names or [], self.gateway._gateway_client
        )
    
        # Send to Java
        result_map = self.java_bridge.executeTMapPreprocessing(
            arrow_bytes,
            self._convert_expressions_to_java(expressions),
            main_table_name,
            java_lookup_names,
            self._convert_context_to_java(),
            self._convert_globalmap_to_java()
        )
    
        # Convert Java Object[] arrays back to numpy arrays
        results = {}
        for expr_id, java_array in result_map.items():
            # Convert java array to Python list, then to numpy array
            python_list = list(java_array) if java_array else []#Convert Java array to Python list
            results[expr_id] = np.array(python_list) #Convert to numpy array

        return results
        
    def execute_tmap_compiled(self, java_script: str, df: pd.DataFrame,
                             output_schemas: Dict[str, list],
                             output_types: Dict[str, str],
                             main_table_name: str = None,
                             lookup_names: list = None) -> Dict[str, pd.DataFrame]:

        """
        Execute tMap outputs using COMPILED script (OPTIMIZED)
        Generates and compiles entire tMap logic once, then executes in parallel.
        Achieves similar performance to tJavaRow (~189k rows/sec).

        Args:
        java_script: Pre-generated Java/Groovy script containing all tMap logic
        df: Joined DataFrame (after all lookups are complete)
        output_schemas: Dict of output_name: [column_names...]}
        output_types: Dict of output_name_columnName: type_string}
        main_table_name: Name of the main input table (e.g., "orders")
        lookup_names: List of lookup table names (e.g., ["customers", "products"])

        Returns:
         Dict of output_name: DataFrame for each output
        """
        #Convert input to Arrow
        #***FIX: Preserve pandas dtypes when converting to Arrow**
        #Create Arrow schema that matches pandas DataFrame dtypes exactly 
        # This prevents Arrow from automatically inferring types (e.g., object -> int64)

        arrow_schema_fields = []
        for col_name in df.columns:
            pandas_dtype = str(df[col_name].dtype)

            #Map pandas dtypes to Arrow types, preserving string types
            if pandas_dtype == 'object':
                #Keep object columns as string in Arrow (don't let Arrow int
                arrow_type = pa.string()
            elif pandas_dtype.startswith('int'):
                arrow_type = pa.int64()
            elif pandas_dtype.startswith('float'):
                arrow_type = pa.float64()
            elif pandas_dtype == 'bool':
                arrow_type = pa.bool_()
            else:
                #Default to string for any unknown types
                arrow_type = pa.string()

            arrow_schema_fields.append(pa.field(col_name, arrow_type))
            
        #Create explicit Arrow schema
        explicit_schema = pa.schema(arrow_schema_fields)

        #Convert input to Arrow WITH explicit schema (prevents type inference)    
        arrow_table = pa.Table.from_pandas(df, schema=explicit_schema) 
        sink = pa.BufferOutputStream()
        writer = pa.ipc.new_stream(sink, arrow_table.schema)
        writer.write_table(arrow_table)
        writer.close()
        arrow_bytes = sink.getvalue().to_pybytes()

        #Convert python collections to Java collections
        if lookup_names is None:
            lookup_names = []

        from py4j.java_collections import ListConverter, MapConverter

        #Convert output_schemas: Map<String, List<String>>
        java_output_schemas = {}
        for output_name, col_list in output_schemas.items():
            java_col_list = ListConverter().convert(col_list, self.gateway._gateway_client)
            java_output_schemas[output_name] = java_col_list

        #Convert output_types: Map<String, String>
        java_output_types = output_types

        #Convert lookup_names: List<String>
        java_lookup_names = ListConverter().convert(lookup_names, self.gateway._gateway_client)

        #Send to Java
        result_map = self.java_bridge.executeTMap(
            java_script,
            arrow_bytes,
            java_output_schemas,
            java_output_types,
            main_table_name or "row1",
            java_lookup_names,
            self._convert_context_to_java(),
            self._convert_globalmap_to_java()
        )

        #Convert each output's Arrow bytes back to DataFrame
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

        This method compiles the provided tMap Java script using the Java bridge.
        the compild script can then be executed multiple times with different data inputs.

        Args:
            component_id: Unique identifier for the tMap component instance
            java_script: The full Java/Groovy script representing the tMap logic
            output_schemas: Dict of output_name: [column_names...]}
            output_types: Dict of output_name_columnName: type_string}
            main_table_name: Name of the main input table (e.g., "row1")
            lookup_names: List of lookup table names (e.g., ["lookup1", "lookup2"])

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

        This method chunks the input DataFrame and processes each chunk using the pre-compiled tMap script
        on each chunk. The results from all chunks are then combined into final output DataFrames.

        Compile ONCE -> Execute MANY with chunking for large datasets.

        Args:
        component_id: Compoenent ID used during compilation
        df: Joined DataFrame (after all lookups are complete)
        chunk_size: Number of rows per chunk to process (default: 50000)
        
        Returns:
         Dict of output_name: DataFrame for each output
        """
        total_rows = len(df)
        print(f"Processing {total_rows} rows in chunks of {chunk_size}...")

        # Dictionary to accumulate results from all chunks
        output_dfs_list = {}

        # Process in chunks
        num_chunks = (total_rows + chunk_size - 1) // chunk_size

        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min(start_idx + chunk_size, total_rows)
            chunk_df = df.iloc[start_idx:end_idx]

            print(f"Processing chunk {chunk_idx + 1}/{num_chunks} (rows {start_idx} to {end_idx} ({len(chunk_df)} rows)")

            arrow_schema_fields = []
            for col_name in chunk_df.columns:
                pandas_dtype = str(chunk_df[col_name].dtype)

                # Map pandas dtypes to Arrow types, preserving string types
                if pandas_dtype == 'object':
                    # Keep object columns as string in Arrow (don't let Arrow infer numeric type)
                    arrow_type = pa.string()
                    # print(f"Column {col_name} treated as string")
                elif pandas_dtype.startswith('int'):
                    arrow_type = pa.int64()
                elif pandas_dtype.startswith('float'):
                    arrow_type = pa.float64()
                elif pandas_dtype == 'bool':
                    arrow_type = pa.bool_()
                else:
                    # Default to string for any unknown types
                    arrow_type = pa.string()

                arrow_schema_fields.append(pa.field(col_name, arrow_type))

            # Create explicit Arrow schema
            explicit_schema = pa.schema(arrow_schema_fields)

            # Convert chunk to Arrow WITH explicit schema (prevents type inference)    
            arrow_table = pa.Table.from_pandas(chunk_df, schema=explicit_schema)
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
                self._convert_global_map_to_java()
            )

            # Convert each output's Arrow bytes back to DataFrame
            for output_name, output_bytes in result_map.items():
                if output_bytes and len(output_bytes) > 0:
                    reader = pa.ipc.open_stream(pa.py_buffer(output_bytes))
                    result_table = reader.read_all()
                    chunk_output_df = result_table.to_pandas()

                    #Accumulate chunk results
                    if output_name not in output_dfs_list:
                        output_dfs_list[output_name] = []
                    output_dfs_list[output_name].append(chunk_output_df)

        # Combine all chunk results into final DataFrames
        output_dfs = {}
        for output_name, df_list in output_dfs_list.items():
            if df_list:
                output_dfs[output_name] = pd.concat(df_list, ignore_index=True)
                print(f"Output '{output_name}' has {len(output_dfs[output_name])} total rows after combining chunks")
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
        libraries: List of library names to validate

        Returns:
        List of missing libraries (empty if all are present)
        """
        if not libraries:
            return []

        # Convert Python list to Java list

        from py4j.java_collections import ListConverter
        java_list = ListConverter().convert(libraries, self.gateway._gateway_client)

        #Call Java validation method
        missing = self.java_bridge.validateLibraries(java_list)

        #Convert result back to Python list
        return list(missing) if missing else []

    def set_context(self, key: str, value: Any):
        """Set a context variable"""
        self.context[key] = value

    def get_context(self, key: str) -> Any:
        """Get a context variable"""
        return self.context.get(key)

    def set_global_map(self, key: str, value: Any):
        """Set a global map variable"""
        self.global_map[key] = value

    def get_global_map(self, key: str) -> Any:
        """Get a global map variable"""
        return self.global_map.get(key)

    def _convert_context_to_java(self) -> Dict:
        """Convert Python context to Java Map"""
        #Py4j handles dict conversion automatically
        return self.context

    def _convert_globalmap_to_java(self) -> Dict:
        """Convert Python global map to Java Map"""
        return self.global_map
    
    def _convert_schema_to_java(self, schema: Dict[str, str]) -> Dict:
        """Convert output schema to Java Map"""
        return schema
    
    def _sync_from_java(self):
        """Sync context and global map from Java back to Python"""
        # Get updated values from Java"
        java_context = self.java_bridge.getContext()
        java_globalmap = self.java_bridge.getGlobalMap()

        # Update Python dictionaries
        self.context.update(java_context)
        self.global_map.update(java_globalmap)

    
