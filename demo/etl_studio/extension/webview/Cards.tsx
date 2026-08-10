// Anchored interrupt cards (ticket 12: cards live in viewport space with
// dashed leaders to their canvas subject) + the ticket 13 increment: the
// spec-gate card, Request-changes ghosts with a required free-text reveal,
// and the hold card. Every affordance resolves through 08's one answer
// shape {question_id, choice, free_text?} -- <= 3 affordances per card.

import React, { useLayoutEffect, useRef, useState } from "react";
import { answer } from "./bridge";
import type { QuestionView } from "./state";
import type { CodeCell, QuestionOption } from "./types";
import { vwNarrow } from "./layout";

export interface Anchor {
  x: number;
  y: number;
}

interface PlacementProps {
  side: "right" | "near";
  anchors: Anchor[]; // viewport-space points (already camera-projected)
  vw: number;
  vh: number;
  leadClass?: string;
  delay?: number; // card appear delay (after the camera settles)
  width?: number;
  children: React.ReactNode;
}

// Placement math ported from the design record's placeCard().
function place(
  side: "right" | "near",
  anchors: Anchor[],
  cw: number,
  ch: number,
  vw: number,
  vh: number
): { left: number; top: number } {
  const top = 84;
  if (side === "right" || !anchors.length) {
    const left = vw - cw - 26;
    const cy = Math.max(top + 8, Math.min(top + 40, vh - ch - 170));
    return { left, top: cy };
  }
  const a = anchors[0];
  const minLeft = vwNarrow(vw) ? 24 : 452;
  const left = Math.min(Math.max(a.x - cw / 2, minLeft), vw - cw - 24);
  let cy = Math.min(a.y + 34, vh - ch - 168);
  if (cy < top) {
    cy = top;
  }
  return { left, top: cy };
}

function leadPaths(
  side: "right" | "near",
  anchors: Anchor[],
  pos: { left: number; top: number },
  cw: number
): string[] {
  return anchors.map((a) => {
    const edgeX =
      side === "right" ? pos.left : Math.max(pos.left + 18, Math.min(a.x, pos.left + cw - 18));
    const edgeY = side === "right" ? pos.top + 64 : pos.top;
    // Leave the subject on the side facing the card, never back through it.
    const dir = edgeY >= a.y ? 1 : -1;
    const sy = a.y + dir * 6;
    return `M${a.x},${sy} C${a.x},${(sy + edgeY) / 2} ${edgeX - (side === "right" ? 60 : 0)},${edgeY} ${edgeX},${edgeY}`;
  });
}

