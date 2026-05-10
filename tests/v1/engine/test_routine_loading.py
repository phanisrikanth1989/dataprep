"""Tests for Java and Python routine loading enhancements.

Covers:
- PythonRoutineManager top-level loading, subdirectory scanning, namespace access
- RoutineNamespace attribute access and error handling
- Required routine fail-fast validation
- JavaBridge classpath extension with routine_jars
- JavaBridgeManager routine_jars passthrough
- Engine config wiring for routine_jars and required routines
"""

import inspect
import os
import textwrap
import tempfile

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from src.v1.engine.python_routine_manager import PythonRoutineManager, RoutineNamespace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_py_file(directory: Path, filename: str, content: str) -> Path:
    """Write a Python file with dedented content."""
    filepath = directory / filename
    filepath.write_text(textwrap.dedent(content))
    return filepath


# ===========================================================================
# TestPythonRoutineTopLevel
# ===========================================================================

@pytest.mark.unit
class TestPythonRoutineTopLevel:
    """Test top-level .py file loading."""

    def test_loads_py_files(self, tmp_path):
        _write_py_file(tmp_path, "demo_routine.py", """\
            def greet(name):
                return f"Hello, {name}"
        """)
        manager = PythonRoutineManager(str(tmp_path))
        routine = manager.get_routine("DemoRoutine")
        assert routine is not None
        assert routine.greet("World") == "Hello, World"

    def test_skips_init_and_private(self, tmp_path):
        _write_py_file(tmp_path, "__init__.py", "# init")
        _write_py_file(tmp_path, "_helper.py", "x = 1")
        _write_py_file(tmp_path, "good_routine.py", "y = 2")
        manager = PythonRoutineManager(str(tmp_path))
        assert manager.get_routine("GoodRoutine") is not None
        # __init__ and _helper should not be loaded
        assert "Init" not in manager.routines
        assert "__init__" not in manager.routines
        assert "Helper" not in manager.routines
        assert "_helper" not in manager.routines

    def test_missing_directory_warns(self, tmp_path):
        nonexistent = str(tmp_path / "does_not_exist")
        manager = PythonRoutineManager(nonexistent)
        assert len(manager.routines) == 0

    def test_class_name_conversion(self, tmp_path):
        _write_py_file(tmp_path, "my_util_lib.py", "val = 42")
        manager = PythonRoutineManager(str(tmp_path))
        assert manager.get_routine("MyUtilLib") is not None


# ===========================================================================
# TestPythonRoutineSubdirectory
# ===========================================================================

@pytest.mark.unit
class TestPythonRoutineSubdirectory:
    """Test subdirectory scanning for organized routine packages."""

    def test_subdirectory_scanning(self, tmp_path):
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        _write_py_file(system_dir, "talend_string.py", """\
            def upper(s):
                return s.upper()
        """)
        manager = PythonRoutineManager(str(tmp_path))
        # Qualified name
        assert manager.get_routine("system.TalendString") is not None
        # Short name (no collision)
        assert manager.get_routine("TalendString") is not None

    def test_qualified_name_access(self, tmp_path):
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        _write_py_file(system_dir, "talend_string.py", """\
            def upper(s):
                return s.upper()
        """)
        manager = PythonRoutineManager(str(tmp_path))
        routine = manager.get_routine("system.TalendString")
        assert routine is not None
        assert routine.upper("hello") == "HELLO"

    def test_short_name_available_no_collision(self, tmp_path):
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        _write_py_file(system_dir, "talend_string.py", """\
            def upper(s):
                return s.upper()
        """)
        manager = PythonRoutineManager(str(tmp_path))
        short = manager.get_routine("TalendString")
        qualified = manager.get_routine("system.TalendString")
        assert short is qualified  # Same module object

    def test_skips_private_subdirectories(self, tmp_path):
        internal_dir = tmp_path / "_internal"
        internal_dir.mkdir()
        _write_py_file(internal_dir, "secret.py", "x = 1")
        manager = PythonRoutineManager(str(tmp_path))
        assert manager.get_routine("Secret") is None
        assert manager.get_routine("_internal.Secret") is None

    def test_skips_private_files_in_subdir(self, tmp_path):
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        _write_py_file(system_dir, "_helper.py", "x = 1")
        _write_py_file(system_dir, "public_util.py", "y = 2")
        manager = PythonRoutineManager(str(tmp_path))
        assert manager.get_routine("Helper") is None
        assert manager.get_routine("system.Helper") is None
        assert manager.get_routine("PublicUtil") is not None

    def test_short_name_collision_keeps_first(self, tmp_path):
        """When a top-level routine and subdir routine have the same class name,
        top-level wins (loaded first) and subdir only has qualified name."""
        _write_py_file(tmp_path, "talend_string.py", """\
            source = "top-level"
        """)
        system_dir = tmp_path / "system"
        system_dir.mkdir()
        _write_py_file(system_dir, "talend_string.py", """\
            source = "subdir"
        """)
        manager = PythonRoutineManager(str(tmp_path))
        # Short name should be top-level (loaded first)
        assert manager.get_routine("TalendString").source == "top-level"
        # Qualified name should be subdir
        assert manager.get_routine("system.TalendString").source == "subdir"


