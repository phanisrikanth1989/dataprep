"""Tests for the SendMailConverter (tSendMail -> SendMailComponent)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.send_mail import SendMailConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="sendmail_1",
               component_type="tSendMail"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 400, "y": 300},
        raw_xml=ET.Element("node"),
    )


class TestSendMailConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tSendMail") is SendMailConverter


class TestSendMailConverterBasic:
    def test_basic_conversion(self):
        node = _make_node(params={
            "SMTP_HOST": '"smtp.example.com"',
            "SMTP_PORT": "587",
            "FROM": '"sender@example.com"',
            "TO": '"user1@example.com;user2@example.com"',
            "CC": '"cc1@example.com"',
            "BCC": '""',
            "SUBJECT": '"Test Subject"',
            "MESSAGE": '"Hello World"',
            "SSL": "true",
            "STARTTLS": "false",
            "AUTH_USERNAME": '"myuser"',
            "AUTH_PASSWORD": '"mypass"',
            "DIE_ON_ERROR": "true",
        })
        result = SendMailConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "sendmail_1"
        assert comp["type"] == "SendMailComponent"
        assert comp["original_type"] == "tSendMail"
        assert comp["position"] == {"x": 400, "y": 300}
        assert comp["config"]["smtp_host"] == "smtp.example.com"
        assert comp["config"]["smtp_port"] == 587
        assert comp["config"]["from_email"] == "sender@example.com"
        assert comp["config"]["to"] == ["user1@example.com", "user2@example.com"]
        assert comp["config"]["cc"] == ["cc1@example.com"]
        assert comp["config"]["bcc"] == []
        assert comp["config"]["subject"] == "Test Subject"
        assert comp["config"]["message"] == "Hello World"
        assert comp["config"]["ssl"] is True
        assert comp["config"]["starttls"] is False
        assert comp["config"]["auth_username"] == "myuser"
        assert comp["config"]["auth_password"] == "mypass"
        assert comp["config"]["die_on_error"] is True
        assert comp["schema"] == {"input": [], "output": []}
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = SendMailConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["smtp_host"] == ""
        assert cfg["smtp_port"] == 25
        assert cfg["from_email"] == ""
        assert cfg["to"] == []
        assert cfg["cc"] == []
        assert cfg["bcc"] == []
        assert cfg["subject"] == ""
        assert cfg["message"] == ""
        assert cfg["ssl"] is False
        assert cfg["starttls"] is False
        assert cfg["auth_username"] == ""
        assert cfg["auth_password"] == ""
        assert cfg["die_on_error"] is True

    def test_semicolon_splitting_with_whitespace(self):
        """TO/CC/BCC values with extra whitespace around semicolons."""
        node = _make_node(params={
            "SMTP_HOST": '"mail.test.com"',
            "TO": '"a@x.com ; b@x.com ; c@x.com"',
            "CC": '" d@x.com ; e@x.com "',
            "BCC": '"f@x.com"',
        })
        result = SendMailConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["to"] == ["a@x.com", "b@x.com", "c@x.com"]
        assert cfg["cc"] == ["d@x.com", "e@x.com"]
        assert cfg["bcc"] == ["f@x.com"]

    def test_empty_semicolons_filtered_out(self):
        """Trailing or consecutive semicolons should not produce empty entries."""
        node = _make_node(params={
            "SMTP_HOST": '"mail.test.com"',
            "TO": '"a@x.com;;b@x.com;"',
        })
        result = SendMailConverter().convert(node, [], {})

        assert result.component["config"]["to"] == ["a@x.com", "b@x.com"]

    def test_die_on_error_defaults_to_true(self):
        """DIE_ON_ERROR should default to True when not provided."""
        node = _make_node(params={
            "SMTP_HOST": '"smtp.test.com"',
            "TO": '"x@y.com"',
        })
        result = SendMailConverter().convert(node, [], {})

        assert result.component["config"]["die_on_error"] is True

    def test_die_on_error_false(self):
        node = _make_node(params={
            "SMTP_HOST": '"smtp.test.com"',
            "TO": '"x@y.com"',
            "DIE_ON_ERROR": "false",
        })
        result = SendMailConverter().convert(node, [], {})

        assert result.component["config"]["die_on_error"] is False

    def test_ssl_and_starttls_booleans(self):
        node = _make_node(params={
            "SMTP_HOST": '"host"',
            "TO": '"a@b.com"',
            "SSL": "false",
            "STARTTLS": "true",
        })
        result = SendMailConverter().convert(node, [], {})

        assert result.component["config"]["ssl"] is False
        assert result.component["config"]["starttls"] is True


class TestSendMailConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """SendMail is a utility component — no data flow schema."""
        node = _make_node(params={
            "SMTP_HOST": '"smtp.test.com"',
            "TO": '"user@test.com"',
        })
        result = SendMailConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


class TestSendMailConverterWarnings:
    def test_no_warnings_when_valid(self):
        node = _make_node(params={
            "SMTP_HOST": '"smtp.example.com"',
            "TO": '"user@example.com"',
        })
        result = SendMailConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []

    def test_warning_when_smtp_host_empty(self):
        node = _make_node(params={
            "TO": '"user@example.com"',
        })
        result = SendMailConverter().convert(node, [], {})

        assert any("SMTP_HOST" in w for w in result.warnings)

    def test_warning_when_to_empty(self):
        node = _make_node(params={
            "SMTP_HOST": '"smtp.test.com"',
        })
        result = SendMailConverter().convert(node, [], {})

        assert any("TO" in w for w in result.warnings)

    def test_both_warnings_when_both_missing(self):
        node = _make_node(params={})
        result = SendMailConverter().convert(node, [], {})

        assert len(result.warnings) == 2
        warning_text = " ".join(result.warnings)
        assert "SMTP_HOST" in warning_text
        assert "TO" in warning_text
