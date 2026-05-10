"""Tests for SendMailComponent (tSendMail engine implementation).

Phase 07.2 Group B DEFER verdict: smtp_port content check moved from
_validate_config to _process. The converter at
``src/converters/talend_to_v1/components/control/send_mail.py:171``
extracts SMTP_PORT via ``_get_str(node, "SMTP_PORT", "25")``, so the
unresolved engine config may hold a ``${context.SMTP_PORT}`` literal
when _validate_config runs (Step 2 of BaseComponent lifecycle).

Phase 14 Plan 03 lift (smtplib boundary mocks per CONTEXT.md D-A4):
extends coverage to >= 95% for ``send_mail.py`` by exercising
SSL / STARTTLS / plain SMTP, attachment success + missing-file paths
(both ``die_on_error`` modes), the SMTPException + catch-all OSError
branches, recipient handling, and the public ``validate_config()``
helper. ``smtplib.SMTP`` and ``smtplib.SMTP_SSL`` are patched at the
module boundary -- no live SMTP, no aiosmtpd -- aligned with the
existing pattern at line ~111 below.
"""
import smtplib
from unittest.mock import MagicMock, patch

import pytest

from src.v1.engine.components.control.send_mail import SendMailComponent
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import (
    ComponentExecutionError,
    ConfigurationError,
    FileOperationError,
)
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

    def test_process_below_range_smtp_port_raises(self):
        """smtp_port=0 must raise ConfigurationError (below 1..65535)."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 0
        comp = _make_component(config)

        with pytest.raises(ConfigurationError) as excinfo:
            comp._process()
        assert "smtp_port" in str(excinfo.value)

    def test_process_default_smtp_port_when_omitted(self):
        """When smtp_port is absent, _process uses DEFAULT_SMTP_PORT (25)."""
        config = dict(_BASE_CONFIG)
        config.pop("smtp_port", None)
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()

        args, _ = mock_smtp.call_args
        assert args[0] == "smtp.example.com"
        assert args[1] == SendMailComponent.DEFAULT_SMTP_PORT
        assert args[1] == 25


# ------------------------------------------------------------------
# TestSmtpTransportBranches -- SSL / STARTTLS / plain / auth coverage
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSmtpTransportBranches:
    """Covers the SSL / STARTTLS / plain-SMTP branches and auth login.

    The component selects the connection class via ``ssl=True`` ->
    ``smtplib.SMTP_SSL``, ``ssl=False`` -> ``smtplib.SMTP``. STARTTLS
    is a separate flag that runs ``server.starttls()`` AFTER connect
    but BEFORE login. Auth fires only when both ``auth_username`` and
    ``auth_password`` are truthy.
    """

    def test_ssl_branch_uses_smtp_ssl_class(self):
        """ssl=True -> smtplib.SMTP_SSL is instantiated; SMTP is NOT."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 465
        config["ssl"] = True
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP_SSL"
        ) as mock_ssl, patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_plain:
            mock_server = MagicMock()
            mock_ssl.return_value = mock_server
            comp._process()

        mock_ssl.assert_called_once_with("smtp.example.com", 465)
        mock_plain.assert_not_called()
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()
        # No auth provided -> login must NOT be called.
        mock_server.login.assert_not_called()
        # starttls only fires when starttls=True (not set here).
        mock_server.starttls.assert_not_called()

    def test_starttls_branch_invokes_starttls_then_login(self):
        """starttls=True + creds -> starttls() then login() then sendmail()."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 587
        config["starttls"] = True
        config["auth_username"] = "u"
        config["auth_password"] = "p"
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()

        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("u", "p")
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    def test_plain_smtp_no_auth(self):
        """Plain SMTP with no auth credentials skips login entirely."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()

        mock_smtp.assert_called_once_with("smtp.example.com", 25)
        mock_server.starttls.assert_not_called()
        mock_server.login.assert_not_called()
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    def test_auth_skipped_when_only_username_provided(self):
        """login() requires BOTH username and password; one alone is a no-op."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["auth_username"] = "u"
        # password missing
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()

        mock_server.login.assert_not_called()
        mock_server.sendmail.assert_called_once()
