import { useEffect, useRef, useState } from "react";
import { getReport } from "../api/client";
import { CellMark } from "../components/CrashGrid";
import type { ReportData } from "../types";
import "./report.css";

function Score({fix}: {fix: {fixes_n: number; still_broken_n: number; new_crosses_n: number}}) {
  return <p className="report-score mono">fixes {fix.fixes_n} · still broken {fix.still_broken_n} · new crosses {fix.new_crosses_n}</p>;
}

export function ReportContent({data, onBack}: {data: ReportData; onBack: () => void}) {
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => { title.current?.focus(); }, []);
  const total = data.after.total;
  return <article className="report-screen" aria-label="Crash-test report">
    <header className="report-header">
      <p className="eyebrow">05 / REPORT</p><h1 ref={title} tabIndex={-1}>The plan, tested.</h1>
      <p className="report-read-by mono">Read by {data.read_by}</p>
      <div className="report-controls"><button className="button button-secondary" type="button" onClick={onBack}>Back to results</button><button className="button button-primary" type="button" onClick={() => window.print()}>Print or save as PDF</button></div>
    </header>
    <section className="report-section report-plan" aria-labelledby="report-plan-title">
      <h2 id="report-plan-title">The plan</h2>
      <p className="report-review-summary mono">AI read {data.summary.ai_read} items, {data.summary.corrected} corrected by you, {data.summary.added} added by you</p>
      {[...new Set(data.facts.map((row) => row.group))].map((group) => <div className="report-fact-group" key={group}><h3>{group}</h3><ul>{data.facts.filter((row) => row.group === group).map((row) => <li key={row.id} className="report-fact">
        {row.status === "corrected" && row.original_statement && !row.changed_by_fix && <del>{row.original_statement} </del>}<span>{row.statement}</span>
        <span className="report-fact-trail mono">{row.source_line ? ` · ${row.source_line}` : " · no source line"}{row.changed_by_fix ? ` · changed by Fix ${row.changed_by_fix}` : row.status === "added" ? " · added by you" : row.status === "corrected" ? " · corrected by you" : " · confirmed"}</span>
      </li>)}</ul></div>)}
      {data.review_answers.length > 0 && <div className="report-review-answers"><h3>Review decisions</h3><ul>{data.review_answers.map((row, i) => <li key={i}>{row.question} <strong>{row.answer}</strong></li>)}</ul></div>}
    </section>
    <section className="report-section report-tested" aria-labelledby="report-tested-title">
      <h2 id="report-tested-title">What was tested</h2>
      <p className="mono">{total} tests: every single problem and every pair that can happen</p>
      <p>{data.after.problems.length} problems, at the sizes confirmed below.</p>
      <table><thead><tr><th scope="col">Problem</th><th scope="col">Size tested</th></tr></thead><tbody>{data.after.problems.map((problem) => <tr key={problem.id}><td>{problem.label}</td><td className="mono">{problem.size === null ? "Absent (no duration)" : `${problem.size} minutes`}</td></tr>)}</tbody></table>
    </section>
    <section className="report-section report-before" aria-labelledby="report-before-title">
      <h2 id="report-before-title">What broke before fixes</h2><p className="mono">{data.before.count.line}</p>
      {data.broken_before.length ? data.broken_before.map((row) => <div className="report-broken-case" key={row.scenario_id}><h3><CellMark state="cross" />{row.label}</h3><p>{row.failures.length === 1 ? "Single weak spot" : "Hidden pair: each problem alone survived"}</p><p>{row.human_cost}</p></div>) : <p>No single weak spots or hidden pairs were proved.</p>}
      {data.dimmed_groups.map((group) => <details className="report-dimmed-group" key={group.weak_spot}><summary>{group.count} pairs already broken by {group.weak_spot} alone</summary><ul>{group.pairs.map((pair) => <li key={pair}>{pair}</li>)}</ul></details>)}
    </section>
    <section className="report-section report-fixes" aria-labelledby="report-fixes-title">
      <h2 id="report-fixes-title">Fixes</h2>
      <h3>Accepted changes</h3>
      {data.accepted_fixes.length === 0 && <p>No fixes have been accepted. This report shows the plan as it stands.</p>}
      {data.accepted_fixes.map((fix) => <article className="report-fix report-accepted-fix" key={fix.to_fingerprint}><h4><CellMark state="tick" />Fix {fix.number} ({fix.origin === "yours" ? "yours" : "AI"}): {fix.description}</h4><p className="report-provider">{fix.provider_label}</p><ul>{fix.changes.map((line) => <li key={line}>{line}</li>)}</ul><Score fix={fix} /></article>)}
      <h3>Turned-down and couldn't-apply suggestions</h3>
      <p>These are the changes requested and checked during this run. Scores use the plan at that point.</p>
      {!data.suggestion_batches.some((batch) => batch.suggestions.some((fix) => !fix.eligible)) && <p>No turned-down suggestions have been recorded.</p>}
      {data.suggestion_batches.map((batch, i) => <div className="report-suggestion-batch" key={`${batch.fingerprint}:${i}`}>{batch.suggestions.filter((fix) => !fix.eligible).map((fix) => <article className="report-fix report-rejected-fix" key={fix.id}>
        <p className="report-case-label">Case: {batch.scenario_label}</p><h4>{fix.origin === "yours" ? "Your change: " : ""}{fix.description}</h4><p className="report-provider">{fix.origin === "yours" ? "Your change" : batch.provider_label}</p>
        <p><strong>{fix.gate_status !== "passed" ? "Couldn't apply" : "Turned down"}.</strong> {fix.gate_reason ?? fix.rejection_reason}</p>{fix.gate_status === "passed" ? <Score fix={fix} /> : <p>Not scored. The operation did not pass the gate.</p>}
      </article>)}</div>)}
    </section>
    <section className="report-section report-after" aria-labelledby="report-after-title"><h2 id="report-after-title">After the fixes</h2><p className="report-final-count mono">{data.after.count.line}</p>{data.after.count.survived === total && <h3><CellMark state="tick" />All {total} tested scenarios survive.</h3>}<p>Survived means survived the listed problems at the listed sizes. It is not a guarantee.</p></section>
    <section className="report-section report-limits" aria-labelledby="report-limits-title"><h2 id="report-limits-title">What was NOT tested</h2><ul>{data.not_tested.map((line) => <li key={line}>{line}</li>)}</ul><h3>Question-mark results</h3>{data.unknown_results.length ? <ul>{data.unknown_results.map((row) => <li key={row.label}><strong>?</strong> {row.label} ({row.phases.join(" and ")}). Unknown is not a pass.</li>)}</ul> : <p>No question-mark results in the original or current run.</p>}</section>
    <footer className="report-footer">{data.source !== "live" && <p>This report used a saved AI reading of the example plan.</p>}<p className="mono">Fingerprint: {data.fingerprint}</p></footer>
  </article>;
}

export default function Report({fingerprint, onBack}: {fingerprint: string; onBack: () => void}) {
  const [data, setData] = useState<ReportData | null>(null), [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { let active = true; setData(null); setError(""); getReport(fingerprint).then((result) => { if (active) setData(result); }).catch((reason: Error) => { if (active) setError(reason.message); }); return () => { active = false; }; }, [fingerprint, attempt]);
  if (!data) return <div className="report-screen"><button className="button button-secondary" type="button" onClick={onBack}>Back to results</button>{error ? <div role="alert"><p>{error}</p><button className="button button-primary" type="button" onClick={() => setAttempt((n) => n + 1)}>Try report again</button></div> : <p role="status">Preparing the report from your checked plan…</p>}</div>;
  return <ReportContent data={data} onBack={onBack} />;
}
