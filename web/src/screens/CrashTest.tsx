import { useEffect, useRef, useState } from "react";
import { APIError, applyFix, getReport, streamTests, suggestFixes, testChange } from "../api/client";
import CrashGrid from "../components/CrashGrid";
import CasePanel from "../components/CasePanel";
import Report from "./Report";
import { countResults } from "../lib/results";
import type { CaseDetail, FixOperation, FixSuggestion, PlanMap, ReadingSource, ReportData, RunCount, RunMeta, ScenarioResult } from "../types";

export default function CrashTest({ plan, onEdit, onPlanChange, onTryExample, readingSource = "saved", fallbackUsed = false, embedded = false }: { plan: PlanMap; onEdit: () => void; onPlanChange: (plan: PlanMap) => void; onTryExample: () => void; readingSource?: ReadingSource; fallbackUsed?: boolean; embedded?: boolean }) {
  const [meta, setMeta] = useState<RunMeta | null>(null);
  const [showReport, setShowReport] = useState(false);
  const [history, setHistory] = useState<ReportData | null>(null);
  const [historyError, setHistoryError] = useState("");
  const [historyAttempt, setHistoryAttempt] = useState(0);
  const [before, setBefore] = useState(false);
  const [results, setResults] = useState<ScenarioResult[]>([]);
  const [count, setCount] = useState<RunCount | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [detailAttempt, setDetailAttempt] = useState(0);
  const detailOptions = useRef<{retry?: boolean; live?: boolean}>({});
  const [preview, setPreview] = useState<FixSuggestion | null>(null);
  const [applying, setApplying] = useState(false);
  const [flippedIds, setFlippedIds] = useState<string[]>([]);
  const resultsRef = useRef<ScenarioResult[]>([]);
  const currentCase = useRef("");
  currentCase.current = `${plan.fingerprint}:${selectedId}`;

  useEffect(() => {
    const controller = new AbortController();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const previous = new Map(resultsRef.current.map((result) => [result.scenario_id, result]));
    let collected: ScenarioResult[] = [];
    setCount(null); setDone(false); setError(""); setPreview(null); setFlippedIds([]); setBefore(false); setHistory(null);
    streamTests(plan.fingerprint!, reduced, (event) => {
      if (event.type === "start") setMeta(event);
      if (event.type === "result") {
        collected = [...collected, event.result];
        if (!reduced) {
          setResults((shown) => [...shown.filter((r) => r.scenario_id !== event.result.scenario_id), event.result]);
          setCount(event.count);
          if (previous.has(event.result.scenario_id) && previous.get(event.result.scenario_id)?.state !== event.result.state) setFlippedIds((ids) => [...ids, event.result.scenario_id]);
        }
      }
      if (event.type === "complete") { resultsRef.current = collected; setResults(collected); setCount(event.count); setDone(true); }
    }, controller.signal).catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, [plan.fingerprint, attempt]);

  useEffect(() => {
    if (!done || !plan.fix_history.length) return;
    let active = true; setHistoryError("");
    getReport(plan.fingerprint!).then((data) => { if (active) setHistory(data); }).catch((reason: Error) => { if (active) setHistoryError(reason.message); });
    return () => { active = false; };
  }, [plan.fingerprint, plan.fix_history.length, done, historyAttempt]);

  const selected = results.find((result) => result.scenario_id === selectedId);
  const broken = results.filter((result) => result.state === "cross");
  useEffect(() => {
    if (!selectedId || !done || selected?.state !== "cross") { setDetailLoading(false); return; }
    let active = true;
    setDetail(null); setDetailLoading(true); setDetailError("");
    suggestFixes(plan.fingerprint!, selectedId, detailOptions.current).then((payload) => { if (active) setDetail(payload); })
      .catch((reason: Error) => { if (active) { if (reason instanceof APIError && reason.caseDetail) setDetail(reason.caseDetail); setDetailError(reason.message); } })
      .finally(() => { if (active) setDetailLoading(false); });
    return () => { active = false; };
  }, [selectedId, plan.fingerprint, done, detailAttempt]);

  async function accept(fix: FixSuggestion) {
    if (!selectedId || !fix.eligible || !done) return;
    setApplying(true); setDetailError("");
    try {
      const response = await applyFix(plan.fingerprint!, selectedId, fix.id);
      setPreview(null); setDone(false); onPlanChange(response.plan_map);
    } catch (reason) { setDetailError(reason instanceof Error ? reason.message : "Could not apply this change."); }
    finally { setApplying(false); }
  }

  async function testOwnChange(operations: FixOperation[]) {
    if (!selectedId || !done) return;
    const capturedCase = currentCase.current;
    const fix = await testChange(plan.fingerprint!, selectedId, operations);
    if (currentCase.current !== capturedCase) return;
    setPreview(null);
    setDetail((current) => current ? {...current, suggestions: [...current.suggestions, fix]} : {
      placeholder: false, source: readingSource, explanation: null, result: selected!,
      route_reasons: {}, alone_results: [], suggestions: [fix], can_retry: false,
    });
  }

  const shown = before && history ? history.before.results : preview?.scenario_results ?? results;
  const shownMeta = before && history ? history.before : meta;
  const shownCount = before && history ? history.before.count : preview ? countResults(shown) : count;
  const changedIds = preview ? shown.filter((result) => results.find((r) => r.scenario_id === result.scenario_id)?.state !== result.state).map((r) => r.scenario_id) : [];
  function nextCase() {
    const next = broken.find((result) => result.failures.length === 2) ?? broken[0];
    if (next) { detailOptions.current = {}; setSelectedId(next.scenario_id); setDetail(null); setPreview(null); }
  }

  if (showReport) return <Report fingerprint={plan.fingerprint!} onBack={() => { setShowReport(false); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>(".report-launch")?.focus()); }} />;
  return <div className={`app-shell crash-shell ${selected && !before ? "panel-open" : ""}`}>
    {!embedded && <header className="topbar"><div className="brand brand-compact"><div className="brand-name">Failure Compiler</div><div className="brand-subtitle">Crash-test a plan before Saturday does.</div></div><div className="topbar-meta"><span>{readingSource === "live" ? "YOUR PLAN" : "EXAMPLE MODE"}</span><button type="button" onClick={onEdit}>← Plan map</button></div></header>}
    <section className="crash-main">
      {embedded && <div className="live-view-bar"><span className="mono">{readingSource === "live" ? "YOUR PLAN" : "EXAMPLE PLAN"} · LIVE CHECKER<br />Read by {plan.ai_meta.provider} / {plan.ai_meta.model}{fallbackUsed && " · fallback provider"}</span><button type="button" className="button button-text" onClick={onEdit}>← Plan map</button></div>}
      <div className="eyebrow">03 / CRASH TEST</div>
      <div className="crash-heading"><h1>What could break this plan?</h1><span className="mono run-progress">{count?.completed ?? 0} / {meta?.total ?? "…"} checked</span></div>
      <p className="crash-count mono" aria-live="polite">{before ? <span className="history-label">BEFORE · </span> : preview && <span className="projected-label">PROJECTED · </span>}{shownCount?.line ?? "The checker is starting with one problem at a time."}</p>
      <p className="crash-intro">A tick means this case survives. A cross means the checker proved it breaks. Every mark has a reason.</p>
      {error && <div className="run-error" role="alert">{error}<button type="button" className="button button-secondary" onClick={() => setAttempt((n) => n + 1)}>Try again</button></div>}
      {plan.fix_history.length > 0 && <section className="history-controls" aria-label="Before and After comparison"><div className="history-toggle" role="group" aria-label="Results to show"><button type="button" className="button button-secondary" aria-pressed={before} disabled={!done || !history} onClick={() => { setPreview(null); setBefore(true); }}>Before</button><button type="button" className="button button-secondary" aria-pressed={!before} disabled={!done} onClick={() => setBefore(false)}>After</button></div><p className="history-view-notice mono">{before ? "Original confirmed plan. Read-only results; choose After to inspect current cases." : "Current plan, including accepted changes."}</p>{historyError && <p role="alert">{historyError} <button type="button" className="quiet-link" onClick={() => setHistoryAttempt((n) => n + 1)}>Retry comparison</button></p>}</section>}
      <div className="crash-layout"><div className="crash-left">
        {preview && <div className="preview-banner" role="status"><div><span className="section-kicker">PREVIEW {preview.eligible ? "" : "· TURNED DOWN"}</span><strong>Previewing: {preview.description}</strong><span>Changed cases are outlined.{preview.new_crosses_n > 0 ? " A starred cross is newly revealed." : ""}</span></div><button className="button button-secondary" type="button" onClick={() => setPreview(null)}>Cancel preview</button></div>}
        {shownMeta && <CrashGrid readOnly={before} meta={shownMeta} results={shown} changedIds={changedIds} newCrossIds={preview?.new_crosses} flippedIds={flippedIds} rechecking={!done} selectedId={selectedId ?? undefined} onSelect={(result) => { if (!before && !preview && done && result.state === "cross" && result.scenario_id !== selectedId) { detailOptions.current = {}; setSelectedId(result.scenario_id); setDetail(null); setDetailError(""); } }} />}
        {done && !preview && <div className="run-outcome"><div>{shownCount?.survived === meta?.total ? <><h2>Your plan survived all {meta?.total} tested scenarios.</h2><p>It survived the listed problems at the sizes you confirmed.</p></> : <><h2>{shownCount?.weak_spots} single weak spot{shownCount?.weak_spots === 1 ? "" : "s"}. {shownCount?.hidden_pairs} hidden pair{shownCount?.hidden_pairs === 1 ? "" : "s"}.</h2><p>Open a cross to see the households affected and test a change.</p></>}</div><button type="button" className="button button-secondary report-launch" onClick={() => setShowReport(true)}>See report</button></div>}
        {plan.fix_history?.length > 0 && <section className="accepted-changes"><h3>Changes accepted</h3>{plan.fix_history.map((fix, index) => <p key={fix.to_fingerprint}><span className="mono">Fix {index + 1} ({fix.origin === "yours" ? "yours" : "AI"})</span><span>{fix.description}</span></p>)}</section>}
      </div>
      {selected && !before && meta && <CasePanel plan={plan} meta={meta} result={selected} detail={detail} loading={detailLoading} running={!done || applying} error={detailError} previewId={preview?.id} remaining={broken.length} onRetry={() => setDetailAttempt((value) => value + 1)} onExtraSuggestions={(live) => { detailOptions.current = live ? {live: true} : {retry: true}; setDetailAttempt((value) => value + 1); }} onTryExample={onTryExample} onTestChange={testOwnChange} onClose={() => { setSelectedId(null); setPreview(null); }} onPreview={setPreview} onAccept={accept} onNext={nextCase} onReport={() => setShowReport(true)} />}
      </div>
    </section>
  </div>;
}
