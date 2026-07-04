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


# ------------------------------------------------------------------
# TestAttachments -- success path + missing-file under both die modes
# ------------------------------------------------------------------


@pytest.mark.unit
class TestAttachments:
    """Attachment loop coverage: success, missing file, unreadable file.

    The component opens each path with ``open(path, 'rb')``. A
    ``FileNotFoundError`` is the missing-file branch; any other
    Exception (e.g. PermissionError, IsADirectoryError) lands in the
    generic ``except Exception`` branch. Each branch has die_on_error
    True/False sub-paths.
    """

    def test_attachment_success_attaches_to_message(self, tmp_path):
        """A real file path attaches and the SMTP send still runs."""
        att = tmp_path / "report.txt"
        att.write_bytes(b"hello attachment")

        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["attachments"] = [str(att)]
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()

        # sendmail args: (from_email, all_recipients, msg_as_string)
        args, _ = mock_server.sendmail.call_args
        msg_str = args[2]
        # MIME multipart with attachment must reference the filename in
        # the Content-Disposition header.
        assert "report.txt" in msg_str
        assert "Content-Disposition" in msg_str

    def test_attachment_missing_die_on_error_true_raises(self, tmp_path):
        """Missing file with die_on_error=True raises FileOperationError."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["attachments"] = [str(tmp_path / "missing.txt")]
        config["die_on_error"] = True
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ):
            with pytest.raises(FileOperationError) as excinfo:
                comp._process()

        assert "Attachment file not found" in str(excinfo.value)

    def test_attachment_missing_die_on_error_false_skips_and_continues(
        self, tmp_path
    ):
        """Missing file with die_on_error=False logs warning + still sends."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["attachments"] = [str(tmp_path / "missing.txt")]
        config["die_on_error"] = False
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()

        # The send still proceeds despite the missing attachment.
        mock_server.sendmail.assert_called_once()

    def test_attachment_unreadable_die_on_error_true_raises(self, tmp_path):
        """Non-FileNotFoundError -> generic except branch -> FileOperationError."""
        # Use a directory path; open(path, 'rb') on a directory raises
        # IsADirectoryError (subclass of OSError) which lands in the
        # generic ``except Exception`` branch (not FileNotFoundError).
        att_dir = tmp_path / "not_a_file"
        att_dir.mkdir()

        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["attachments"] = [str(att_dir)]
        config["die_on_error"] = True
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ):
            with pytest.raises(FileOperationError) as excinfo:
                comp._process()

        assert "Failed to read attachment" in str(excinfo.value)

    def test_attachment_unreadable_die_on_error_false_skips(self, tmp_path):
        """Non-FileNotFoundError + die_on_error=False -> warning, send proceeds."""
        att_dir = tmp_path / "not_a_file"
        att_dir.mkdir()

        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["attachments"] = [str(att_dir)]
        config["die_on_error"] = False
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()

        mock_server.sendmail.assert_called_once()


# ------------------------------------------------------------------
# TestSendFailureBranches -- SMTPException / OSError / generic Exception
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSendFailureBranches:
    """SMTP-send failure branches.

    The component wraps the connect/login/sendmail/quit block in a
    try/except that catches (smtplib.SMTPException, ConnectionError,
    OSError) -> ComponentExecutionError, plus a catch-all ``Exception``
    that wraps any other error type into ComponentExecutionError.
    """

    def test_smtp_exception_die_on_error_true_raises_component_error(self):
        """SMTPException with die_on_error=True -> ComponentExecutionError."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["die_on_error"] = True
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            mock_server.sendmail.side_effect = smtplib.SMTPException(
                "boom"
            )
            with pytest.raises(ComponentExecutionError) as excinfo:
                comp._process()

        assert "Failed to send email" in str(excinfo.value)
        assert excinfo.value.component_id == "tSM_1"

    def test_smtp_exception_die_on_error_false_swallows_and_continues(self):
        """SMTPException with die_on_error=False logs warning + returns."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["die_on_error"] = False
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            mock_server.sendmail.side_effect = smtplib.SMTPException(
                "transient"
            )
            # No raise expected.
            result = comp._process()

        assert result == {}

    def test_oserror_die_on_error_true_raises_component_error(self):
        """OSError (e.g. ConnectionRefusedError) -> ComponentExecutionError."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["die_on_error"] = True
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_smtp.side_effect = OSError("connection refused")
            with pytest.raises(ComponentExecutionError):
                comp._process()

    def test_generic_exception_die_on_error_true_raises_component_error(self):
        """Catch-all branch wraps non-SMTP/OS errors into ComponentExecutionError."""
        # ValueError is NOT in (SMTPException, ConnectionError, OSError) -- it
        # falls through to the second except Exception block.
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["die_on_error"] = True
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            mock_server.sendmail.side_effect = ValueError("unexpected")
            with pytest.raises(ComponentExecutionError) as excinfo:
                comp._process()

        assert "Unexpected error sending email" in str(excinfo.value)

    def test_generic_exception_die_on_error_false_swallows(self):
        """Catch-all branch with die_on_error=False returns silently."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["die_on_error"] = False
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            mock_server.sendmail.side_effect = ValueError("unexpected")
            # Component must NOT raise; _process returns {}.
            result = comp._process()

        assert result == {}


