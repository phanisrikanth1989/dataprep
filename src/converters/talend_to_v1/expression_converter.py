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

        if ExpressionConverter._looks_like_file_path(value):
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
    def _looks_like_file_path(value: str) -> bool:
        """Return True for plain literal file/URL paths.

        Used to short-circuit Java-expression detection for values that are
        unambiguously paths, so that special characters inside file names
        (e.g. spaces, dots) do not trigger a false-positive
        ``{{java}}`` marker, etc.
        """
        path = value.strip()

        # Recognized shapes (no Java operators / quoting / parens around the
        # path itself):
        #
        # - Drive-letter absolute paths: "C:/foo/bar.txt", "D:\\x\\y"
        # - POSIX absolute paths: "/var/log/x.log"
        # - UNC paths: "\\\\server\\share\\file"
        # - URL-like locators: "http://", "https://", "ftp://",
        #   "file://"

        # A value is rejected if it contains characters that only appear in
        # Java/Groovy source -- quotes, parentheses, '+', '<' (concatenation),
        # a Talend ``context.``/``globalMap.`` reference. Hyphens, spaces,
        # underscores, dots and '*' inside file names are allowed.

        if not value:
            return False
        s = value.strip()
        if not s:
            return False
        # Reject anything that contains tokens that only appear in code,
        # not in literal paths.
        if re.search(r"['()+=&|<>]", s):
            return False
        if "context." in s or "globalMap." in s or "routines." in s:
            return False
        # Multi-line strings are never paths.
        if "\n" in s or "\r" in s:
            return False
        # URL-style.
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", s):
            return True
        # Drive-letter absolute path: C:/... or C:\...
        if re.match(r"^[A-Za-z]:[\\/]", s):
            return True
        
        # UNC path.

        if s.startswith("\\\\"):
            return True
        # POSIX absolute path: must contain at least one separator after
        # the leading '/', so we don't catch single-token Java identifiers
        # like '/'.
        if s.startswith("/") and "/" in s[1:]:
            return True

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
    def _find_receiver_start(s: str, end: int, lower_bound: int = 0) -> int:
        """Walk backwards from ``end`` to locate the start of the receiver
        expression that immediately precedes a method call.

        The receiver of a Java method call (e.g. the ``x`` in ``x.contains(y)``)
        can take several shapes that all need to be respected:

        - A plain identifier or dotted chain: ``foo``, ``obj.field.value``
        - A balanced parenthesised expression: ``((String)x)``
        - A method-call chain: ``routines.Util.parse(input).strip()``

        Walking the source backwards from the position of the trailing ``.``
        we accept characters that belong to such a receiver and stop as soon
        as we hit a token that cannot be part of one (whitespace before an
        operator, a ``;``, ``&&``, ``||``, the start of the slice, etc).

        Args:
            s: Full source string.
            end: Exclusive end position; ``s[end]`` is typically the ``.``
                of the trailing method call.
            lower_bound: Inclusive lower bound for the walk -- never look
                further left than this index.

        Returns:
            The inclusive start index of the receiver.
        """
        i = end - 1

        # Skip trailing whitespace.
        while i >= lower_bound and s[i].isspace():
            i -= 1
        while i >= lower_bound:
            ch = s[i]
            # Match the corresponding '(' by counting depth.
            if ch == ')':
                depth = 1
                i -= 1
                while i >= lower_bound and depth > 0:
                    if s[i] == ')':
                        depth += 1
                    elif s[i] == '(':
                        depth -= 1
                    i -= 1
                # If the parens were unbalanced we stop here (safety net).
                if depth != 0:
                    return i + 2
                # i now points to the char BEFORE the matching '('; continue
                # the outer loop in case the receiver is a chained call such
                # as ``foo.bar().baz()`` (we should consume ``foo.bar()`` too).
            elif ch.isalnum() or ch in "._":
                i -= 1
            else:
                break
        return i + 1


    @staticmethod
    def _convert_contains_calls(expression: str) -> str:
        """
        Convert every Java ``<receiver>.contains(<arg>)`` to Python
        ``<arg> in <receiver>``.

        Unlike a naive regex, this implementation is paren-aware: it walks
        backwards from each ``.contains(`` to identify the receiver and
        forwards through balanced parens to capture the argument. As a
        result it handles:

        - Multiple ``.contains()`` calls joined by ``&&`` / ``||``
        - Parenthesised receivers: ``((globalMap.get("k"))).contains("v")``
        - Method-chain receivers: ``foo.bar().contains("v")``
        - Arguments containing nested parens: ``x.contains(y(z))``

        Args:
            expression: Source expression (post cast/globalMap normalisation).

        Returns:
            Expression with ``.contains()`` calls rewritten in Python form.
        """
        if not expression or ".contains(" not in expression:
            return expression
            
        out: list[str] = []
        pos = 0
        n = len(expression)

        while pos < n:
            idx = expression.find(".contains(", pos)
            if idx == -1:
                out.append(expression[pos:])
                break
            # Locate the matching ')' for the .contains( argument list,
            # honouring nested parens inside the argument.
            arg_start = idx + len(".contains(")
            depth = 1
            j = arg_start
            while j < n and depth > 0:
                ch = expression[j]
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if depth != 0:
                # Unbalanced: emit the rest verbatim and stop.
                out.append(expression[pos:])
                break
            arg = expression[arg_start:j]
            # Walk backwards to delimit the receiver. We never look further
            # left than the end of the previous already-emitted segment
            # (``pos``) so prior clauses cannot be swallowed.
            receiver_start = ExpressionConverter._find_receiver_start(
                expression, idx, lower_bound=pos
            )
            receiver = expression[receiver_start:idx]
            # Emit the prefix that is NOT part of the receiver, then the
            # rewritten ``<arg> in <receiver>`` path.
            out.append(expression[pos:receiver_start])
            out.append(f"({arg} in ({receiver}))")
            # Advance past the ')'
            pos = j + 1

        return "".join(out)
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

        # Convert string methods.
        # equalsIgnoreCase MUST be rewritten before equals (shared 'equals' prefix).
        # The '.method(args)' form is matched as a whole so the trailing ')' is
        # consumed in the replacement -- native str.replace('.equals(', ...)
        # would otherwise leave a dangling ')'.
        # -> '"Y" == ${context.X}' Args are restricted to non-paren content
        #   ([^()]*) so simple Talend trigger conditions are rewritten cleanly;
        #   nested-call arguments fall through unchanged (and are flagged for
        #   manual review by trigger_mapper).

        expression = re.sub(r'\.equalsIgnoreCase\(([^()]*)\)', r'.lower() == str(\1).lower()', expression)
        expression = re.sub(r'\.equals\(([^()]*)\)', r' == \1', expression)

        # Java's <receiver>.contains(<arg>) tests whether <arg> is a substring
        # of <receiver> -- the Python equivalent is '<arg>' in <receiver>,
        # NOT the naive textual swap '<receiver>' in <arg>' (which inverts the
        # truth value because Python's 'a in b' tests if *a* is a substring of
        # *b*).
        #expression = re.sub(r'(.+?)\.contains\(([^()]*)\)', r'\2 in \1', expression)
        expression = ExpressionConverter._convert_contains_calls(expression)
        expression = expression.replace('.startsWith(', '.startswith(')
        expression = expression.replace('.endsWith(', '.endswith(')
        expression = expression.replace('.length()', '.__len__()')
        expression = expression.replace('.toLowerCase()', '.lower()')
        expression = expression.replace('.toUpperCase()', '.upper()')
        expression = expression.replace('.trim()', '.strip()')

        # Convert null checks (tolerate optional whitespace around the operator)
        expression = re.sub(r'!=\s*null\b', 'is not None', expression)
        expression = re.sub(r'==\s*null\b', 'is None', expression)
        expression = re.sub(r'\bnull\b', 'None', expression)

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
