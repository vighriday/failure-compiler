import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { confirmMap, readExample, validateMap } from "./api/client";
import type { ExampleReading, PlanMap, ReadingItem, RuleQuestion, Status } from "./types";
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
const allProblems = [
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
    <div ref={lines} className="line-paper" aria-label="Original plan with line numbers">
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

function statusLabel(status: Status, changedName = "Ravi") {
  if (status === "guessed") return "guessed";
  if (status === "corrected") return "corrected by you";
  if (status === "added") return "added by you";
  if (status === "unconfirmed") return "needs your answer";
  if (status === "stale") return `Check this: ${changedName} changed`;
  return "confirmed";
}

function initialStatement(item: ReadingItem) {
  if (item.id === "route-c-loading") return "Route C's drive takes about an hour.";
  return item.statement;
}

function correctedStatement(item: ReadingItem, planMap: PlanMap) {
  if (item.id === "ravi-driver") return planMap.people.find((person) => person.id === item.entity_id)?.can_drive ? "Ravi can drive." : "Ravi cannot drive.";
  if (item.id === "route-c-loading") return `Route C's drive takes ${item.value ?? 60} minutes.`;
  if (item.entity_type === "route") {
    const route = planMap.routes.find((candidate) => candidate.id === item.entity_id);
    if (!route) return item.statement;
    const driverNames = route.driver_ids.map((id: string) => planMap.people.find((person: Record<string, any>) => person.id === id)?.name).filter(Boolean);
    const vehicleName = planMap.vehicles.find((vehicle) => vehicle.id === route.vehicle_id)?.name.toLowerCase() ?? "vehicle";
    const backups = driverNames.slice(1);
    const loaderNames = route.loader_ids.map((id: string) => planMap.people.find((person: Record<string, any>) => person.id === id)?.name).filter(Boolean);
    return `Route ${route.name} serves ${route.households} households by ${vehicleName}; ${driverNames[0]} drives${backups.length ? `, with ${backups.join(" and ")} as backups` : ""}. Loading cover: ${loaderNames.join(", ")}.`;
  }
  return item.statement;
}

function App() {
  const [tab, setTab] = useState<LandingTab>(() => TABS.find(([id]) => id === location.hash.slice(1))?.[0] ?? "top");
  const navigate = useCallback((next: LandingTab) => { setTab(next); if (location.hash !== `#${next}`) history.pushState(null, "", `#${next}`); }, []);
  useEffect(() => { const back = () => setTab(TABS.find(([id]) => id === location.hash.slice(1))?.[0] ?? "top"); window.addEventListener("popstate", back); return () => window.removeEventListener("popstate", back); }, []);
  const [screen, setScreen] = useState<"paste" | "map" | "grid">("paste");
  const [planText, setPlanText] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [reading, setReading] = useState<ExampleReading | null>(null);
  const [items, setItems] = useState<ReadingItem[]>([]);
  const [planMap, setPlanMap] = useState<PlanMap | null>(null);
  const [questions, setQuestions] = useState<RuleQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [sizes, setSizes] = useState<Record<string, number>>({});
  const [issues, setIssues] = useState<Array<{ item_id: string; message: string }>>([]);
  const [activeLine, setActiveLine] = useState<string | undefined>();
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [outOfDate, setOutOfDate] = useState(false);

  const confirmedCount = useMemo(() => items.filter((item) => ["confirmed", "corrected", "added"].includes(item.status)).length, [items]);
  const openQuestions = questions.filter((question) => !answers[question.id]);
  const unresolvedItems = items.filter((item) => !["confirmed", "corrected", "added"].includes(item.status));
  const ready = Boolean(planMap && unresolvedItems.length === 0 && openQuestions.length === 0 && issues.length === 0);

  useEffect(() => {
    if (!planMap || screen !== "map") return;
    const timer = window.setTimeout(() => {
      validateMap(planMap, items, questions, answers).then((result) => setIssues(result.issues)).catch((reason: Error) => setError(reason.message));
    }, 150);
    return () => window.clearTimeout(timer);
  }, [planMap, items, questions, answers, screen]);

  async function loadExample() {
    setError("");
    try {
      const result = await readExample(planText);
      setReading(result);
      setPlanText(result.plan_text);
      return result.plan_text;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the example plan.");
    }
  }

  async function readPlan() {
    setError("");
    if (!reading || planText !== reading.plan_text) {
      if (!apiKey.trim()) {
        setShowKey(true);
        setError("Add your own AI key to read a pasted plan. Or load the saved example reading.");
      } else {
        setError("Live AI reading is not available yet. Load the example plan for now.");
      }
      return;
    }
    try {
      const result = reading;
      setReading(result);
      setPlanMap(result.plan_map);
      setItems(result.items);
      setQuestions(result.questions);
      setSizes(result.problem_types);
      setAnswers({});
      setConfirmed(false);
      setOutOfDate(false);
      setScreen("map");
      navigate("read");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the example reading.");
    }
  }

  function planEntity(item: ReadingItem, map: PlanMap) {
    if (item.entity_type === "plan") return map as unknown as Record<string, any>;
    const collection: Record<string, keyof PlanMap> = { person: "people", vehicle: "vehicles", place: "places", delivery: "deliveries", route: "routes" };
    const key = collection[item.entity_type];
    if (!key) return undefined;
    const entities = map[key] as Array<Record<string, any>>;
    return entities.find((entity) => entity.id === item.entity_id);
  }

  function updateMapItem(item: ReadingItem, status: Status, value?: number | boolean) {
    if (value !== undefined && planMap && planEntity(item, planMap)?.[item.field] !== value) {
      setOutOfDate(true);
      setConfirmed(false);
    }
    setPlanMap((current) => {
      if (!current) return current;
      const updated = structuredClone(current);
      const target = planEntity(item, updated) as Record<string, any> | undefined;
      if (!target) return current;
      if (value !== undefined && item.field !== "loading" && item.field !== "loading_team" && item.field !== "route") target[item.field] = value;
      if (item.entity_type !== "plan") target.status = status === "guessed" || status === "unconfirmed" ? "unconfirmed" : status;
      return updated;
    });
  }

  function confirmItem(item: ReadingItem) {
    const next = items.map((candidate) => candidate.id === item.id ? { ...candidate, status: "confirmed" as const } : candidate);
    setItems(next);
    updateMapItem(item, "confirmed");
  }

  function applyCorrection(item: ReadingItem, value: number | boolean) {
    updateMapItem(item, "corrected", value);
    const next = items.map((candidate) => candidate.id === item.id
      ? { ...candidate, status: "corrected" as const, value }
      : candidate);
    setItems(next);
    setEditing(null);
  }

  function changeDriverAbility(item: ReadingItem, value: boolean) {
    if (!planMap) return;
    const previous = planMap.people.find((person) => person.id === item.entity_id)?.can_drive;
    const status: Status = value === reading?.plan_map.people.find((person) => person.id === item.entity_id)?.can_drive ? "confirmed" : "corrected";
    updateMapItem(item, status, value);
    if (previous === value) {
      setItems((current) => current.map((candidate) => candidate.id === item.id ? { ...candidate, status, value } : candidate));
      setEditing(null);
      return;
    }
    if (!value) {
      const routeItems = new Set(planMap.routes.filter((route) => route.driver_ids.includes(item.entity_id)).map((route) => `route-${route.name.toLowerCase()}`));
      setItems((current) => current.map((candidate) => candidate.id === item.id
        ? { ...candidate, status, value }
        : routeItems.has(candidate.id) ? { ...candidate, status: "stale" as const } : candidate));
      setPlanMap((current) => {
        if (!current) return current;
        const updated = structuredClone(current);
        for (const route of updated.routes.filter((candidate) => candidate.driver_ids.includes(item.entity_id))) route.status = "unconfirmed";
        return updated;
      });
    } else {
      setItems((current) => current.map((candidate) => candidate.id === item.id ? { ...candidate, status, value } : candidate));
    }
    setEditing(null);
  }

  function resolveRoute(routeId: string, personId: string) {
    if (!planMap) return;
    const updated = structuredClone(planMap);
    const route = updated.routes.find((candidate) => candidate.id === routeId);
    if (!route) return;
    route.driver_ids = [personId, ...route.driver_ids.filter((id: string) => id !== "person-ravi" && id !== personId)];
    route.status = "corrected";
    setOutOfDate(true);
    setPlanMap(updated);
    const routeItemId = `route-${route.name.toLowerCase()}`;
    setItems((current) => current.map((item) => item.id === routeItemId ? { ...item, status: "corrected" } : item));
  }

  async function handleConfirm() {
    if (!planMap || !ready) return;
    setError("");
    try {
      const result = await confirmMap(planMap, items, questions, answers);
      setPlanMap((current) => current ? { ...current, fingerprint: result.fingerprint } : current);
      setConfirmed(true);
      setOutOfDate(false);
      setScreen("grid");
      navigate("test");
      window.scrollTo({ top: 0, behavior: "instant" });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The map could not be confirmed.");
    }
  }

  function bulkConfirm() {
    const toConfirm = items.filter((item) => item.status === "unconfirmed" && !item.guessed);
    setItems((current) => current.map((item) => item.status === "unconfirmed" && !item.guessed ? { ...item, status: "confirmed" } : item));
    for (const item of toConfirm) updateMapItem(item, "confirmed");
  }

  function answerQuestion(question: RuleQuestion, choice: string) {
    setAnswers((current) => ({ ...current, [question.id]: choice }));
    if (question.id !== "ravi-van-loading-question" || !planMap) return;
    const updated = structuredClone(planMap);
    const changedRoutes = new Set<string>();
    for (const route of updated.routes) {
      const baseline = reading?.plan_map.routes.find((candidate) => candidate.id === route.id);
      const shouldLoad = choice === "The van too" || Boolean(baseline?.loader_ids.includes("person-ravi"));
      if (route.vehicle_id === "vehicle-van" && route.loader_ids.includes("person-ravi") !== shouldLoad) {
        route.loader_ids = shouldLoad ? [...route.loader_ids, "person-ravi"] : route.loader_ids.filter((id: string) => id !== "person-ravi");
        route.status = "corrected";
        changedRoutes.add(route.id);
      }
    }
    if (changedRoutes.size === 0) return;
    updated.fingerprint = null;
    setOutOfDate(true);
    setPlanMap(updated);
    setItems((current) => current.map((item) => item.field === "route" && changedRoutes.has(item.entity_id) ? { ...item, status: "corrected" } : item));
  }

  const mapContent = reading && planMap ? (
    <div className="app-shell map-shell">
      <div className="map-view-heading"><p className="eyebrow">02 · READ</p><h1>Here’s what we understood.</h1><p>Check each detail against the plan. You decide what the checker will use.</p></div>
      <section className="map-layout">
        <aside className="source-column">
          <div className="source-heading">
            <div><span className="eyebrow">SOURCE PLAN</span><h2>Saturday food run</h2></div>
            <span className="mono small">{reading.plan_text.trimEnd().split("\n").length} lines</span>
          </div>
          <div className="source-paper">
            <LineNumbers text={reading.plan_text} activeLine={activeLine} onLineClick={setActiveLine} />
          </div>
          <div className="source-legend"><span className="legend-dot" /> Hover a statement to trace its source</div>
        </aside>

        <section className="map-content" aria-label="Plan map">
          <div className="map-intro">
            {outOfDate && <div className="outdated-notice">Out of date: re-run. Confirm the edited map to test it again.</div>}
            <div className="placeholder-notice"><span className="notice-mark">i</span><span>Example mode: this reading was written by hand for testing and is not real AI output.</span></div>
          </div>

          <section className="checklist-card">
            <div className="section-kicker">THE PLAN AT A GLANCE</div>
            <h2>Every job has a person and a backup</h2>
            <p>This is how the plan looks today.</p>
            <div className="job-checks">{planMap.routes.map((route) => { const vehicle = planMap.vehicles.find((candidate) => candidate.id === route.vehicle_id)?.name.toLowerCase(); const drivers = route.driver_ids.map((id: string) => planMap.people.find((person: Record<string, any>) => person.id === id)?.name).filter(Boolean); return <div className="job-check" key={route.id}><Tick /><span>Route {route.name} · {vehicle} · {drivers[0]}, backups {drivers.slice(1).join(" and ")}</span></div>; })}</div>
          </section>

          <section className="questions-section">
            <div className="section-heading"><div><div className="section-kicker">NEEDS YOUR ANSWER</div><h2>One question before we test</h2></div><span className={`question-count ${openQuestions.length + issues.length === 0 ? "count-neutral" : ""}`}>{openQuestions.length + issues.length} open</span></div>
            {questions.map((question) => (
              <div className={`question-card ${answers[question.id] ? "question-resolved" : ""}`} key={question.id} onFocus={() => question.source_line && setActiveLine(question.source_line)} onBlur={() => setActiveLine(undefined)} onMouseEnter={() => question.source_line && setActiveLine(question.source_line)} onMouseLeave={() => setActiveLine(undefined)}>
                <div className="question-icon">?</div>
                <div className="question-body"><p>{question.question_text}</p>
                  {answers[question.id]
                    ? <div className="question-answer"><span className="answer-check"><Tick /></span> Confirmed: {answers[question.id]}<button type="button" className="quiet-link" onClick={() => { setAnswers((current) => { const next = { ...current }; delete next[question.id]; return next; }); setConfirmed(false); setOutOfDate(true); }}>Change</button></div>
                    : <div className="choice-row">{question.choices.map((choice) => <button key={choice} type="button" className="choice-button" onClick={() => answerQuestion(question, choice)}>{choice}</button>)}</div>}
                </div>
              </div>
            ))}
            {planMap.people.find((person) => person.id === "person-ravi")?.can_drive === false && planMap.routes.filter((route) => route.driver_ids.includes("person-ravi")).map((route) => {
              const routeItemId = `route-${route.name.toLowerCase()}`;
              const routeItem = items.find((item) => item.id === routeItemId);
              const candidates = route.driver_ids.filter((id: string) => id !== "person-ravi" && planMap.people.find((person: Record<string, any>) => person.id === id)?.can_drive);
              return <div className="question-card rule-question" key={route.id}><div className="question-icon">?</div><div className="question-body"><p>{route.name === "C" ? "Route C needs a driver who can drive. Ravi can't drive any more. Who drives Route C?" : `${route.name} needs a driver who can drive. Ravi can't drive any more. Who drives Route ${route.name}?`}</p><select aria-label={`Choose a driver for route ${route.name}`} value="" onChange={(event) => resolveRoute(route.id, event.target.value)}><option value="">Choose a driver</option>{candidates.map((id: string) => <option key={id} value={id}>{planMap.people.find((person: Record<string, any>) => person.id === id)?.name}</option>)}</select>{routeItem && <span className={`status-chip status-${routeItem.status}`}>{statusLabel(routeItem.status)}</span>}</div></div>;
            })}
            {issues.length > 0 && <div className="rule-summary"><span className="rule-symbol">!</span><span>{issues.map((issue) => issue.message).join(" · ")}</span></div>}
          </section>

          <section className="reading-section">
            <div className="section-heading reading-heading"><div><div className="section-kicker">THE READING</div><h2>Check each detail against the plan</h2></div></div>
            {groups.map((group) => (
              <div className="reading-group" key={group}>
                <h3>{group}</h3>
                {items.filter((item) => item.group === group).map((item) => {
                  const isRouteCDuration = item.id === "route-c-loading";
                  const isRaviDriver = item.id === "ravi-driver";
                  const changedText = item.status === "corrected" ? correctedStatement(item, planMap) : item.statement;
                  const changedBy = planEntity(item, planMap)?.changed_by_fix as number | undefined;
                  const acceptedChange = changedBy ? planMap.fix_history?.[changedBy - 1] : undefined;
                  return (
                    <article className={`reading-row ${item.status === "unconfirmed" || item.status === "guessed" || item.status === "stale" ? "needs-confirm" : ""}`} data-item-id={item.id} key={item.id} tabIndex={0} onFocus={() => setActiveLine(item.source_line)} onBlur={() => setActiveLine(undefined)} onMouseEnter={() => setActiveLine(item.source_line)} onMouseLeave={() => setActiveLine(undefined)}>
                      <div className="reading-copy">
                        <div className="statement-line">
                          {item.status === "corrected" ? <><del>{initialStatement(item)}</del><span>{changedText}</span></> : <span>{item.statement}</span>}
                        </div>
                        <button type="button" className="source-tag" onClick={() => setActiveLine(item.source_line)}>{item.source_line}</button>
                        {acceptedChange && <div className="fix-map-note">{acceptedChange.description}</div>}
                      </div>
                      <div className="reading-controls">
                        {changedBy ? <span className="status-chip status-fix">changed by Fix {changedBy}</span> : item.status === "confirmed" ? <span className="confirmed-mark"><Tick /> confirmed</span> : <span className={`status-chip status-${item.status}`}>{statusLabel(item.status)}</span>}
                        {["confirmed", "corrected", "added"].includes(item.status) && (isRouteCDuration || isRaviDriver) && <button className="edit-link" type="button" onClick={() => setEditing(editing === item.id ? null : item.id)}>Correct</button>}
                        {["unconfirmed", "stale"].includes(item.status) && <button className="row-confirm" type="button" onClick={() => confirmItem(item)}>Confirm</button>}
                        {item.status === "guessed" && editing !== item.id && <button className="edit-link" type="button" onClick={() => setEditing(item.id)}>Answer</button>}
                      </div>
                      {editing === item.id && (isRouteCDuration || isRaviDriver) && <div className="inline-editor">
                        <label>{item.guessed ? "Answer this guess" : "Choose the correct value"}
                          <select aria-label={`Correction for ${item.statement}`} value={item.status === "corrected" ? String(item.value) : ""} onChange={(event) => {
                            if (isRouteCDuration) applyCorrection(item, Number(event.target.value));
                            else changeDriverAbility(item, event.target.value === "true");
                          }}>
                            <option value="">Choose a value</option>
                            {isRouteCDuration ? (item.choices ?? [45, 60, 90]).map((value) => <option key={value} value={value}>{value} minutes</option>) : <><option value="true">Yes, Ravi can drive</option><option value="false">No, Ravi cannot drive</option></>}
                          </select>
                        </label>
                        {item.status === "guessed" && <button className="quiet-link" type="button" onClick={() => confirmItem(item)}>Keep this guess</button>}
                      </div>}
                    </article>
                  );
                })}
              </div>
            ))}
          </section>

          <section className="what-test-section">
            <div className="section-kicker">THE CRASH TEST</div>
            <h2>What we’ll test</h2>
            <p className="section-subtitle">14 problems, tested one at a time and in pairs.</p>
            <div className="problem-list">
              {allProblems.map((problem) => <div className="problem-row" key={problem.id}>
                <div><span className="problem-name">{problemLabels[problem.id]}</span><span className="problem-count mono">{problem.count} {problem.count === 1 ? "problem" : "problems"}</span></div>
                {problem.hasSize ? <label className="size-select"><select aria-label={`${problemLabels[problem.id]} size`} value={sizes[problem.id] ?? 30} onChange={(event) => {
                  const value = Number(event.target.value);
                  setOutOfDate(true);
                  setSizes((current) => ({ ...current, [problem.id]: value }));
                  setPlanMap((current) => current ? { ...current, problem_sizes: { ...current.problem_sizes, [problem.id]: value } } : current);
                }}>{presets.map((value) => <option key={value} value={value}>{value} min</option>)}</select></label> : <span className="no-size mono">no duration</span>}
              </div>)}
            </div>
            <div className="problem-total"><span>Pairwise tests when you confirm</span><span className="mono">100 scenarios</span></div>
          </section>
          <div className="read-by mono">READ BY · {reading.read_by} <span>·</span> {reading.placeholder ? "PLACEHOLDER" : "SAVED READING"}</div>
          {error && <p className="inline-error map-error" role="alert">{error}</p>}
          {confirmed && <div className="confirmation-result" role="status"><Tick /> Plan confirmed. Fingerprint <span className="mono">{planMap.fingerprint}</span></div>}
        </section>
      </section>
      <footer className="confirm-footer">
          <div className="footer-status"><span className="mono">{confirmedCount} of {items.length} confirmed</span><span className="footer-dot">·</span><span className="mono">{openQuestions.length + issues.length} question{openQuestions.length + issues.length === 1 ? "" : "s"} open</span></div>
        <div className="footer-actions"><button type="button" className="button button-text" onClick={bulkConfirm}>Confirm everything that isn’t a guess</button><button className="button button-primary" type="button" disabled={!ready || confirmed} onClick={handleConfirm}>{confirmed ? "Plan confirmed" : "Confirm plan"}<span aria-hidden="true">→</span></button></div>
      </footer>
    </div>
  ) : undefined;
  return <LandingPage
    tab={tab} onNavigate={navigate}
    text={planText} onTextChange={(value) => { setPlanText(value); if (planMap && value !== reading?.plan_text) { setOutOfDate(true); setConfirmed(false); } }}
    apiKey={apiKey} onKeyChange={setApiKey} keyOpen={showKey} onKeyOpen={setShowKey}
    onLoadExample={loadExample} onReadPlan={readPlan} error={error}
    readContent={mapContent}
    testContent={planMap ? planMap.fingerprint && !outOfDate ? <CrashTest embedded plan={planMap} onPlanChange={setPlanMap} onEdit={() => { setScreen("map"); setConfirmed(false); navigate("read"); }} /> : <section className="confirmation-gate"><p className="eyebrow">03 · CRASH TEST</p><h1>Confirm the plan before we test it.</h1><p>{outOfDate ? "The map changed. Review and confirm it so the checker uses your current plan." : "Every detail and open question needs your answer first."}</p><button type="button" className="button button-primary" onClick={() => navigate("read")}>Review the plan <span aria-hidden="true">→</span></button></section> : undefined}
  />;
}

export default App;
