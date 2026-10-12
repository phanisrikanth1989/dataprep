"""Oracle connection: a session opened for other components to work on."""
from __future__ import annotations

from typing import List

from ... import oracle
from ...job.keys import Key
from ..base import Action
from ..registry import REGISTRY


@REGISTRY.register
class OracleConnection(Action):
    """Open a session with an Oracle database for other components to work on.

    A component that names this one in `connection`, with
    `use_existing_connection` on, does its work on this session. What
    they do waits until a commit component stores it. A subjob that
    fails loses what it did on the session, and what earlier subjobs did
    still waits. A job that ends with work still waiting has failed, and
    the work is rolled back.

    The session says in the database who it is: its module is
    `dataprep-v2` and its action the job's name.

    It leaves in globalMap what Talend leaves there, save the password
    and the session itself: `connectionType_<id>`, `dbschema_<id>`,
    `username_<id>`, and by `connection_type` either `host_<id>`,
    `port_<id>` and `dbname_<id>`, or `localServiceName_<id>`, or
    `rac_url_<id>`.
    """

    names = ("oracle_connection", "OracleConnection", "tOracleConnection", "tDBConnection")
    opens_session = "Oracle"
    keys = oracle.CONNECTION_KEYS + (
        Key("auto_commit", type=bool, default=False,
            doc="Whether what a subjob did on the session is stored when that subjob has succeeded, with no "
                "commit component. (Talend stores after each statement; nothing is stored here for a subjob "
                "that fails.)"),
    )

    def problems(self) -> List[str]:
        return oracle.problems(self.config)

    def act(self) -> None:
        config, run = self.config, self.run_context
        session = oracle.opened(config, self.id, run.job_name, run.oracle, auto_commit=config["auto_commit"])
        run.sessions.share(session)
        kind = config["connection_type"]
        left = {"connectionType": kind, "dbschema": config["schema_db"], "username": config["user"]}
        if kind == oracle.OCI:
            left["localServiceName"] = config["local_service_name"]
        elif kind == oracle.CUSTOM:
            left["rac_url"] = config["rac_url"]
        else:
            left.update(host=config["host"], port=str(config["port"]), dbname=config["dbname"])
        self.global_map.update({f"{name}_{self.id}": value for name, value in left.items()})
