"""
RowGenerator component - Generates synthetic rows based on expressions or random values.
Equivalent to Talend's tRowGenerator component.

Configuration:
    nb_rows (int or str): Number of rows to generate (supports context variable)
    values (list): List of dicts with keys:
        - schema_column (str): Output column name
        - array (str): Expression or random value generator (hex-encoded in Talend XML)

Inputs:
    None (source component)

Outputs:
    main: Generated DataFrame as per schema
    reject: DataFrame of failed rows (if any)

Example:
    {
        "type": "RowGenerator",
        "config": {
            "nb_rows": 100,
            "values": [
                {"schema_column": "id", "array": "random.randint(1, 1000)"},
                {"schema_column": "name", "array": "'Name_' + str(random.randint(1, 100))"}
            ]
        },
        "schema": {
            "output": [
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"}
            ]
        }
    }
"""
import pandas as pd
import random
import binascii
import logging
import re
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

class RowGenerator(BaseComponent):
    def _eval_talend_expr(self, expr, context):
        """
        Evaluate Talend-style string expressions with context and StringHandling support.
        Supports:
            - context.<var>
            - StringHandling.SPACE(n)
            - StringHandling.LEN(str)
            - + for string concatenation
        """
        # Replace context variables
        def context_repl(match):
            var = match.group(1)
            return str(context.get(var, ''))
        expr = re.sub(r'context\.([A-Za-z0-9_]+)', context_repl, expr)

        # Replace StringHandling.LEN(str)
        def len_repl(match):
            arg = match.group(1)
            arg_val = arg
            if arg.startswith('"') and arg.endswith('"'):
                arg_val = arg[1:-1]
            elif arg.startswith("'") and arg.endswith("'"):
                arg_val = arg[1:-1]
            else:
                arg_val = context.get(arg, arg)
            return str(len(str(arg_val)))
        expr = re.sub(r'StringHandling\.LEN\(([^\)]+)\)', len_repl, expr)

        # Replace StringHandling.SPACE(n)
        def space_repl(match):
            n = match.group(1)
            try:
                n_eval = eval(n, {}, {})
                return ' ' * int(n_eval)
            except Exception:
                return ''
        expr = re.sub(r'StringHandling\.SPACE\(([^\)]+)\)', space_repl, expr)

        # Restore previous logic: split by '+' and join, then replace newlines
        parts = [part.strip() for part in re.split(r'\s*\+\s*', expr)]
        result = ''.join(parts)
        # Replace all escaped and literal newlines with actual newlines (generic)
        result = re.sub(r'(\\r\\n|\\n|\r\n|\n)', '\n', result)
        # Remove all double quotes (generic, no hardcoding)
        result = result.replace('"', '')
        return result

    def _process(self, input_data=None):
        print(f"[RowGenerator] Starting row generation for component: {self.id}")
        nb_rows = self.config.get('nb_rows', 1)
        print(f"[RowGenerator] nb_rows (raw): {nb_rows}")
        if isinstance(nb_rows, str):
            try:
                nb_rows = int(nb_rows)
                print(f"[RowGenerator] nb_rows (converted to int): {nb_rows}")
            except ValueError:
                if self.context_manager:
                    nb_rows = self.context_manager.resolve_string(nb_rows)
                    nb_rows = int(nb_rows)
                    print(f"[RowGenerator] nb_rows (resolved from context): {nb_rows}")
                else:
                    nb_rows = 1
                    print(f"[RowGenerator] nb_rows (defaulted to 1)")
        values = self.config.get('values', [])
        print(f"[RowGenerator] values config: {values}")
        output_schema = self.config.get('schema', {}).get('output', [])
        print(f"[RowGenerator] output_schema: {output_schema}")
        columns = [v.get('schema_column') for v in values]
        exprs = [v.get('array') for v in values]
        print(f"[RowGenerator] columns: {columns}")
        print(f"[RowGenerator] exprs: {exprs}")

        def decode_if_hex(val):
            try:
                if isinstance(val, str) and all(c in '0123456789abcdefABCDEF' for c in val) and len(val) % 2 == 0:
                    decoded = binascii.unhexlify(val).decode('utf-8')
                    print(f"[RowGenerator] Decoded hex expression: {val} -> {decoded}")
                    return decoded
            except Exception as ex:
                print(f"[RowGenerator] Error decoding hex: {ex}")
            return val
        exprs = [decode_if_hex(e) for e in exprs]
        data = []
        rejects = []
        for i in range(nb_rows):
            print(f"[RowGenerator] Generating row {i}")
            row = {}
            reject_row = False
            for col, expr in zip(columns, exprs):
                print(f"[RowGenerator] Generating value for column '{col}' with expr '{expr}'")
                try:
                    context = {}
                    if self.context_manager:
                        context = self.context_manager.get_all()
                        print(f"[RowGenerator] Context for row {i}: {context}")
                    if (
                        'context.' in expr or
                        'StringHandling.SPACE' in expr or
                        'StringHandling.LEN' in expr
                    ):
                        value = self._eval_talend_expr(expr, context)
                        print(f"[RowGenerator] Talend-style eval result for '{col}': {value}")
                    else:
                        try:
                            value = eval(expr, {"random": random, "context": context})
                            print(f"[RowGenerator] Python eval result for '{col}': {value}")
                        except SyntaxError:
                            value = expr
                            print(f"[RowGenerator] SyntaxError for '{col}', assigning literal value: {value}")
                            logger.warning(f"RowGenerator: SyntaxError for column '{col}' in row {i}, assigning literal value.")
                    row[col] = value
                except Exception as e:
                    print(f"[RowGenerator] ERROR generating value for column '{col}' in row {i}: {e}")
                    logger.error(f"RowGenerator: Failed to generate value for column '{col}' in row {i}: {e}")
                    row[col] = None
                    reject_row = True
            print(f"[RowGenerator] Generated row {i}: {row}")
            if reject_row:
                print(f"[RowGenerator] Row {i} rejected: {row}")
                rejects.append(row)
            else:
                data.append(row)
        print(f"[RowGenerator] Total rows generated: {len(data)}")
        print(f"[RowGenerator] Total rows rejected: {len(rejects)}")
        df = pd.DataFrame(data, columns=columns)
        reject_df = pd.DataFrame(rejects, columns=columns) if rejects else pd.DataFrame(columns=columns)
        print(f"[RowGenerator] DataFrame shape: {df.shape}")
        print(f"[RowGenerator] Reject DataFrame shape: {reject_df.shape}")
        df = self.validate_schema(df, output_schema)
        reject_df = self.validate_schema(reject_df, output_schema)
        self._update_stats(rows_read=nb_rows, rows_ok=len(df), rows_reject=len(reject_df))
        print(f"[RowGenerator] Finished row generation for component: {self.id}")
        return {'main': df, 'reject': reject_df}

    def validate_config(self) -> bool:
        required = ['nb_rows', 'values']
        for param in required:
            if param not in self.config:
                logger.error(f"RowGenerator: Missing required parameter: {param}")
                return False
        if not isinstance(self.config['values'], list):
            logger.error(f"RowGenerator: 'values' must be a list")
            return False
        return True
