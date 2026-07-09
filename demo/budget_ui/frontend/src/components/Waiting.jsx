// src/components/Waiting.jsx
// Shown for a live ?job=<id> stream before the first event arrives (instead of a blank
// canvas): a calm "queued" state for the audience -- the job reference and a promise that
// the screen fills in the moment the run starts. NO operator plumbing (daemon command,
// Copilot) is surfaced here; the operator wires the run up out of band. The moment the
// daemon relays the first event, the Presenter swaps to the live view.

export function Waiting({ job }) {
  return (
    <div className="waiting">
      <div className="waiting-badge"><span className="spin" /> queued</div>
      <h2 className="waiting-title">Your document is ready to build.</h2>
      <p className="waiting-sub">
        Queued as job <code className="job-id">{job}</code>. The moment the run starts, this
        screen fills in &mdash; live.
      </p>
    </div>
  );
}
