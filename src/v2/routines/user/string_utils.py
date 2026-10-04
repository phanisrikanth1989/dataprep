"""
String Utilities - Common string manipulation functions.

Provides efficient string operations for ETL transformations.
"""
import re
from typing import Optional


def clean_whitespace(text: str) -> str:
    """
    Clean and normalize whitespace in text.

    Replaces multiple spaces/tabs with single space and trims.

    Args:
        text: Input text

    Returns:
        Cleaned text

    Example:
        >>> clean_whitespace("  hello   world  ")
        'hello world'
    """
    if text is None:
        return ""
    return " ".join(text.split())


def extract_digits(text: str) -> str:
    """
    Extract only digits from text.

    Args:
        text: Input text

    Returns:
        String containing only digits

    Example:
        >>> extract_digits("ABC123DEF456")
        '123456'
    """
    if text is None:
        return ""
    return "".join(c for c in text if c.isdigit())


def extract_alpha(text: str) -> str:
    """
    Extract only alphabetic characters from text.

    Args:
        text: Input text

    Returns:
        String containing only letters

    Example:
        >>> extract_alpha("ABC123DEF456")
        'ABCDEF'
    """
    if text is None:
        return ""
    return "".join(c for c in text if c.isalpha())


def mask_string(text: str, keep_start: int = 0, keep_end: int = 0, mask_char: str = "*") -> str:
    """
    Mask a string, keeping first/last N characters visible.

    Args:
        text: Input text
        keep_start: Number of characters to keep at start
        keep_end: Number of characters to keep at end
        mask_char: Character to use for masking

    Returns:
        Masked string

    Example:
        >>> mask_string("1234567890", keep_start=2, keep_end=4)
        '12****7890'
    """
    if text is None:
        return ""

    length = len(text)
    if length <= keep_start + keep_end:
        return text

    mask_length = length - keep_start - keep_end
    start = text[:keep_start] if keep_start > 0 else ""
    end = text[-keep_end:] if keep_end > 0 else ""

    return start + (mask_char * mask_length) + end


def to_snake_case(text: str) -> str:
    """
    Convert text to snake_case.

    Args:
        text: Input text (CamelCase, PascalCase, or mixed)

    Returns:
        snake_case version

    Example:
        >>> to_snake_case("HelloWorld")
        'hello_world'
        >>> to_snake_case("HTTPResponse")
        'http_response'
    """
    if text is None:
        return ""

    # Insert underscore before uppercase letters and convert to lowercase
    result = re.sub(r'(?<!^)(?=[A-Z])', '_', text).lower()
    # Replace multiple underscores with single
    result = re.sub(r'_+', '_', result)
    return result


def to_title_case(text: str) -> str:
    """
    Convert text to Title Case.

    Args:
        text: Input text

    Returns:
        Title Case version

    Example:
        >>> to_title_case("hello world")
        'Hello World'
    """
    if text is None:
        return ""
    return text.title()


def safe_substring(text: str, start: int, length: Optional[int] = None) -> str:
    """
    Safe substring that handles None and out-of-bounds.

    Args:
        text: Input text
        start: Start position (0-based)
        length: Optional length (if None, returns rest of string)

    Returns:
        Substring

    Example:
        >>> safe_substring("hello", 0, 3)
        'hel'
        >>> safe_substring("hello", 10, 3)
        ''
    """
    if text is None:
        return ""

    if start >= len(text):
        return ""

    if length is None:
        return text[start:]

    return text[start:start + length]


def pad_left(text: str, width: int, fill_char: str = " ") -> str:
    """
    Pad string on left to specified width.

    Args:
        text: Input text
        width: Target width
        fill_char: Character to use for padding

    Returns:
        Left-padded string

    Example:
        >>> pad_left("42", 5, "0")
        '00042'
    """
    if text is None:
        text = ""
    return text.rjust(width, fill_char[0] if fill_char else " ")


def pad_right(text: str, width: int, fill_char: str = " ") -> str:
    """
    Pad string on right to specified width.

    Args:
        text: Input text
        width: Target width
        fill_char: Character to use for padding

    Returns:
        Right-padded string

    Example:
        >>> pad_right("42", 5, "0")
        '42000'
    """
    if text is None:
        text = ""
    return text.ljust(width, fill_char[0] if fill_char else " ")
