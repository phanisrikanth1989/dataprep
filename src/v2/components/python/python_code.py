"""PythonCode Component for V2 engine."""
import logging
from typing import Any, Dict, List

import polars as pl

from ..base import PythonComponent
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("python_code")
class PythonCode(PythonComponent):
    """
    Execute arbitrary Python code with DataFrame access.

    Code has access to: input_df (Polars DataFrame), context (dict), pl (Polars module)
    Code MUST set output_df to the result DataFrame.

    Config:
        code: str - Python code to execute (required)
        imports: list - Additional modules to import (optional)
    """

    # Class-level code cache (shared across instances)
    _code_cache: Dict[str, Any] = {}

    def _post_init(self):
        self._compiled_code = None

    def validate(self) -> List[str]:
        errors = []
        if 'code' not in self.config:
            errors.append("Missing required configuration: 'code'")
        elif not isinstance(self.config['code'], str):
            errors.append("'code' must be a string")
        elif not self.config['code'].strip():
            errors.append("'code' cannot be empty")
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

        # Compile code (cached)
        compiled_code = self._compile_code()

        # Build execution env
        globals_dict = {
            '__builtins__': __builtins__,
            'input_df': input_df,
            'context': self.context,
            'pl': pl,
        }
        # Import additional modules
        for module_name in self.config.get('imports', []):
            try:
                globals_dict[module_name] = __import__(module_name)
            except ImportError:
                logger.warning(f"Failed to import {module_name}")

        locals_dict = {}

        # Execute
        try:
            exec(compiled_code, globals_dict, locals_dict)
        except Exception as e:
            raise RuntimeError(f"PythonCode execution failed: {e}")

        if 'output_df' not in locals_dict:
            raise RuntimeError("Code must set 'output_df' variable")

        output = locals_dict['output_df']

        # Ensure result is a LazyFrame for downstream
        if isinstance(output, pl.LazyFrame):
            return {"main": output}
        elif isinstance(output, pl.DataFrame):
            return {"main": output.lazy()}
        else:
            raise RuntimeError(f"'output_df' must be a Polars DataFrame, got {type(output)}")

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
