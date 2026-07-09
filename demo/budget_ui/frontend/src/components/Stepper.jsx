// src/components/Stepper.jsx
// The seven stages, lit by state.stage. Keyed by the DAEMON stage names (STAGE_ORDER),
// NOT the prototype's role keys -- so every stage past the first actually lights up.
//   - i <  current -> `.past`
//   - i === current -> `.active`
//   - terminal `done` -> current index past the end, so all seven read `.past`.

import { STAGES, STAGE_ORDER, stepLabel } from "../stages.js";

function currentIndex(state) {
  const name = state.stage && state.stage.name;
  if (!name) return -1; // nothing active yet (initial / reading not seen)
  if (name === "done") return STAGE_ORDER.length; // finale: all seven are past
  return STAGE_ORDER.indexOf(name);
}

export function Stepper({ state }) {
  const idx = currentIndex(state);
  return (
    <div className="stepper">
      {STAGES.map((s, i) => {
        const cls = "step" + (i < idx ? " past" : i === idx ? " active" : "");
        return (
          <div key={s.name} className={cls}>
            <span className="k">{i + 1} &middot; {s.k}</span>
            <span className="l">{stepLabel(s.l)}</span>
            <span className="rt">{s.rt}</span>
          </div>
        );
      })}
    </div>
  );
}
