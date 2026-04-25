---
phase: manager-commits-api
reviewed: 2026-04-25T00:00:00Z
depth: deep
files_reviewed: 5
files_reviewed_list:
  - api/__init__.py
  - api/app.py
  - api/routes/__init__.py
  - api/routes/jobs.py
  - pyproject.toml
findings:
  critical: 9
  warning: 11
  info: 7
  total: 27
status: issues_found
---

# Code Review: api/ (manager-commits)

## Summary

Freshly-added FastAPI surface wrapping `ETLEngine` for upload/run/poll. As a functional prototype it works, but as code that "will eventually ship to production" it has **fundamental security, concurrency, and reliability defects** that must be addressed before exposure beyond a single trusted developer on localhost.

Highlights of why this is not production-ready:

1. **No authentication, no authorization, no rate limiting; CORS wide open with credentials** — any browser on the corporate network can drive job execution. Combined with the engine's ability to load arbitrary Java JARs, run Python routines from configurable directories, write files, connect to databases, an unauthenticated POST endpoint is effectively unauthenticated RCE.
2. **`/run-inline` accepts arbitrary job_config dicts and immediately executes them** — bypasses upload/auth entirely.
3. **Background threads spawn unbounded** with no concurrency cap, no queue, no timeout, no cancellation — a few clients can DoS the host or exhaust the JVM.
4. **`_runs` dict grows forever** (memory leak; also loses all state on restart).
5. **Path traversal on `job_id`** — `JOBS_DIR / f"{job_id}.json"` built from user string with no UUID validation.
6. **JSON bomb / size DoS** — `await file.read()` reads entire upload into memory.
7. **Conventions violated**: bare `except Exception:` swallows, generic `Exception` raised to caller instead of typed `ETLError` subclasses.
8. **pyproject.toml** mislabels required deps as optional; bare install will fail at import.

Recommendation: treat this whole module as a prototype and gate it behind authentication + a job execution queue before any production exposure.

## Critical Issues

### API-CR-01: Path traversal in job_id allows read/write/delete outside JOBS_DIR

**File:** `api/routes/jobs.py:97, 199, 208-211`
`job_id` taken directly from URL path and concatenated into filesystem path with no validation:
```python
job_path = JOBS_DIR / f"{job_id}.json"
```
Path components like `..`, `/`, or absolute paths pass straight through. `delete_job` will `unlink()` any reachable `*.json`. `get_job` leaks contents of any readable `*.json`. `run_job` will execute any reachable `*.json` as ETL config — **trivial RCE** because engine loads arbitrary Java JARs and Python routines from configurable paths inside the job config.

**Fix:**
```python
import re
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

def _resolve_job_path(job_id: str) -> Path:
    if not _UUID_RE.match(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format")
    job_path = (JOBS_DIR / f"{job_id}.json").resolve()
    if JOBS_DIR.resolve() not in job_path.parents:
        raise HTTPException(status_code=400, detail="Invalid job_id")
    return job_path
```
Apply same pattern (regex check) to `run_id` in `get_run_status`.

### API-CR-02: No authentication or authorization on any endpoint

**File:** `api/app.py:1-30`, `api/routes/jobs.py:42-212`
Every endpoint — upload, run, run-inline, list runs, list jobs, get job, delete job — is unauthenticated. Any client that can reach the host can upload arbitrary job configs that load Java JARs and Python routine modules; execute jobs; read every other user's uploaded job; delete every other user's uploaded job; enumerate and read every run's results including stack traces.

**Fix:** Add an authentication dependency to every router (or the app):
```python
from fastapi import Depends, Security
from fastapi.security import APIKeyHeader

api_key_scheme = APIKeyHeader(name="X-API-Key")

def require_auth(api_key: str = Security(api_key_scheme)) -> str:
    expected = os.environ.get("DATAPREP_API_KEY")
    if not expected or not hmac.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return api_key

router = APIRouter(dependencies=[Depends(require_auth)])
```
Without this, **the API must not be deployed.**

### API-CR-03: CORS allows any origin with credentials — dangerous and invalid

**File:** `api/app.py:16-22`
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    ...
)
```
This combination is explicitly forbidden by the CORS spec — Starlette/FastAPI refuses to send `Access-Control-Allow-Origin: *` when credentials allowed. If a future maintainer "fixes" the contradiction by switching `allow_origins` to a regex or origin reflection, **any malicious page** loaded by an authenticated user could drive the API in their browser session.

**Fix:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("DATAPREP_ALLOWED_ORIGINS", "").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type"],
)
```

