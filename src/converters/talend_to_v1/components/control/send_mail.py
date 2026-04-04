"""Converter for Talend tSendMail component.

Sends emails via SMTP with support for attachments, custom headers,
SSL/STARTTLS, and multiple authentication modes (NO_AUTH, BASIC, OAUTH2).

Config mapping (29 params total):
  TO                     -> to (str, default "receiver@example.com")
  FROM                   -> from_email (str, default "send@example.com")
  NEED_PERSONAL_NAME     -> need_personal_name (bool, default False)
  PERSONAL_NAME          -> personal_name (str, default "sender")
  CC                     -> cc (str, default "carbon@example.com")
  BCC                    -> bcc (str, default "blindcarbon@example.com")
  SUBJECT                -> subject (str, default "Talaxie Open Studio notification")
  MESSAGE                -> message (str, default "Hello")
  CHECK_ATTACHMENT       -> check_attachment (bool, default True)
  ATTACHMENTS            -> attachments (list[dict], default [])
  HEADERS                -> headers (list[dict], default [])
  SMTP_HOST              -> smtp_host (str, default "smtp.provider.com")
  SMTP_PORT              -> smtp_port (str, default "25")
  SSL                    -> ssl (bool, default False)
  STARTTLS               -> starttls (bool, default False)
  IMPORTANCE             -> importance (str, default "NORMAL")
  AUTH_MODE              -> auth_mode (str, default "BASIC")
  AUTH_USERNAME           -> auth_username (str, default "username")
  AUTH_PASSWORD           -> auth_password (str, default "password")
  TOKEN                  -> token (str, default "password")
  DIE_ON_ERROR           -> die_on_error (bool, default True)
  TEXT_SUBTYPE            -> text_subtype (str, default "PLAIN")
  ENCODING               -> encoding (str, default "ISO-8859-15")
  SET_LOCALHOST           -> set_localhost (bool, default False)
  LOCALHOST               -> localhost (str, default "localhost")
  USE_TWO_LINE_TOKEN     -> use_two_line_token (bool, default False)
  CONFIGS                -> configs (list[dict], default [])
  TSTATCATCHER_STATS     -> tstatcatcher_stats (bool, default False)
  LABEL                  -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_ATTACHMENTS_FIELDS = ("FILE", "CONTENT_TRANSFER_ENCODING")
_ATTACHMENTS_GROUP_SIZE = 2

_HEADERS_FIELDS = ("KEY", "VALUE")
_HEADERS_GROUP_SIZE = 2

_CONFIGS_FIELDS = ("KEY", "VALUE")
_CONFIGS_GROUP_SIZE = 2


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_attachments(raw: Any) -> List[Dict[str, str]]:
    """Parse ATTACHMENTS TABLE into list of attachment dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      FILE                       -> file (str)
      CONTENT_TRANSFER_ENCODING  -> content_transfer_encoding (str)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _ATTACHMENTS_GROUP_SIZE):
        group = raw[i: i + _ATTACHMENTS_GROUP_SIZE]
        if len(group) < _ATTACHMENTS_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "FILE":
                row["file"] = val.strip('"')
            elif ref == "CONTENT_TRANSFER_ENCODING":
                row["content_transfer_encoding"] = val.strip('"')
        if row.get("file"):
            result.append(row)
    return result


