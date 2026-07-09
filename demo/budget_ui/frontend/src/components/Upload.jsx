// src/components/Upload.jsx
// The entry view (no ?job= / ?replay=). Drag or browse a requirements document, POST it to
// /upload, then hand off to the live watch view (?job=<id>) with a clear "waiting" state.

import { useState, useRef } from "react";

const STEPS = ["Read", "Understand", "Build", "Test"];

const UP_ICON = (
  <svg width="22" height="22" viewBox="0 0 40 40" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 27V9" /><path d="M11 18l9-9 9 9" /><path d="M8 31h24" />
  </svg>
);
const CHECK_ICON = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 13l4 4L19 7" />
  </svg>
);

export function Upload() {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);

  function pick(f) {
    if (f) { setFile(f); setErr(""); }
  }

  async function start() {
    if (!file) { setErr("Choose a requirements document first."); return; }
    setBusy(true);
    setErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/upload", { method: "POST", body: fd });
      if (!res.ok) throw new Error("Upload failed (" + res.status + ")");
      const data = await res.json();
      if (!data || !data.job) throw new Error("No job id returned.");
      const url = new URL(window.location.href);
      url.searchParams.set("job", data.job);
      window.location.assign(url.toString()); // reload -> App reads ?job= -> live watch view
    } catch (ex) {
      setErr(String((ex && ex.message) || ex));
      setBusy(false);
    }
  }

  return (
    <div className="up-screen">
      <div className="up-card">
        <div className="up-eyebrow">DataPrep &middot; ETL Pipeline Builder</div>
        <h1 className="up-title">Turn a requirements document<br />into a working data pipeline.</h1>
        <p className="up-lede">
          Hand over a business requirements document. The assistant reads it, designs the
          pipeline, and builds it live &mdash; narrating each decision and pausing for a human
          to sign off on any generated code.
        </p>

        <label
          className={"up-drop" + (drag ? " drag" : "") + (file ? " has-file" : "")}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files && e.dataTransfer.files[0]); }}
        >
          <input ref={inputRef} type="file" accept=".docx" hidden
                 onChange={(e) => pick(e.target.files && e.target.files[0])} />
          <span className="up-drop-icon">{file ? CHECK_ICON : UP_ICON}</span>
          {file ? (
            <>
              <span className="up-file-name">{file.name}</span>
              <span className="up-drop-hint">{Math.max(1, Math.round(file.size / 1024))} KB &middot; click to choose another</span>
            </>
          ) : (
            <>
              <span className="up-drop-main">Drop your requirements document here</span>
              <span className="up-drop-hint">or click to browse &middot; .docx</span>
            </>
          )}
        </label>

        <div className="up-steps">
          {STEPS.map((s, i) => (
            <span className="up-step" key={s}>
              {s}{i < STEPS.length - 1 && <em className="up-arrow">&rarr;</em>}
            </span>
          ))}
        </div>

        <div className="up-actions">
          <button className="up-cta" onClick={start} disabled={busy || !file}>
            {busy ? <>Starting&hellip;</> : <>Build my pipeline &rarr;</>}
          </button>
          {err && <span className="up-err">{err}</span>}
        </div>
      </div>
    </div>
  );
}
