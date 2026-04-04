"""Tests for SendMailConverter (tSendMail -> v1 send_mail config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.send_mail import SendMailConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="sm_1",
               component_type="tSendMail"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 400, "y": 300},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
        ]
    }


def _make_attachments_data(rows):
    """Generate ATTACHMENTS TABLE data with stride-2 per row.

    rows: list of (file_path, content_transfer_encoding) tuples
    """
    result = []
    for file_path, encoding in rows:
        result.append({"elementRef": "FILE", "value": file_path})
        result.append({"elementRef": "CONTENT_TRANSFER_ENCODING", "value": encoding})
    return result


def _make_headers_data(rows):
    """Generate HEADERS TABLE data with stride-2 per row.

    rows: list of (key, value) tuples
    """
    result = []
    for key, value in rows:
        result.append({"elementRef": "KEY", "value": key})
        result.append({"elementRef": "VALUE", "value": value})
    return result


def _make_configs_data(rows):
    """Generate CONFIGS TABLE data with stride-2 per row.

    rows: list of (key, value) tuples
    """
    result = []
    for key, value in rows:
        result.append({"elementRef": "KEY", "value": key})
        result.append({"elementRef": "VALUE", "value": value})
    return result


def _convert(params=None, schema=None, component_id="sm_1"):
    """Helper: create node and convert, return ComponentResult."""
    node = _make_node(params=params, schema=schema, component_id=component_id)
    return SendMailConverter().convert(node, [], {})


def _cfg(params=None, schema=None, component_id="sm_1"):
    """Helper: return the config dict from a conversion."""
    return _convert(params=params, schema=schema, component_id=component_id).component["config"]


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tSendMail") is SendMailConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_to_default(self):
        assert _cfg()["to"] == "receiver@example.com"

    def test_from_default(self):
        assert _cfg()["from_email"] == "send@example.com"

    def test_need_personal_name_default(self):
        assert _cfg()["need_personal_name"] is False

    def test_personal_name_default(self):
        assert _cfg()["personal_name"] == "sender"

    def test_cc_default(self):
        assert _cfg()["cc"] == "carbon@example.com"

    def test_bcc_default(self):
        assert _cfg()["bcc"] == "blindcarbon@example.com"

    def test_subject_default(self):
        assert _cfg()["subject"] == "Talaxie Open Studio notification"

    def test_message_default(self):
        assert _cfg()["message"] == "Hello"

    def test_check_attachment_default(self):
        assert _cfg()["check_attachment"] is True

    def test_attachments_default(self):
        assert _cfg()["attachments"] == []

    def test_headers_default(self):
        assert _cfg()["headers"] == []

    def test_smtp_host_default(self):
        assert _cfg()["smtp_host"] == "smtp.provider.com"

    def test_smtp_port_default(self):
        assert _cfg()["smtp_port"] == "25"

    def test_ssl_default(self):
        assert _cfg()["ssl"] is False

    def test_starttls_default(self):
        assert _cfg()["starttls"] is False

    def test_importance_default(self):
        assert _cfg()["importance"] == "NORMAL"

    def test_auth_mode_default(self):
        assert _cfg()["auth_mode"] == "BASIC"

    def test_auth_username_default(self):
        assert _cfg()["auth_username"] == "username"

    def test_auth_password_default(self):
        assert _cfg()["auth_password"] == "password"

    def test_token_default(self):
        assert _cfg()["token"] == "password"

    def test_die_on_error_default(self):
        assert _cfg()["die_on_error"] is True

    def test_text_subtype_default(self):
        assert _cfg()["text_subtype"] == "PLAIN"

    def test_encoding_default(self):
        assert _cfg()["encoding"] == "ISO-8859-15"

    def test_set_localhost_default(self):
        assert _cfg()["set_localhost"] is False

    def test_localhost_default(self):
        assert _cfg()["localhost"] == "localhost"

    def test_use_two_line_token_default(self):
        assert _cfg()["use_two_line_token"] is False

    def test_configs_default(self):
        assert _cfg()["configs"] == []


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_to_extracted(self):
        assert _cfg({"TO": '"user@test.com"'})["to"] == "user@test.com"

    def test_from_extracted(self):
        assert _cfg({"FROM": '"noreply@test.com"'})["from_email"] == "noreply@test.com"

    def test_smtp_host_extracted(self):
        assert _cfg({"SMTP_HOST": '"mail.corp.com"'})["smtp_host"] == "mail.corp.com"

    def test_smtp_port_extracted(self):
        assert _cfg({"SMTP_PORT": '"587"'})["smtp_port"] == "587"

    def test_ssl_true(self):
        assert _cfg({"SSL": "true"})["ssl"] is True

    def test_starttls_true(self):
        assert _cfg({"STARTTLS": "true"})["starttls"] is True

    def test_die_on_error_false(self):
        assert _cfg({"DIE_ON_ERROR": "false"})["die_on_error"] is False

    def test_need_personal_name_true(self):
        assert _cfg({"NEED_PERSONAL_NAME": "true"})["need_personal_name"] is True

    def test_personal_name_extracted(self):
        assert _cfg({"PERSONAL_NAME": '"John Doe"'})["personal_name"] == "John Doe"

    def test_check_attachment_false(self):
        assert _cfg({"CHECK_ATTACHMENT": "false"})["check_attachment"] is False

    def test_auth_mode_no_auth(self):
        assert _cfg({"AUTH_MODE": '"NO_AUTH"'})["auth_mode"] == "NO_AUTH"

    def test_auth_mode_oauth2(self):
        assert _cfg({"AUTH_MODE": '"OAUTH2"'})["auth_mode"] == "OAUTH2"

    def test_auth_username_extracted(self):
        assert _cfg({"AUTH_USERNAME": '"myuser"'})["auth_username"] == "myuser"

    def test_auth_password_extracted(self):
        assert _cfg({"AUTH_PASSWORD": '"mypass"'})["auth_password"] == "mypass"

    def test_token_extracted(self):
        assert _cfg({"TOKEN": '"oauth_tok_123"'})["token"] == "oauth_tok_123"

    def test_importance_high(self):
        assert _cfg({"IMPORTANCE": '"HIGH"'})["importance"] == "HIGH"

    def test_importance_low(self):
        assert _cfg({"IMPORTANCE": '"LOW"'})["importance"] == "LOW"

    def test_text_subtype_html(self):
        assert _cfg({"TEXT_SUBTYPE": '"HTML"'})["text_subtype"] == "HTML"

    def test_encoding_utf8(self):
        assert _cfg({"ENCODING": '"UTF-8"'})["encoding"] == "UTF-8"

    def test_set_localhost_true(self):
        assert _cfg({"SET_LOCALHOST": "true"})["set_localhost"] is True

    def test_localhost_extracted(self):
        assert _cfg({"LOCALHOST": '"myhost.local"'})["localhost"] == "myhost.local"

    def test_use_two_line_token_true(self):
        assert _cfg({"USE_TWO_LINE_TOKEN": "true"})["use_two_line_token"] is True

    def test_subject_extracted(self):
        assert _cfg({"SUBJECT": '"Job Complete"'})["subject"] == "Job Complete"

    def test_message_extracted(self):
        assert _cfg({"MESSAGE": '"Job ran OK"'})["message"] == "Job ran OK"

    def test_cc_extracted(self):
        assert _cfg({"CC": '"mgr@test.com"'})["cc"] == "mgr@test.com"

    def test_bcc_extracted(self):
        assert _cfg({"BCC": '"archive@test.com"'})["bcc"] == "archive@test.com"

    def test_auth_mode_fallback_from_need_auth_true(self):
        """When AUTH_MODE missing but NEED_AUTH=true, auth_mode should be BASIC."""
        assert _cfg({"NEED_AUTH": "true"})["auth_mode"] == "BASIC"

    def test_auth_mode_fallback_from_need_auth_false(self):
        """When AUTH_MODE missing and NEED_AUTH=false, auth_mode should be NO_AUTH."""
        assert _cfg({"NEED_AUTH": "false"})["auth_mode"] == "NO_AUTH"


class TestTableParsing:
    """Verify TABLE parameter parsing for ATTACHMENTS, HEADERS, and CONFIGS."""

    # ---- ATTACHMENTS ----

    def test_attachments_parsed(self):
        """ATTACHMENTS TABLE with FILE + CONTENT_TRANSFER_ENCODING pairs."""
        data = _make_attachments_data([("/tmp/report.pdf", "BASE64")])
        cfg = _cfg({"ATTACHMENTS": data})
        assert cfg["attachments"] == [
            {"file": "/tmp/report.pdf", "content_transfer_encoding": "BASE64"},
        ]

    def test_attachments_empty_when_missing(self):
        """No ATTACHMENTS param returns empty list."""
        assert _cfg()["attachments"] == []

    def test_attachments_empty_list(self):
        """Explicit empty ATTACHMENTS list returns empty list."""
        assert _cfg({"ATTACHMENTS": []})["attachments"] == []

    def test_attachments_multiple_entries(self):
        """Multiple attachment entries parsed correctly."""
        data = _make_attachments_data([
            ("/tmp/report.pdf", "BASE64"),
            ("/tmp/data.csv", "DEFAULT"),
            ("/tmp/log.txt", "7BIT"),
        ])
        cfg = _cfg({"ATTACHMENTS": data})
        assert len(cfg["attachments"]) == 3
        assert cfg["attachments"][0]["file"] == "/tmp/report.pdf"
        assert cfg["attachments"][1]["file"] == "/tmp/data.csv"
        assert cfg["attachments"][2]["file"] == "/tmp/log.txt"
        assert cfg["attachments"][0]["content_transfer_encoding"] == "BASE64"
        assert cfg["attachments"][1]["content_transfer_encoding"] == "DEFAULT"
        assert cfg["attachments"][2]["content_transfer_encoding"] == "7BIT"

    # ---- HEADERS ----

    def test_headers_parsed(self):
        """HEADERS TABLE with KEY + VALUE pairs."""
        data = _make_headers_data([("X-Priority", "1")])
        cfg = _cfg({"HEADERS": data})
        assert cfg["headers"] == [{"key": "X-Priority", "value": "1"}]

    def test_headers_empty_when_missing(self):
        """No HEADERS param returns empty list."""
        assert _cfg()["headers"] == []

    def test_headers_multiple_entries(self):
        """Multiple header entries parsed correctly."""
        data = _make_headers_data([
            ("X-Priority", "1"),
            ("X-Mailer", "Talend"),
        ])
        cfg = _cfg({"HEADERS": data})
        assert len(cfg["headers"]) == 2
        assert cfg["headers"][0] == {"key": "X-Priority", "value": "1"}
        assert cfg["headers"][1] == {"key": "X-Mailer", "value": "Talend"}

    # ---- CONFIGS ----

    def test_configs_parsed(self):
        """CONFIGS TABLE with KEY + VALUE pairs."""
        data = _make_configs_data([("mail.smtp.timeout", "30000")])
        cfg = _cfg({"CONFIGS": data})
        assert cfg["configs"] == [{"key": "mail.smtp.timeout", "value": "30000"}]

    def test_configs_empty_when_missing(self):
        """No CONFIGS param returns empty list."""
        assert _cfg()["configs"] == []

    def test_configs_multiple_entries(self):
        """Multiple config entries parsed correctly."""
        data = _make_configs_data([
            ("mail.smtp.timeout", "30000"),
            ("mail.smtp.connectiontimeout", "10000"),
        ])
        cfg = _cfg({"CONFIGS": data})
        assert len(cfg["configs"]) == 2
        assert cfg["configs"][0] == {"key": "mail.smtp.timeout", "value": "30000"}
        assert cfg["configs"][1] == {"key": "mail.smtp.connectiontimeout", "value": "10000"}


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        assert _cfg()["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        assert _cfg({"TSTATCATCHER_STATS": "true"})["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        assert _cfg()["label"] == ""

    def test_label_extracted(self):
        assert _cfg({"LABEL": '"my_label"'})["label"] == "my_label"


class TestSchema:
    """Verify schema handling for utility component."""

    def test_schema_empty_for_utility_component(self):
        """SendMail is a utility component -- no data flow schema."""
        result = _convert()
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Converter should produce at least 11 engine_gap entries."""
        result = _convert()
        assert len(result.needs_review) >= 11

    def test_needs_review_severity_all_engine_gap(self):
        """All needs_review entries must have severity 'engine_gap'."""
        result = _convert()
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries must reference the component_id."""
        result = _convert(component_id="test_comp")
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_needs_review_encoding_mismatch(self):
        """There should be a needs_review entry for encoding default mismatch."""
        result = _convert()
        issues = [e["issue"] for e in result.needs_review]
        assert any("encoding" in issue.lower() for issue in issues), (
            "Expected needs_review entry for encoding mismatch"
        )

    def test_needs_review_expected_keys(self):
        """All 11 engine gap keys should have needs_review entries."""
        result = _convert()
        issues = " ".join(e["issue"] for e in result.needs_review)
        expected_keys = [
            "need_personal_name", "personal_name", "check_attachment",
            "headers", "importance", "auth_mode", "token",
            "set_localhost", "localhost", "use_two_line_token", "configs",
        ]
        for key in expected_keys:
            assert key in issues, f"Expected needs_review for '{key}' not found"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        result = _convert()
        for entry in result.needs_review:
            issue_lower = entry["issue"].lower()
            assert "tstatcatcher_stats" not in issue_lower
            # Check for exact 'label' as standalone concept, not substring of 'localhost'
            assert entry["issue"] != "Engine does not read 'label' from config"


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All 27 + 2 framework = 29 config keys must be present."""
        cfg = _cfg()
        expected_keys = {
            "to", "from_email", "need_personal_name", "personal_name",
            "cc", "bcc", "subject", "message",
            "check_attachment", "attachments", "headers",
            "smtp_host", "smtp_port", "ssl", "starttls",
            "importance", "auth_mode", "auth_username", "auth_password",
            "token", "die_on_error",
            "text_subtype", "encoding",
            "set_localhost", "localhost", "use_two_line_token", "configs",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(cfg.keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_config_key_count(self):
        """Config should have exactly 29 keys."""
        cfg = _cfg()
        assert len(cfg) == 29, f"Expected 29 config keys, got {len(cfg)}: {sorted(cfg.keys())}"


class TestPhantomParams:
    """Verify no phantom params are extracted.

    tSendMail has no known phantom params -- the converter correctly maps
    all _java.xml params. This class verifies no unexpected keys appear.
    """

    def test_no_unexpected_config_keys(self):
        """Only expected keys should be in config."""
        cfg = _cfg()
        expected_keys = {
            "to", "from_email", "need_personal_name", "personal_name",
            "cc", "bcc", "subject", "message",
            "check_attachment", "attachments", "headers",
            "smtp_host", "smtp_port", "ssl", "starttls",
            "importance", "auth_mode", "auth_username", "auth_password",
            "token", "die_on_error",
            "text_subtype", "encoding",
            "set_localhost", "localhost", "use_two_line_token", "configs",
            "tstatcatcher_stats", "label",
        }
        unexpected = set(cfg.keys()) - expected_keys
        assert not unexpected, f"Unexpected config keys: {unexpected}"


class TestWarnings:
    """Verify validation warnings."""

    def test_no_warnings_when_valid(self):
        """No warnings when SMTP_HOST and TO are provided."""
        result = _convert({"SMTP_HOST": '"smtp.test.com"', "TO": '"user@test.com"'})
        assert result.warnings == []

    def test_warning_when_smtp_host_empty(self):
        """Warning when SMTP_HOST is explicitly empty."""
        result = _convert({"SMTP_HOST": '""', "TO": '"user@test.com"'})
        assert any("SMTP_HOST" in w for w in result.warnings)

    def test_warning_when_to_empty(self):
        """Warning when TO is explicitly empty."""
        result = _convert({"SMTP_HOST": '"smtp.test.com"', "TO": '""'})
        assert any("TO" in w for w in result.warnings)

    def test_both_warnings_when_both_empty(self):
        """Both warnings when SMTP_HOST and TO explicitly empty."""
        result = _convert({"SMTP_HOST": '""', "TO": '""'})
        assert len(result.warnings) == 2

    def test_component_structure(self):
        """Verify the full component dict structure."""
        result = _convert({"SMTP_HOST": '"smtp.test.com"', "TO": '"user@test.com"'})
        comp = result.component
        assert comp["id"] == "sm_1"
        assert comp["type"] == "SendMailComponent"
        assert comp["original_type"] == "tSendMail"
        assert comp["position"] == {"x": 400, "y": 300}
        assert comp["schema"] == {"input": [], "output": []}
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert isinstance(comp["config"], dict)
