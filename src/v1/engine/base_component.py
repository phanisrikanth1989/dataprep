"""
Enhanced base component class with statistics tracking and exceution modes
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Iterator
from enum import Enum
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution modes for components  """
    BATCH = "batch" #Process entire dataframe at once
    STREAMING = "streaming" #Process in chunks
    HYBRID = "hybrid" #Auto-switch based on data size


class ComponentStatus(Enum):
    """Component execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


class BaseComponent(ABC):
    """
    Enhanced base class for al ETL components with statistics tracking
    """

    #Memory threshold for auto-switching to streaming mode (in MB)
    MEMORY_THRESHOLD_MB = 3072

    def __init__(
            self,
            component_id: str,
            config: Dict[str, Any],
            global_map: Any = None,
            context_manager: Any = None
    ):
        self.id = component_id
        self.config = config
        self.global_map = global_map
        self.context_manager = context_manager

        #component metadata
        self.component_type = self.__class__.__name__
        self.subjob_id: Optional[str] = None
        self.is_subjob_start: bool = False

        #Execution mode
        self.execution_mode = self._determine_execution_mode()
        self.chunk_size = config.get("chunk_size", 100000)

        # Java Bridge (for JavaComponent and JavaRowComponent)
        self.java_bridge = None #Will be set by engine if Java is enabled

        #python routine manager (for python expression evaluation)
        self.python_routine_manager = None #Will be set by engine if Python is enabled

        #Input/Output connections
        self.inputs: List[str] = []
        self.outputs: List[str] = []
        self.triggers: List[Dict[str, Any]] = []

        #Schema definitions
        self.input_schema: Optional[Dict[str, Any]] = None
        self.output_schema: Optional[Dict[str, Any]] = None

        #Statistics
        self.stats = {
            'NB_LINE': 0,
            'NB_LINE_OK': 0,
            'NB_LINE_REJECT': 0,
            'NB_LINE_INSERT': 0,
            'NB_LINE_UPDATE': 0,   
            'NB_LINE_DELETE': 0,
            'EXECUTION_TIME': 0.0
        }

        # Status
        self.status = ComponentStatus.PENDING
        self.error_message: Optional[str] = None

    def _determine_execution_mode(self) -> ExecutionMode:
        """Determine execution mode based on configuration"""
        mode_str = self.config.get('execution_mode', 'hybrid')

        if mode_str == "batch":
            return ExecutionMode.BATCH
        elif mode_str == "streaming":
            return ExecutionMode.STREAMING
        else:
            return ExecutionMode.HYBRID
    
    def _resolve_java_expressions(self) -> None:
        """
        Resolve Java expressions marked with {{java}} prefix in config
        Uses batch execution for efficiency
        """
        #Collect all Java expressions from config
        java_expressions = {}

        def scan_config(obj, path=""):
            """recursively scan config for {{java}} markers"""
            if isinstance(obj, dict):
                for key, value in obj.items():
                        scan_config(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    scan_config(item, f"{path}[{i}]")
            elif isinstance(obj, str) and obj.startswith('{{java}}'):
                #Found a Java expression
                expression = obj[8:] #Remove marker
                java_expressions[path] = expression

        #Scan entire config for Java expressions
        scan_config(self.config)
        
        if not java_expressions:
            #No Java expressions to resolve
            return
        
        if not self.java_bridge:
            logger.warning(f"Component {self.id}: Java expressions found but no Java bridge available")
            logger.warning(f"Java expressions: {java_expressions}")
            return
        
        #Sync context to Java bridge before executing
        if self.context_manager:
            current_context = self.context_manager.get_all()
            for key, value in current_context.items():
                self.java_bridge.set_context_variable(key, value)   
            
        #Also sync globalMap to JAva bridge so expressions can access iteration variables
        if self.global_map:
            gm_all = self.global_map.get_all()
            logger.debug(f"Component {self.id}: Syncing {len(gm_all)} globalMap variables to Java ")
            for key, value in gm_all.items():
                self.java_bridge.set_global_map(key, value)
        
        #Execute all Java expressions in batch
        try:
            logger.info(f"Component {self.id}: Executing Java Expressions: {java_expressions}")
            results = self.java_bridge.execute_batch_one_time_expressions(java_expressions)
            logger.info(f"Component {self.id}: Java Expression Results: {results}")
        except Exception as e:
            logger.error(f"Failed to resolve     Java expressions: {e}")
            raise

        #Replace marked expressions with resolved values
        def replace_in_config(obj, path=""):
            """recursively replace resolved expressions in config"""

            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if current_path in results:
                        #check for errors
                        result_value = results[current_path]
                        if isinstance(result_value, str) and result_value.startswith("{{ERROR}}"):
                            error_msg = result_value[9:] #Remove marker
                            raise RuntimeError(f"Error in Java expression at {current_path}: {error_msg}")
                        logger.info(f"Component {self.id}: Replaced {current_path}: '{value}'-> '{result_value}'")
                        obj[key] = result_value
                    else:
                        replace_in_config(value, current_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_path = f"{path}[{i}]"
                    if current_path in results:
                        result_value = results[current_path]
                        if isinstance(result_value, str) and result_value.startswith("{{ERROR}}"):
                            error_msg = result_value[9:] #Remove marker
                            raise RuntimeError(f"Error in Java expression at {current_path}: {error_msg}")
                        obj[i] = result_value
                    else:
                        replace_in_config(item, current_path)
        
        replace_in_config(self.config)

        logger.debug(f"Component {self.id}: Resolved {len(java_expressions)} Java expression(s)")

    def execute(self, input_data: Optional[Union[pd.DataFrame, Iterator]] =None) -> Dict[str, Any]:
        """
        Main execution method with mode handling and statistics tracking
        """
        self.status = ComponentStatus.RUNNING
        start_time = time.time()

        try:
            #Step 1: Resolve Java expressions first ({{java}} markers)
            if self.java_bridge:
                self._resolve_java_expressions()

            #Step 2: Determine execution mode if hybrid
            if self.execution_mode == ExecutionMode.HYBRID:
                self.config = self.context_manager.resolve_dict(self.config)

            #Determine execution mode if hybrid
                if self.execution_mode == ExecutionMode.HYBRID:
                    mode = self._determine_execution_mode()
                else:
                    mode = self.execution_mode  
                
                #Executed based on mode 
                if mode == ExecutionMode.STREAMING:
                    result = self._execute_streaming(input_data)
                else:
                    result = self._execute_batch(input_data)  

                #Update sttatistics
                self.stats['EXECUTION_TIME'] = time.time() - start_time
                self._update_global_map()
        
                self.status = ComponentStatus.SUCCESS

                #Add stats to result
                result['stats'] = self.stats.copy()

                return result
            
        except Exception as e:
                self.status = ComponentStatus.ERROR
                self.error_message = str(e)
                self.stats['EXECUTION_TIME'] = time.time() - start_time
                self._update_global_map()

                logger.error(f"Component {self.id} execution failed: {e}")
                raise

    def _auto_select_mode(self, input_data: Any) -> ExecutionMode:
        """Auto-select execution mode based on input data size"""
        if input_data is None:
            return ExecutionMode.BATCH
        
        if isinstance(input_data, pd.DataFrame):
            #Estimate memory usage in MB
            memory_usage_mb = input_data.memory_usage(deep=True).sum() / (1024 * 1024)
            logger.debug(f"Component {self.id}: Input data memory usage: {memory_usage_mb:.2f} MB")
            if memory_usage_mb > self.MEMORY_THRESHOLD_MB:
                logger.info(f"Component {self.id}: Switching to STREAMING mode (data size: {memory_usage_mb:.2f} MB)")  
                return ExecutionMode.STREAMING
        
        return ExecutionMode.BATCH
    
    def _execute_batch(self, input_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """Execute component in batch mode"""
        return self._process(input_data)

    def _execute_streaming(self, input_data: Optional[Iterator]) -> Dict[str, Any]:
        """Execute component in streaming mode"""
        if input_data is None:
            return self._process(None)  

        #Convert DataFrame to chunks if needed
        if isinstance(input_data, pd.DataFrame):
                chunks = self._creae_chunks(input_data)
        else:
            chunks = input_data

        #process chunks
        results = []
        for chunk in chunks:
                chunk_result = self._process(chunk)
                if chunk_result.get('main') is not None:
                    results.append(chunk_result['main'])  
        
        #Combine results
        if results:
            combined = pd.concat(results, ignore_index=True)
            return {'main': combined}
        else:
            return {'main': pd.DataFrame()}
        
    def _create_chunks(self, df: pd.DataFrame) -> Iterator[pd.DataFrame]:
            """Create chunks from a DataFrame """
            for i in range(0, len(df), self.chunk_size):
                yield df.iloc[i:i + self.chunk_size]

    @abstractmethod
    def _process(self, input_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """
        Process data - to be implemented by each component

        Returns:
            Dict with keys:
            -'main': main output DataFrame
            -'reject': Rejected rows DataFrame (optional)
            - Any other outputs specific to the component
        """
        pass

    def _update_global_map(self) -> None:
        """Update global map with current statistics""" 
        if self.global_map:
            for stat_name, value in self.stats.items():
                self.global_map.put_component_stat(self.id, stat_name, value)   
    
    def _update_stats(self, rows_read:int=0, rows_ok:int=0, rows_reject:int=0) -> None:
        """Helpter to update statistics """
        self.stats['NB_LINE'] += rows_read
        self.stats['NB_LINE_OK'] += rows_ok
        self.stats['NB_LINE_REJECT'] += rows_reject

    def validate_schema(self, df: pd.DataFrame, schema: List[Dict]) -> pd.DataFrame:
        """Validate and convert DataFram according to schema definition"""
        if not schema or df.empty:
            return df   
        
        #Type mapping from Talend to pandas
        type_mapping = {
            'id_string': 'object',
            'id_integer': 'Int64',
            'id_Long': 'Int64',
            'id_Float': 'float64',
            'id_Double': 'float64',
            'id_Boolean': 'boolean',
            'id_Date': 'datetime64[ns]',
            'id_BigDecimal': 'object',
            #Also support simple type names
            'str': 'object',
            'int': 'Int64', 
            'long': 'Int64',
            'float': 'float64',
            'double': 'float64',
            'bool': 'boolean',
            'date': 'datetime64[ns]',
            'decimal': 'object'
        }

        for col_def in schema:
            col_name = col_def['name'] 
            col_type = col_def.get('type', 'id_string')
            
            if col_name in df.columns:
                pandas_type = type_mapping.get(col_type, 'object')
                try:
                    if pandas_type == 'datetime64[ns]':
                        df[col_name] = pd.to_datetime(df[col_name])
                    elif pandas_type in ['Int64', 'float64']:
                        df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
                        if pandas_type == 'Int64' and col_def.get('nullable', True):
                            df[col_name] = df[col_name].fillna(pd.NA).astype('Int64')
                    elif pandas_type == 'bool':
                        df[col_name] = df[col_name].astype('bool')

                except Exception as e:
                    logger.warning(f"Failed to convert column {col_name} to type {pandas_type}: {e}")
        
        return df
    
    def get_status(self) -> ComponentStatus:
        """Get component execution  status"""
        return self.status 

    def get_stats(self) -> Dict[str, Any]:
        """Get component    statistics"""
        return self.stats.copy() 
    
    def get_python_routines(self) -> Dict[str, Any]:
        """
        Get loaded python routines for use in expressions

        Returns:
            Dictionary mapping routines names to routine objects
            Empty dict if no python routine manager is configured
        """
        if self.python_routine_manager:
            return self.python_routine_manager.get_all_routines()
        return {}
    
    def __repr__(self) -> str:
        return f"<{self.component_type} id={self.id} status={self.status.value})"