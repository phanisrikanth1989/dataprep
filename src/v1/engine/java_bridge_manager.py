"""
Java Bridge Manager - Manages Java bridge lifecycle per job
"""
import logging
import socket
from typing import Optional, List

logger = logging.getLogger(__name__)


class JavaBridgeManager:
    """
    Manages Java bridge lifecycle for a single job.
    Each job gets its own Java process to ensure isolation.
    """

    def __init__(self,enable: bool = True,routines: Optional[List[str]] = None,libraries: Optional[List[str]] = None):
        """
        Initialize Java bridge manager

        Args:
            enable: Whether to enable Java execution
            routines: List of routine class names to load(e.g., ['routines.StringUtils', 'routines.DateUtil'])
            libraries: List of required JAR files(e.g., ['commons-lang3-3.14.0.jar', 'gson-2.8.9.jar'])
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
            logger.info(f"Starting Java bridge on port {self.port}")

            # Import and initialize bridge
            from src.java_bridge import JavaBridge

            self.bridge = JavaBridge()
            self.bridge.start(port=self.port)
            self.is_running = True

            logger.info(f"Java bridge started successfully on port {self.port}")

            # Validate required libraries if specified
            if self.libraries:
                logger.info(f"Validating {len(self.libraries)} required library(ies)...")
                missing_libraries = self.bridge.validate_libraries(self.libraries)
                if missing_libraries:
                    error_msg = f"Missing required libraries: {missing_libraries}"
                    logger.error(error_msg)
                    self.bridge.stop()
                    raise RuntimeError(error_msg)
                logger.info(f"All {len(self.libraries)} libraries are available on classpath")

            # Load routines if specified
            if self.routines:
                logger.info(f"Loading {len(self.routines)} routine(s)...")
                for routine_class in self.routines:
                    try:
                        self.bridge.load_routine(routine_class)
                        logger.info(f"Loaded: {routine_class}")
                    except Exception:
                        logger.error(f"Failed to load {routine_class}")

        except Exception as e:
            logger.error(f"Failed to start Java bridge: {e}")
            logger.warning("Java execution will be disabled. Components will fall back to Python execution.")
            self.enable = False
            self.bridge = None
            self.is_running = False

    def stop(self):
        """Stop Java bridge and cleanup"""
        if self.bridge and self.is_running:
            try:
                self.bridge.stop()
                logger.info(f"Java bridge stopped (port {self.port})")
            except Exception as e:
                logger.error(f"Error stopping Java bridge: {e}")
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
            s.bind(("", 0))
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