### API-CR-04: `/run-inline` allows unauthenticated arbitrary job execution

**File:** `api/routes/jobs.py:127-153`
Takes a JSON `job_config` directly and runs it. Combined with API-CR-02, the worst exposure: a single POST can load arbitrary Java JARs (via `java_config.routine_jars`), arbitrary Python routine directories (via `python_config.routines_dir`), and execute arbitrary Java/Groovy expressions through the bridge. tJavaRow / tJava and Python row components are essentially `eval` with Arrow data — full RCE.

**Fix:**
1. Remove this endpoint until authentication and config-policy validation are in place.
2. Once auth is added, validate incoming configs against an allowlist policy: reject filesystem paths outside an allowlist, reject `java_config.libraries` outside an allowlisted directory, reject `python_config.routines_dir` overrides entirely.

### API-CR-05: Unbounded thread spawn — no queue, no concurrency cap, no timeout

**File:** `api/routes/jobs.py:117-122, 146-151`
Every call to `/run` or `/run-inline` spawns a fresh `threading.Thread`. No upper bound. An attacker can spawn thousands of threads, each starting a JVM (each is a Py4J subprocess + JVM heap). Trivial DoS. No timeout, no cancellation.

**Fix:** Use a bounded `ThreadPoolExecutor` (or real queue like Celery/RQ for production). Track futures so jobs can be cancelled. Add `max_runtime_seconds`:
```python
_executor = ThreadPoolExecutor(max_workers=int(os.environ.get("DATAPREP_MAX_CONCURRENT_RUNS", "4")))
_run_futures: Dict[str, Future] = {}
```
Expose `POST /runs/{run_id}/cancel`.

### API-CR-06: Unbounded upload size and unbounded `_runs` dict

**File:** `api/routes/jobs.py:25, 48, 56, 105-115`
1. `await file.read()` reads entire upload into memory before any size check. 10 GB POST happily accepted; JSON parse OOMs the server.
2. `_runs` grows forever. On a long-running server with thousands of jobs the dict consumes gigabytes.

**Fix:**
```python
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
content = await file.read(MAX_UPLOAD_BYTES + 1)
if len(content) > MAX_UPLOAD_BYTES:
    raise HTTPException(status_code=413, detail="File too large")
```
For `_runs`, use TTL cache or evict completed runs older than N hours via background task.

### API-CR-07: Java bridge subprocess collisions / context pollution under concurrency

