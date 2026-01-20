"""
Custom exception hierarchy for the data processing engine.
"""


class ETLError(Exception):
    """Base class for all ETL-related exceptions."""
    pass


class ConfigurationError(ETLError):
    """Raised when there is a configuration issue with a component."""
    pass


class DataValidationError(ETLError):
    """Raised when data validation fails."""
    pass


class ComponentExecutionError(ETLError):
    """Raised when a component fails during execution."""
   
    def __init__(self, component_id: str, message: str, cause: Exception = None):
        self.component_id = component_id
        self.cause = cause
        super().__init__(f"[{component_id}] {message}")


class FileOperationError(ETLError):
    """Raised when file operations (read/write) fail."""
    pass


class JavaBridgeError(ETLError):
    """Raised when there is an error in Java-Python bridge communication."""
    pass

class ExpressionError(ETLError):
    """Raised when there is an error in evaluating expressions."""
    pass



class SchemaError(ETLError):
    """Raised when there is a schema-related issue."""
    pass
