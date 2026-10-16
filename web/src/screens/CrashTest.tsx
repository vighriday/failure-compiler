import { useEffect, useState } from "react";
import { streamTests } from "../api/client";
import CrashGrid from "../components/CrashGrid";
import type { PlanMap, RunCount, RunMeta, ScenarioResult } from "../types";

export default function CrashTest({ plan, onEdit }: { plan: PlanMap; onEdit: () => void }) {
  const [meta, setMeta] = useState<RunMeta | null>(null);
  const [results, setResults] = useState<ScenarioResult[]>([]);
  const [count, setCount] = useState<RunCount | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let collected: ScenarioResult[] = [];
    setMeta(null); setResults([]); setCount(null); setDone(false); setError("");
    streamTests(plan.fingerprint!, reduced, (event) => {
      if (event.type === "start") setMeta(event);
      if (event.type === "result") {
        collected = [...collected, event.result];
        if (!reduced) { setResults(collected); setCount(event.count); }
      }
      if (event.type === "complete") { setResults(collected); setCount(event.count); setDone(true); }
    }, controller.signal).catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, [plan.fingerprint, attempt]);

  return <div className="app-shell crash-shell">
    <header className="topbar"><div className="brand brand-compact"><div className="brand-name">Failure Compiler</div><div className="brand-subtitle">Crash-test a plan before Saturday does.</div></div><div className="topbar-meta"><span>EXAMPLE MODE</span><button type="button" onClick={onEdit}>← Plan map</button></div></header>
    <main className="crash-main">
      <div className="eyebrow">03 / CRASH TEST</div>
      <div className="crash-heading"><h1>What could break this plan?</h1><span className="mono run-progress">{count?.completed ?? 0} / {meta?.total ?? "…"} checked</span></div>
      <p className="crash-count mono" aria-live="polite">{count?.line ?? "The checker is starting with one problem at a time."}</p>
      <p className="crash-intro">A tick means this case survives. A cross means the checker proved it breaks. Every mark has a reason.</p>
      {error && <div className="run-error" role="alert">{error}<button type="button" className="button button-secondary" onClick={() => setAttempt((n) => n + 1)}>Try again</button></div>}
      {meta && <CrashGrid meta={meta} results={results} />}
      {done && <div className="run-outcome"><div>{count?.survived === meta?.total ? <><h2>Your plan survived all {meta?.total} tested scenarios.</h2><p>It survived the listed problems at the sizes you confirmed.</p></> : <><h2>{count?.weak_spots} single weak spot. {count?.hidden_pairs} hidden pairs.</h2><p>Open a cross to see the households affected and test a change.</p></>}</div><button type="button" className="button button-secondary" disabled title="The report is coming in the next build step.">See report</button></div>}
    </main>
  </div>;
}