**File:** `api/routes/jobs.py:75-79`, cross-ref `src/v1/engine/engine.py:31-100, 215-228`
Each `ETLEngine(job_config)` call instantiates `JavaBridgeManager` which spawns a JVM subprocess. Concurrent `/run` requests will spawn many JVMs simultaneously. While ports are dynamically allocated, no documented guarantees that:
- JAR is reentrant / safe to load multiple times concurrently
- `__exit__` reliably stops the JVM if the thread is killed (it isn't — `daemon=True` threads torn down hard at process exit, leaking JVMs and Arrow buffers)
- `GlobalMap`/`ContextManager` are isolated (per-engine instance — that's good — but if anything in `JavaBridgeManager` is class-level/shared, runs pollute each other)

**Fix:** Verify `JavaBridgeManager` fully per-instance. Add explicit `try/finally engine._cleanup()` even on `KeyboardInterrupt`/`SystemExit`. At service shutdown, iterate `_runs` and force-stop live engines. Track JVM PIDs and reap on cancel/timeout.

### API-CR-08: Error responses leak full exception strings (info disclosure)

**File:** `api/routes/jobs.py:52, 86-91, 165`
- `detail=f"Invalid JSON: {exc}"` echoes the user's content via parser's error
- `_runs[run_id]["error"] = str(exc)` stores raw exception. Polling endpoint returns this verbatim — attacker who triggers parsing/IO failure inside engine sees absolute filesystem paths, database hostnames, environment-specific stack context.

**Fix:**
```python
except Exception as exc:
    logger.error("Run %s failed", run_id, exc_info=True)
    with _runs_lock:
        _runs[run_id]["status"] = "error"
        _runs[run_id]["error"] = "Job execution failed; see server logs"
        _runs[run_id]["error_id"] = run_id
```
Only return safe, classified error codes (e.g., `JOB_CONFIG_INVALID`, `JAVA_BRIDGE_FAILED`).

### API-CR-09: `JOBS_DIR` is created at import time relative to CWD

**File:** `api/routes/jobs.py:21-22`
`JOBS_DIR = Path("data/jobs")` is relative to current working directory at process start. Behavior changes based on CWD; combined with API-CR-01, attacker who can influence CWD can poison the location. Also, doing filesystem `mkdir` at import time is bad practice (breaks tests, breaks read-only deploys).

**Fix:**
```python
JOBS_DIR = Path(os.environ.get("DATAPREP_JOBS_DIR", "/var/lib/dataprep/jobs")).resolve()
```
Move `mkdir` into explicit startup hook (`@app.on_event("startup")`).

## Warnings

### API-WR-01: `_runs[run_id]` accessed without lock in worker thread (race / TOCTOU)
**File:** `api/routes/jobs.py:70-91`
Reads/writes split across multiple `with _runs_lock:` blocks. `list_runs` does `list(_runs.values())` then sorts outside the lock — values are mutable dicts shared with worker threads, so sort key may observe inconsistent state.
**Fix:** Snapshot deep-copies under the lock.

### API-WR-02: Bare `except Exception:` swallowing in `list_jobs`
**File:** `api/routes/jobs.py:184-192`
Hides corrupt configs, permission errors, encoding errors silently. Violates project convention (typed `ETLError` hierarchy).
**Fix:**
```python
except (json.JSONDecodeError, OSError) as exc:
    logger.warning("Skipping unreadable job file %s: %s", path, exc)
    continue
```

### API-WR-03: Generic `Exception` caught in worker, project convention is typed `ETLError`
**File:** `api/routes/jobs.py:86`
`_execute_in_background` catches bare `Exception`, lumps `ETLError` subclasses with truly unexpected errors.
**Fix:**
```python
except ETLError as exc:
    # expected, classified
    ...
except Exception as exc:
    logger.exception("UNEXPECTED error in run %s", run_id)
    ...
```

### API-WR-04: Logging uses f-strings; project convention is `%`-style for new code
**File:** `api/routes/jobs.py:87`
Per CLAUDE.md, converter modules use `%`-style; engine mixes both. Establish convention now.

### API-WR-05: No timezone-aware timestamps, `time.time()` returns float seconds
**File:** `api/routes/jobs.py:72, 84, 91, 173`
Frontend gets raw float epochs. No ISO-8601. Sort fallback to `0` puts queued jobs at bottom — surprising UX.
**Fix:** Add ISO-8601 fields, sort by `created_at` (always set).

### API-WR-06: Missing type hints on `health_check`, several handlers; missing docstrings
**File:** `api/app.py:28`, `api/routes/jobs.py:42, 95, 128, 159, 169, 180, 197, 206`
None of endpoints declare a `response_model`, so OpenAPI shows untyped `dict` outputs.
**Fix:** Define response models (`UploadResponse`, `RunResponse`, `RunStatus`, `JobSummary`).

### API-WR-07: `_make_serializable` is incomplete
**File:** `api/routes/jobs.py:217-227`
Engine `stats` may contain numpy scalars, `Decimal`, `datetime`, `pd.Timestamp`, byte strings. The function only handles `set`, `(list, tuple)`, `dict`, `float-NaN`. First numpy scalar will crash JSON encoder.
**Fix:** Use `fastapi.encoders.jsonable_encoder` or handle numpy/datetime explicitly.

### API-WR-08: `engine.execute()` returns dict with `status='error'` instead of raising — worker treats as success
**File:** `api/routes/jobs.py:79-84`, cross-ref `src/v1/engine/engine.py:182-194`
Worker's `except` block bypassed when engine returns error status; `_runs[run_id]["error"]` never populated.
**Fix:** When `stats.get("status") == "error"`, copy `stats.get("error")` into `_runs[run_id]["error"]`.

### API-WR-09: Pydantic `Dict[str, str]` artificially narrow for context_overrides
**File:** `api/routes/jobs.py:31-37`
Engine accepts `Any` in `set_context_variable`. Booleans submitted as strings will be `"true"`/`"True"`.
**Fix:** Tighten to `Dict[str, Union[str, int, float, bool, None]]`.

### API-WR-10: pyproject.toml — required deps mislabeled as optional extras
**File:** `pyproject.toml:10-23`
- `pyarrow`, `py4j` tagged as `[java]` extras, but `JavaBridgeManager` imports them at module load when `java_config.enabled=True`. Bare install: `ModuleNotFoundError`.
- Same for `lxml`, `openpyxl`/`xlrd`, `PyYAML`, `jsonpath-ng`.
- `pandas>=2.0,<4` permits pandas 4.x (not yet released); meaningless upper bound.
- Missing `dev` extras: pytest included, but no `pytest-cov`, `mypy`, `ruff`, `flake8`.

**Fix:**
```toml
dependencies = [
    "pandas>=2.0,<3.1",
    "numpy>=1.24,<3",
    "pyarrow>=15.0,<24",
    "py4j>=0.10.9,<0.11",
    "openpyxl>=3.1,<4",
    "xlrd>=2.0,<3",
    "lxml>=4.9,<7",
    "PyYAML>=6.0,<7",
    "jsonpath-ng>=1.5,<2",
]
[project.optional-dependencies]
api = ["fastapi>=0.111,<1", "uvicorn[standard]>=0.29,<1", "python-multipart>=0.0.9,<1"]
dev = ["pytest>=8.0,<10", "pytest-cov>=5,<7", "ruff>=0.5,<1"]
```

### API-WR-11: `unused import os` in `api/routes/jobs.py`
**File:** `api/routes/jobs.py:4`

## Info

### API-IN-01: `api/__init__.py` and `api/routes/__init__.py` are empty
Convention: one-line module docstrings.

### API-IN-02: Decorative box-drawing characters in comments (`──`) violate ASCII-only convention
**File:** `api/routes/jobs.py:29, 40, 66, 156, 177, 215`
RHEL terminals/log shippers occasionally mangle non-ASCII. Use `# ---- Section ----` matching converter style.

### API-IN-03: Magic strings for run statuses
**File:** `api/routes/jobs.py:71, 82, 89, 110, 124, 153`
Use an `Enum`:
```python
class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"
```

### API-IN-04: `delete_job` doesn't check if any active run depends on the job_id
**File:** `api/routes/jobs.py:205-212`
Consider returning 409 if any run with `status in {queued, running}` references this job_id.

### API-IN-05: `health_check` always returns ok; no real probes
**File:** `api/app.py:27-29`
Add `JOBS_DIR.is_dir() and os.access(JOBS_DIR, os.W_OK)`, optional `/api/ready` distinct from `/api/health`.

### API-IN-06: `RunInlineRequest.job_config` is `Dict[str, Any]` — no schema validation
**File:** `api/routes/jobs.py:35-37`
Define `JobConfig(BaseModel)` mirroring converter output schema. Validate at parse time.

### API-IN-07: `pyproject.toml` lacks repository / homepage / authors metadata
**File:** `pyproject.toml:5-13`
Once published (even internally), `[project]` should list `authors`, `readme`, `license`, `urls`.

## Cross-File / Deep-Analysis Notes

- **Engine import contract**: `from src.v1.engine.engine import ETLEngine` requires package root on `sys.path`. When `uvicorn api.app:app` launched from repo root, works; from anywhere else it fails. Add `"api*"` to `[tool.setuptools.packages.find]` `include`.
- **State-mutation isolation**: `ETLEngine` instances each own their own `GlobalMap`, `ContextManager`, `JavaBridgeManager` (good). Only shared mutable state in API module is `_runs` (covered) and JVM port allocation. Verify `JavaBridgeManager` has no class-level mutable state.
- **No tests for `api/`**: Add at minimum: upload happy-path, upload rejects non-JSON, run round-trip with tiny inline config, run-status 404, path-traversal regression test (`GET /api/jobs/..%2f..%2fetc%2fpasswd`).
- **Error propagation**: Exception in `_execute_in_background` caught and recorded, but if thread dies before reaching `except` (e.g., `ETLEngine.__init__` raises), run stays at `status="queued"` forever. Catch the constructor.

---

_Reviewed: 2026-04-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

**Bottom line:** As a UI-driven prototype this works, but **do not put it in production as-is**. Big rocks: auth (CR-02), open CORS-with-credentials (CR-03), `/run-inline` (CR-04), path traversal (CR-01), unbounded thread/memory growth (CR-05/06). Fix those, then warnings, then ship.
