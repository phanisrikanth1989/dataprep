"""
Demo Routine - Example Python routine for v2 engine.

Provides utility functions for demonstration and testing.
"""


def greet(name: str) -> str:
    """
    Generate a greeting message.

    Args:
        name: Name to greet

    Returns:
        Greeting string

    Example:
        >>> greet("World")
        'Hello, World!'
    """
    return f"Hello, {name}!"


def is_senior_male(age: int, gender: str) -> bool:
    """
    Check if person is a senior male (age >= 60 and gender is Male).

    Args:
        age: Person's age
        gender: Person's gender ('M', 'Male', 'F', 'Female')

    Returns:
        True if senior male, False otherwise

    Example:
        >>> is_senior_male(65, "Male")
        True
        >>> is_senior_male(65, "Female")
        False
    """
    if age is None or age < 60:
        return False

    if gender in ('F', 'Female', None):
        return False

    return True


def format_name(first: str, last: str, title: str = "") -> str:
    """
    Format a full name with optional title.

    Args:
        first: First name
        last: Last name
        title: Optional title (Mr., Mrs., Dr., etc.)

    Returns:
        Formatted name string

    Example:
        >>> format_name("John", "Doe", "Dr.")
        'Dr. John Doe'
        >>> format_name("Jane", "Smith")
        'Jane Smith'
    """
    if title:
        return f"{title} {first} {last}"
    return f"{first} {last}"


def calculate_discount(price: float, discount_pct: float) -> float:
    """
    Calculate discounted price.

    Args:
        price: Original price
        discount_pct: Discount percentage (0-100)

    Returns:
        Price after discount

    Example:
        >>> calculate_discount(100.0, 20.0)
        80.0
    """
    if price is None or discount_pct is None:
        return price or 0.0

    discount = price * (discount_pct / 100.0)
    return price - discount


def concat_with_sep(*args, sep: str = ", ") -> str:
    """
    Concatenate multiple values with a separator.

    Args:
        *args: Values to concatenate
        sep: Separator string (default: ", ")

    Returns:
        Concatenated string

    Example:
        >>> concat_with_sep("a", "b", "c")
        'a, b, c'
        >>> concat_with_sep("a", "b", sep="-")
        'a-b'
    """
    return sep.join(str(arg) for arg in args if arg is not None)
