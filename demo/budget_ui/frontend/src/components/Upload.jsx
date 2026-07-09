// src/components/Upload.jsx
// The default view when neither ?job= nor ?replay= is present. POST the chosen file to
// /upload, read the returned { job }, set ?job=<id> and reload into the live watch view.

import { useState } from "react";

export function Upload() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function onSubmit(e) {
    e.preventDefault();
    // Read the file synchronously, before any await (currentTarget is only valid
    // during the event handler).
    const input = e.currentTarget.elements.file;
    const file = input && input.files && input.files[0];
    if (!file) {
      setErr("Choose a document first.");
      return;
    }
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
      window.location.assign(url.toString()); // reload -> App reads ?job= -> live mode
    } catch (ex) {
      setErr(String((ex && ex.message) || ex));
      setBusy(false);
    }
  }

  return (
    <div className="wrap upload">
      <div className="up-card">
        <h1>Build an ETL pipeline from your document</h1>
        <p>
          Upload a business requirements document. The assistant reads it, designs the
          pipeline, and builds it &mdash; narrating every step, and pausing for a human to
          sign off on any generated code.
        </p>
        <form onSubmit={onSubmit}>
          <div className="up-row">
            <input type="file" name="file" />
            <button className="btn" type="submit" disabled={busy}>
              {busy ? "Uploading..." : "Start"}
            </button>
          </div>
          <div className="up-err">{err}</div>
        </form>
      </div>
    </div>
  );
}
