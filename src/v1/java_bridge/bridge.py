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