# ===========================================================================
# TestRoutineNamespace
# ===========================================================================

@pytest.mark.unit
class TestRoutineNamespace:
    """Test RoutineNamespace attribute access pattern."""

    def test_attribute_access(self):
        mock_module = MagicMock()
        ns = RoutineNamespace({"DemoRoutine": mock_module})
        assert ns.DemoRoutine is mock_module

    def test_unknown_attribute_raises(self):
        ns = RoutineNamespace({"DemoRoutine": MagicMock()})
        with pytest.raises(AttributeError, match="Available:"):
            _ = ns.NonExistent

    def test_repr(self):
        ns = RoutineNamespace({"A": 1, "B": 2})
        result = repr(ns)
        assert "RoutineNamespace" in result

    def test_get_namespace_from_manager(self, tmp_path):
        _write_py_file(tmp_path, "demo_routine.py", """\
            def greet(name):
                return f"Hello, {name}"
        """)
        manager = PythonRoutineManager(str(tmp_path))
        ns = manager.get_namespace()
        assert isinstance(ns, RoutineNamespace)
        assert ns.DemoRoutine.greet("Test") == "Hello, Test"

    def test_private_attr_raises(self):
        ns = RoutineNamespace({"_secret": "hidden"})
        with pytest.raises(AttributeError):
            _ = ns._secret


# ===========================================================================
# TestRequiredRoutines
# ===========================================================================

@pytest.mark.unit
class TestRequiredRoutines:
    """Test required routine fail-fast validation."""

    def test_required_present_succeeds(self, tmp_path):
        _write_py_file(tmp_path, "demo.py", "x = 1")
        # Should not raise
        manager = PythonRoutineManager(str(tmp_path), required_routines=["Demo"])
        assert manager.get_routine("Demo") is not None

    def test_required_missing_raises(self, tmp_path):
        _write_py_file(tmp_path, "demo.py", "x = 1")
        with pytest.raises(RuntimeError, match="Missing required Python routines"):
            PythonRoutineManager(str(tmp_path), required_routines=["Missing"])

    def test_no_required_routines_default(self, tmp_path):
        _write_py_file(tmp_path, "demo.py", "x = 1")
        # Should not raise -- no required_routines
        manager = PythonRoutineManager(str(tmp_path))
        assert manager.get_routine("Demo") is not None

    def test_required_missing_lists_available(self, tmp_path):
        _write_py_file(tmp_path, "demo.py", "x = 1")
        with pytest.raises(RuntimeError, match="Available:"):
            PythonRoutineManager(str(tmp_path), required_routines=["NotHere"])


# ===========================================================================
# TestJavaBridgeClasspath
# ===========================================================================

