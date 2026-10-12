"""Change file encoding: a file's text written in another encoding."""
from __future__ import annotations

import logging
import os

from ...errors import ConfigurationError
from ...files import not_a_file, put_in_place, temp_beside, transcode
from ...job.keys import Key, Kind
from ..base import DIE_ON_ERROR, Action, one_line
from ..registry import REGISTRY
from .file_input_delimited import encoding
from .file_row_count import unreadable

logger = logging.getLogger(__name__)


def _named(value: str) -> str:
    if not value.strip():
        raise ValueError("there is no file named")
    return value


@REGISTRY.register
class ChangeFileEncoding(Action):
    """Write the text of the file `infile_name` to `outfile_name` in `encoding`.

    The text is read in `inencoding` when `use_inencoding` is on, and as
    UTF-8 when it is off. It is written as it is: line ends are not
    touched. A byte order mark at the start of the input is not carried
    over, and the output starts with one where its encoding writes one
    (UTF-16, UTF-32).

    A byte that is no character in the input's encoding, and a character
    the output's encoding cannot write, fail the job and say on which
    line. Nothing is put in a character's place.

    The file is gone through piece by piece and never held in memory. It
    is written beside `outfile_name` and put there when it is whole, so
    the two may be the same file, and a job that fails leaves the output
    as it was. The output's path is left in `<id>_FILENAME`, and it counts
    one row. No flow comes to it or leaves it.
    """

    names = ("change_file_encoding", "ChangeFileEncoding", "tChangeFileEncoding")
    keys = (
        Key("infile_name", required=True, convert=_named, doc="The file to read."),
        Key("outfile_name", required=True, convert=_named, doc="The file to write; it may be the file that is read."),
        Key("use_inencoding", type=bool, default=False,
            doc="Whether the input is read in `inencoding`; when off it is read as UTF-8."),
        Key("inencoding", default="ISO-8859-15", convert=encoding, doc="The input's character encoding."),
        Key("encoding", default="ISO-8859-15", convert=encoding, doc="The character encoding the output is written in."),
        Key("create", type=bool, default=True, doc="Whether the folder of the output is made when it is not there."),
        Key("buffersize", kind=Kind.IGNORED, type=object, doc="Talend's size of a piece read; v2 has its own."),
        DIE_ON_ERROR,
    )

    def act(self) -> None:
        try:
            self._change()
        except ConfigurationError as exc:
            if not self.goes_on_after(str(exc)):
                raise
            self.global_map.update({f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 0, f"{self.id}_NB_LINE_REJECT": 1})

    def _change(self) -> None:
        config = self.config
        source, target = config["infile_name"], config["outfile_name"]
        read_as = config["inencoding"] if config["use_inencoding"] else "UTF-8"
        if not os.path.exists(source):
            raise ConfigurationError(f"File not found: '{source}'")
        if not_a_file(source):
            raise ConfigurationError(f"'{source}' cannot be read: {not_a_file(source)}")
        folder = os.path.dirname(target)
        if folder and not os.path.isdir(folder):
            if not config["create"]:
                raise ConfigurationError(f"the folder '{folder}' is not there, and is not to be made")
            os.makedirs(folder, exist_ok=True)
        beside = temp_beside(target, self.id)
        try:
            size = transcode(source, beside, read_as, config["encoding"])
            put_in_place(beside, target)
        except OSError as exc:
            if exc.filename == source:
                raise ConfigurationError(f"'{source}' cannot be read: {unreadable(source, exc)}") from None
            raise ConfigurationError(f"'{target}' cannot be written: {unreadable(target, exc)}") from None
        finally:
            if os.path.exists(beside):
                os.remove(beside)
        logger.info(one_line(f"[{self.id}] wrote '{source}' ({read_as}) as '{target}' ({config['encoding']}), {size} bytes"))
        self.global_map.update({
            f"{self.id}_FILENAME": target,
            f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 1, f"{self.id}_NB_LINE_REJECT": 0,
        })
