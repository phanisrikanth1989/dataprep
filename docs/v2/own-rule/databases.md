# Databases

The components that open a session with a database, work in it, and end
what was done.

Built to their own rule: what is written here is what they are held to,
not v1 or Talend. ([What that means](README.md).) Why each rule is as it
is, and what a real Oracle said when it was tried, is in the decisions
ticket (`.scratch/engine-v2/issues/118-databases-the-decisions.md`).

## Sessions and transactions

- **A component does its work and never ends a transaction. The engine
  does.** Nothing is stored for a subjob that fails.
- **A session a connection component opens is shared.** Components that
  name it in `connection` work on it, and what they do waits until a
  commit component stores it. A subjob that fails on it loses what it
  did there; what earlier subjobs did still waits.
- **A component that opens a session for itself** has its work stored
  when its subjob has succeeded, and rolled back when it has not. It
  needs no commit component.
- **A commit comes before any file of the subjob is put in place.** A
  commit can fail, and no file is in place yet when one does. A file
  that cannot be put in place after a commit fails the subjob and says
  what is stored: a commit is not taken back.
- **A job that ends with work nothing stored has failed.** The work is
  rolled back and the failure says whose it was. Rows that were loaded
  and never stored are no success.
- **A statement that stores by itself** (in Oracle: `CREATE`, `ALTER`,
  `DROP`, `TRUNCATE` and the like) stores what waited on the session
  before it. The engine sees that, and does not say afterwards that the
  work waits.
- A job run by another job has sessions of its own. None is shared
  between them.

### Oracle

- The driver is python-oracledb, 26.0.1 or later
  (`pip install 'dataprep[v2-oracle]'`); an older one refuses to open a
  session, since earlier ones hand on wrong numbers. It needs no client
  of Oracle's. A job says otherwise at its top:

  ```json
  "oracle_config": {"thick_mode": true, "lib_dir": "/opt/oracle/instantclient"}
  ```

  Oracle's own client is then loaded (it is needed where a database asks
  for Native Network Encryption or Kerberos). A process uses one or the
  other: the first job that opens a session decides. This was not tried
  here: no client was at hand.
- A session says in the database who it is: its module is `dataprep-v2`
  and its action the job's name (`v$session`).
- **The connection block** is the same on every component that can open
  a session:

  | `connection_type` | Opens a session with |
  |---|---|
  | `ORACLE_SID` | `host`, `port`, and a SID in `dbname` |
  | `ORACLE_SERVICE_NAME` | `host`, `port`, and a service name in `dbname` |
  | `ORACLE_RAC` | the connect string in `rac_url`: Oracle's own form, or a JDBC URL, whose `jdbc:oracle:thin:@` is taken off |
  | `ORACLE_OCI` | the name `local_service_name` has in tnsnames.ora; with `use_tns_file`, the file `tns_file` names |
  | `ORACLE_WALLET` | refused: the wallet holds the user and the password, and only Oracle's own client reads it |

- `user` and `password` are given by themselves. A `rac_url` that
  carries them refuses the job. The password is shown in no log and is
  put nowhere, globalMap included.
- A password Talend encrypted (`enc:system.encryption.key.v1:...`)
  refuses the job: only Talend can read it. Give the password from a
  context variable.
- Refused, with what to do instead: `use_ssl` (Java key stores are not
  read; a `rac_url` that says `tcps` opens a session over TLS),
  `use_shared_connection`, and any JDBC parameter in `properties`.
- What the database refuses is said in its own words on one line
  (`ORA-00942: ...`), without the link to its help.
- For whoever builds on the driver: python-oracledb 26.0.1 brings the
  interpreter down (a segmentation fault) when `call_timeout` is set on
  a session the database has closed. A time limit is set once, when a
  session is opened, and never after. Asking a dead session whether it
  lives, rolling it back and closing it are safe.

## Oracle connection

- Opens a session and keeps it for the components that name this one.
  The job closes it when it ends, if nothing else did.
- Leaves in globalMap what Talend leaves there, save the password and
  the session itself: `connectionType_<id>`, `dbschema_<id>`,
  `username_<id>`, and by `connection_type` either `host_<id>`,
  `port_<id>` and `dbname_<id>`, or `localServiceName_<id>`, or
  `rac_url_<id>`.
- `auto_commit` stores what a subjob did on the session when that
  subjob has succeeded, with no commit component. (Talend stores after
  each statement. Here a subjob that fails stores nothing, also with
  this on.)
- Run again while its earlier session is still open, it closes that one
  and opens another; with work still waiting on the earlier one it
  fails, and the work stays where it was.
- `tDBConnection` is this component.

## Oracle commit

- Stores what was done on the session of the connection it names, and
  closes the session unless `close` is off.
- Set off by a trigger, it commits when its turn comes.
- With a flow leading to it, it commits once, when its subjob has
  succeeded and a row reached it. The rows go on as they came. (Talend
  commits at the first row, while the others are still on their way.)
- A session that is not open fails it: a commit that stores nothing is
  a job that stored nothing.

## Oracle rollback

- Takes back what was done on the session and not stored, and closes the
  session unless `close` is off.
- Set off by a trigger or standing in a flow, as the commit.
- A session that is not open has nothing to take back, and is no fault.

## Oracle close

- Closes the session of the connection it names.
- **Work that waits on the session fails the job and is rolled back.** A
  close is no commit. Talend's close stores such work, so a close in a
  job's clean-up stores the half of a job that failed.
- `uncommitted` says otherwise: `commit` stores the work, `rollback`
  takes it back and goes on, `fail` is what happens without it.
- A session that is not open is no fault.

## What refuses the job

- `connection` on a commit, a rollback or a close has to be the id of an
  Oracle connection of the job. The refusal lists the ones it has.
- What is wrong with a connection block: no host, no user, a password
  only Talend can read.
