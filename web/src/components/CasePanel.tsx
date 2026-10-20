import type { CaseDetail, FixSuggestion, PlanMap, RunMeta, ScenarioResult } from "../types";
import { CellMark } from "./CrashGrid";
import CaseTimeline from "./CaseTimeline";

export default function CasePanel({ plan, meta, result, detail, loading, running, error, previewId, remaining, onClose, onPreview, onAccept, onNext, onRetry, onTryExample, onExtraSuggestions }: {
  plan: PlanMap; meta: RunMeta; result: ScenarioResult; detail: CaseDetail | null;
  loading: boolean; running: boolean; error: string; previewId?: string; remaining: number;
  onClose: () => void; onPreview: (fix: FixSuggestion) => void; onAccept: (fix: FixSuggestion) => void; onNext: () => void;
  onRetry: () => void; onTryExample: () => void;
  onExtraSuggestions: (live: boolean) => void;
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
    {error && <div className="inline-error" role="alert"><p>{error}</p><div className="choice-row"><button type="button" className="button button-secondary" disabled={loading || running} onClick={onRetry}>Try suggestions again</button><button type="button" className="button button-text" disabled={loading || running} onClick={onTryExample}>Try the example plan instead</button></div></div>}
    {!survives && !running && detail && <>
      {!error && <div className="ai-sentence"><div className="section-kicker">AI'S EXPLANATION{detail.placeholder && " · PLACEHOLDER"}</div><p>{detail.explanation ?? (detail.source === "live" ? "The AI returned no explanation for this case." : "No saved explanation for this case.")}</p><span>{detail.placeholder ? "Written by hand for testing." : `Suggested by ${detail.suggested_by ?? "AI"}${detail.fallback_used && detail.source !== "saved" ? " (fallback: primary unavailable)" : ""}`}</span></div>}
      <div className="fix-section-heading"><h3>Test a change</h3>{detail.placeholder && <span className="placeholder-label">PLACEHOLDER SUGGESTIONS</span>}</div>
      {detail.suggestions.map((fix) => <article className={`fix-card ${!fix.eligible ? "turned-down-card" : ""}`} key={fix.id} data-fix-id={fix.id}>
        <div className="fix-card-title"><h4>{fix.description}</h4>{fix.gate_status !== "passed" ? <span className="fix-verdict">Couldn't apply</span> : !fix.eligible && <span className="fix-verdict">Turned down</span>}</div>
        {fix.gate_status === "passed" ? <><p className="fix-score mono">fixes {fix.fixes_n} · still broken {fix.still_broken_n} · new crosses {fix.new_crosses_n}</p>{fix.rejection_reason && <p className="fix-reason">{fix.rejection_reason}</p>}
          {fix.new_crosses.map((id) => <p className="new-cross-callout" key={id}><CellMark state="cross" /><span>New {id.includes("+") ? "hidden pair" : "single weak spot"}: {id.split("+").map(label).join(" + ")}</span></p>)}
          <div className="fix-card-actions"><button className="button button-secondary" type="button" onClick={() => onPreview(fix)}>{previewId === fix.id ? "Previewing" : "Preview"}</button>{fix.eligible && <button className="button button-primary" type="button" onClick={() => onAccept(fix)}>Accept fix</button>}</div>
        </> : <p className="fix-reason">{fix.gate_reason}</p>}
      </article>)}
      {!error && detail.suggestions.length === 0 && <p className="no-suggestions">{detail.source === "live" ? "The AI returned no suggestions for this case." : "No saved suggestions for this case. Add a key to ask the AI."}</p>}
      {!detail.suggestions.some((fix) => fix.eligible) && detail.can_retry && <div className="no-suggestions"><p>None of these fixes worked. You can ask once more.</p><button type="button" className="button button-secondary" disabled={loading || running} onClick={() => onExtraSuggestions(false)}>None worked. Try once more</button></div>}
      {detail.source !== "live" && detail.suggestions.length === 0 && <button type="button" className="button button-secondary" disabled={loading || running} onClick={() => onExtraSuggestions(true)}>Ask AI for suggestions</button>}
    </>}
    {survives && <div className="next-case-action">{remaining ? <button className="button button-primary" type="button" onClick={onNext}>Next broken case ({remaining} left)</button> : <><h3>All {meta.total} tested scenarios survive.</h3><button className="button button-secondary" type="button" disabled title="Report preview is not available yet.">See report</button></>}</div>}
  </aside>;
}
