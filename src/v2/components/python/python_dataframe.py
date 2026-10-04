"""PythonDataFrame Component for V2 engine."""
import logging
from typing import Any, Dict, List

import polars as pl

from ..base import PythonComponent
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("python_dataframe")
class PythonDataFrame(PythonComponent):
    """
    Execute Python code with full DataFrame access.

    Code has access to:
    - `df`: The input Polars DataFrame (or pandas if use_pandas=True)
    - `context`: Dictionary of context variables
    - `pl`: Polars module
    - `np`: NumPy module (if available)
    - `routines`: Routine namespace (if routine_manager set)

    Code MUST set `output_df` to the result DataFrame.

    Config:
        code: str - Python code to execute (required)
        imports: list - Additional modules to import (optional)
        use_pandas: bool - Convert to pandas for processing (default: False)
    """

    # Class-level code cache (shared across instances)
    _code_cache: Dict[str, Any] = {}

    def _post_init(self):
        self._compiled_code = None
        self._routine_manager = None

    def validate(self) -> List[str]:
        errors = []
        if 'code' not in self.config:
            errors.append("Missing required configuration: 'code'")
        elif not isinstance(self.config['code'], str):
            errors.append("'code' must be a string")
        elif not self.config['code'].strip():
            errors.append("'code' cannot be empty")

        if 'imports' in self.config:
            if not isinstance(self.config['imports'], list):
                errors.append("'imports' must be a list of module names")

        if 'use_pandas' in self.config:
            if not isinstance(self.config['use_pandas'], bool):
                errors.append("'use_pandas' must be a boolean")

        return errors

    def set_routine_manager(self, manager: Any) -> None:
        """Set the routine manager for external function access."""
        self._routine_manager = manager

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        data = inputs.get("main")
        if data is None:
            return {}

        # Collect -- this is a barrier
        if isinstance(data, pl.LazyFrame):
            input_df = data.collect()
        else:
            input_df = data

        use_pandas = self.config.get('use_pandas', False)

        # Convert to pandas if requested
        if use_pandas:
            try:
                df = input_df.to_pandas()
            except Exception as e:
                raise RuntimeError(f"Failed to convert to pandas: {e}")
        else:
            df = input_df

        # Compile code (cached)
        compiled_code = self._compile_code()

        # Build execution env
        globals_dict = {
            '__builtins__': __builtins__,
            'df': df,
            'context': self.context,
            'pl': pl,
        }

        # Add routine manager namespace if available
        if self._routine_manager is not None:
            class RoutineNamespace:
                pass

            routines = RoutineNamespace()
            for routine_name in self._routine_manager.list_routines():
                module = self._routine_manager._modules.get(routine_name)
                if module:
                    setattr(routines, routine_name, module)

            globals_dict['routines'] = routines

        # Import additional modules
        for module_name in self.config.get('imports', []):
            try:
                globals_dict[module_name] = __import__(module_name)
            except ImportError:
                logger.warning(f"Failed to import {module_name}")

        # Add numpy if available
        try:
            import numpy as np
            globals_dict['np'] = np
        except ImportError:
            pass

        locals_dict = {}

        # Execute
        try:
            exec(compiled_code, globals_dict, locals_dict)
        except Exception as e:
            raise RuntimeError(f"PythonDataFrame execution failed: {e}")

        if 'output_df' not in locals_dict:
            raise RuntimeError("Code must set 'output_df' variable")

        output = locals_dict['output_df']

        # Convert output to Polars LazyFrame for downstream
        if isinstance(output, pl.LazyFrame):
            return {"main": output}
        elif isinstance(output, pl.DataFrame):
            return {"main": output.lazy()}
        else:
            # Try pandas conversion
            try:
                import pandas as pd
                if isinstance(output, pd.DataFrame):
                    return {"main": pl.from_pandas(output).lazy()}
            except ImportError:
                pass
            raise RuntimeError(
                f"'output_df' must be a DataFrame, got {type(output)}"
            )

    def _compile_code(self):
        if self._compiled_code is not None:
            return self._compiled_code
        code_str = self.config['code']
        if code_str in self._code_cache:
            self._compiled_code = self._code_cache[code_str]
            return self._compiled_code
        try:
            compiled = compile(code_str, f"<{self.component_id}>", 'exec')
            # Limit cache size
            if len(self._code_cache) > 100:
                self._code_cache.clear()
            self._code_cache[code_str] = compiled
            self._compiled_code = compiled
            return compiled
        except SyntaxError as e:
            raise ValueError(f"Syntax error in code: {e}")
