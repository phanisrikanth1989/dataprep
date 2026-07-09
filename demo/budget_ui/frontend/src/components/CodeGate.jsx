// src/components/CodeGate.jsx
// The human sign-off mirror beat, driven entirely by state.gate.
//   - status "awaiting" : show the exact `code` + the operator control.
//   - status "signed"   : KEEP the code visible under a "signed" stamp (the `.signed`
//                         CSS hides the action row and shows the stamp; the <pre> code
//                         stays visible), matching the prototype.
// Hidden once the result (testing beat) arrives, so the finale is unobstructed.
//
// The "Sign off and run" button signs off and gracefully closes the modal (the presenter's
// action -- shows the "signed" stamp, then fades out). The real run's approval also arrives
// from the backend as a `gate:signed` status; either path flips the modal to the stamp.

import { useEffect, useState } from "react";

export function CodeGate({ gate, result, revealMs = 0 }) {
  const status = gate && gate.status;
  const present = !!gate && (status === "awaiting" || status === "signed") && !result;

  // Reveal pause: hold the modal back until the pipeline has finished assembling (revealMs
  // from Canvas), then RISE it in -- never a sudden pop mid-build.
  const [shown, setShown] = useState(false);
  // Operator clicked "Sign off" -> show the stamp, then gracefully fade the modal out. (The
  // real approval also arrives from the backend as status "signed"; either path shows the stamp.)
  const [localSigned, setLocalSigned] = useState(false);
  const [closed, setClosed] = useState(false);
  const signed = status === "signed" || localSigned;

  useEffect(() => {
    if (!present) { setShown(false); return undefined; }
    if (status === "signed") { setShown(true); return undefined; }
    const t = setTimeout(() => setShown(true), revealMs);
    return () => clearTimeout(t);
  }, [present, status, revealMs]);

  useEffect(() => {
    if (!localSigned) return undefined; // let the stamp read for a beat, then close the modal
    const t = setTimeout(() => setClosed(true), 1400);
    return () => clearTimeout(t);
  }, [localSigned]);

  const cls = "gate" + (shown && !closed ? " on" : "") + (signed ? " signed" : "");

  return (
    <div className={cls}>
      <h4><span className="lock">&#9679;</span> Human sign-off required</h4>
      <p>This step writes code to compute a value. Nothing runs until a person approves the exact code.</p>
      <pre>{(gate && gate.code) || ""}</pre>
      <div className="row">
        <button type="button" className="signbtn" onClick={() => setLocalSigned(true)}>
          Sign off and run
        </button>
      </div>
      <span className="stamp">&#10003; Signed off &mdash; running</span>
    </div>
  );
}
