// src/components/CodeGate.jsx
// The human sign-off mirror beat, driven entirely by state.gate.
//   - status "awaiting" : show the exact `code` + the operator control.
//   - status "signed"   : KEEP the code visible under a "signed" stamp (the `.signed`
//                         CSS hides the action row and shows the stamp; the <pre> code
//                         stays visible), matching the prototype.
// Hidden once the result (testing beat) arrives, so the finale is unobstructed.
//
// The "Sign off (operator)" button is decorative for rehearsal only: the real gate is
// the operator's action in VS Code, surfaced as the daemon's `gate:signed` event.

export function CodeGate({ gate, result }) {
  const status = gate && gate.status;
  const visible = !!gate && (status === "awaiting" || status === "signed") && !result;
  const signed = status === "signed";
  const cls = "gate" + (visible ? " on" : "") + (signed ? " signed" : "");

  return (
    <div className={cls}>
      <h4><span className="lock">&#9679;</span> Human sign-off required</h4>
      <p>This step writes code to compute a value. Nothing runs until a person approves the exact code.</p>
      <pre>{(gate && gate.code) || ""}</pre>
      <div className="row">
        <button type="button" className="signbtn">Sign off (operator)</button>
        <span className="hint">In the real demo, the operator approves this in VS Code.</span>
      </div>
      <span className="stamp">&#10003; Signed off &mdash; running</span>
    </div>
  );
}
