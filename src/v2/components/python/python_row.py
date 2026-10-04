"""PythonRow Component for V2 engine."""
import logging
from typing import Callable, Dict, List

import polars as pl

from ..base import PythonComponent
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("python_row")
class PythonRow(PythonComponent):
    """
    Execute Python code for each row in the DataFrame.

    Supports two modes:
    - scalar: Process one row at a time via map_elements
    - vectorized: Process batches of rows

    Code has access to:
    - `row`: Dictionary of column values for current row (scalar mode)
    - `rows`: List of row dictionaries (vectorized mode)
    - `context`: Dictionary of context variables

    The code MUST return a dictionary of output column values (scalar)
    or a list of dictionaries (vectorized).

    Config:
        code: str - Python code to execute for each row (required)
        mode: str - 'scalar' or 'vectorized' (default: 'scalar')
        batch_size: int - Batch size for vectorized mode (default: 10000)
        output_columns: list - Output column definitions (required)
            Each: {"name": "col_name", "type": "String|Integer|Float|Boolean"}
        pass_through: bool - Include input columns in output (default: True)
    """

    # Type mapping for output columns
    TYPE_MAPPING = {
        'string': pl.Utf8,
        'str': pl.Utf8,
        'utf8': pl.Utf8,
        'integer': pl.Int64,
        'int': pl.Int64,
        'int64': pl.Int64,
        'float': pl.Float64,
        'float64': pl.Float64,
        'double': pl.Float64,
        'boolean': pl.Boolean,
        'bool': pl.Boolean,
        'date': pl.Date,
        'datetime': pl.Datetime,
    }

    # Cache for compiled row functions
    _code_cache: Dict[str, Callable] = {}

    def _post_init(self):
        self._row_func = None

    def validate(self) -> List[str]:
        errors = []

        if 'code' not in self.config:
            errors.append("Missing required configuration: 'code'")
        elif not isinstance(self.config['code'], str):
            errors.append("'code' must be a string")

        mode = self.config.get('mode', 'scalar')
        if mode not in ('scalar', 'vectorized'):
            errors.append(f"'mode' must be 'scalar' or 'vectorized', got: {mode}")

        if 'output_columns' not in self.config:
            errors.append("Missing required configuration: 'output_columns'")
        elif not isinstance(self.config['output_columns'], list):
            errors.append("'output_columns' must be a list")
        else:
            for i, col in enumerate(self.config['output_columns']):
                if not isinstance(col, dict):
                    errors.append(f"output_columns[{i}] must be a dictionary")
                elif 'name' not in col:
                    errors.append(f"output_columns[{i}] missing 'name'")
                elif 'type' not in col:
                    errors.append(f"output_columns[{i}] missing 'type'")
                elif col['type'].lower() not in self.TYPE_MAPPING:
                    errors.append(
                        f"output_columns[{i}] unknown type: {col['type']}"
                    )

        batch_size = self.config.get('batch_size', 10000)
        if not isinstance(batch_size, int) or batch_size < 1:
            errors.append("'batch_size' must be a positive integer")

        return errors

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        data = inputs.get("main")
        if data is None:
            return {}

        # Collect -- this is a barrier
        if isinstance(data, pl.LazyFrame):
            input_df = data.collect()
        else:
            input_df = data

        # Compile row function
        row_func = self._compile_row_function()

        mode = self.config.get('mode', 'scalar')
        output_columns = self.config['output_columns']
        pass_through = self.config.get('pass_through', True)
        die_on_error = self.config.get('die_on_error', True)

        if mode == 'scalar':
            output_df, error_indices, error_messages = self._process_scalar(
                input_df, row_func, output_columns, die_on_error
            )
        else:
            batch_size = self.config.get('batch_size', 10000)
            output_df, error_indices, error_messages = self._process_vectorized(
                input_df, row_func, output_columns, batch_size, die_on_error
            )

        # Add pass-through columns if requested
        if pass_through and len(output_df) > 0:
            # Build good-rows-only input for pass-through
            if error_indices:
                good_mask = [i not in error_indices for i in range(len(input_df))]
                good_input = input_df.filter(pl.Series(good_mask))
            else:
                good_input = input_df

            output_col_names = {col['name'] for col in output_columns}
            for col in good_input.columns:
                if col not in output_col_names:
                    output_df = output_df.with_columns(good_input[col])

        # Build result
        result = {"main": output_df.lazy()}

        # Add reject output if there are errors and die_on_error is false
        if not die_on_error and error_indices:
            reject_mask = [i in error_indices for i in range(len(input_df))]
            reject_df = input_df.filter(pl.Series(reject_mask))
            reject_msgs = [error_messages[i] for i in sorted(error_indices)]
            reject_df = reject_df.with_columns(
                pl.Series("_error_message", reject_msgs)
            )
            result["reject"] = reject_df.lazy()

        return result

    def _compile_row_function(self) -> Callable:
        """Compile the row processing function."""
        if self._row_func is not None:
            return self._row_func

        code_str = self.config['code']
        mode = self.config.get('mode', 'scalar')

        cache_key = f"{mode}:{code_str}"
        if cache_key in self._code_cache:
            self._row_func = self._code_cache[cache_key]
            return self._row_func

        # Wrap code in a function
        if mode == 'scalar':
            func_code = f"def _row_processor(row, context):\n{self._indent_code(code_str, 4)}\n"
        else:  # vectorized
            func_code = f"def _row_processor(rows, context):\n{self._indent_code(code_str, 4)}\n"

        # Compile and extract function
        try:
            compiled = compile(func_code, f"<{self.component_id}>", 'exec')
            namespace = {}
            exec(compiled, namespace)
            self._row_func = namespace['_row_processor']
            # Limit cache size
            if len(self._code_cache) > 100:
                self._code_cache.clear()
            self._code_cache[cache_key] = self._row_func
            return self._row_func
        except SyntaxError as e:
            raise ValueError(f"Syntax error in code: {e}")

    def _indent_code(self, code: str, spaces: int) -> str:
        """Indent code block by given number of spaces."""
        indent = ' ' * spaces
        lines = code.split('\n')
        return '\n'.join(indent + line for line in lines)

    def _get_output_dtype(self, type_name: str) -> pl.DataType:
        """Get Polars dtype from type name."""
        return self.TYPE_MAPPING.get(type_name.lower(), pl.Utf8)

    def _process_scalar(
        self,
        input_df: pl.DataFrame,
        row_func: Callable,
        output_columns: List[Dict],
        die_on_error: bool = True,
    ) -> tuple:
        """Process rows in scalar mode. Returns (output_df, error_indices, error_messages)."""
        context = self.context
        results = []
        error_indices = set()
        error_messages = {}

        for idx in range(len(input_df)):
            row_dict = input_df.row(idx, named=True)
            try:
                result = row_func(row_dict, context)
                if result is None:
                    if die_on_error:
                        raise ValueError(f"Row function returned None for row {idx}")
                    error_indices.add(idx)
                    error_messages[idx] = "Row function returned None"
                    continue
                results.append(tuple(result.get(col['name']) for col in output_columns))
            except Exception as e:
                if die_on_error:
                    raise
                logger.debug(f"Row {idx} error: {e}")
                error_indices.add(idx)
                error_messages[idx] = str(e)

        # Build output DataFrame from good results only
        if not results:
            output_data = {
                col['name']: pl.Series(col['name'], [], dtype=self._get_output_dtype(col['type']))
                for col in output_columns
            }
            return pl.DataFrame(output_data), error_indices, error_messages

        output_data = {}
        for i, col in enumerate(output_columns):
            col_name = col['name']
            col_type = self._get_output_dtype(col['type'])
            values = [r[i] for r in results]
            output_data[col_name] = pl.Series(col_name, values, dtype=col_type)

        return pl.DataFrame(output_data), error_indices, error_messages

    def _process_vectorized(
        self,
        input_df: pl.DataFrame,
        row_func: Callable,
        output_columns: List[Dict],
        batch_size: int,
        die_on_error: bool = True,
    ) -> tuple:
        """Process rows in vectorized mode. Returns (output_df, error_indices, error_messages)."""
        context = self.context
        all_results = []
        error_indices = set()
        error_messages = {}

        for batch_start in range(0, len(input_df), batch_size):
            batch_end = min(batch_start + batch_size, len(input_df))
            batch_df = input_df.slice(batch_start, batch_end - batch_start)
            rows = batch_df.to_dicts()

            try:
                results = row_func(rows, context)
                if results is None:
                    if die_on_error:
                        raise ValueError(f"Batch function returned None for batch at {batch_start}")
                    for i in range(batch_start, batch_end):
                        error_indices.add(i)
                        error_messages[i] = "Batch function returned None"
                    continue

                for i, r in enumerate(results):
                    global_idx = batch_start + i
                    if r is None:
                        if die_on_error:
                            raise ValueError(f"Row result is None at index {global_idx}")
                        error_indices.add(global_idx)
                        error_messages[global_idx] = "Row result is None"
                    else:
                        all_results.append(r)
            except Exception as e:
                if die_on_error:
                    raise
                logger.error(f"[{self.component_id}] Batch error at {batch_start}: {e}")
                for i in range(batch_start, batch_end):
                    error_indices.add(i)
                    error_messages[i] = str(e)

        # Build output DataFrame from good results only
        if not all_results:
            output_data = {
                col['name']: pl.Series(col['name'], [], dtype=self._get_output_dtype(col['type']))
                for col in output_columns
            }
            return pl.DataFrame(output_data), error_indices, error_messages

        output_data = {}
        for col in output_columns:
            col_name = col['name']
            col_type = self._get_output_dtype(col['type'])
            values = [r.get(col_name) if isinstance(r, dict) else None for r in all_results]
            output_data[col_name] = pl.Series(col_name, values, dtype=col_type)

        return pl.DataFrame(output_data), error_indices, error_messages
