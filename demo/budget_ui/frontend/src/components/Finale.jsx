// src/components/Finale.jsx
// The result panel, driven by state.result. BRANCHES on result.passed (spec 16.4:
// never render the green "matched" state on a non-pass):
//   - passed  : the green success panel + the output sample table (synthetic mode).
//               When there is no sample, show counts only (rows / graded / tier).
//   - non-pass: a NEUTRAL "refining" panel (the `.refining` variant) -- never green.
//
// The green glow on the output node(s) (result.outputs) is applied on the nodes
// themselves in Canvas/GraphNode (`.done-glow`), since those live in the scaled stage
// while this panel overlays the canvas -- exactly as the prototype split them.

export function Finale({ result }) {
  if (!result) return null;

  const passed = !!result.passed;
  const sample = Array.isArray(result.sample) ? result.sample : [];
  const headers = sample.length ? Object.keys(sample[0]) : [];
  const rowCount = result.rows != null ? result.rows : sample.length;

  return (
    <div className={"result on" + (passed ? "" : " refining")}>
      <h4>{passed ? <>&#10003; Tested against your sample</> : <>Refining the pipeline</>}</h4>

      {headers.length > 0 && (
        <table>
          <tbody>
            <tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr>
            {sample.map((row, i) => (
              <tr key={i}>
                {headers.map((h) => (
                  <td key={h}>{row[h] === "" ? <>&mdash;</> : row[h]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="meta">
        {passed ? (
          <>
            <b style={{ color: "var(--done)" }}>{rowCount} rows</b>
            {result.graded ? <> &middot; {result.graded} outputs graded</> : null}
            {result.tier ? <> &middot; tier: {result.tier}</> : null}
          </>
        ) : (
          <>
            Not a match yet{rowCount != null ? <> &middot; {rowCount} rows</> : null}
            {result.tier ? <> &middot; tier: {result.tier}</> : null} &mdash; refining before it ships.
          </>
        )}
      </div>
    </div>
  );
}
