import MissingFactQuestion from "./components/MissingFactQuestion";
import { routeLabel } from "./lib/labels";
import { routeCoverage } from "./lib/coverage";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { APIError, aiStatus, confirmMap, readExample, readPlan as readLivePlan, updateMap } from "./api/client";
import type { AIProvider, ExampleReading, PlanMap, ReadingItem, RuleQuestion, ReviewState, Status } from "./types";
import FactEditor from "./components/FactEditor";
import SourceTags, { focusedSourceLine } from "./components/SourceTags";
import CrashTest from "./screens/CrashTest";
import LandingPage from "./landing/LandingPage";
import { TABS, type LandingTab } from "./landing/data";

const groups = ["People", "Vehicles", "Routes", "Times"] as const;
const presets = [15, 30, 45, 60, 90];
const problemLabels: Record<string, string> = {
  volunteer_absent: "Volunteer absent",
  volunteer_leaves_early: "Volunteer leaves early",
  vehicle_returns_late: "Vehicle returns late",
  supply_delivery_late: "Supply delivery arrives late",
  place_blocked: "Loading area blocked",
};
const problemTypes = [
  { id: "volunteer_absent", count: 5, hasSize: false },
  { id: "volunteer_leaves_early", count: 5, hasSize: true },
  { id: "vehicle_returns_late", count: 2, hasSize: true },
  { id: "supply_delivery_late", count: 1, hasSize: true },
  { id: "place_blocked", count: 1, hasSize: true },
];

function LineNumbers({ text, activeLine, onLineClick }: { text: string; activeLine?: string; onLineClick?: (line: string) => void }) {
  const lines = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const line = activeLine ? lines.current?.querySelector<HTMLElement>(`#plan-${activeLine}`) : undefined;
    const paper = lines.current?.closest<HTMLElement>(".source-paper");
    if (!line || !paper) return;
    const target = line.getBoundingClientRect(), viewport = paper.getBoundingClientRect();
    if (target.top < viewport.top) paper.scrollTop += target.top - viewport.top;
    if (target.bottom > viewport.bottom) paper.scrollTop += target.bottom - viewport.bottom;
  }, [activeLine]);
  return (
    <div ref={lines} className="line-paper" role="region" aria-label="Original plan with line numbers">
      {text.trimEnd().split("\n").map((line, index) => {
        const number = String(index + 1);
        const source = `L${number}`;
        return (
          <div className={`paper-line ${activeLine === source ? "line-active" : ""}`} id={`plan-${source}`} key={number}>
            <button className="line-number" type="button" onClick={() => onLineClick?.(source)} aria-label={`Source line ${number}`}>{number}</button>
            <span>{line || " "}</span>
          </div>
        );
      })}
    </div>
  );
}

function Tick() {
  return <svg className="tick-mark" viewBox="0 0 20 20" aria-hidden="true"><path d="m3.5 10.5 4.2 4.1L16.7 5.8" /></svg>;
}

function statusLabel(status: Status) {
  if (status === "guessed") return "guessed";
  if (status === "corrected") return "corrected by you";
  if (status === "added") return "added by you";
  if (status === "unconfirmed") return "needs your answer";
  if (status === "stale") return "Check this: a dependency changed";
  return "confirmed";
}

