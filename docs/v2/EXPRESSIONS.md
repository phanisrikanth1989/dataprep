# Expression DSL Reference

The v2 engine includes a powerful expression language for defining column transformations, filter conditions, and computed values.

## Table of Contents

1. [Basic Syntax](#basic-syntax)
2. [Data References](#data-references)
3. [Operators](#operators)
4. [Functions](#functions)
5. [Python Routines](#python-routines)
6. [Conditionals](#conditionals)
7. [Examples](#examples)

---

## Basic Syntax

Expressions are strings that define computations on columns. They're used in:

- **Map component**: Column expressions
- **Filter component**: Filter conditions
- **Aggregate component**: Group by expressions

```json
{
    "name": "total_price",
    "expression": "quantity * unit_price * (1 + context.tax_rate)"
}
```

---

## Data References

### Column References

Reference columns directly by name:

```
amount
customer_name
order_id
```

Or with explicit `row.` prefix:

```
row.amount
row.customer_name
```

### Context Variables

Access shared context variables:

```
context.tax_rate
context.processing_date
context.threshold
```

Context variables are defined at the job level:

```json
{
    "context": {
        "tax_rate": {"value": 0.08, "type": "float"},
        "threshold": {"value": 100, "type": "integer"}
    }
}
```

### Literals

| Type | Examples |
|------|----------|
| String | `'hello'`, `"world"` |
| Integer | `42`, `-10`, `0` |
| Float | `3.14`, `-0.5`, `1.0` |
| Boolean | `true`, `false` |
| Null | `null` |

---

## Operators

### Arithmetic Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `+` | Addition | `price + tax` |
| `-` | Subtraction | `total - discount` |
| `*` | Multiplication | `quantity * price` |
| `/` | Division | `amount / count` |
| `%` | Modulo | `id % 10` |

### Comparison Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equal | `status == 'active'` |
| `!=` | Not equal | `category != 'test'` |
| `<` | Less than | `amount < 100` |
| `<=` | Less or equal | `score <= 50` |
| `>` | Greater than | `count > 0` |
| `>=` | Greater or equal | `age >= 18` |

### Logical Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `&&` | AND | `active && verified` |
| `\|\|` | OR | `admin \|\| moderator` |
| `!` | NOT | `!deleted` |

### Operator Precedence

From highest to lowest:
1. `!` (NOT), `-` (unary minus)
2. `*`, `/`, `%`
3. `+`, `-`
4. `<`, `<=`, `>`, `>=`
5. `==`, `!=`
6. `&&` (AND)
7. `||` (OR)
8. `? :` (ternary)

Use parentheses to override: `(a + b) * c`

---

## Functions

### String Functions

| Function | Description | Example |
|----------|-------------|---------|
| `UPPER(str)` | Convert to uppercase | `UPPER(name)` → `"JOHN"` |
| `LOWER(str)` | Convert to lowercase | `LOWER(name)` → `"john"` |
| `TRIM(str)` | Remove leading/trailing whitespace | `TRIM(input)` |
| `LTRIM(str)` | Remove leading whitespace | `LTRIM(input)` |
| `RTRIM(str)` | Remove trailing whitespace | `RTRIM(input)` |
| `LENGTH(str)` | String length in characters | `LENGTH(name)` → `4` |
| `CONCAT(s1, s2, ...)` | Concatenate strings | `CONCAT(first, ' ', last)` |
| `SUBSTRING(str, start, len)` | Extract substring | `SUBSTRING(code, 0, 3)` |
| `REPLACE(str, find, repl)` | Replace all occurrences | `REPLACE(text, 'old', 'new')` |
| `LEFT(str, n)` | First n characters | `LEFT(code, 2)` |
| `RIGHT(str, n)` | Last n characters | `RIGHT(code, 4)` |
| `CONTAINS(str, substr)` | Check if contains | `CONTAINS(desc, 'urgent')` |
| `STARTS_WITH(str, prefix)` | Check prefix | `STARTS_WITH(code, 'PRD')` |
| `ENDS_WITH(str, suffix)` | Check suffix | `ENDS_WITH(file, '.csv')` |

**NULL Handling**: For `CONCAT`, NULL values are treated as empty strings:
```
CONCAT(first_name, ' ', middle_name, ' ', last_name)
// If middle_name is NULL: "John  Doe" (double space)
```

### Numeric Functions

| Function | Description | Example |
|----------|-------------|---------|
| `ABS(n)` | Absolute value | `ABS(-5)` → `5` |
| `ROUND(n)` | Round to nearest integer | `ROUND(3.7)` → `4` |
| `ROUND(n, decimals)` | Round to decimal places | `ROUND(3.14159, 2)` → `3.14` |
| `FLOOR(n)` | Round down | `FLOOR(3.9)` → `3` |
| `CEIL(n)` | Round up | `CEIL(3.1)` → `4` |
| `SQRT(n)` | Square root | `SQRT(16)` → `4` |
| `POW(base, exp)` | Power | `POW(2, 3)` → `8` |
| `LOG(n)` | Natural logarithm | `LOG(2.718)` → `1` |
| `EXP(n)` | e^n | `EXP(1)` → `2.718` |
| `SIGN(n)` | Sign (-1, 0, or 1) | `SIGN(-5)` → `-1` |

### Null Handling Functions

| Function | Description | Example |
|----------|-------------|---------|
| `COALESCE(v1, v2, ...)` | First non-null value | `COALESCE(phone, mobile, 'N/A')` |
| `IFNULL(v, default)` | Default if null | `IFNULL(amount, 0)` |
| `ISNULL(v)` | Check if null | `ISNULL(email)` |
| `ISNOTNULL(v)` | Check if not null | `ISNOTNULL(phone)` |
| `NULLIF(v1, v2)` | NULL if equal | `NULLIF(value, 0)` |

### Conditional Functions

| Function | Description | Example |
|----------|-------------|---------|
| `IF(cond, then, else)` | Conditional | `IF(age >= 18, 'adult', 'minor')` |

### Type Conversion Functions

| Function | Description | Example |
|----------|-------------|---------|
| `TO_STRING(v)` | Convert to string | `TO_STRING(id)` |
| `TO_INTEGER(v)` | Convert to integer | `TO_INTEGER(amount)` |
| `TO_FLOAT(v)` | Convert to float | `TO_FLOAT(price)` |
| `TO_BOOLEAN(v)` | Convert to boolean | `TO_BOOLEAN(flag)` |

### Date Functions

| Function | Description | Example |
|----------|-------------|---------|
| `YEAR(date)` | Extract year | `YEAR(order_date)` → `2024` |
| `MONTH(date)` | Extract month (1-12) | `MONTH(order_date)` → `6` |
| `DAY(date)` | Extract day (1-31) | `DAY(order_date)` → `15` |
| `HOUR(datetime)` | Extract hour (0-23) | `HOUR(timestamp)` → `14` |
| `MINUTE(datetime)` | Extract minute (0-59) | `MINUTE(timestamp)` → `30` |
| `SECOND(datetime)` | Extract second (0-59) | `SECOND(timestamp)` → `45` |

### Aggregate Functions

Used within the Aggregate component:

| Function | Description | Example |
|----------|-------------|---------|
| `SUM(col)` | Sum of values | `SUM(amount)` |
| `COUNT(col)` | Count of values | `COUNT(id)` |
| `AVG(col)` | Average | `AVG(score)` |
| `MIN(col)` | Minimum | `MIN(price)` |
| `MAX(col)` | Maximum | `MAX(price)` |
| `FIRST(col)` | First value | `FIRST(name)` |
| `LAST(col)` | Last value | `LAST(timestamp)` |

---

## Python Routines

The v2 engine supports calling external Python functions (routines) directly in expressions. This is similar to Talend's Java routine support.

### Syntax

Call routines using the `RoutineName.function()` pattern:

```
DemoRoutine.greet(name)
StringUtils.clean_whitespace(text)
OrderManagement.calculate_discount(price, customer_type)
```

### Built-in Routines

The engine loads routines from `src/v2/routines/user/`. Two example routines are provided:

#### DemoRoutine

| Function | Description | Example |
|----------|-------------|---------|
| `greet(name)` | Generate greeting | `DemoRoutine.greet(name)` → `"Hello, John!"` |
| `is_senior_male(age, gender)` | Check if senior male | `DemoRoutine.is_senior_male(age, gender)` |
| `format_name(first, last, title)` | Format full name | `DemoRoutine.format_name(first, last, "Dr.")` |
| `calculate_discount(price, pct)` | Apply discount | `DemoRoutine.calculate_discount(100, 20)` → `80.0` |

#### StringUtils

| Function | Description | Example |
|----------|-------------|---------|
| `clean_whitespace(text)` | Normalize whitespace | `StringUtils.clean_whitespace(input)` |
| `extract_digits(text)` | Get only digits | `StringUtils.extract_digits(phone)` |
| `extract_alpha(text)` | Get only letters | `StringUtils.extract_alpha(code)` |
| `mask_string(text, keep_start, keep_end)` | Mask string | `StringUtils.mask_string(ssn, 0, 4)` |
| `to_snake_case(text)` | Convert to snake_case | `StringUtils.to_snake_case("HelloWorld")` |
| `to_title_case(text)` | Convert to Title Case | `StringUtils.to_title_case("hello world")` |
| `pad_left(text, width, char)` | Left pad string | `StringUtils.pad_left("42", 5, "0")` → `"00042"` |
| `pad_right(text, width, char)` | Right pad string | `StringUtils.pad_right("42", 5, "0")` → `"42000"` |

### Creating Custom Routines

1. Create a Python file in `src/v2/routines/user/`:

```python
# src/v2/routines/user/my_routine.py
"""
My Custom Routine - Custom transformation functions.
"""

def calculate_tax(amount: float, rate: float) -> float:
    """Calculate tax amount."""
    return amount * rate

def format_currency(amount: float, symbol: str = "$") -> str:
    """Format amount as currency."""
    return f"{symbol}{amount:,.2f}"

def is_valid_email(email: str) -> bool:
    """Check if email is valid."""
    if email is None:
        return False
    return "@" in email and "." in email.split("@")[-1]
```

2. Use in expressions:

```
MyRoutine.calculate_tax(amount, 0.08)
MyRoutine.format_currency(total, "$")
MyRoutine.is_valid_email(email)
```

### Performance Notes

- Routines are loaded **once** at engine startup
- Function lookups are **O(1)** via flat registry
- Code is compiled once and cached
- For best performance with large datasets, use vectorized Polars operations when possible

### Expression Examples with Routines

```json
{
    "columns": [
        {"name": "greeting", "expression": "DemoRoutine.greet(customer_name)"},
        {"name": "clean_address", "expression": "StringUtils.clean_whitespace(address)"},
        {"name": "masked_ssn", "expression": "StringUtils.mask_string(ssn, 0, 4)"},
        {"name": "is_senior", "expression": "DemoRoutine.is_senior_male(age, gender)"}
    ]
}
```

---

## Conditionals

### Ternary Operator

```
condition ? then_value : else_value
```

Examples:

```
// Simple condition
status == 'active' ? 'Yes' : 'No'

// Nested ternary
score >= 90 ? 'A' : (score >= 80 ? 'B' : 'C')

// Numeric result
amount > 1000 ? amount * 0.9 : amount
```

### IF Function

```
IF(condition, then_value, else_value)
```

Examples:

```
IF(age >= 18, 'adult', 'minor')
IF(balance < 0, 'overdrawn', 'ok')
IF(ISNULL(email), 'No email', email)
```

---

## Examples

### Basic Column Transformations

```json
{
    "columns": [
        {"name": "id", "expression": "id"},
        {"name": "full_name", "expression": "CONCAT(first_name, ' ', last_name)"},
        {"name": "email_lower", "expression": "LOWER(TRIM(email))"},
        {"name": "total", "expression": "quantity * unit_price"},
        {"name": "with_tax", "expression": "total * (1 + context.tax_rate)"}
    ]
}
```

### Complex Business Logic

```json
{
    "columns": [
        {
            "name": "customer_segment",
            "expression": "total_orders >= 100 ? 'platinum' : (total_orders >= 50 ? 'gold' : 'standard')"
        },
        {
            "name": "discount_rate",
            "expression": "IF(customer_segment == 'platinum', 0.15, IF(customer_segment == 'gold', 0.10, 0.05))"
        },
        {
            "name": "final_price",
            "expression": "base_price * (1 - discount_rate)"
        }
    ]
}
```

### Filter Conditions

```json
{
    "type": "filter",
    "config": {
        "condition": "status == 'active' && amount > 100 && !ISNULL(email)"
    }
}
```

```json
{
    "type": "filter",
    "config": {
        "condition": "YEAR(order_date) == 2024 && CONTAINS(category, 'electronics')"
    }
}
```

### Null Handling

```json
{
    "columns": [
        {"name": "display_name", "expression": "COALESCE(nickname, first_name, 'Unknown')"},
        {"name": "phone", "expression": "IFNULL(mobile, IFNULL(home_phone, 'N/A'))"},
        {"name": "has_email", "expression": "ISNOTNULL(email)"},
        {"name": "division_safe", "expression": "IF(denominator != 0, numerator / denominator, 0)"}
    ]
}
```

### String Manipulation

```json
{
    "columns": [
        {"name": "initials", "expression": "CONCAT(LEFT(first_name, 1), LEFT(last_name, 1))"},
        {"name": "domain", "expression": "SUBSTRING(email, CONTAINS(email, '@') ? LENGTH(LEFT(email, CONTAINS(email, '@'))) : 0, LENGTH(email))"},
        {"name": "clean_code", "expression": "UPPER(TRIM(REPLACE(product_code, '-', '')))"}
    ]
}
```

### Date Calculations

```json
{
    "columns": [
        {"name": "order_year", "expression": "YEAR(order_date)"},
        {"name": "order_month", "expression": "MONTH(order_date)"},
        {"name": "is_q4", "expression": "MONTH(order_date) >= 10"},
        {"name": "hour_of_day", "expression": "HOUR(created_at)"},
        {"name": "is_business_hours", "expression": "HOUR(created_at) >= 9 && HOUR(created_at) < 17"}
    ]
}
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Unknown function: X` | Function not supported | Check function name spelling |
| `Unknown context variable: X` | Variable not defined | Define in job `context` section |
| `Unknown operator: X` | Invalid operator | Use supported operators |
| `CONCAT requires at least 2 arguments` | Too few arguments | Provide multiple values |

### Type Mismatches

The expression compiler will raise errors for invalid operations:

```
// Error: Cannot add string and number
name + 5

// Fix: Convert to same type
TO_INTEGER(name) + 5
// or
name + TO_STRING(5)
```

### Division by Zero

Always guard against division by zero:

```
// Unsafe
amount / count

// Safe
count != 0 ? amount / count : 0

// Or using IF
IF(count != 0, amount / count, 0)
```
