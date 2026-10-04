# Python Routines Reference

The v2 engine supports Python routines - reusable functions that can be called directly from expressions. This is analogous to Talend's Java routines.

## Table of Contents

1. [Overview](#overview)
2. [Using Routines in Expressions](#using-routines-in-expressions)
3. [Built-in Routines](#built-in-routines)
4. [Creating Custom Routines](#creating-custom-routines)
5. [Best Practices](#best-practices)

---

## Overview

Routines are Python modules containing functions that can be called from expression strings using the `RoutineName.function()` syntax.

```
DemoRoutine.greet(name)
StringUtils.mask_string(ssn, 0, 4)
OrderManagement.calculate_discount(price, customer_type)
```

### Key Features

- **O(1) Lookup**: Functions are registered in a flat registry for instant access
- **Loaded Once**: Routines are loaded at engine startup, not per-row
- **Type Flexible**: Functions can return any type (string, number, boolean, etc.)
- **Null Safe**: Functions receive actual values, including `None` for nulls

---

## Using Routines in Expressions

### Basic Syntax

```
RoutineName.function_name(arg1, arg2, ...)
```

- `RoutineName`: PascalCase name derived from the Python module filename
- `function_name`: The function name within the module
- Arguments can be column references, literals, or other expressions

### Examples in Map Component

```json
{
    "type": "map",
    "config": {
        "outputs": [{
            "name": "main",
            "columns": [
                {"name": "greeting", "expression": "DemoRoutine.greet(customer_name)"},
                {"name": "clean_address", "expression": "StringUtils.clean_whitespace(address)"},
                {"name": "masked_ssn", "expression": "StringUtils.mask_string(ssn, 0, 4)"},
                {"name": "discount", "expression": "DemoRoutine.calculate_discount(price, 0.2)"}
            ]
        }]
    }
}
```

### Combining with Other Expressions

Routine results can be used in larger expressions:

```json
{
    "columns": [
        {
            "name": "final_price",
            "expression": "price - DemoRoutine.calculate_discount(price, discount_rate)"
        },
        {
            "name": "formatted_name",
            "expression": "UPPER(StringUtils.clean_whitespace(name))"
        }
    ]
}
```

---

## Built-in Routines

The engine includes example routines in `src/v2/routines/user/`.

### DemoRoutine

General-purpose demonstration functions.

| Function | Description | Example |
|----------|-------------|---------|
| `greet(name)` | Generate greeting | `DemoRoutine.greet("Alice")` → `"Hello, Alice!"` |
| `is_senior_male(age, gender)` | Check if senior male (60+) | `DemoRoutine.is_senior_male(65, "Male")` → `True` |
| `format_name(first, last, title)` | Format full name with title | `DemoRoutine.format_name("John", "Doe", "Dr.")` → `"Dr. John Doe"` |
| `calculate_discount(price, pct)` | Calculate discount amount | `DemoRoutine.calculate_discount(100, 0.2)` → `20.0` |

### StringUtils

String manipulation utilities.

| Function | Description | Example |
|----------|-------------|---------|
| `clean_whitespace(text)` | Normalize whitespace | `StringUtils.clean_whitespace("  hello   world  ")` → `"hello world"` |
| `extract_digits(text)` | Get only digits | `StringUtils.extract_digits("abc123def")` → `"123"` |
| `extract_alpha(text)` | Get only letters | `StringUtils.extract_alpha("abc123def")` → `"abcdef"` |
| `mask_string(text, keep_start, keep_end)` | Mask middle characters | `StringUtils.mask_string("1234567890", 0, 4)` → `"******7890"` |
| `to_snake_case(text)` | Convert to snake_case | `StringUtils.to_snake_case("HelloWorld")` → `"hello_world"` |
| `to_title_case(text)` | Convert to Title Case | `StringUtils.to_title_case("hello world")` → `"Hello World"` |
| `pad_left(text, width, char)` | Left pad string | `StringUtils.pad_left("42", 5, "0")` → `"00042"` |
| `pad_right(text, width, char)` | Right pad string | `StringUtils.pad_right("42", 5, "0")` → `"42000"` |

---

## Creating Custom Routines

### Step 1: Create Python File

Create a new file in `src/v2/routines/user/`:

```python
# src/v2/routines/user/order_utils.py
"""
OrderUtils - Order processing utility functions.
"""
from typing import Optional
from datetime import date


def calculate_tax(amount: float, rate: float = 0.08) -> float:
    """Calculate tax amount.

    Args:
        amount: Base amount
        rate: Tax rate (default: 0.08 = 8%)

    Returns:
        Tax amount
    """
    if amount is None:
        return 0.0
    return round(amount * rate, 2)


def format_currency(amount: float, symbol: str = "$") -> str:
    """Format amount as currency string.

    Args:
        amount: Numeric amount
        symbol: Currency symbol (default: $)

    Returns:
        Formatted string like "$1,234.56"
    """
    if amount is None:
        return f"{symbol}0.00"
    return f"{symbol}{amount:,.2f}"


def is_valid_email(email: str) -> bool:
    """Check if email has valid format.

    Args:
        email: Email address string

    Returns:
        True if valid format
    """
    if email is None:
        return False
    return "@" in email and "." in email.split("@")[-1]


def days_until(target_date: date) -> int:
    """Calculate days until target date.

    Args:
        target_date: Target date

    Returns:
        Number of days (negative if past)
    """
    if target_date is None:
        return 0
    return (target_date - date.today()).days
```

### Step 2: Use in Expressions

The routine is automatically loaded. The class name is derived from the filename:
- `order_utils.py` → `OrderUtils`

```json
{
    "columns": [
        {"name": "tax", "expression": "OrderUtils.calculate_tax(subtotal, 0.08)"},
        {"name": "total_formatted", "expression": "OrderUtils.format_currency(total)"},
        {"name": "email_valid", "expression": "OrderUtils.is_valid_email(customer_email)"},
        {"name": "days_to_ship", "expression": "OrderUtils.days_until(ship_date)"}
    ]
}
```

### Naming Convention

| File Name | Routine Name |
|-----------|--------------|
| `my_routine.py` | `MyRoutine` |
| `string_utils.py` | `StringUtils` |
| `order_management.py` | `OrderManagement` |
| `demo_routine.py` | `DemoRoutine` |

The conversion is:
1. Remove `.py` extension
2. Split on underscores
3. Capitalize each part
4. Join without separator

### Function Requirements

1. **Regular functions only** - No classes or decorators needed
2. **Type hints recommended** - Helps documentation and IDE support
3. **Handle None** - Check for null inputs if the function can receive them
4. **Return single value** - Not generators or complex objects

```python
# Good
def calculate(amount: float, rate: float) -> float:
    if amount is None:
        return 0.0
    return amount * rate

# Bad - Don't use classes
class Calculator:
    def calculate(self, amount, rate):
        return amount * rate

# Bad - Don't use generators
def process_items(items):
    for item in items:
        yield item * 2
```

---

## Best Practices

### 1. Handle Null Values

Always check for `None` since column values can be null:

```python
def safe_upper(text: str) -> str:
    if text is None:
        return ""
    return text.upper()
```

### 2. Use Type Hints

Type hints improve code clarity and IDE support:

```python
def calculate_discount(
    price: float,
    discount_percent: float,
    max_discount: float = 100.0
) -> float:
    """Calculate discount with optional cap."""
    ...
```

### 3. Write Docstrings

Document what the function does:

```python
def mask_pii(value: str, visible_chars: int = 4) -> str:
    """Mask personally identifiable information.

    Args:
        value: The string to mask
        visible_chars: Number of characters to keep visible at end

    Returns:
        Masked string with asterisks

    Example:
        mask_pii("123-45-6789", 4) -> "*****6789"
    """
```

### 4. Keep Functions Pure

Functions should not have side effects:

```python
# Good - pure function
def add_tax(amount: float, rate: float) -> float:
    return amount * (1 + rate)

# Bad - side effects
_cache = {}
def add_tax_cached(amount: float, rate: float) -> float:
    key = (amount, rate)
    if key not in _cache:
        _cache[key] = amount * (1 + rate)  # Modifies global state
    return _cache[key]
```

### 5. Performance Considerations

- Functions are called **per row** - keep them lightweight
- Avoid I/O operations (file reads, network calls)
- For complex logic on large datasets, consider using Polars expressions or PythonDataFrame component instead

```python
# Fast - simple calculation
def calculate_total(quantity: int, unit_price: float) -> float:
    return quantity * unit_price

# Slow - avoid in routines
def lookup_price(product_id: str) -> float:
    import requests  # Don't do this!
    response = requests.get(f"http://api/prices/{product_id}")
    return response.json()["price"]
```

---

## Architecture

### RoutineManager

Loads routines from the configured directory at engine startup:

```python
from v2.routines import RoutineManager

manager = RoutineManager()
manager.list_routines()     # ['DemoRoutine', 'StringUtils']
manager.list_functions('DemoRoutine')  # ['greet', 'is_senior_male', ...]
```

### RoutineRegistry

Provides O(1) lookup for the expression compiler:

```python
registry = manager.get_registry()
func = registry.get('DemoRoutine', 'greet')
result = func('World')  # "Hello, World!"
```

### Integration with Expression Compiler

The expression compiler uses the registry to resolve routine calls:

```python
from v2.expressions import ExpressionCompiler

compiler = ExpressionCompiler(
    context={'tax_rate': 0.08},
    routine_registry=manager.get_registry()
)

expr = compiler.compile("DemoRoutine.greet(name)")
```