@pytest.mark.unit
class TestJavaBridgeClasspath:
    """Test Java bridge classpath extension."""

    def test_start_accepts_routine_jars(self):
        from src.v1.java_bridge.bridge import JavaBridge
        sig = inspect.signature(JavaBridge.start)
        assert "routine_jars" in sig.parameters

    def test_classpath_construction(self, tmp_path):
        """Verify routine_jars are included in the -cp argument."""
        from src.v1.java_bridge.bridge import JavaBridge

        # Create a fake JAR file
        fake_jar = tmp_path / "test.jar"
        fake_jar.write_bytes(b"fake")

        bridge = JavaBridge()

        with patch.object(bridge, '_find_jar_path', return_value="/fake/bridge.jar"), \
             patch('src.v1.java_bridge.bridge.subprocess.Popen') as mock_popen, \
             patch('src.v1.java_bridge.bridge.JavaGateway') as mock_gw:

            # Setup mock process
            mock_proc = MagicMock()
            mock_proc.poll.return_value = None
            mock_proc.stderr = MagicMock()
            mock_popen.return_value = mock_proc

            # Setup mock gateway
            mock_entry = MagicMock()
            mock_entry.getContext.return_value = {}
            mock_entry.getGlobalMap.return_value = {}
            mock_gw_instance = MagicMock()
            mock_gw_instance.entry_point = mock_entry
            mock_gw.return_value = mock_gw_instance

            bridge.start(port=25333, routine_jars=[str(fake_jar)])

            # Verify classpath in cmd
            cmd = mock_popen.call_args[0][0]
            cp_idx = cmd.index("-cp")
            classpath = cmd[cp_idx + 1]
            assert str(fake_jar) in classpath
            assert "/fake/bridge.jar" in classpath

    def test_directory_jar_discovery(self, tmp_path):
        """Verify directory mode scans for .jar files."""
        from src.v1.java_bridge.bridge import JavaBridge

        # Create fake JARs in directory
        (tmp_path / "alpha.jar").write_bytes(b"a")
        (tmp_path / "beta.jar").write_bytes(b"b")

        bridge = JavaBridge()

        with patch.object(bridge, '_find_jar_path', return_value="/fake/bridge.jar"), \
             patch('src.v1.java_bridge.bridge.subprocess.Popen') as mock_popen, \
             patch('src.v1.java_bridge.bridge.JavaGateway') as mock_gw:

            mock_proc = MagicMock()
            mock_proc.poll.return_value = None
            mock_proc.stderr = MagicMock()
            mock_popen.return_value = mock_proc

            mock_entry = MagicMock()
            mock_entry.getContext.return_value = {}
            mock_entry.getGlobalMap.return_value = {}
            mock_gw_instance = MagicMock()
            mock_gw_instance.entry_point = mock_entry
            mock_gw.return_value = mock_gw_instance

            bridge.start(port=25333, routine_jars=[str(tmp_path)])

            cmd = mock_popen.call_args[0][0]
            cp_idx = cmd.index("-cp")
            classpath = cmd[cp_idx + 1]
            assert "alpha.jar" in classpath
            assert "beta.jar" in classpath


# ===========================================================================
# TestJavaBridgeManagerRoutineJars
# ===========================================================================

@pytest.mark.unit
class TestJavaBridgeManagerRoutineJars:
    """Test JavaBridgeManager passes routine_jars to bridge."""

    def test_passes_routine_jars_to_bridge(self):
        from src.v1.engine.java_bridge_manager import JavaBridgeManager

        manager = JavaBridgeManager(
            enable=True,
            routine_jars=["/tmp/test.jar"]
        )
        assert manager.routine_jars == ["/tmp/test.jar"]

    def test_routine_jars_passed_in_start(self):
        from src.v1.engine.java_bridge_manager import JavaBridgeManager

        manager = JavaBridgeManager(
            enable=True,
            routine_jars=["/tmp/custom.jar"]
        )

        mock_bridge = MagicMock()
        mock_bridge.set_log_level = MagicMock()
        mock_bridge.validate_libraries = MagicMock(return_value=[])

        with patch('src.v1.engine.java_bridge_manager.JavaBridgeManager._find_free_port', return_value=25333), \
             patch('src.v1.java_bridge.JavaBridge', return_value=mock_bridge):
            manager.start()

        mock_bridge.start.assert_called_once_with(port=25333, routine_jars=["/tmp/custom.jar"])

    def test_default_routine_jars_empty(self):
        from src.v1.engine.java_bridge_manager import JavaBridgeManager

        manager = JavaBridgeManager(enable=True)
        assert manager.routine_jars == []


