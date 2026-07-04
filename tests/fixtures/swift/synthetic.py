"""Synthetic SWIFT MT message generator (Phase 14-07).

Builds realistic MT messages from primitive block builders. Implementation is
strict ASCII; all field values are made-up and contain no production data.

Block reference (SWIFT user-handbook):
    Block 1 -- Basic Header     {1:F01BANKBICAXXX0000000000}
    Block 2 -- Application Hdr  {2:I103BANKBICBXXXN}        (input)
                                {2:O940...}                  (output)
    Block 3 -- User Header      {3:{121:UUID}{119:COV}}      (optional)
    Block 4 -- Text Block       {4:\n:20:REF\n...\n-}
    Block 5 -- Trailer          {5:{CHK:1234567890AB}}

Public API:
    MTBlock4Field(tag, value)           -- dataclass for block-4 fields
    build_block_1(...)                  -- block 1 string
    build_block_2(...)                  -- block 2 string
    build_block_3(...)                  -- block 3 string (optional)
    build_block_4(fields)               -- block 4 string
    build_block_5(...)                  -- block 5 string
    build_mt_message(...)               -- full MT message composer
    mt103_minimum()                     -- MT103 customer transfer template
    mt202_cov()                         -- MT202 COV template (block 3 119:COV)
    mt940_with_balance()                -- MT940 customer statement template
    malformed_missing_block_4()         -- reject-path fixture (no block 4)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


# ----------------------------------------------------------------------
# Dataclass
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class MTBlock4Field:
    """One field-tag entry inside SWIFT Block 4.

    Attributes:
        tag:   Field tag without colons -- e.g. "20", "23B", "32A", "61".
        value: Single-line OR multi-line string. Multi-line content is
               written verbatim into the block-4 body; the parser will
               re-join continuation lines per its layout-driven rules.
    """

    tag: str
    value: str


# ----------------------------------------------------------------------
# Block builders
# ----------------------------------------------------------------------


def build_block_1(
    app_id: str = "F",
    service_id: str = "01",
    sender_bic: str = "BANKBICAXXXX",
    session: str = "0000",
    sequence: str = "000000",
) -> str:
    """Build SWIFT Block 1 (Basic Header) -- ``{1:F01BANKBICAXXX00000000000}``.

    The receiver in block 1 is actually the sender BIC (block 2 carries the
    real receiver). Block 1 is the originator side.

    Args:
        app_id: 1-char application id ("F" for FIN, "A" for GPA, "L" for FIN-Copy)
        service_id: 2-char service id ("01" for FIN, "21" for ACK, etc.)
        sender_bic: 12-char BIC of the sender (4-letter bank, 2-letter country,
            2-letter location, 3-letter branch)
        session: 4-digit session number
        sequence: 6-digit sequence number
    """
    return "{1:" + f"{app_id}{service_id}{sender_bic}{session}{sequence}" + "}"


def build_block_2(
    direction: str = "I",
    message_type: str = "103",
    receiver_bic: str = "BANKBICBXXXX",
    priority: str = "N",
    delivery_monitoring: str = "",
    obsolescence_period: str = "",
) -> str:
    """Build SWIFT Block 2 (Application Header).

    Input format  : ``{2:I<MT><RECEIVER_BIC><PRIORITY>...}``
    Output format : ``{2:O<MT><HHMM><MIR><RECEIVER_BIC>N}``  (not used here;
                    the engine code handles "O" too -- callers can override)
    """
    body = f"{direction}{message_type}{receiver_bic}{priority}"
    if delivery_monitoring:
        body += delivery_monitoring
    if obsolescence_period:
        body += obsolescence_period
    return "{2:" + body + "}"


def build_block_3(
    uetr: Optional[str] = None,
    validation_flag: Optional[str] = None,
) -> str:
    """Build SWIFT Block 3 (User Header).

    All sub-fields are optional. Tag 121 carries a UUID-shaped UETR (Unique
    End-to-End Transaction Reference) and tag 119 carries a validation flag
    such as ``COV`` for cover messages or ``STP`` for straight-through
    processing. Returns an empty string if both inputs are ``None``.
    """
    parts: List[str] = []
    if uetr is not None:
        parts.append("{121:" + uetr + "}")
    if validation_flag is not None:
        parts.append("{119:" + validation_flag + "}")
    if not parts:
        return ""
    return "{3:" + "".join(parts) + "}"


def build_block_4(fields: Iterable[MTBlock4Field]) -> str:
    """Build SWIFT Block 4 (Text Block).

    Block 4 is line-oriented: it opens with ``{4:`` followed by a newline,
    then each field starts with ``:tag:`` on its own line; continuation lines
    are written verbatim (no leading colon). Block 4 closes with ``-}``.

    Args:
        fields: Iterable of ``MTBlock4Field``. Multi-line values are split on
            ``\\n`` and written one per line.
    """
    lines: List[str] = ["{4:"]
    for field in fields:
        value_lines = field.value.split("\n")
        # First line carries the :tag: prefix, continuation lines are bare.
        lines.append(f":{field.tag}:{value_lines[0]}")
        for cont in value_lines[1:]:
            lines.append(cont)
    lines.append("-}")
    return "\n".join(lines)


def build_block_5(checksum: str = "1234567890AB") -> str:
    """Build SWIFT Block 5 (Trailer) -- ``{5:{CHK:checksum}}``.

    Real trailers also carry MAC, TNG, PDE, etc. We only emit CHK; the engine
    code under test stores block5_content as a flat string so any contents
    work for branch coverage.
    """
    return "{5:{CHK:" + checksum + "}}"


def build_mt_message(
    block1: str,
    block2: str,
    block4: str,
    block5: str,
    block3: str = "",
) -> str:
    """Compose the full MT message string from individual blocks.

    Block ordering on the wire is 1, 2, 3 (optional), 4, 5. Blocks are
    concatenated without separators (the parser uses ``{N:`` boundaries).
    """
    parts = [block1, block2]
    if block3:
        parts.append(block3)
    parts.append(block4)
    parts.append(block5)
    return "".join(parts)


# ----------------------------------------------------------------------
# Convenience templates
# ----------------------------------------------------------------------


def mt103_minimum() -> str:
    """MT103 -- Single Customer Credit Transfer (minimum required fields).

    Tags exercised: 20, 23B, 32A, 50K, 59, 70, 71A. No block 3.
    """
    fields = [
        MTBlock4Field("20", "REF103MIN0001"),
        MTBlock4Field("23B", "CRED"),
        MTBlock4Field("32A", "260510USD1500,00"),
        MTBlock4Field("50K", "/12345678901\nACME CORP\n123 MAIN STREET\nNEW YORK NY"),
        MTBlock4Field("59", "/98765432109\nBETA LLC\n456 MARKET AVENUE\nLONDON UK"),
        MTBlock4Field("70", "INVOICE 12345 PAYMENT"),
        MTBlock4Field("71A", "OUR"),
    ]
    return build_mt_message(
        block1=build_block_1(sender_bic="BANKBICAXXXX"),
        block2=build_block_2(direction="I", message_type="103",
                             receiver_bic="BANKBICBXXXX", priority="N"),
        block4=build_block_4(fields),
        block5=build_block_5(),
    )


def mt202_cov() -> str:
    """MT202 COV -- General Financial Institution Transfer (cover message).

    Tags exercised: 20, 21, 32A, 52A, 58A. Block 3 carries 121 (UETR) +
    119:COV.
    """
    fields = [
        MTBlock4Field("20", "REF202COV0001"),
        MTBlock4Field("21", "RELATED202COV"),
        MTBlock4Field("32A", "260510USD2500000,00"),
        MTBlock4Field("52A", "ORIGBANKXXXX"),
        MTBlock4Field("58A", "BENEBANKYYYY"),
    ]
    return build_mt_message(
        block1=build_block_1(sender_bic="BANKBICAXXXX"),
        block2=build_block_2(direction="I", message_type="202",
                             receiver_bic="BANKBICBXXXX", priority="U"),
        block3=build_block_3(
            uetr="abcd1234-ef56-7890-abcd-1234567890ef",
            validation_flag="COV",
        ),
        block4=build_block_4(fields),
        block5=build_block_5(),
    )


def mt940_with_balance() -> str:
    """MT940 -- Customer Statement (with opening balance + transactions).

    Tags exercised: 20, 21, 25, 28C, 60F, 61, 86, 62F. Multi-line :86: with
    structured narrative.
    """
    fields = [
        MTBlock4Field("20", "REF940STMT001"),
        MTBlock4Field("21", "ACCT12345"),
        MTBlock4Field("25", "12345678901"),
        MTBlock4Field("28C", "00001/00001"),
        MTBlock4Field("60F", "C260501USD1000000,00"),
        MTBlock4Field("61", "2605100510C2500,00NTRFTXN001//REF001\nTRANSFER FROM ACME"),
        MTBlock4Field("86", "/PURP/INVOICE\n/REF/INV12345"),
        MTBlock4Field("61", "2605100510D1500,75NCHGTXN002//REF002"),
        MTBlock4Field("86", "FEE FOR SERVICES"),
        MTBlock4Field("62F", "C260510USD1000999,25"),
    ]
    return build_mt_message(
        block1=build_block_1(sender_bic="BANKBICCXXXX"),
        block2=build_block_2(direction="I", message_type="940",
                             receiver_bic="BANKBICDXXXX", priority="N"),
        block4=build_block_4(fields),
        block5=build_block_5(checksum="ABCDEF123456"),
    )


def malformed_missing_block_4() -> str:
    """Fixture for the reject path: block 4 is intentionally missing.

    The block-formatter parser requires block 4 to extract field-tag values;
    when absent, downstream tests assert that the parser handles this
    gracefully (returns empty mapping or raises a documented exception).
    """
    return build_mt_message(
        block1=build_block_1(),
        block2=build_block_2(),
        block4="",  # MISSING -- the whole reason this template exists
        block5=build_block_5(),
    )