export function AnchoredCard({
  side,
  anchors,
  vw,
  vh,
  leadClass,
  delay = 1.15,
  width,
  children,
}: PlacementProps): React.ReactElement {
  const ref = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }
    const measure = () => setSize({ w: el.offsetWidth, h: el.offsetHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const cw = size?.w ?? width ?? 372;
  const ch = size?.h ?? 300;
  const pos = place(side, anchors, cw, ch, vw, vh);
  const leads = size ? leadPaths(side, anchors, pos, cw) : [];

  return (
    <>
      <svg className="leads" viewBox={`0 0 ${vw} ${vh}`} style={{ width: vw, height: vh }}>
        {leads.map((d, i) => (
          <path key={i} className={`lead ${leadClass ?? ""}`} d={d} style={{ animation: `springin .01s linear ${delay}s both` }} />
        ))}
      </svg>
      <div
        className="card"
        ref={ref}
        style={{
          left: pos.left,
          top: pos.top,
          width,
          animationDelay: `${delay}s`,
          visibility: size ? "visible" : "hidden",
        }}
      >
        {children}
      </div>
    </>
  );
}

// ---- shared bits -----------------------------------------------------------

function RequestChangesRow({
  q,
  placeholder,
  onSent,
}: {
  q: QuestionView;
  placeholder: string;
  onSent: () => void;
}): React.ReactElement {
  const [text, setText] = useState("");
  return (
    <div className="reqrow">
      <input
        className="qfree"
        autoFocus
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        onKeyDown={(e) => {
          if (e.key === "Enter" && text.trim()) {
            answer(q.id, "request_changes", text.trim());
            onSent();
          }
        }}
      />
      <button
        className="go"
        disabled={!text.trim()}
        onClick={() => {
          answer(q.id, "request_changes", text.trim());
          onSent();
        }}
      >
        Send
      </button>
    </div>
  );
}

const rejectOption = (q: QuestionView): QuestionOption | undefined =>
  q.options.find((o) => o.kind === "reject");

// ---- the question-round card ----------------------------------------------

interface GapSel {
  choice: string | null;
  free: string;
  waived: boolean;
}

export function GapRoundCard({
  qs,
  vw,
  vh,
  anchors,
}: {
  qs: QuestionView[];
  vw: number;
  vh: number;
  anchors: Anchor[];
}): React.ReactElement {
  const [sels, setSels] = useState<Record<string, GapSel>>(() => {
    const out: Record<string, GapSel> = {};
    for (const q of qs) {
      const rec = q.options.find((o) => o.recommended);
      out[q.id] = { choice: rec?.id ?? null, free: "", waived: false };
    }
    return out;
  });
  const [sent, setSent] = useState(false);

  const upd = (qid: string, patch: Partial<GapSel>) =>
    setSels((s) => ({ ...s, [qid]: { ...s[qid], ...patch } }));

  const ready = qs.every((q) => {
    const s = sels[q.id];
    return s && (s.waived || s.choice || s.free.trim());
  });

  const send = () => {
    if (!ready || sent) {
      return;
    }
    setSent(true);
    for (const q of qs) {
      const s = sels[q.id];
      if (s.waived) {
        answer(q.id, "waive");
      } else if (s.free.trim() && !s.choice) {
        answer(q.id, "other", s.free.trim());
      } else {
        answer(q.id, s.choice ?? "other", s.free.trim() || undefined);
      }
    }
  };

  const round = qs[0]?.payload.round ?? { k: 1, n: 3 };
  return (
    <AnchoredCard side="right" anchors={anchors} vw={vw} vh={vh} delay={0.45}>
      <div className="eyebrow em">
        Question round
        <span className="n">
          round {round.k} of {round.n} · {qs.length} gap{qs.length > 1 ? "s" : ""}
        </span>
      </div>
      {qs.map((q) => {
        const s = sels[q.id];
        const waivable = q.options.some((o) => o.kind === "waive");
        const choices = q.options.filter((o) => o.kind !== "waive");
        return (
          <div key={q.id} className={`qgap${s?.waived ? " waived" : ""}`}>
            <div className={`sev ${q.payload.severity}`}>
              <span className="d" />
              {q.payload.severity === "blocking" ? "Blocking" : "Advisory"}
              <span className="onr">
                {q.payload.gap_id} · on {q.payload.rule_id}
              </span>
            </div>
            <div className="qp">{q.payload.prompt}</div>
            <div className="opts">
              {choices.map((o) => (
                <button
                  key={o.id}
                  className={`opt${s?.choice === o.id ? " sel" : ""}`}
                  onClick={() => upd(q.id, { choice: o.id, waived: false })}
                >
                  <span className="radio" />
                  <span>
                    {o.label}
                    {o.recommended && o.why ? <span className="why">Recommended — {o.why}</span> : null}
                  </span>
                </button>
              ))}
            </div>
            <input
              className="qfree"
              value={s?.free ?? ""}
              placeholder={q.payload.free_prompt ?? "Something else…"}
              onChange={(e) => upd(q.id, { free: e.target.value, choice: null, waived: false })}
            />
            {waivable ? (
              <>
                <button className="qwaive" onClick={() => upd(q.id, { waived: !s?.waived })}>
                  Waive — proceed with the default
                </button>
                <div className="waivetag">✓ Waived — default applies, recorded on the spec</div>
              </>
            ) : null}
          </div>
        );
      })}
      <div className="cfoot">
        <button className="go" disabled={!ready || sent} onClick={send}>
          Send answers
        </button>
        <span className="note">
          Recorded on the spec.
          <br />
          Nothing times out.
        </span>
      </div>
    </AnchoredCard>
  );
}

// ---- the spec-gate card (ticket 13's new surface) --------------------------

export function SpecGateCard({
  q,
  vw,
  vh,
  anchors,
}: {
  q: QuestionView;
  vw: number;
  vh: number;
  anchors: Anchor[];
}): React.ReactElement {
  const [rejecting, setRejecting] = useState(false);
  const [sent, setSent] = useState(false);
  const draft = Number(q.payload.draft ?? 1);
  const summary = q.payload.summary ?? {};
  const gapRes: { gap_id: string; note?: string }[] = q.payload.gap_resolutions ?? [];
  return (
    <AnchoredCard side="right" anchors={anchors} vw={vw} vh={vh} delay={0.45}>
      <div className="eyebrow em">
        Spec sign-off
        <span className="n">
          draft {draft} · {q.payload.job ?? ""}
        </span>
      </div>
      <div className="spechead">
        <span className="st">Requirement spec</span>
        <span className="ss">
          {summary.sources ?? "?"} sources · {summary.rules ?? "?"} rules
        </span>
      </div>
      {q.payload.what_changed ? <div className="whatchanged">{q.payload.what_changed}</div> : null}
      <div className="gapres">
        {gapRes
          .filter((g) => g.note)
          .map((g) => (
            <span key={g.gap_id} className="gr">
              <span>{g.note}</span>
            </span>
          ))}
      </div>
      {q.payload.voice ? (
        <div className="voice">
          <b>Orchestrator</b> — {q.payload.voice}
        </div>
      ) : null}
      {rejecting ? (
        <RequestChangesRow
          q={q}
          placeholder={rejectOption(q)?.placeholder ?? "What should change…"}
          onSent={() => setSent(true)}
        />
      ) : null}
      <div className="cfoot">
        <button className="go" disabled={sent} onClick={() => (setSent(true), answer(q.id, "approve"))}>
          Approve and sign
        </button>
        {!rejecting ? (
          <button className="ghostbtn" disabled={sent} onClick={() => setRejecting(true)}>
            Request changes
          </button>
        ) : null}
        <span className="note">
          Signing fixes what the job must do.
          <br />
          Nothing times out.
        </span>
      </div>
    </AnchoredCard>
  );
}

// ---- the code-gate card ----------------------------------------------------

export function CodeGateCard({
  q,
  vw,
  vh,
  anchors,
  onAskCell,
}: {
  q: QuestionView;
  vw: number;
  vh: number;
  anchors: Anchor[];
  onAskCell: (cell: CodeCell) => void;
}): React.ReactElement {
  const [rejecting, setRejecting] = useState(false);
  const [sent, setSent] = useState(false);
  const cells: CodeCell[] = q.payload.cells ?? [];
  const cell = cells[0];
  return (
    <AnchoredCard side="near" anchors={anchors} vw={vw} vh={vh} leadClass="vi" width={440}>
      <div className="eyebrow vi">
        Pre-execution code gate
        <span className="n">
          {cells.length} cell{cells.length !== 1 ? "s" : ""} · round {q.payload.round ?? 1}
        </span>
      </div>
      {q.payload.voice ? (
        <div className="voice">
          <b>Orchestrator</b> — {q.payload.voice}
        </div>
      ) : null}
      {cell ? (
        <>
          <div className="gmeta">
            <span className="gtag">
              <b>{cell.id}</b>
            </span>
            {cell.component ? <span className="gtag">{cell.component}</span> : null}
            {cell.author ? <span className="gtag">authored by {cell.author}</span> : null}
            {cell.changed ? <span className="gtag chg">changed</span> : null}
          </div>
          <pre>{cell.code}</pre>
          {cell.validator ? <div className="valline">✓ {cell.validator}</div> : null}
        </>
      ) : null}
      <div className="gnote">Re-pauses only if a cell is new or changed on a later iteration.</div>
      {rejecting ? (
        <RequestChangesRow
          q={q}
          placeholder={rejectOption(q)?.placeholder ?? "What should change in this cell…"}
          onSent={() => setSent(true)}
        />
      ) : null}
      <div className="cfoot">
        <button className="go" disabled={sent} onClick={() => (setSent(true), answer(q.id, "approve"))}>
          Approve and run
        </button>
        {!rejecting ? (
          <button className="ghostbtn" disabled={sent} onClick={() => setRejecting(true)}>
            Request changes
          </button>
        ) : null}
        {cell ? (
          <button className="ghostbtn" onClick={() => onAskCell(cell)}>
            Ask about this cell
          </button>
        ) : null}
      </div>
    </AnchoredCard>
  );
}

// ---- the verdict card ------------------------------------------------------

export function VerdictCard({
  q,
  vw,
  vh,
  anchors,
}: {
  q: QuestionView;
  vw: number;
  vh: number;
  anchors: Anchor[];
}): React.ReactElement {
  const [rejecting, setRejecting] = useState(false);
  const [sent, setSent] = useState(false);
  const verified = q.payload.verdict === "verified";
  const table = q.payload.table ?? { headers: [], rows: [] };
  const runs = q.payload.runs ?? {};
  return (
    <AnchoredCard side="near" anchors={anchors} vw={vw} vh={vh} leadClass="ja" width={460}>
      <div className="eyebrow ja">
        Harness verdict · human gate
        <span className="n">
          run {runs.k ?? "?"} of {runs.n ?? "?"}
        </span>
      </div>
      <div className="vhead">
        <span className={`vt${verified ? "" : " red"}`}>{verified ? "Verified" : "Not verified"}</span>
        <span className="vs">{q.payload.matched} rows matched your golden</span>
      </div>
      {q.payload.diagnosis ? <div className="vsub">{q.payload.diagnosis}</div> : null}
      <div className="vtw">
        <div className="sc">
          <table>
            <thead>
              <tr>
                {table.headers.map((h: string) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r: string[], i: number) => (
                <tr key={i}>
                  {r.map((c, j) => (
                    <td key={j}>{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {q.payload.voice ? <div className="voice">{q.payload.voice}</div> : null}
      {rejecting ? (
        <RequestChangesRow
          q={q}
          placeholder={rejectOption(q)?.placeholder ?? "What's wrong with the output…"}
          onSent={() => setSent(true)}
        />
      ) : null}
      <div className="cfoot">
        {verified ? (
          <button className="go jadec" disabled={sent} onClick={() => (setSent(true), answer(q.id, "approve"))}>
            Approve job
          </button>
        ) : null}
        {!rejecting ? (
          <button className="ghostbtn" disabled={sent} onClick={() => setRejecting(true)}>
            Request changes
          </button>
        ) : null}
        <button className="ghostbtn" disabled={sent} onClick={() => (setSent(true), answer(q.id, "stop"))}>
          Stop
        </button>
      </div>
    </AnchoredCard>
  );
}

// ---- the hold card (ticket 13) ---------------------------------------------

export function HoldCard({
  q,
  vw,
  vh,
}: {
  q: QuestionView;
  vw: number;
  vh: number;
}): React.ReactElement {
  const [steer, setSteer] = useState("");
  const [sent, setSent] = useState(false);
  const steerOpt = q.options.find((o) => o.kind === "steer");
  return (
    <AnchoredCard side="right" anchors={[]} vw={vw} vh={vh} delay={0.3}>
      <div className="eyebrow em">
        Holding
        <span className="n">after {q.payload.after_label ?? q.payload.after_stage}</span>
      </div>
      {q.payload.voice ? <div className="voice">{q.payload.voice}</div> : null}
      <div className="reqrow" style={{ paddingTop: 14 }}>
        <input
          className="qfree"
          value={steer}
          placeholder={steerOpt?.placeholder ?? "Steer with a note…"}
          onChange={(e) => setSteer(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && steer.trim() && !sent) {
              setSent(true);
              answer(q.id, "steer", steer.trim());
            }
          }}
        />
      </div>
      <div className="cfoot">
        <button className="go" disabled={sent} onClick={() => (setSent(true), answer(q.id, "resume"))}>
          Resume
        </button>
        {steer.trim() ? (
          <button
            className="go"
            disabled={sent}
            onClick={() => (setSent(true), answer(q.id, "steer", steer.trim()))}
          >
            Steer
          </button>
        ) : (
          <button className="ghostbtn" disabled={sent} onClick={() => (setSent(true), answer(q.id, "stop"))}>
            Stop the run
          </button>
        )}
      </div>
    </AnchoredCard>
  );
}
