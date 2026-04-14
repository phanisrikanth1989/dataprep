"""
Java Bridge Manager - Manages Java bridge lifecycle per job
"""
import logging
import socket
from typing import Optional, List

from .exceptions import JavaBridgeError

logger = logging.getLogger(__name__)


class JavaBridgeManager:
    """
    Manages Java bridge lifecycle for a single job.
    Each job gets its own Java process to ensure isolation.
    """

    def __init__(self, enable: bool = True, routines: Optional[List[str]] = None, libraries: Optional[List[str]] = None):
        """
        Initialize Java bridge manager

        Args:
            enable: Whether to enable Java execution
            routines: List of routine class names to load (e.g., ['routines.StringUtils', 'routines.DateUtil'])
            libraries: List of required JAR files (e.g., ['commons-lang3-3.14.0.jar', 'gson-2.8.9.jar'])
        """
        self.enable = enable
        self.bridge = None
        self.is_running = False
        self.port = None
        self.routines = routines or []
        self.libraries = libraries or []

    def start(self):
        """Start Java bridge with dynamic port allocation"""
        if not self.enable:
            logger.info("Java execution disabled")
            return

        try:
            # Find available port
            self.port = self._find_free_port()
            logger.info("[OK] Starting Java bridge on port %d", self.port)

            # Import and initialize bridge
            from src.v1.java_bridge import JavaBridge

            self.bridge = JavaBridge()
            self.bridge.start(port=self.port)
            self.is_running = True

            # Sync Python log level to Java side (D-16)
            python_level = logger.getEffectiveLevel()
            self.bridge.set_log_level(python_level)
            logger.info("[OK] Java bridge started on port %d, log level synced", self.port)

            # Validate required libraries if specified
            if self.libraries:
                logger.info("[OK] Validating %d required library(ies)...", len(self.libraries))
                missing_libraries = self.bridge.validate_libraries(self.libraries)
                if missing_libraries:
                    error_msg = f"Missing required libraries: {missing_libraries}"
                    logger.error("[ERROR] %s", error_msg)
                    self.bridge.stop()
                    raise RuntimeError(error_msg)
                logger.info("[OK] All %d libraries are available on classpath", len(self.libraries))

            # Load routines if specified
            if self.routines:
                logger.info("[OK] Loading %d routine(s)...", len(self.routines))
                for routine_class in self.routines:
                    try:
                        self.bridge.load_routine(routine_class)
                        logger.info("[OK] Loaded: %s", routine_class)
                    except Exception as e:
                        logger.error("[ERROR] Failed to load %s", routine_class)

        except Exception as e:
            logger.error("[ERROR] Java bridge failed to start: %s", e, exc_info=True)
            raise JavaBridgeError(f"Java bridge failed to start: {e}") from e

    def stop(self):
        """Stop Java bridge and cleanup"""
        if self.bridge and self.is_running:
            try:
                self.bridge.stop()
                logger.info("[OK] Java bridge stopped (port %s)", self.port)
            except Exception as e:
                logger.error("[ERROR] Error stopping Java bridge: %s", e)
            finally:
                self.bridge = None
                self.is_running = False
                self.port = None

    def get_bridge(self):
        """Get the Java bridge instance"""
        return self.bridge if self.is_running else None

    def is_available(self) -> bool:
        """Check if Java execution is available"""
        return self.enable and self.is_running and self.bridge is not None

    def _find_free_port(self) -> int:
        """
        Find an available port for the Java bridge

        Returns:
            Available port number
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0)) # Bind to an available port assigned by the OS
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
        return False

    def __repr__(self) -> str:
        status = "running" if self.is_running else "stopped"
        port_info = f"port={self.port}" if self.port else "no port"
        return f"JavaBridgeManager(status={status}, {port_info})"