function App() {
  const [tab, setTab] = useState<LandingTab>(() => TABS.find(([id]) => id === location.hash.slice(1))?.[0] ?? "top");
  const [confirmed, setConfirmed] = useState(false);
  const navigate = useCallback((next: LandingTab) => {
    setTab(next);
    if (next === "read") setConfirmed(false);
    if (location.hash !== `#${next}`) history.pushState(null, "", `#${next}`);
  }, []);
  useEffect(() => {
    const back = () => { const next = TABS.find(([id]) => id === location.hash.slice(1))?.[0] ?? "top"; setTab(next); if (next === "read") setConfirmed(false); };
    window.addEventListener("popstate", back); return () => window.removeEventListener("popstate", back);
  }, []);
  const [planText, setPlanText] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [keyProvider, setKeyProvider] = useState<AIProvider>("gemini");
  const [readingPlan, setReadingPlan] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const savedExampleText = useRef<string>();
  useEffect(() => { aiStatus().then((status) => setKeyProvider(status.selected_provider ?? status.primary_provider)).catch(() => undefined); }, []);
  const [reading, setReading] = useState<ExampleReading | null>(null);
  const [items, setItems] = useState<ReadingItem[]>([]);
  const [planMap, setPlanMap] = useState<PlanMap | null>(null);
  const [questions, setQuestions] = useState<RuleQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [sizes, setSizes] = useState<Record<string, number>>({});
  const [issues, setIssues] = useState<ReviewState["issues"]>([]);
  const [activeLine, setActiveLine] = useState<string | undefined>();
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { if (showKey && tab === "start") document.getElementById("landing-key")?.focus(); }, [showKey, error, tab]);
  const [outOfDate, setOutOfDate] = useState(false);
  const [pending, setPending] = useState(0);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const activeReading = useRef<string>();
  const confirmedCount = useMemo(() => items.filter((item) => ["confirmed", "corrected", "added"].includes(item.status)).length, [items]);
  const openQuestions = questions.filter((question) => !answers[question.id]);
  const unresolvedItems = items.filter((item) => !["confirmed", "corrected", "added"].includes(item.status));
  const ready = Boolean(planMap && planText === reading?.plan_text && unresolvedItems.length === 0 && openQuestions.length === 0 && issues.length === 0 && pending === 0);
  const allProblems = problemTypes.map((problem) => ({...problem, count: !planMap ? problem.count : problem.id.startsWith("volunteer_") ? planMap.people.length : problem.id === "vehicle_returns_late" ? planMap.vehicles.length : problem.id === "place_blocked" ? planMap.places.length : planMap.deliveries.length}));
  const totalProblems = allProblems.reduce((total, problem) => total + problem.count, 0);
  const coverage = planMap ? routeCoverage(planMap) : [];
  const allJobsCovered = coverage.length > 0 && coverage.every((route) => route.complete);
  const totalScenarios = totalProblems + totalProblems * (totalProblems - 1) / 2 - (planMap?.people.length ?? 5);

  function syncReview(result: ReviewState) {
    if (result.reading_id !== activeReading.current) return;
    setPlanMap(result.plan_map); setItems(result.items); setQuestions(result.questions);
    setAnswers(result.answers); setIssues(result.issues); setSizes(result.plan_map.problem_sizes);
    setConfirmed(result.confirmed); setOutOfDate(result.out_of_date);
  }

  async function mutate(action: string, values: Record<string, unknown> = {}) {
    if (!reading) return;
    const readingId = reading.reading_id;
    setPending((count) => count + 1); setError("");
    const work = queue.current.then(() => updateMap(readingId, action, values));
    queue.current = work.catch(() => undefined);
    try { const result = await work; syncReview(result); return result; }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update the review."); }
    finally { setPending((count) => count - 1); }
  }

  async function loadExample() {
    setError("");
    try { const result = await readExample(planText); savedExampleText.current = result.plan_text; activeReading.current = undefined; setReading(result); setPlanText(result.plan_text); setPlanMap(null); setItems([]); setQuestions([]); setAnswers({}); setIssues([]); setConfirmed(false); setOutOfDate(false); return result.plan_text; }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load the example plan."); }
  }

  async function readPlan() {
    if (readingPlan || !planText.trim() || planText.length > 4000) return;
    setError("");
    setReadingPlan(true);
    try {
      const result = savedExampleText.current === planText
        ? await readExample(planText)
        : await readLivePlan(planText, apiKey.trim(), keyProvider);
      setReading(result); activeReading.current = result.reading_id; setApiKey("");
      syncReview(result as ExampleReading & ReviewState); setEditing(null); navigate("read");
      window.scrollTo({top: 0, behavior: "instant"});
    } catch (reason) {
      if (reason instanceof APIError && ["missing_key", "invalid_key"].includes(reason.code)) setShowKey(true);
      setError(reason instanceof Error ? reason.message : "Could not read this plan. Try again, or load the example plan.");
    } finally { setReadingPlan(false); }
  }

  function confirmItem(item: ReadingItem) { void mutate("confirm_item", {item_id: item.id}).then((result) => { if (result) setEditing(null); }); }
  function applyCorrection(item: ReadingItem, field: string, value: unknown) { void mutate("correct", {item_id: item.id, field, value}); }
  function bulkConfirm() { void mutate("confirm_all"); }
  function answerQuestion(question: RuleQuestion, choice: unknown) { void mutate("answer", {question_id: question.id, value: choice}); }
  function resolveRoute(routeId: string, personId: string) {
    const route = planMap?.routes.find((candidate) => candidate.id === routeId);
    const row = items.find((candidate) => candidate.entity_id === routeId);
    if (!route || !row || !planMap) return;
    const remaining = route.driver_ids.filter((id: string) => id !== personId && planMap.people.find((person) => person.id === id)?.can_drive);
    applyCorrection(row, "driver_ids", [personId, ...remaining]);
  }
  async function handleConfirm() {
    if (!reading || !ready) return;
    setError(""); setPending((count) => count + 1);
    try { syncReview(await confirmMap(reading.reading_id)); navigate("test"); window.scrollTo({top: 0, behavior: "instant"}); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "The map could not be confirmed."); }
    finally { setPending((count) => count - 1); }
  }
  const mapContent = reading && planMap ? (
    <div className="app-shell map-shell">
      <div className="map-view-heading"><p className="eyebrow">02 · READ</p><h1>Here’s what we understood.</h1><p>Check each detail against the plan. You decide what the checker will use.</p></div>
      <section className="map-layout">
        <aside className="source-column">
          <div className="source-heading">
            <div><span className="eyebrow">SOURCE PLAN</span><h2>{reading.source === "live" ? "Your plan" : "Saturday food run"}</h2></div>
            <span className="mono small">{reading.plan_text.trimEnd().split("\n").length} lines</span>
          </div>
          <div className="source-paper">
            <LineNumbers text={reading.plan_text} activeLine={activeLine} onLineClick={setActiveLine} />
          </div>
          <div className="source-legend"><span className="legend-dot" /> Hover or focus a source tag to trace its line</div>
        </aside>

        <section className="map-content" aria-label="Plan map">
          <div className="map-intro">
            {outOfDate && <div className="outdated-notice">Out of date: re-run. Confirm the edited map to test it again.</div>}
            <div className="placeholder-notice"><span className="notice-mark">i</span><span>{reading.placeholder ? "Example mode: this reading was written by hand for testing and is not real AI output." : `${reading.source === "live" ? "Live AI reading" : "Example mode: saved AI reading"}. Read by ${reading.read_by}.`}{reading.fallback_used && " The fallback provider answered."}</span></div>
          </div>

          <section className="checklist-card">
            <div className="section-kicker">THE PLAN AT A GLANCE</div>
            <h2>{allJobsCovered ? "Every job has a person and a backup" : "Some jobs still need cover"}</h2>
            <p>This is how the plan looks today.</p>
            <div className="job-checks">{coverage.map((route) => <div className="job-check" key={route.id}>{route.complete ? <Tick /> : <span className="rule-symbol" aria-label="Needs attention">!</span>}<span>{routeLabel(route.name)} · {route.vehicle ?? "No vehicle"} · {route.drivers[0] ?? "No driver"}, {route.drivers.length > 1 ? `backups ${route.drivers.slice(1).join(" and ")}` : "no backup"}{!route.hasLoader && " · no loader"}</span></div>)}</div>
          </section>

          <section className="questions-section">
            <div className="section-heading"><div><div className="section-kicker">NEEDS YOUR ANSWER</div><h2>Questions before we test</h2></div><span className={`question-count ${openQuestions.length + issues.length === 0 ? "count-neutral" : ""}`}>{openQuestions.length + issues.length} open</span></div>
            {questions.map((question) => (
              <div className={`question-card ${answers[question.id] ? "question-resolved" : ""}`} data-question-id={question.id} data-source-line={question.source_line} key={question.id} onFocus={() => question.source_line && setActiveLine(question.source_line)} onBlur={() => setActiveLine(undefined)} onMouseMove={() => question.source_line && setActiveLine(question.source_line)} onMouseLeave={() => setActiveLine(focusedSourceLine())}>
                <div className="question-icon">?</div>
                <div className="question-body"><p>{question.question_text}</p>
                  {answers[question.id]
                    ? <div className="question-answer"><span className="answer-check"><Tick /></span> Confirmed: {answers[question.id]}<button type="button" className="quiet-link" disabled={pending > 0} onClick={() => void mutate("reopen_question", {question_id: question.id})}>Change</button></div>
                    : question.kind ? <MissingFactQuestion question={question} plan={planMap} disabled={pending > 0} onAnswer={(value) => answerQuestion(question, value)} /> : <div className="choice-row">{question.choices.map((choice) => <button key={choice} type="button" className="choice-button" disabled={pending > 0} onClick={() => answerQuestion(question, choice)}>{choice}</button>)}</div>}
                </div>
              </div>
            ))}
            {issues.filter((issue) => issue.field === "driver_ids").map((issue, index) => {
              const route = planMap.routes.find((candidate) => candidate.id === issue.item_id);
              return route ? <div className="question-card rule-question" key={`${issue.item_id}-${index}`}><div className="question-icon">?</div><div className="question-body"><p>{routeLabel(route.name)} needs a driver who can drive. {issue.message}. Who drives {routeLabel(route.name)}?</p><select disabled={pending > 0} aria-label={`Choose a driver for ${routeLabel(route.name)}`} value="" onChange={(event) => resolveRoute(route.id, event.target.value)}><option value="">Choose a driver</option>{planMap.people.filter((person) => person.can_drive).map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}</select></div></div> : null;
            })}
            {issues.length > 0 && <div className="rule-summary"><span className="rule-symbol">!</span><span>{issues.map((issue) => issue.message).join(" · ")}</span></div>}
          </section>

          <section className="reading-section">
            <div className="section-heading reading-heading"><div><div className="section-kicker">THE READING</div><h2>Check each detail against the plan</h2></div></div>
            {groups.map((group) => (
              <div className="reading-group" key={group}>
                <h3>{group}</h3>
                {items.filter((item) => item.group === group).map((item) => {
                  const changedBy = item.changed_by_fix;
                  const acceptedChange = changedBy ? planMap.fix_history?.[changedBy - 1] : undefined;
                  const factLine = item.source_tags?.find((tag) => tag.kind === "fact")?.source_line ?? item.source_tags?.[0]?.source_line;
                  return (
                    <article className={`reading-row ${item.status === "unconfirmed" || item.status === "guessed" || item.status === "stale" ? "needs-confirm" : ""}`} data-item-id={item.id} data-source-line={factLine} key={item.id} tabIndex={0} onFocus={(event) => { if (event.target === event.currentTarget) setActiveLine(factLine); }} onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setActiveLine(undefined); }} onMouseMove={() => setActiveLine(factLine)} onMouseLeave={() => setActiveLine(focusedSourceLine())}>
                      <div className="reading-copy">
                        <div className="statement-line">
                          {item.status === "corrected" ? <><del>{item.original_statement}</del><span>{item.statement}</span></> : <span>{item.statement}</span>}
                        </div>
                        <SourceTags tags={item.source_tags} onHighlight={setActiveLine} />
                        {acceptedChange && <div className="fix-map-note">{acceptedChange.description}</div>}
                      </div>
                      <div className="reading-controls">
                        {changedBy ? <span className="status-chip status-fix">changed by Fix {changedBy}</span> : item.status === "confirmed" ? <span className="confirmed-mark"><Tick /> confirmed</span> : <span className={`status-chip status-${item.status}`}>{statusLabel(item.status)}</span>}
                        {item.status !== "guessed" && <button className="edit-link" type="button" onClick={() => setEditing(editing === item.id ? null : item.id)}>Correct</button>}
                        {["unconfirmed", "stale"].includes(item.status) && <button className="row-confirm" type="button" disabled={pending > 0} onClick={() => confirmItem(item)}>Confirm</button>}
                        {item.status === "guessed" && editing !== item.id && <button className="edit-link" type="button" onClick={() => setEditing(item.id)}>Answer</button>}
                      </div>
                      {editing === item.id && <FactEditor item={item} disabled={pending > 0} onCorrect={(field, value) => applyCorrection(item, field, value)} onConfirm={() => confirmItem(item)} />}
                    </article>
                  );
                })}
              </div>
            ))}
          </section>

          <section className="what-test-section">
            <div className="section-kicker">THE CRASH TEST</div>
            <h2>What we’ll test</h2>
            <p className="section-subtitle">{totalProblems} problems, tested one at a time and in pairs.</p>
            <div className="problem-list">
              {allProblems.map((problem) => <div className="problem-row" key={problem.id}>
                <div><span className="problem-name">{problemLabels[problem.id]}</span><span className="problem-count mono">{problem.count} {problem.count === 1 ? "problem" : "problems"}</span></div>
                {problem.hasSize ? <label className="size-select"><select aria-label={`${problemLabels[problem.id]} size`} value={sizes[problem.id] ?? 30} disabled={pending > 0} onChange={(event) => { void mutate("problem_size", {field: problem.id, value: Number(event.target.value)}); }}>{presets.map((value) => <option key={value} value={value}>{value} min</option>)}</select></label> : <span className="no-size mono">no duration</span>}
              </div>)}
            </div>
            <div className="problem-total"><span>Pairwise tests when you confirm</span><span className="mono">{totalScenarios} scenarios</span></div>
          </section>
          <div className="read-by mono">Read by {reading.read_by} <span>·</span> {reading.placeholder ? "PLACEHOLDER" : reading.source === "live" ? "LIVE READING" : "SAVED READING"}</div>
          {error && <p className="inline-error map-error" role="alert">{error}</p>}
          {confirmed && <div className="confirmation-result" role="status"><Tick /> Plan confirmed. Fingerprint <span className="mono">{planMap.fingerprint}</span></div>}
        </section>
      </section>
      <footer className="confirm-footer">
          <div className="footer-status"><span className="mono">{confirmedCount} of {items.length} confirmed</span><span className="footer-dot">·</span><span className="mono">{openQuestions.length + issues.length} question{openQuestions.length + issues.length === 1 ? "" : "s"} open</span></div>
        <div className="footer-actions"><button type="button" className="button button-text" disabled={pending > 0} onClick={bulkConfirm}>Confirm everything that isn’t a guess</button><button className="button button-primary" type="button" disabled={!ready || confirmed} onClick={handleConfirm}>{confirmed ? "Plan confirmed" : "Confirm plan"}<span aria-hidden="true">→</span></button></div>
      </footer>
    </div>
  ) : undefined;
  return <LandingPage
    tab={tab} onNavigate={navigate}
    text={planText} onTextChange={(value, userEdit) => { if (userEdit) savedExampleText.current = undefined; setPlanText(value); if (planMap && value !== reading?.plan_text) { setOutOfDate(true); setConfirmed(false); } }}
    apiKey={apiKey} onKeyChange={setApiKey} keyOpen={showKey} onKeyOpen={setShowKey}
    keyProvider={keyProvider} onKeyProviderChange={setKeyProvider} readingPlan={readingPlan}
    onLoadExample={loadExample} onReadPlan={readPlan} error={error}
    readContent={mapContent}
    testContent={planMap ? planMap.fingerprint && !outOfDate ? <CrashTest embedded plan={planMap} readingSource={reading?.source} fallbackUsed={reading?.fallback_used} onTryExample={() => { navigate("start"); void loadExample(); }} onPlanChange={(updated) => { void mutate("restore_fixed", {fingerprint: updated.fingerprint}); }} onEdit={() => navigate("read")} /> : <section className="confirmation-gate"><p className="eyebrow">03 · CRASH TEST</p><h1>Confirm the plan before we test it.</h1><p>{outOfDate ? "Out of date. The map changed. Review and confirm it so the checker uses your current plan." : "Every detail and open question needs your answer first."}</p><button type="button" className="button button-primary" onClick={() => navigate("read")}>Review the plan <span aria-hidden="true">→</span></button></section> : undefined}
  />;
}

export default App;
