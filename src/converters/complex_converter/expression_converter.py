"""
Expression converter for Talend/Java to Python
"""
import re


class ExpressionConverter:
    """Converts Talend/Java expressions to Python"""

    @staticmethod
    def detect_java_expression(value: str) -> bool:
        """
        Detect if a value contains Java/Groovy expressions that need Java execution.

        Returns True if the expression should be executed in Java.
        Returns False if it's a simple literal or already-resolved context reference.

        Args:
            value: The value/expression to check

        Returns:
            True if Java execution is needed, False otherwise
        """
        if not value or not isinstance(value, str):
            return False

        value = value.strip()

        # Skip empty strings
        if not value:
            return False

        # Already resolved context references (${...}) - Let ContextManager handle
        if value.startswith('${') and value.endswith('}'):
            return False

        # Check for Java-specific patterns

        # 1. Routine calls (with or without routines. prefix)
        if 'routines.' in value:
            return True

        # Static method calls with CamelCase class names (common routine pattern)
        # e.g., ValidationUtils.method(), StringHandling.method()
        if re.search(r'\b[A-Z]\w+\.\w+\s*\(', value):
            return True

        # 2. Method calls with parentheses (e.g., .method(), .substring())
        if re.search(r'\.\w+\s*\(', value):
            return True

        # 3. Unary operators (Java-specific)
        # ! (not), ~ (bitwise not), ++ (increment), -- (decrement)
        if re.search(r'![\w\(]', value):  # ! followed by word or (
            return True
        if re.search(r'~[\w\(]', value):  # ~ followed by word or (
            return True
        if '++' in value or '--' in value:
            return True

        # 4. Type casting (Java-specific)
        # e.g., (String)value, (Integer)count
        if re.search(r'\([A-Z]\w+\)\s*\w+', value):
            return True

        # 5. Java operators (arithmetic, comparison, logical, ternary)
        # Philosophy: If in doubt, mark as Java (aggressive detection)
        # Better to send to Java unnecessarily than to fail in Python
        java_operators = [
            r'\+',              # Addition: "1 + 2" or "1+2"
            r'-',               # Subtraction: "5 - 3" or "5-3"
            r'\*',              # Multiplication: "2 * 3" or "2*3"
            r'/',               # Division: "10 / 2" or "10/2"
            r'%',               # Modulo: "10 % 3" or "10%3"
            r'>',               # Greater than: "x > 5" or "x>5"
            r'<',               # Less than: "x < 10" or "x<10"
            r'>=',              # Greater or equal
            r'<=',              # Less or equal
            r'==',              # Equality
            r'!=',              # Not equal
            r'&&',              # Logical AND
            r'\|\|',            # Logical OR
            r'\?',              # Ternary operator
        ]

        # Be aggressive: if ANY operator is present, mark as Java
        # Exceptions: URLs, file paths, pure numbers, identifiers with hyphens
        for operator in java_operators:
            if re.search(operator, value):
                # Skip false positives for common patterns

                # Skip URLs and web paths
                if operator == '/' and (value.startswith('http://') or value.startswith('https://') or
                                        value.startswith('//') or value.startswith('ftp://')):
                    continue

                # Skip file system paths (start with / or drive letter or contain only path separators)
                if operator == '/' and (value.startswith('/') or re.match(r'^[A-Za-z]:[/\\]', value) or
                                        not re.search(r'[+\-"%><\?=&|!()]', value)):  # No other operators
                    continue

                # Skip negative numbers (just "-5" or "-5.2", nothing else)
                if operator == '-' and re.match(r'^-?\d+(\.\d+)?$', value.strip()):
                    continue

                # Skip identifiers with hyphens (encodings, UUIDs, etc.)
                # Examples: "UTF-8", "ISO-8859-15", "en-US", "550e8400-e29b-41d4-a716-446655440000"
                if operator == '-' and re.match(r'^[a-zA-Z0-9]+-[a-zA-Z0-9\-]+$', value.strip()):
                    # Check it's not a subtraction expression (has spaces around -)
                    if not re.search(r'\s-\s', value):
                        continue

                return True

        # 6. Raw context references (not wrapped in ${...})
        # But ONLY if they're part of an expression, not standalone
        # Standalone "context.var" should be wrapped as ${context.var} by ContextManager
        # But "context.var + something" is already caught by operators above
        # So we DON'T need to mark simple context.var as Java here
        # (This check is kept as a fallback, but operators above should catch complex expressions)

        # 7. GlobalMap access
        if 'globalMap.' in value:
            return True

        # 8. Java comments
        if '/*' in value or '//' in value:
            return True

        # 9. String concatenation with + (Java style)
        # But be careful: filepath="/data" should not trigger
        # Only if it's clear concatenation like: "file" + ".csv"
        if re.search(r'["\w]\s*\+\s*["\w]', value):
            return True

        # If none of the above patterns match, it's a simple literal
        return False

    @staticmethod
    def mark_java_expression(value: str) -> str:
        """
        Mark a value with {{java}} prefix if it needs Java execution.

        Args:
            value: The value/expression to potentially mark

        Returns:
            Original value prefixed with {{java}} if needed, otherwise unchanged
        """
        if not value or not isinstance(value, str):
            return value

        # Already marked?
        if value.startswith('{{java}}'):
            return value

        # Check if it needs Java execution
        if ExpressionConverter.detect_java_expression(value):
            return f'{{{{java}}}}{value}'

        return value

    @staticmethod
    def convert(expression: str) -> str:
        """
        Convert Talend/Java expression to Python

        Args:
            expression: Talend/Java expression

        Returns:
            Python expression
        """
        if not expression:
            return expression

        # Remove Java casting
        expression = re.sub(r'\(String\)\s*', '', expression)
        expression = re.sub(r'\(Integer\)\s*', '', expression)
        expression = re.sub(r'\(Double\)\s*', '', expression)
        expression = re.sub(r'\(Boolean\)\s*', '', expression)

        # Convert row references (row1.column -> df['column'])
        expression = re.sub(r'row(\d+)\.(\w+)', r"df['\2']", expression)

        # Convert context references
        expression = re.sub(r'context\.(\w+)', r"${context.\1}", expression)

        # Convert globalMap references
        expression = re.sub(r'globalMap\.get\("([^"]+)"\)', r"globalMap.get('\1')", expression)
        expression = re.sub(r'globalMap\.put\("([^"]+)",\s*([^)]+)\)', r"globalMap.put('\1', \2)", expression)

        # Convert string methods
        expression = expression.replace('.equals(', ' == ')
        expression = expression.replace('.equalsIgnoreCase(', '.lower() == str(')
        expression = expression.replace('.contains(', ' in ')
        expression = expression.replace('.startsWith(', '.startswith(')
        expression = expression.replace('.endsWith(', '.endswith(')
        expression = expression.replace('.length()', '.__len__()')
        expression = expression.replace('.toLowerCase()', '.lower()')
        expression = expression.replace('.toUpperCase()', '.upper()')
        expression = expression.replace('.trim()', '.strip()')

        # Convert null checks
        expression = expression.replace('!= null', 'is not None')
        expression = expression.replace('== null', 'is None')
        expression = expression.replace('null', 'None')

        # Convert logical operators
        expression = expression.replace('&&', ' and ')
        expression = expression.replace('||', ' or ')
        expression = expression.replace('!', ' not ')

        # Convert StringHandling functions
        expression = expression.replace('StringHandling.LEN(', 'len(')
        expression = expression.replace('StringHandling.UPCASE(', 'str(')
        expression = expression.replace('StringHandling.DOWNCASE(', 'str(')
        expression = expression.replace('StringHandling.TRIM(', 'str(')

        # Convert TalendDate functions
        expression = expression.replace('TalendDate.getCurrentDate()', 'datetime.now()')
        expression = expression.replace('TalendDate.getDate(', 'datetime.strptime(')

        # Convert Numeric functions
        expression = expression.replace('Numeric.round(', 'round(')
        expression = expression.replace('Numeric.abs(', 'abs(')

        return expression

    @staticmethod
    def convert_type(talend_type: str) -> str:
        """
        Convert Talend data type to Python type

        Args:
            talend_type: Talend type string

        Returns:
            Python type string
        """
        type_mapping = {
            'id_String': 'str',
            'id_Integer': 'int',
            'id_Long': 'int',
            'id_Double': 'float',
            'id_Float': 'float',
            'id_Boolean': 'bool',
            'id_Date': 'datetime',
            'id_BigDecimal': 'Decimal',
            'id_Object': 'object',
            'id_Character': 'str',
            'id_Byte': 'int',
            'id_Short': 'int'
        }
        return type_mapping.get(talend_type, 'str')
