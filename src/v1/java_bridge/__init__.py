"""
Java Bridge Layer for ETL Engine

This module provides Java execution capabilities for the ETL engine using:
- Apache Arrow for efficient data transfer
- Py4J for Java-Python communication
- Groovy for dynamic Java code execution

Main components:
- JavaBridge: Core bridge class for Java execution
"""

from .bridge import JavaBridge

__all__ = ['JavaBridge']