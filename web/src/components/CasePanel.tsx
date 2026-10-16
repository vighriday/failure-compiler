import type { CaseDetail, FixSuggestion, PlanMap, RunMeta, ScenarioResult } from "../types";
import { CellMark } from "./CrashGrid";
import CaseTimeline from "./CaseTimeline";

export default function CasePanel({ plan, meta, result, detail, loading, running, error, previewId, remaining, onClose, onPreview, onAccept, onNext }: {
  plan: PlanMap; meta: RunMeta; result: ScenarioResult; detail: CaseDetail | null;
  loading: boolean; running: boolean; error: string; previewId?: string; remaining: number;
  onClose: () => void; onPreview: (fix: FixSuggestion) => void; onAccept: (fix: FixSuggestion) => void; onNext: () => void;
}) {
  const label = (id: string) => meta.problems.find((problem) => problem.id === id)?.label ?? id;
  const survives = result.state === "tick" && !running;
  return <aside className="case-panel" aria-label="Case details" data-state={survives ? "survives" : "broken"}>
    <header className="case-panel-heading"><span className="eyebrow">04 / {survives ? "AFTER THE FIX" : "BROKEN CASE"}</span><button className="quiet-link" type="button" onClick={onClose}>Close</button></header>
    <h2>{result.failures.map(label).map((text, index) => <span key={text}>{index > 0 && <span className="case-plus"> + </span>}{text}</span>)}</h2>
    {result.failures.length === 2 && detail && <div className="single-proof"><strong>Each alone: survives</strong>{detail.alone_results.map((single) => <span key={single.scenario_id}><CellMark state={single.state} />{label(single.scenario_id)}</span>)}</div>}
    {running ? <p className="case-retesting mono">Re-testing the changed plan…</p> : survives ? <div className="case-resolved"><CellMark state="tick" /><strong>Now survives.</strong></div> : <p className="human-cost">{result.human_cost}</p>}
    {!survives && detail && !running && <div className="checker-facts"><h3>Why the checker says so</h3>{[...new Set(Object.values(detail.route_reasons))].map((reason) => <p key={reason}>{reason}</p>)}</div>}
    <CaseTimeline plan={plan} result={result} reasons={survives ? {} : detail?.route_reasons ?? {}} />
    {loading && <p className="suggestion-loading mono" role="status">Checking suggestions against all {meta.total} scenarios…</p>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {!survives && !running && detail && <>
      <div className="ai-sentence"><div className="section-kicker">AI'S EXPLANATION · PLACEHOLDER</div><p>{detail.explanation ?? "No saved explanation for this case."}</p><span>Written by hand for testing.</span></div>
      <div className="fix-section-heading"><h3>Test a change</h3><span className="placeholder-label">PLACEHOLDER SUGGESTIONS</span></div>
      {detail.suggestions.map((fix) => <article className={`fix-card ${!fix.eligible ? "turned-down-card" : ""}`} key={fix.id} data-fix-id={fix.id}>
        <div className="fix-card-title"><h4>{fix.description}</h4>{fix.gate_status !== "passed" ? <span className="fix-verdict">Couldn't apply</span> : !fix.eligible && <span className="fix-verdict">Turned down</span>}</div>
        {fix.gate_status === "passed" ? <><p className="fix-score mono">fixes {fix.fixes_n} · still broken {fix.still_broken_n} · new crosses {fix.new_crosses_n}</p>{fix.rejection_reason && <p className="fix-reason">{fix.rejection_reason}</p>}
          {fix.new_crosses.map((id) => <p className="new-cross-callout" key={id}><CellMark state="cross" /><span>New hidden pair: {id.split("+").map(label).join(" + ")}</span></p>)}
          <div className="fix-card-actions"><button className="button button-secondary" type="button" onClick={() => onPreview(fix)}>{previewId === fix.id ? "Previewing" : "Preview"}</button>{fix.eligible && <button className="button button-primary" type="button" onClick={() => onAccept(fix)}>Accept fix</button>}</div>
        </> : <p className="fix-reason">{fix.gate_reason}</p>}
      </article>)}
      {detail.suggestions.length === 0 && <p className="no-suggestions">No saved suggestions for this case. Add a key to ask the AI.</p>}
    </>}
    {survives && <div className="next-case-action">{remaining ? <button className="button button-primary" type="button" onClick={onNext}>Next broken case ({remaining} left)</button> : <><h3>All {meta.total} tested scenarios survive.</h3><button className="button button-secondary" type="button" disabled title="Report preview is not available yet.">See report</button></>}</div>}
  </aside>;
}
