import { useState } from "react";
import type { CellState, RunMeta, ScenarioResult } from "../types";

export function CellMark({ state }: { state: CellState }) {
  return <svg className={`cell-mark mark-${state}`} viewBox="0 0 24 24" aria-hidden="true">
    {state === "tick" && <path d="m4.5 12.5 5 5L20 6" />}
    {state === "cross" && <path d="m6 6 12 12M18 6 6 18" />}
    {state === "dim" && <path d="M6 12h12" />}
    {state === "qmark" && <><path d="M7.5 7.5C8 3 16 3 16.5 7.5c.4 3.5-4.5 3.8-4.5 7" /><path d="M12 19h.01" /></>}
  </svg>;
}

const stateWords: Record<CellState, string> = { tick: "Survives", cross: "Breaks", dim: "Already broken", qmark: "Unknown" };

export default function CrashGrid({ meta, results, onSelect, changedIds = [], newCrossIds = [], flippedIds = [], selectedId, rechecking = false, readOnly = false }: {
  meta: RunMeta; results: ScenarioResult[]; onSelect?: (result: ScenarioResult) => void;
  changedIds?: string[]; newCrossIds?: string[]; flippedIds?: string[]; selectedId?: string;
  rechecking?: boolean;
  readOnly?: boolean;
}) {
  const [active, setActive] = useState<{ row: number; col: number; id: string } | null>(null);
  const byId = new Map(results.map((result) => [result.scenario_id, result]));
  const coordinates = new Map<string, string>();
  for (const scenario of meta.scenarios) {
    const indexes = scenario.failures.map((id) => meta.problems.findIndex((p) => p.id === id));
    coordinates.set(`${Math.max(...indexes)}-${Math.min(...indexes)}`, scenario.scenario_id);
  }
  const activeResult = active ? byId.get(active.id) : undefined;
  const label = (id: string) => meta.problems.find((problem) => problem.id === id)?.label ?? id;
  const detail = (result: ScenarioResult) => result.state === "dim"
    ? `Already broken by ${label(result.dim_cause ?? "")} alone`
    : result.human_cost ?? (result.state === "qmark" ? "The checker could not prove this case. Unknown is not a pass." : "Every route finishes by the deadline.");

  return <section className="crash-grid-section" aria-label="Crash-test results">
    <div className="triangle-scroll">
      <div className="crash-triangle" style={{ gridTemplateColumns: `var(--label-width) repeat(${meta.problems.length}, var(--cell-size))` }}>
        <div className="grid-corner"><span className="mono">ONE PROBLEM</span><span>on the diagonal</span></div>
        {meta.problems.map((problem, col) => <div key={`column-${problem.id}`} style={{ gridColumn: col + 2, gridRow: 1 }} className={`axis-column ${active && (active.col === col || active.row === col) ? "axis-active" : ""}`}><span>{problem.label}</span></div>)}
        {meta.problems.map((problem, row) => <div key={`row-${problem.id}`} style={{ gridColumn: 1, gridRow: row + 2 }} className={`axis-row ${row > 0 && meta.problems[row - 1].type_id !== problem.type_id ? "type-start" : ""} ${active && (active.row === row || active.col === row) ? "axis-active" : ""}`}>{problem.label}</div>)}
        {meta.problems.flatMap((_problem, row) => meta.problems.slice(0, row + 1).map((_other, col) => {
          const id = coordinates.get(`${row}-${col}`);
          const result = id ? byId.get(id) : undefined;
          const separator = row > 0 && meta.problems[row - 1].type_id !== meta.problems[row].type_id;
          const classes = `cell-slot ${separator ? "type-start" : ""}`;
          if (!id) return <div key={`${row}-${col}`} className={`${classes} omitted-cell`} style={{ gridColumn: col + 2, gridRow: row + 2 }} title="Not tested: two problems for the same person cannot happen together." aria-label="Impossible combination omitted" />;
          if (!result) return <div key={id} className={`${classes} pending-cell`} style={{ gridColumn: col + 2, gridRow: row + 2 }} aria-label="Waiting for checker" />;
          return <button key={id} type="button" data-scenario={id} data-state={result.state} style={{ gridColumn: col + 2, gridRow: row + 2 }} className={`${classes} result-cell result-${result.state} ${row === col ? "single-cell" : ""} ${result.state === "cross" && row !== col ? "hidden-pair-cell" : ""} ${changedIds.includes(id) ? "changed-cell" : ""} ${newCrossIds.includes(id) ? "new-cross-cell" : ""} ${flippedIds.includes(id) ? "flipped-cell" : ""} ${rechecking && result.map_fingerprint !== meta.fingerprint ? "previous-run-cell" : ""} ${id === selectedId ? "selected-cell" : ""}`}
            onMouseEnter={() => setActive({ row, col, id })} onMouseLeave={() => setActive(null)} onFocus={() => setActive({ row, col, id })} onBlur={() => setActive(null)}
            onClick={() => { if (!readOnly) onSelect?.(result); }} aria-disabled={readOnly || undefined} aria-label={`${result.failures.map(label).join(" + ")}: ${stateWords[result.state]}${readOnly ? ", original result, read only" : ""}${newCrossIds.includes(id) ? ", new cross in preview" : ""}`} aria-describedby={active?.id === id ? "case-tooltip" : undefined}>
            <CellMark state={result.state} />{newCrossIds.includes(id) && <span className="new-cross-star" aria-hidden="true">*</span>}
          </button>;
        }))}
      </div>
    </div>
    <div className="grid-caption"><span>Two problems together sit below the diagonal.</span><span className="mono">{meta.total} feasible scenarios</span></div>
    <div className="case-tooltip" id="case-tooltip" role="tooltip">
      {activeResult ? <><strong>{activeResult.failures.map(label).join(" + ")}</strong><span className={`tooltip-state mark-${activeResult.state}`}>{stateWords[activeResult.state]}</span><span>{detail(activeResult)}</span></> : <span>{readOnly ? "Original confirmed results. Hover or focus a mark to trace its case." : "Hover or focus a mark to trace a case. Open a cross to see what breaks."}</span>}
    </div>
    <div className="grid-legend">{(["tick", "cross", "dim", "qmark"] as CellState[]).map((state) => <span key={state}><CellMark state={state} />{stateWords[state].toLowerCase()}</span>)}<span className="ring-key">ring = hidden pair</span></div>
  </section>;
}
