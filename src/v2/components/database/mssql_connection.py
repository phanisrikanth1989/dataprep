"""SQL Server connection: a session opened for the SQL Server inputs of a job to read on."""
from __future__ import annotations

from typing import List

from ... import mssql
from ...job.keys import Key, Kind
from ..base import Action
from ..registry import REGISTRY


@REGISTRY.register
class MssqlConnection(Action):
    """Open a session with a SQL Server database for the SQL Server inputs of the job to read on.

    An input that names this one in `connection`, with
    `use_existing_connection` on, reads on this session. The job closes
    the session when it ends.

    Every statement on the session is stored by itself. v2 has no SQL
    Server component that changes anything and none that commits, so
    nothing waits: what a procedure a query calls has changed is stored
    at once.

    It leaves in globalMap what Talend leaves there, save the session
    itself: `dbschema_<id>` and `db_<id>`.
    """

    names = ("mssql_connection", "MSSqlConnection", "tMSSqlConnection")
    opens_session = "SQL Server"
    keys = mssql.CONNECTION_KEYS + (
        Key("auto_commit", kind=Kind.IGNORED, type=object,
            doc="Talend's switch for storing after each statement. Here every statement is stored by itself."),
        Key("share_identity_setting", kind=Kind.IGNORED, type=object,
            doc="For Talend's outputs that write into identity columns."),
    )

    def problems(self) -> List[str]:
        return mssql.problems(self.config)

    def act(self) -> None:
        config = self.config
        self.run_context.sessions.share(mssql.opened(config, self.id))
        self.global_map.update({f"dbschema_{self.id}": config["schema_db"], f"db_{self.id}": config["dbname"]})