# ------------------------------------------------------------------
# TestValidateConfigErrors -- required-field + list-shape validation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidateConfigErrors:
    """Error branches in _validate_config + ConfigurationError raise path.

    These cover lines 105 (required-field error), 110 (empty/non-list to),
    119 (non-list cc/bcc/attachments), and 143-145 (the join + raise path).
    """

    def test_missing_smtp_host_yields_required_error(self):
        config = {
            "component_type": "SendMailComponent",
            "from_email": "from@example.com",
            "to": ["to@example.com"],
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert any("smtp_host" in err for err in errors)

    def test_missing_from_email_yields_required_error(self):
        config = {
            "component_type": "SendMailComponent",
            "smtp_host": "smtp.example.com",
            "to": ["to@example.com"],
        }
        comp = _make_component(config)
        errors = comp._validate_config()
        assert any("from_email" in err for err in errors)

    def test_empty_to_list_yields_error(self):
        config = dict(_BASE_CONFIG)
        config["to"] = []
        comp = _make_component(config)
        errors = comp._validate_config()
        assert any("non-empty list" in err for err in errors)

    def test_non_list_to_yields_error(self):
        config = dict(_BASE_CONFIG)
        config["to"] = "to@example.com"  # string, not list
        comp = _make_component(config)
        errors = comp._validate_config()
        assert any("non-empty list" in err for err in errors)

    @pytest.mark.parametrize("field", ["cc", "bcc", "attachments"])
    def test_non_list_cc_bcc_attachments_yields_error(self, field):
        config = dict(_BASE_CONFIG)
        config[field] = "not-a-list"
        comp = _make_component(config)
        errors = comp._validate_config()
        assert any(f"'{field}' must be a list" in err for err in errors)

    def test_process_raises_configuration_error_when_validate_fails(self):
        """_process re-raises validate errors as ConfigurationError."""
        config = {
            "component_type": "SendMailComponent",
            "smtp_host": "smtp.example.com",
            # missing from_email and to -> two errors
        }
        comp = _make_component(config)
        with pytest.raises(ConfigurationError) as excinfo:
            comp._process()
        # Both missing fields should appear in the joined message.
        assert "from_email" in str(excinfo.value)
        assert "to" in str(excinfo.value)


# ------------------------------------------------------------------
# TestRecipientHandling -- to/cc/bcc are concatenated for the envelope
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRecipientHandling:
    """The envelope passed to sendmail() is to + cc + bcc.

    Headers (To/Cc) are joined with ', ' but Bcc deliberately stays
    out of the headers (standard email-privacy behavior). The envelope
    arg, however, includes Bcc.
    """

    def test_envelope_includes_to_cc_bcc(self):
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["cc"] = ["cc1@example.com", "cc2@example.com"]
        config["bcc"] = ["bcc@example.com"]
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()

        args, _ = mock_server.sendmail.call_args
        envelope_recipients = args[1]
        assert envelope_recipients == [
            "to@example.com",
            "cc1@example.com",
            "cc2@example.com",
            "bcc@example.com",
        ]
        # Bcc must NOT be in the rendered headers.
        msg_str = args[2]
        assert "bcc@example.com" not in msg_str
        # Cc IS in the headers.
        assert "cc1@example.com" in msg_str

    def test_default_empty_cc_bcc(self):
        """When cc/bcc absent, only 'to' recipients hit the envelope."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()

        args, _ = mock_server.sendmail.call_args
        assert args[1] == ["to@example.com"]


# ------------------------------------------------------------------
# TestPublicValidateConfig -- the legacy public validate_config() method
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPublicValidateConfig:
    """Coverage for the public ``validate_config()`` helper (lines 274-280).

    This is a separate code path from the internal ``_validate_config``;
    it returns bool and logs error rather than collecting a string list.
    """

    def test_validate_config_true_on_valid_config(self):
        comp = _make_component(dict(_BASE_CONFIG))
        assert comp.validate_config() is True

    @pytest.mark.parametrize("missing", ["smtp_host", "from_email", "to"])
    def test_validate_config_false_on_missing_required(self, missing):
        config = dict(_BASE_CONFIG)
        config.pop(missing)
        comp = _make_component(config)
        assert comp.validate_config() is False


# ------------------------------------------------------------------
# TestAsciiLogging -- enforce ASCII-only log messages (CLAUDE.md rule)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestAsciiLogging:
    """Project rule (memory feedback_ascii_logging): no unicode in logs.

    Uses the ``assert_ascii_logs`` fixture from Plan 14-01 root conftest.
    The fixture captures logs at DEBUG and asserts no non-ASCII bytes
    on teardown.
    """

    def test_happy_path_logs_are_ascii(self, assert_ascii_logs):
        """Plain successful send produces only ASCII log messages."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()
        # Fixture asserts ASCII on teardown -- no body assertion needed.
        # Positive content check on log capture (proves we captured DEBUG).
        assert any(
            "Sending email started" in r.getMessage()
            for r in assert_ascii_logs.records
        )

    def test_error_path_logs_are_ascii(self, assert_ascii_logs, tmp_path):
        """Missing-attachment + die_on_error=False warning path is ASCII."""
        config = dict(_BASE_CONFIG)
        config["smtp_port"] = 25
        config["attachments"] = [str(tmp_path / "missing.txt")]
        config["die_on_error"] = False
        comp = _make_component(config)

        with patch(
            "src.v1.engine.components.control.send_mail.smtplib.SMTP"
        ) as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            comp._process()
        # Fixture enforces ASCII on teardown.
        assert any(
            "Skipping missing attachment" in r.getMessage()
            for r in assert_ascii_logs.records
        )
