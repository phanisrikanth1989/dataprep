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
    
    
    



