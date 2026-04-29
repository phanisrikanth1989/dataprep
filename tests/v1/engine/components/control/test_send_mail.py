"""Tests for SendMailComponent (tSendMail engine implementation).

Phase 07.2 Group B DEFER verdict: smtp_port content check moved from
_validate_config to _process. The converter at
``src/converters/talend_to_v1/components/control/send_mail.py:171``
extracts SMTP_PORT via ``_get_str(node, "SMTP_PORT", "25")``, so the
unresolved engine config may hold a ``${context.SMTP_PORT}`` literal
when _validate_config runs (Step 2 of BaseComponent lifecycle).

These tests pin:
  1. _validate_config accepts an unresolved ``${context.PORT}`` string.
  2. _validate_config accepts a string-of-int (e.g. "587").
  3. _process resolves a context-var port and connects with the int.
  4. _process raises ConfigurationError on a non-numeric resolved port.
  5. _process raises ConfigurationError on an out-of-range resolved port.
"""
from unittest.mock import MagicMock, patch

import pytest

from src.v1.engine.components.control.send_mail import SendMailComponent
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


_BASE_CONFIG = {
    "component_type": "SendMailComponent",
    "smtp_host": "smtp.example.com",
    "from_email": "from@example.com",
    "to": ["to@example.com"],
    "subject": "Test",
    "message": "Hello",
}


def _make_component(config, context_manager=None):
    """Create a SendMailComponent and populate self.config.

    BaseComponent only assigns ``self.config`` from ``_original_config`` at
    the start of ``execute()``. For direct ``_validate_config()`` /
    ``_process()`` calls in unit tests we mirror that lifecycle step
    manually.
    """
    cm = context_manager if context_manager is not None else ContextManager()
    comp = SendMailComponent(
        component_id="tSM_1",
        config=config,
        global_map=GlobalMap(),
        context_manager=cm,
    )
    # Mirror execute() Step 1: populate working config from original.
    comp.config = dict(config)
    return comp


# ------------------------------------------------------------------
# TestValidateConfigDeferred -- _validate_config accepts unresolved values
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidateConfigDeferred:
    """_validate_config must NOT reject unresolved smtp_port values.

    Pre-fix bug: isinstance(smtp_port, int) check rejected
    ``"${context.PORT}"`` as a non-int. Post-fix the content check is
    deferred to _process (after context-var resolution).
    """

    def test_validate_config_accepts_context_var_smtp_port(self):
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = "${context.PORT}"
        comp = _make_component(config)
        errors = comp._validate_config()
        assert all("smtp_port" not in err for err in errors), (
            f"Expected no smtp_port error, got: {errors}"
        )

    def test_validate_config_accepts_string_int_smtp_port(self):
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = "587"
        comp = _make_component(config)
        errors = comp._validate_config()
        assert all("smtp_port" not in err for err in errors), (
            f"Expected no smtp_port error, got: {errors}"
        )


# ------------------------------------------------------------------
# TestProcessSmtpPort -- _process performs the post-resolution port check
# ------------------------------------------------------------------


@pytest.mark.unit
class TestProcessSmtpPort:
    """_process is the new home for the smtp_port content check."""

    def test_process_resolves_context_var_smtp_port(self):
        """With context PORT=587, _process must connect with port=587."""
        cm = ContextManager()
        cm.set("PORT", "587", "id_String")

        config = dict(_BASE_CONFIG)
        config["smtp_port"] = "${context.PORT}"
        comp = _make_component(config, context_manager=cm)

        # Resolution happens at execute() Step 3; mirror it here.
        comp.config = cm.resolve_dict(comp.config)

        with patch("src.v1.engine.components.control.send_mail.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()

        mock_smtp.assert_called_once()
        args, kwargs = mock_smtp.call_args
        # smtplib.SMTP is called positionally as SMTP(host, port).
        assert args[0] == "smtp.example.com"
        assert args[1] == 587

    def test_process_invalid_resolved_smtp_port_raises(self):
        """A non-numeric resolved smtp_port must raise ConfigurationError."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = "not_a_number"
        comp = _make_component(config)

        with pytest.raises(ConfigurationError) as excinfo:
            comp._process()
        assert "smtp_port" in str(excinfo.value)

    def test_process_out_of_range_smtp_port_raises(self):
        """An out-of-range resolved smtp_port must raise ConfigurationError."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = "99999"
        comp = _make_component(config)

        with pytest.raises(ConfigurationError) as excinfo:
            comp._process()
        assert "smtp_port" in str(excinfo.value)