# ===========================================================================
# TestEngineRoutineConfig
# ===========================================================================

@pytest.mark.unit
class TestEngineRoutineConfig:
    """Test engine config wiring for routines."""

    def test_java_config_reads_routine_jars(self):
        """Engine should read routine_jars from java_config."""
        from src.v1.engine.java_bridge_manager import JavaBridgeManager

        job_config = {
            "job_name": "test_job",
            "java_config": {
                "enabled": True,
                "routines": [],
                "libraries": [],
                "routine_jars": ["/tmp/test.jar"],
            },
            "components": [],
            "flows": [],
            "triggers": [],
            "context": {"Default": {}},
        }

        with patch('src.v1.engine.engine.JavaBridgeManager') as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.bridge = MagicMock()
            mock_mgr_cls.return_value = mock_mgr

            from src.v1.engine.engine import ETLEngine
            engine = ETLEngine(job_config)

            mock_mgr_cls.assert_called_once_with(
                enable=True,
                routines=[],
                libraries=[],
                routine_jars=["/tmp/test.jar"],
            )

    def test_python_config_reads_routines_list(self, tmp_path):
        """Engine should pass routines list as required_routines."""
        _write_py_file(tmp_path, "demo.py", "x = 1")

        job_config = {
            "job_name": "test_job",
            "python_config": {
                "enabled": True,
                "routines_dir": str(tmp_path),
                "routines": ["Demo"],
            },
            "components": [],
            "flows": [],
            "triggers": [],
            "context": {"Default": {}},
        }

        from src.v1.engine.engine import ETLEngine
        engine = ETLEngine(job_config)

        assert engine.python_routine_manager is not None
        assert engine.python_routine_manager.get_routine("Demo") is not None

    def test_python_config_missing_routine_raises(self, tmp_path):
        """Engine should fail fast when required routines are missing."""
        _write_py_file(tmp_path, "demo.py", "x = 1")

        job_config = {
            "job_name": "test_job",
            "python_config": {
                "enabled": True,
                "routines_dir": str(tmp_path),
                "routines": ["NonExistent"],
            },
            "components": [],
            "flows": [],
            "triggers": [],
            "context": {"Default": {}},
        }

        with pytest.raises(RuntimeError, match="Missing required Python routines"):
            from src.v1.engine.engine import ETLEngine
            ETLEngine(job_config)


# ===========================================================================
# Plan 14-10 lift: 81.6% -> 95%+ -- coverage for missed branches
# ===========================================================================


@pytest.mark.unit
class TestPythonRoutineLoadFailures:
    """Failures during module load are logged but do not abort discovery (122-123)."""

    def test_top_level_load_failure_logged_continues(self, tmp_path, caplog):
        _write_py_file(tmp_path, "broken_routine.py", "raise ImportError('cannot load')")
        _write_py_file(tmp_path, "good_routine.py", "x = 1")
        with caplog.at_level("ERROR"):
            mgr = PythonRoutineManager(str(tmp_path))
        # Good still loaded; broken failure recorded
        assert mgr.get_routine("GoodRoutine") is not None
        assert "Failed to load broken_routine" in caplog.text

    def test_subdir_load_failure_logged_continues(self, tmp_path, caplog):
        sub = tmp_path / "subpkg"
        sub.mkdir()
        _write_py_file(sub, "broken.py", "raise SyntaxError('intentional')")
        _write_py_file(sub, "ok.py", "y = 2")
        with caplog.at_level("ERROR"):
            mgr = PythonRoutineManager(str(tmp_path))
        # Subdir Ok loaded under qualified name
        assert "subpkg.Ok" in mgr.routines
        assert "Failed to load subpkg/broken" in caplog.text