def _parse_kv_table(raw: Any) -> List[Dict[str, str]]:
    """Parse KEY/VALUE TABLE into list of {key, value} dicts.

    Used for HEADERS and CONFIGS tables. Each group of 2 consecutive
    elementRef entries maps to one row:
      KEY    -> key (str)
      VALUE  -> value (str)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    _GROUP_SIZE = 2
    for i in range(0, len(raw), _GROUP_SIZE):
        group = raw[i: i + _GROUP_SIZE]
        if len(group) < _GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "KEY":
                row["key"] = val.strip('"')
            elif ref == "VALUE":
                row["value"] = val.strip('"')
        if row.get("key"):
            result.append(row)
    return result


# ------------------------------------------------------------------
# Engine gap definitions (engine does not read these)
# ------------------------------------------------------------------
_ENGINE_GAP_KEYS = {
    "need_personal_name": "Engine does not read need_personal_name -- sender display name not supported",
    "personal_name": "Engine does not read personal_name -- sender display name not supported",
    "check_attachment": "Engine does not read check_attachment -- missing attachment validation not supported",
    "headers": "Engine does not read headers TABLE -- custom email headers not supported",
    "importance": "Engine does not read importance -- email priority not supported",
    "auth_mode": "Engine does not read auth_mode -- uses implicit BASIC auth only",
    "token": "Engine does not read token -- OAuth2 authentication not supported",
    "set_localhost": "Engine does not read set_localhost -- custom localhost not supported",
    "localhost": "Engine does not read localhost -- custom localhost not supported",
    "use_two_line_token": "Engine does not read use_two_line_token -- OAuth2 two-line format not supported",
    "configs": "Engine does not read configs TABLE -- custom SMTP properties not supported",
    "encoding": "Engine default encoding 'utf-8' differs from Talend default 'ISO-8859-15'",
}


@REGISTRY.register("tSendMail")
class SendMailConverter(ComponentConverter):
    """Convert a Talend tSendMail node into a v1 SendMailComponent config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        params = node.params
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["to"] = self._get_str(node, "TO", "receiver@example.com")
        config["from_email"] = self._get_str(node, "FROM", "send@example.com")
        config["need_personal_name"] = self._get_bool(node, "NEED_PERSONAL_NAME", False)
        config["personal_name"] = self._get_str(node, "PERSONAL_NAME", "sender")
        config["cc"] = self._get_str(node, "CC", "carbon@example.com")
        config["bcc"] = self._get_str(node, "BCC", "blindcarbon@example.com")
        config["subject"] = self._get_str(node, "SUBJECT", "Talaxie Open Studio notification")
        config["message"] = self._get_str(node, "MESSAGE", "Hello")
        config["check_attachment"] = self._get_bool(node, "CHECK_ATTACHMENT", True)
        config["smtp_host"] = self._get_str(node, "SMTP_HOST", "smtp.provider.com")
        config["smtp_port"] = self._get_str(node, "SMTP_PORT", "25")
        config["ssl"] = self._get_bool(node, "SSL", False)
        config["starttls"] = self._get_bool(node, "STARTTLS", False)
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", True)

        # ---- 2. CLOSED_LIST parameters ----
        config["importance"] = self._get_str(node, "IMPORTANCE", "NORMAL")
        config["text_subtype"] = self._get_str(node, "TEXT_SUBTYPE", "PLAIN")

        # AUTH_MODE with NEED_AUTH backward compatibility
        auth_mode = self._get_str(node, "AUTH_MODE")
        if not auth_mode:
            # Older .item files use NEED_AUTH (CHECK) instead of AUTH_MODE (CLOSED_LIST)
            need_auth = self._get_bool(node, "NEED_AUTH", True)
            auth_mode = "BASIC" if need_auth else "NO_AUTH"
        config["auth_mode"] = auth_mode

        # ---- 3. Conditional parameters ----
        config["auth_username"] = self._get_str(node, "AUTH_USERNAME", "username")
        config["auth_password"] = self._get_str(node, "AUTH_PASSWORD", "password")
        config["token"] = self._get_str(node, "TOKEN", "password")
        config["set_localhost"] = self._get_bool(node, "SET_LOCALHOST", False)
        config["localhost"] = self._get_str(node, "LOCALHOST", "localhost")
        config["use_two_line_token"] = self._get_bool(node, "USE_TWO_LINE_TOKEN", False)

        # ---- 4. Advanced parameters ----
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")

        # ---- 5. TABLE parameters ----
        config["attachments"] = _parse_attachments(params.get("ATTACHMENTS", []))
        config["headers"] = _parse_kv_table(params.get("HEADERS", []))
        config["configs"] = _parse_kv_table(params.get("CONFIGS", []))

        # ---- 6. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 7. Validation warnings ----
        if not config["smtp_host"]:
            warnings.append("SMTP_HOST is empty -- this is a required parameter")
        if not config["to"]:
            warnings.append("TO is empty -- at least one recipient is required")

        # ---- 8. Engine gap needs_review entries (per D-24: per-feature) ----
        for key, issue_desc in _ENGINE_GAP_KEYS.items():
            needs_review.append({
                "issue": issue_desc,
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 9. Build component and return ----
        component = self._build_component_dict(
            node=node,
            type_name="SendMailComponent",
            config=config,
            # Utility component -- no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings, needs_review=needs_review)
