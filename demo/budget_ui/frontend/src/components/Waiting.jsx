// src/components/Waiting.jsx
// Shown for a live ?job=<id> stream before the first event arrives (instead of a blank
// canvas). Surfaces the job id + the two operator commands so the run can be wired up;
// the moment the daemon relays the first event, the Presenter swaps to the live view.

export function Waiting({ job }) {
  const origin = window.location.origin;
  const daemonCmd = `python -m demo.budget_ui.launch_daemon --server ${origin} --job ${job} --synthetic`;

  return (
    <div className="waiting">
      <div className="waiting-badge"><span className="spin" /> queued</div>
      <h2 className="waiting-title">Your document is ready to build.</h2>
      <p className="waiting-sub">
        Queued as job <code className="job-id">{job}</code>. The moment the run starts, this
        screen fills in &mdash; live.
      </p>

      <div className="waiting-ops">
        <div className="waiting-ops-h">To start the run</div>
        <ol>
          <li>
            <span className="n">1</span>
            <div>
              Launch the relay daemon on the laptop:
              <pre>{daemonCmd}</pre>
            </div>
          </li>
          <li>
            <span className="n">2</span>
            <div>
              In Copilot, run the <b>etl-orchestrator</b> on your document with job name{" "}
              <code>{job}</code>.
            </div>
          </li>
        </ol>
      </div>
    </div>
  );
}
