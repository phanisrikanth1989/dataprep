# tJavaRow Migration Guide

How to convert Talend `tJavaRow` components to the V2 Polars-based engine. Covers component selection, Java-to-Python patterns, and performance optimization.

## Table of Contents

1. [Choosing the Right V2 Component](#choosing-the-right-v2-component)
2. [Decomposing a tJavaRow](#decomposing-a-tjavarow)
3. [Java to V2 Expression Patterns](#java-to-v2-expression-patterns)
4. [Performance Optimization with Polars](#performance-optimization-with-polars)
5. [Migrating Java Routines](#migrating-java-routines)
6. [Common Pitfalls](#common-pitfalls)

---

## Choosing the Right V2 Component

A Talend `tJavaRow` processes data row-by-row in Java. The V2 engine offers several alternatives, each with different performance characteristics. The key insight: **most tJavaRow code doesn't actually need row-by-row processing**.

### Decision Framework

```
Analyze each line/block of Java code:
│
├── Column transformation (toUpperCase, trim, substring, concat)?
│   └── Map component with expression DSL (FASTEST - stays lazy)
│
├── Conditional column assignment (if/else → set value)?
│   └── Map component with CASE WHEN expression (FASTEST - stays lazy)
│
├── Type conversion (parseInt, parseDouble, toString)?
│   └── Map component with TO_INTEGER/TO_FLOAT/TO_STRING (FASTEST - stays lazy)
│
├── Math operations (arithmetic, rounding, abs)?
│   └── Map component with expression DSL (FASTEST - stays lazy)
│
├── Row filtering (if condition → skip row)?
│   └── Filter component (FAST - stays lazy)
│
├── Reusable business logic (discount calc, validation)?
│   └── Python routine called from Map expression
│       Vectorize if possible (Tier 1) for near-native speed
│
├── Complex multi-step DataFrame transformation?
│   └── python_code or python_dataframe (barrier, but DataFrame-level)
│
├── External API call or DB lookup per row?
│   └── python_row vectorized mode with batching (barrier, slowest)
│
└── Stateful accumulation across rows?
    └── python_code with DataFrame operations (barrier)
```

### Performance Tiers

| Tier | V2 Approach | Barrier? | Relative Speed | When to Use |
|------|------------|----------|---------------|-------------|
| 1 | Map/Filter with expression DSL | No (lazy) | 1000x | Column transforms, math, string ops, conditionals |
| 2 | Map with Tier 1 vectorized routine | No (lazy) | 500x | Reusable batch logic operating on `pl.Series` |
| 3 | Map with Tier 2 scalar routine | No (lazy*) | 10x | Custom per-row logic callable from expressions |
| 4 | `python_code` / `python_dataframe` | Yes | 100-1000x** | Complex DataFrame-level operations |
| 5 | `python_row` (vectorized) | Yes | 2-10x | Batched row processing, external calls |
| 6 | `python_row` (scalar) | Yes | 1x (baseline) | True row-by-row, error routing needed |

*Tier 3 uses `map_elements` internally (per-row Python) but doesn't force a barrier.*
**Depends on what the Python code does -- Polars operations within `python_code` can be very fast.*

---

## Decomposing a tJavaRow

A 360-line `tJavaRow` often mixes concerns that should be separate V2 components.

### Before (Talend tJavaRow, single component)

```java
// Lines 1-5: String transforms
output_row.full_name = input_row.first_name.trim() + " " + input_row.last_name.trim().toUpperCase();
output_row.email = input_row.email.toLowerCase().trim();

// Lines 6-10: Type conversion
output_row.amount = Double.parseDouble(input_row.amount_str);
output_row.quantity = Integer.parseInt(input_row.qty_str);

// Lines 11-20: Business logic
if (output_row.amount > 1000) {
    output_row.category = "premium";
    output_row.discount = output_row.amount * 0.15;
} else if (output_row.amount > 100) {
    output_row.category = "standard";
    output_row.discount = output_row.amount * 0.05;
} else {
    output_row.category = "basic";
    output_row.discount = 0;
}

// Lines 21-25: Date calculation
output_row.days_since = (int)((System.currentTimeMillis() - input_row.order_date.getTime()) / 86400000);

// Lines 26-30: Validation
output_row.is_valid = input_row.email != null && input_row.email.contains("@");
```

### After (V2 Map component, zero Python needed)

All 30 lines translate to a single Map with expressions, running at native Polars speed:

```json
{
    "type": "map",
    "config": {
        "outputs": [{
            "name": "main",
            "columns": [
                {
                    "name": "full_name",
                    "expression": "CONCAT(TRIM(first_name), ' ', UPPER(TRIM(last_name)))"
                },
                {
                    "name": "email",
                    "expression": "LOWER(TRIM(email))"
                },
                {
                    "name": "amount",
                    "expression": "TO_FLOAT(amount_str)"
                },
                {
                    "name": "quantity",
                    "expression": "TO_INTEGER(qty_str)"
                },
                {
                    "name": "category",
                    "expression": "CASE WHEN TO_FLOAT(amount_str) > 1000 THEN 'premium' WHEN TO_FLOAT(amount_str) > 100 THEN 'standard' ELSE 'basic' END"
                },
                {
                    "name": "discount",
                    "expression": "CASE WHEN TO_FLOAT(amount_str) > 1000 THEN TO_FLOAT(amount_str) * 0.15 WHEN TO_FLOAT(amount_str) > 100 THEN TO_FLOAT(amount_str) * 0.05 ELSE 0 END"
                },
                {
                    "name": "days_since",
                    "expression": "DATE_DIFF(order_date, CURRENT_DATE(), 'day')"
                },
                {
                    "name": "is_valid",
                    "expression": "email IS NOT NULL AND CONTAINS(email, '@')"
                }
            ]
        }]
    }
}
```

### When You Actually Need Python Components

Some Java patterns don't map to expressions:

| Java Pattern | Why Expressions Don't Work | V2 Component |
|---|---|---|
| External API call per row | I/O operation | `python_row` (vectorized, batch API calls) |
| Database lookup per row | I/O operation | `python_row` or `python_code` (batch query) |
| Complex state machine | Requires mutable state across rows | `python_code` |
| ML model inference | External library call | `python_code` or `python_dataframe` |
| Custom serialization (XML, protobuf) | Complex parsing logic | `python_code` |
| Multi-row window logic beyond SQL | Custom windowing | `python_dataframe` with Polars window functions |

---

## Java to V2 Expression Patterns

### String Operations

| Java | V2 Expression |
|------|--------------|
| `s.toUpperCase()` | `UPPER(col)` |
| `s.toLowerCase()` | `LOWER(col)` |
| `s.trim()` | `TRIM(col)` |
| `s.substring(start, end)` | `SUBSTRING(col, start, length)` |
| `s.replace(old, new)` | `REPLACE(col, 'old', 'new')` |
| `s.length()` | `LENGTH(col)` |
| `s.contains(sub)` | `CONTAINS(col, 'sub')` |
| `s.startsWith(prefix)` | `STARTS_WITH(col, 'prefix')` |
| `s.endsWith(suffix)` | `ENDS_WITH(col, 'suffix')` |
| `s + " " + t` | `CONCAT(col1, ' ', col2)` |
| `s.isEmpty()` | `col IS NULL OR col = ''` |
| `String.valueOf(x)` | `TO_STRING(col)` |

### Numeric Operations

| Java | V2 Expression |
|------|--------------|
| `Integer.parseInt(s)` | `TO_INTEGER(col)` |
| `Double.parseDouble(s)` | `TO_FLOAT(col)` |
| `Math.abs(x)` | `ABS(col)` |
| `Math.round(x)` | `ROUND(col, 0)` |
| `Math.floor(x)` | `FLOOR(col)` |
| `Math.ceil(x)` | `CEIL(col)` |
| `Math.sqrt(x)` | `SQRT(col)` |
| `Math.pow(x, n)` | `POW(col, n)` |
| `x % y` | `col1 % col2` |
| `x > 0 ? x : 0` | `CASE WHEN col > 0 THEN col ELSE 0 END` |

### Null Handling

| Java | V2 Expression |
|------|--------------|
| `x == null` | `col IS NULL` |
| `x != null` | `col IS NOT NULL` |
| `x != null ? x : default` | `COALESCE(col, default)` |
| `x != null ? x : ""` | `IFNULL(col, '')` |

### Conditional Logic

| Java | V2 Expression |
|------|--------------|
| `if (c) { a } else { b }` | `CASE WHEN c THEN a ELSE b END` |
| `if/else if/else` chain | `CASE WHEN c1 THEN v1 WHEN c2 THEN v2 ELSE v3 END` |
| `switch` statement | `CASE WHEN` chain |
| `cond1 && cond2` | `cond1 AND cond2` |
| `cond1 \|\| cond2` | `cond1 OR cond2` |
| `!cond` | `NOT cond` |

### Date Operations

| Java | V2 Expression |
|------|--------------|
| `new Date()` / `LocalDate.now()` | `CURRENT_DATE()` |
| `date.getYear()` | `YEAR(col)` |
| `date.getMonth()` | `MONTH(col)` |
| `date.getDay()` | `DAY(col)` |
| Parse date string | `TO_DATE(col, 'yyyy-MM-dd')` |
| Date arithmetic | `DATE_ADD(col, 30, 'day')` |
| Date difference | `DATE_DIFF(col1, col2, 'day')` |

### Type Casting

| Java | V2 Expression |
|------|--------------|
| `(int) x` / `Integer.parseInt(s)` | `TO_INTEGER(col)` |
| `(double) x` / `Double.parseDouble(s)` | `TO_FLOAT(col)` |
| `String.valueOf(x)` / `x.toString()` | `TO_STRING(col)` |
| `Boolean.parseBoolean(s)` | `TO_BOOLEAN(col)` |

---

## Performance Optimization with Polars

### Rule 1: Stay Lazy

The V2 engine uses Polars LazyFrames. Components that don't force `.collect()` (barriers) allow Polars to optimize the entire pipeline -- predicate pushdown, projection pushdown, and parallel execution happen automatically.

```
Source (lazy) → Map (lazy) → Filter (lazy) → Map (lazy) → Sink (barrier)
                                                              │
                                              Polars optimizes entire chain
                                              before executing anything
```

Every barrier breaks this optimization chain. Python components are always barriers.

```
Source → Map → PythonCode (barrier!) → Map → Filter → Sink (barrier)
                   │                                      │
         Chain 1 optimized                    Chain 2 optimized
         separately                           separately
```

### Rule 2: Think Columns, Not Rows

Polars is columnar. Operating on entire columns is orders of magnitude faster than iterating rows.

```python
# SLOW: Row-by-row (python_row scalar mode)
# 1M rows in ~30 seconds
"code": "return {'total': row['price'] * row['qty']}"

# FAST: Column expression (map component)
# 1M rows in ~5 milliseconds
"expression": "price * qty"
```

### Rule 3: Vectorize Custom Logic

If you must write Python, operate on columns (`pl.Series`) not individual values:

```python
# Tier 1 vectorized routine (stays in lazy graph, near-native speed)
def calculate_margin(revenue: pl.Series, cost: pl.Series) -> pl.Series:
    return (revenue - cost) / revenue * 100

calculate_margin._vectorized = True
calculate_margin._return_dtype = pl.Float64
```

vs.

```python
# Tier 2 scalar routine (per-row Python, 50-100x slower)
def calculate_margin(revenue: float, cost: float) -> float:
    if revenue is None or revenue == 0:
        return 0.0
    return (revenue - cost) / revenue * 100
```

Both are called identically in expressions: `MyRoutine.calculate_margin(revenue, cost)`.

### Rule 4: Batch External Calls

If you must call external services, batch them:

```json
{
    "type": "python_row",
    "config": {
        "mode": "vectorized",
        "batch_size": 100,
        "code": "ids = [r['id'] for r in rows]\nresp = requests.post('http://api/batch', json=ids)\nlookup = {r['id']: r['tier'] for r in resp.json()}\nreturn [{'tier': lookup.get(r['id'], 'unknown')} for r in rows]",
        "output_columns": [{"name": "tier", "type": "String"}]
    }
}
```

This makes 1 API call per 100 rows instead of 1 per row.

### Rule 5: Decompose, Don't Translate Line-by-Line

Instead of one big Python component doing everything:

```
# BAD: One big python_code (barrier, all Python)
Source → PythonCode(360 lines) → Sink

# GOOD: Decomposed (mostly lazy, native speed)
Source → Map(transforms) → Filter(conditions) → Map(business logic) → Sink
         lazy               lazy                 lazy                 barrier
```

---

## Migrating Java Routines

Talend Java routines map directly to V2 Python routines.

### Java Routine (Talend)

```java
package routines;

public class OrderUtils {
    public static double calculateTax(double amount, double rate) {
        return amount * rate;
    }

    public static String formatCurrency(double amount) {
        return String.format("$%,.2f", amount);
    }

    public static boolean isValidEmail(String email) {
        return email != null && email.contains("@") && email.contains(".");
    }
}
```

### Python Routine (V2)

```python
# src/v2/routines/user/order_utils.py

def calculate_tax(amount: float, rate: float) -> float:
    if amount is None:
        return 0.0
    return amount * rate

def format_currency(amount: float) -> str:
    if amount is None:
        return "$0.00"
    return f"${amount:,.2f}"

def is_valid_email(email: str) -> bool:
    if email is None:
        return False
    return "@" in email and "." in email.split("@")[-1]
```

**Key differences:**
- Java `static` methods become Python module-level functions
- Java class `OrderUtils` → Python file `order_utils.py` (auto-converts to `OrderUtils`)
- Must handle `None` explicitly (no null-safe operators in Python)
- Usage is identical: `OrderUtils.calculate_tax(amount, 0.08)`

### Making Routines Vectorized (Tier 1)

For simple math/logic, vectorize for 50-100x speedup:

```python
import polars as pl

def calculate_tax(amount: pl.Series, rate: pl.Series) -> pl.Series:
    return amount * rate

calculate_tax._vectorized = True
calculate_tax._return_dtype = pl.Float64
```

**Vectorize when:** pure arithmetic, simple conditionals, string ops available on `pl.Series.str`.

**Don't vectorize when:** external calls, complex branching, cross-row state.

---

## Common Pitfalls

### 1. Translating Java Line-by-Line Into python_row

**Wrong:** Converting each Java line to Python in `python_row` scalar mode.

**Right:** Analyze the _intent_ of the Java code. Most column transforms, conditionals, and type conversions map to Map expressions, not Python.

### 2. Defaulting to python_row Because It "Feels Like" tJavaRow

`python_row` is the direct equivalent of `tJavaRow` but is the **slowest option** in V2. Use Map with expressions for 90%+ of cases.

### 3. Forgetting Null Handling in Routines

Java throws NPE on null access. Python silently passes `None`. Always guard:

```python
def safe_upper(text: str) -> str:
    if text is None:
        return ""
    return text.upper()
```

Expression functions handle nulls automatically (most return null for null input).

### 4. Using Pandas When Polars Works

`python_dataframe` with `use_pandas: true` adds conversion overhead. Only use pandas when you need pandas-specific functionality.

### 5. Not Batching External Calls

1 API call per row is catastrophically slow. Always batch with `python_row` vectorized mode.

---

## Migration Checklist

When converting a tJavaRow:

- [ ] Read the Java code and categorize each block (transform, filter, business logic, I/O)
- [ ] Map transforms to expressions -- string ops, math, conditionals, type casts
- [ ] Identify reusable logic -- extract into Python routines, vectorize if possible
- [ ] Identify true Python needs -- external calls, state, complex parsing
- [ ] Decompose into multiple V2 components (Map → Filter → Map > one big PythonCode)
- [ ] Choose the right component for each block using the decision framework
- [ ] Test with representative data -- verify correctness and measure throughput
- [ ] Profile barriers -- minimize barrier components in the pipeline

---

## Related Documentation

- [Expression DSL](EXPRESSIONS.md) -- Built-in functions and syntax
- [Python Components](PYTHON_COMPONENTS.md) -- PythonCode, PythonRow, PythonDataFrame details
- [Routines](ROUTINES.md) -- Creating and using Python routines
- [Component Reference](COMPONENTS.md) -- All V2 components
- [Error Handling](ERROR_HANDLING.md) -- die_on_error and reject flows
