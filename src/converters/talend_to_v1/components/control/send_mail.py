"""Converter for Talend tSendMail component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


def _split_recipients(value: str) -> List[str]:
    """Split a semicolon-separated recipient string into a clean list."""
    return [e.strip() for e in value.split(";") if e.strip()]


@REGISTRY.register("tSendMail")
class SendMailConverter(ComponentConverter):
    """Convert a Talend tSendMail node into a v1 SendMailComponent component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        to_raw = self._get_str(node, "TO")
        cc_raw = self._get_str(node, "CC")
        bcc_raw = self._get_str(node, "BCC")

        config: Dict[str, Any] = {
            "smtp_host": self._get_str(node, "SMTP_HOST"),
            "smtp_port": self._get_int(node, "SMTP_PORT", default=25),
            "from_email": self._get_str(node, "FROM"),
            "to": _split_recipients(to_raw),
            "cc": _split_recipients(cc_raw),
            "bcc": _split_recipients(bcc_raw),
            "subject": self._get_str(node, "SUBJECT"),
            "message": self._get_str(node, "MESSAGE"),
            "ssl": self._get_bool(node, "SSL"),
            "starttls": self._get_bool(node, "STARTTLS"),
            "auth_username": self._get_str(node, "AUTH_USERNAME"),
            "auth_password": self._get_str(node, "AUTH_PASSWORD"),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", default=True),
        }

        if not config["smtp_host"]:
            warnings.append("SMTP_HOST is empty — this is a required parameter")
        if not config["to"]:
            warnings.append("TO is empty — at least one recipient is required")

        component = self._build_component_dict(
            node=node,
            type_name="SendMailComponent",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