@pytest.mark.unit
class TestPythonRoutineMissingDirectory:
    """Constructor logs warning when routines_dir does not exist (line 71)."""

    def test_missing_directory_logs_warning(self, tmp_path, caplog):
        nonexistent = tmp_path / "does_not_exist"
        with caplog.at_level("WARNING"):
            mgr = PythonRoutineManager(str(nonexistent))
        assert "not found" in caplog.text
        assert mgr.routines == {}


@pytest.mark.unit
class TestPythonRoutineLoadModuleSpecError:
    """_load_module raises ImportError when spec_from_file_location returns None (line 160)."""

    def test_invalid_path_raises_import_error(self, tmp_path, monkeypatch):
        """Force spec_from_file_location to return None to hit line 160."""
        mgr = PythonRoutineManager(str(tmp_path))
        from pathlib import Path
        import importlib.util as _iutil

        monkeypatch.setattr(_iutil, "spec_from_file_location", lambda *a, **kw: None)
        with pytest.raises(ImportError, match="Cannot load module"):
            mgr._load_module(Path(str(tmp_path / "anything.py")))


@pytest.mark.unit
class TestPythonRoutineGetAllAndList:
    """get_all_routines returns a copy (line 201) and list_routines works (line 240)."""

    def test_get_all_returns_copy(self, tmp_path):
        _write_py_file(tmp_path, "demo.py", "x = 1")
        mgr = PythonRoutineManager(str(tmp_path))
        all_r = mgr.get_all_routines()
        assert "Demo" in all_r
        # Mutate the returned dict; should not affect the manager
        all_r["NewKey"] = "x"
        assert "NewKey" not in mgr.routines

    def test_list_routines_returns_keys(self, tmp_path):
        _write_py_file(tmp_path, "alpha.py", "a = 1")
        _write_py_file(tmp_path, "beta.py", "b = 2")
        mgr = PythonRoutineManager(str(tmp_path))
        names = mgr.list_routines()
        assert "Alpha" in names
        assert "Beta" in names


@pytest.mark.unit
class TestPythonRoutineReload:
    """reload_routine paths (222-231)."""

    def test_reload_unknown_routine_logs_warning(self, tmp_path, caplog):
        mgr = PythonRoutineManager(str(tmp_path))
        with caplog.at_level("WARNING"):
            mgr.reload_routine("NonExistent")
        assert "not found, cannot reload" in caplog.text

    def test_reload_known_routine_invokes_importlib(self, tmp_path, monkeypatch, caplog):
        """The success path calls importlib.reload (line 228) and logs INFO (229).

        Patching importlib.reload to a no-op that returns the module exercises
        the success branch deterministically -- the real importlib.reload
        depends on the module having been loaded via the spec system that
        survives across imports.
        """
        _write_py_file(tmp_path, "rel_routine.py", "value = 1")
        mgr = PythonRoutineManager(str(tmp_path))
        import importlib
        monkeypatch.setattr(importlib, "reload", lambda mod: mod)
        with caplog.at_level("INFO"):
            mgr.reload_routine("RelRoutine")
        assert "Reloaded routine: RelRoutine" in caplog.text

    def test_reload_failure_logged(self, tmp_path, caplog, monkeypatch):
        _write_py_file(tmp_path, "rel2.py", "v = 1")
        mgr = PythonRoutineManager(str(tmp_path))
        # Force importlib.reload to raise
        import importlib
        def boom(_module):
            raise RuntimeError("forced reload failure")
        monkeypatch.setattr(importlib, "reload", boom)
        with caplog.at_level("ERROR"):
            mgr.reload_routine("Rel2")
        assert "Failed to reload Rel2" in caplog.text
