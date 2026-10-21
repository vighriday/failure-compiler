import { useCallback, useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent, type MouseEvent, type UIEvent } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { EXAMPLE, FIXES, PLAN, STATEMENTS, STORY, TABS, caseTitle, sampleCellType, type LandingTab } from "./data";
import type { AIProvider } from "../types";

gsap.registerPlugin(ScrollTrigger, useGSAP);
export type LandingProps = {
  tab: LandingTab; onNavigate: (tab: LandingTab) => void;
  text: string; onTextChange: (value: string, userEdit?: boolean) => void;
  apiKey: string; onKeyChange: (value: string) => void;
  keyProvider: AIProvider; onKeyProviderChange: (value: AIProvider) => void;
  keyOpen: boolean; onKeyOpen: (open: boolean) => void;
  readingPlan: boolean;
  onLoadExample: () => Promise<string | undefined>; onReadPlan: () => void;
  error?: string;
};
type Crack = { x1: number; y1: number; x2: number; y2: number; w: number; len: number };
const pct = (minutes: number) => `${(minutes / 220 * 100).toFixed(2)}%`;
export function useLanding(props: LandingProps) {
  const { tab, text } = props;
  const [vw, setVw] = useState(Math.max(320, window.innerWidth));
  const [reduce, setReduce] = useState(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [step, setStep] = useState(0), [flow, setFlow] = useState(0), [heroIn, setHeroIn] = useState(false);
  const [mapHover, setMapHover] = useState<number[] | null>(null);
  const [answer, setAnswer] = useState<string | null>(null), [editing, setEditing] = useState(false), [corrected, setCorrected] = useState(false), [minutes, setMinutes] = useState("60"), [confirmed, setConfirmed] = useState(false);
  const [stage, setStage] = useState(0), [runId, setRunId] = useState(0), [sel, setSel] = useState<[number, number]>([11, 8]), [running, setRunning] = useState(false);
  const [cracks, setCracks] = useState<Crack[]>([]), [toast, setToast] = useState<{ x: number; y: number } | null>(null), [broke, setBroke] = useState(false);
  const [loaded, setLoaded] = useState(text === EXAMPLE), [loadingExample, setLoadingExample] = useState(false), [readFocus, setReadFocus] = useState(false), [edFocused, setEdFocused] = useState(false);
  const root = useRef<HTMLDivElement>(null), progRef = useRef<HTMLDivElement>(null), navRef = useRef<HTMLElement>(null), indRef = useRef<HTMLDivElement>(null), tabRef = useRef<HTMLElement>(null), heroRef = useRef<HTMLDivElement>(null), gridWrap = useRef<HTMLDivElement>(null), readRef = useRef<HTMLButtonElement>(null), gutRef = useRef<HTMLDivElement>(null), minRef = useRef<HTMLSelectElement>(null), shardLayer = useRef<HTMLDivElement>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const typer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const breakCleanup = useRef<(() => void) | null>(null);
  const loadingId = useRef(0);
  const { contextSafe } = useGSAP({ scope: root });
  const later = useCallback((fn: () => void, delay: number) => { const id = setTimeout(fn, delay); timers.current.push(id); return id; }, []);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const resize = () => setVw(Math.max(320, window.innerWidth)), motion = () => setReduce(media.matches);
    window.addEventListener("resize", resize); media.addEventListener("change", motion);
    return () => { window.removeEventListener("resize", resize); media.removeEventListener("change", motion); timers.current.forEach(clearTimeout); clearInterval(typer.current); loadingId.current++; breakCleanup.current?.(); };
  }, []);
  useEffect(() => {
    if (reduce) { breakCleanup.current?.(); setCracks([]); setToast(null); }
  }, [reduce]);
  useEffect(() => {
    let frame = 0;
    const observer = new ResizeObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(() => ScrollTrigger.refresh()); });
    if (root.current) observer.observe(root.current);
    return () => { observer.disconnect(); cancelAnimationFrame(frame); };
  }, []);
  const go = useCallback((id: LandingTab) => {
    breakCleanup.current?.(); setCracks([]); setToast(null); setStep(0);
    props.onNavigate(id); window.scrollTo({ top: 0, behavior: "instant" });
  }, [props.onNavigate]);
  useGSAP(() => {
    if (!tabRef.current) return;
    const match = gsap.matchMedia();
    match.add("(prefers-reduced-motion: no-preference)", () => {
      gsap.fromTo(tabRef.current, { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: .56, ease: "power2.out", clearProps: "opacity,transform" });
    });
    if (tab === "top") setHeroIn(true);
    if (tab === "plan") {
      root.current?.querySelectorAll<HTMLElement>("[data-story-step]").forEach(element => {
        ScrollTrigger.create({ trigger: element, start: "top center", end: "bottom center", onEnter: () => setStep(Number(element.dataset.storyStep)), onEnterBack: () => setStep(Number(element.dataset.storyStep)) });
      });
    }
    const progress = () => {
      const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      gsap.set(progRef.current, { scaleX: Math.min(1, window.scrollY / max) });
    };
    const scroll = ScrollTrigger.create({ start: 0, end: "max", onUpdate: progress });
    progress();
    return () => { scroll.kill(); match.revert(); };
  }, { scope: root, dependencies: [tab, reduce], revertOnUpdate: true });
  useEffect(() => {
    let active = true;
    const indicator = () => {
      const button = navRef.current?.querySelector<HTMLElement>(`[data-tabid="${tab}"]`);
      if (!active || !button || !indRef.current) return;
      indRef.current.style.left = `${button.offsetLeft}px`; indRef.current.style.width = `${button.offsetWidth}px`;
      if (navRef.current) {
        const left = Math.max(0, button.offsetLeft - (navRef.current.clientWidth - button.offsetWidth) / 2);
        navRef.current.scrollTo({ left, behavior: reduce ? "instant" : "smooth" });
      }
    };
    indicator(); document.fonts.ready.then(indicator);
    return () => { active = false; };
  }, [tab, vw, reduce]);
  const [flowRun, setFlowRun] = useState(0);
  useEffect(() => {
    if (tab !== "trust") return;
    if (reduce) { setFlow(4); return; }
    setFlow(0); let n = 0;
    const timer = setInterval(() => { n++; setFlow(n); if (n === 4) clearInterval(timer); }, 520);
    return () => clearInterval(timer);
  }, [tab, reduce, flowRun]);
  const shatter = contextSafe((event: MouseEvent<HTMLButtonElement>) => {
    const host = heroRef.current, prim = host?.querySelector<HTMLElement>('[data-shard="0"]'), layer = shardLayer.current;
    if (!host || !prim || !layer || breakCleanup.current) return;
    const rect = host.getBoundingClientRect(), W = rect.width, H = rect.height;
    const cx = event.detail ? event.clientX - rect.left : W * .4, cy = event.detail ? event.clientY - rect.top : H * .5;
    setBroke(true); setToast({ x: Math.max(12, Math.min(cx + 24, W - 270)), y: Math.max(12, Math.min(cy + 28, H - 90)) });
    if (reduce) { later(() => setToast(null), 1800); return; }
    const originalStyle = prim.getAttribute("style") ?? "";
    const angles = Array.from({ length: 9 }, (_, i) => -.3 + i * Math.PI * 2 / 9);
    const hit = (angle: number) => {
      const dx = Math.cos(angle), dy = Math.sin(angle), distances = [];
      if (dx > 0.000001) distances.push((W - cx) / dx); else if (dx < -0.000001) distances.push(-cx / dx);
      if (dy > 0.000001) distances.push((H - cy) / dy); else if (dy < -0.000001) distances.push(-cy / dy);
      const d = Math.min(...distances); return [cx + dx * d, cy + dy * d];
    };
    const fragments = angles.map((angle, index) => {
      const end = index === 8 ? angles[0] + Math.PI * 2 : angles[index + 1], pts = [[cx, cy], hit(angle)];
      [[0, 0], [W, 0], [W, H], [0, H]].map(corner => { let a = Math.atan2(corner[1] - cy, corner[0] - cx); while (a < angle) a += Math.PI * 2; return { a, corner }; }).filter(item => item.a < end).sort((a, b) => a.a - b.a).forEach(item => pts.push(item.corner));
      pts.push(hit(end));
      const element = index ? prim.cloneNode(true) as HTMLElement : prim;
      if (index) { element.dataset.shard = String(index); element.setAttribute("aria-hidden", "true"); element.inert = true; element.style.pointerEvents = "none"; element.querySelectorAll("[id]").forEach(node => node.removeAttribute("id")); layer.appendChild(element); }
      element.style.clipPath = `polygon(${pts.map(point => point.map(n => n.toFixed(1) + "px").join(" ")).join(",")})`;
      element.style.transformOrigin = `${cx}px ${cy}px`; element.style.willChange = "transform";
      return { element, dx: Math.cos((angle + end) / 2) * (24 + index * 2), dy: Math.sin((angle + end) / 2) * (24 + index * 2), rotation: (index % 2 ? 1 : -1) * 2 };
    });
    setCracks(angles.map(angle => { const end = hit(angle); return { x1: cx, y1: cy, x2: end[0], y2: end[1], len: Math.hypot(end[0] - cx, end[1] - cy), w: 1.6 }; }));
    const timeline = gsap.timeline();
    const restore = () => { timeline.kill(); prim.setAttribute("style", originalStyle); layer.replaceChildren(); gsap.set(root.current?.querySelector("[data-header]") ?? [], { clearProps: "transform" }); breakCleanup.current = null; };
    breakCleanup.current = restore;
    fragments.forEach(({ element, dx, dy, rotation }) => { timeline.to(element, { x: dx, y: dy, rotation, duration: .2, ease: "power2.out" }, .18).to(element, { x: dx * 1.12, y: dy * 1.12, duration: .7 }, .38).to(element, { x: 0, y: 0, rotation: 0, duration: .85, ease: "back.inOut(1.2)" }, 1.08); });
    timeline.to(root.current?.querySelector("[data-header]") ?? [], { keyframes: [{ x: -5, y: 2 }, { x: 4, y: -2 }, { x: -2, y: 1 }, { x: 0, y: 0 }], duration: .23 }, 0);
    timeline.call(() => { restore(); setCracks([]); setToast(null); }, [], 2.25);
  });
  const loadExample = async () => {
    clearInterval(typer.current); const request = ++loadingId.current; setLoadingExample(true); setLoaded(false);
    const result = await props.onLoadExample();
    if (request !== loadingId.current) return;
    if (!result) { setLoadingExample(false); return; }
    const lines = result.trimEnd().split("\n");
    const done = () => { props.onTextChange(result); setLoaded(true); setLoadingExample(false); setReadFocus(true); later(() => readRef.current?.focus({ preventScroll: true }), 0); };
    if (reduce) { done(); return; }
    props.onTextChange(""); let n = 0;
    typer.current = setInterval(() => { n++; props.onTextChange(lines.slice(0, n).join("\n")); if (n === lines.length) { clearInterval(typer.current); done(); } }, 55);
  };
  const tryExample = () => { go("start"); void loadExample(); };
  const save = () => { if (![45, 60, 90].includes(Number(minutes))) return; setEditing(false); setCorrected(true); };
  const onNavKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault(); const buttons = Array.from(navRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]') ?? []), index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next]?.focus(); buttons[next]?.click();
  };
  const S = STORY[step], ti = TABS.findIndex(t => t[0] === tab), nx = TABS[ti + 1], ready = corrected && !!answer;
  const cell = sampleCellType(sel[0], sel[1], stage), isPair = sel[0] !== sel[1], isBroken = cell === "cross" || cell === "ring", fixed = cell === "fixed" || cell === "ok";
  const cs = { code: isPair ? `Problems ${sel[1]} and ${sel[0]} together` : `Problem ${sel[0]} on its own`, title: caseTitle(sel[0], sel[1]), kind: "EXAMPLE PREVIEW", good: fixed, bad: isBroken, isPair: cell === "ring", together: "the plan breaks.", color: isBroken ? "#B23A2E" : fixed ? "#1E6B47" : "#57544C", headline: cell === "hatch" ? "Can't happen." : cell === "dash" ? "Already broken." : cell === "cross" ? "30 households not delivered." : cell === "ring" ? sel[0] === 13 ? "10 households not delivered." : "8 households not delivered." : stage ? "Now survives." : "Survives.", hasWhy: ["hatch", "dash", "cross"].includes(cell), why: cell === "hatch" ? "The same person cannot be absent and leave early. This pair is not tested." : "Joel has the only loading-area key. Nobody can open the loading area without him.", hasTimeline: sel[0] === 11 && (sel[1] === 8 || sel[1] === 3) };
  const bar = (s: number, e: number, label: string, load = false, show = true) => ({ l: pct(s), w: pct(Math.max(0, e - s)), top: load ? "18px" : "28px", h: load ? "6px" : "20px", bg: load ? "#CFC9BB" : "#4D4F45", op: show ? 1 : 0, label, ltop: load ? "2px" : "31px", lc: load ? "#57544C" : "#F6F4EE", pl: load ? "0" : "8px" });
  const tl = [{ route: "Route A", veh: "car", msgOp: 0, bars: [bar(0, 10, "Load", true), bar(45, 105, "Ravi")] }, { route: "Route B", veh: "van", msgOp: 0, bars: [bar(60, 70, "Load", true), bar(70, 105, "Sam")] }, { route: "Route C", veh: "van", msgOp: stage >= 1 ? 0 : 1, bars: [bar(105, 115, "Load: Sam", true, stage >= 1), bar(115, 175, "Ravi", false, stage >= 1)] }];
  const FLOW = [["YOU", "Write the plan", "In plain words, the way you’d text your team."], ["AI", "Reads it", "Finds the people, vehicles, routes and times. Asks you when unsure."], ["CHECKER", "Tests it", "Runs 100 tests. No AI here, just rules and maths."], ["CHECKER", "Shows the proof", "Every result comes with the exact case behind it."]];
  const lineCount = text ? text.split("\n").length : 0, noText = !text.trim() || text.length > 4000 || loadingExample || props.readingPlan;
  return {
    tab_top: tab === "top", tab_plan: tab === "plan", tab_read: tab === "read", tab_test: tab === "test", tab_trust: tab === "trust", tab_start: tab === "start",
    root, progRef, navRef, indRef, tabRef, heroRef, gridWrap, readRef, gutRef, minRef, shardLayer, onNavKeyDown,
    heroCell: vw >= 1380 ? 32 : vw >= 1120 ? 28 : Math.min(26, Math.floor((vw - 70) / 14)), testCell: vw >= 1360 ? 28 : Math.min(26, Math.floor((vw - 70) / 14)), testLabels: vw >= 1360 ? "names" : "numbers",
    tabs: TABS.map(([id, label]) => ({ id, label, sel: (tab === id ? "true" : "false") as "true" | "false", color: tab === id ? "#1A1916" : "#57544C", go: () => go(id) })),
    goTop: () => go("top"), goTest: () => go("test"), goRead: () => go("read"), tryExample, hasNext: !!nx, nextTitle: nx?.[1] ?? "", goNext: () => nx && go(nx[0]),
    heroT: heroIn ? "0%" : "110%", heroOp: heroIn ? 1 : 0, penOff: heroIn ? 0 : 260, hintOp: heroIn && !broke ? 1 : 0, cracks, hasToast: !!toast, toast: toast ?? { x: 0, y: 0 }, shatter,
    storyLines: PLAN.map((t, i) => ({ n: i + 1, text: t, bg: S.hl.includes(i + 1) ? "#ECE9E0" : "transparent", bl: S.hl.includes(i + 1) ? S.red ? "#B23A2E" : "#1A1916" : "transparent", color: S.hl.includes(i + 1) ? "#1A1916" : "#57544C", tick: S.tick.includes(i + 1), q: S.q.includes(i + 1) })),
    story: STORY.map((s, i) => ({ ...s, i, tc: s.red ? "#B23A2E" : "#1A1916", op: i === step ? 1 : .95 })),
    mapLines: PLAN.map((t, i) => ({ n: i + 1, text: t, bg: mapHover?.includes(i + 1) ? "#E9E5D9" : "transparent", bl: mapHover?.includes(i + 1) ? "#1A1916" : "transparent", tc: mapHover?.length && !mapHover.includes(i + 1) ? "#57544C" : "#1A1916", nc: mapHover?.includes(i + 1) ? "#1A1916" : "#57544C" })),
    stm: STATEMENTS.map(([t, l]) => ({ t, l, enter: () => setMapHover([l]), bg: mapHover?.includes(l) ? "#EFECE4" : "transparent", isPlain: t !== "GUESS", isGuess: t === "GUESS" && !editing && !corrected, isEdit: t === "GUESS" && editing, isFixed: t === "GUESS" && corrected })),
    mapHint: mapHover?.length ? "line " + mapHover.join(", ") : `${PLAN.length} lines`, mapLeave: () => setMapHover(null), hoverQ: () => setMapHover([13]), qOpen: !answer, qDone: !!answer, answerText: answer,
    answerCar: () => setAnswer("Only his car"), answerVan: () => setAnswer("The van too"), reopenQ: () => setAnswer(null),
    qBorder: answer ? "#CFE0D3" : "#D9B45A", qBg: answer ? "#F4F8F4" : "#FBF6E9", qTag: answer ? "#1E6B47" : "#8A6410", qKicker: answer ? "ANSWERED" : "WE NEED ONE ANSWER",
    minutes, onMinutes: (event: ChangeEvent<HTMLSelectElement>) => setMinutes(event.target.value), minKey: (event: KeyboardEvent<HTMLSelectElement>) => { if (event.key === "Enter") save(); }, startEdit: () => { setEditing(true); later(() => minRef.current?.focus(), 0); }, saveCorrection: save,
    confText: `${corrected ? 8 : 7} of 8 sample details checked, ${answer ? "no questions left" : "1 question left"}`, notReadyS: ready ? "false" : "true", confBg: ready ? "#1E6B47" : "#E4E0D6", confColor: ready ? "#F6F4EE" : "#57544C", confCursor: ready ? "pointer" : "not-allowed", confLabel: confirmed ? "Confirmed" : "Confirm sample", confirmPlan: () => { if (ready) { setConfirmed(true); go("test"); } },
    stage, runId, selR: sel[0], selC: sel[1], selectCell: contextSafe((r: number, c: number) => { setSel([r, c]); if (!reduce) gsap.fromTo(root.current?.querySelector("[data-case]") ?? [], { x: sampleCellType(r, c, stage) === "ring" ? -7 : 0, opacity: .5 }, { x: 0, opacity: 1, duration: .38, clearProps: "transform,opacity" }); }), cs, tl, axis: [["9:00", 0], ["10:00", 60], ["11:00", 120], ["12:30", 210]].map(([t, m]) => ({ t, x: pct(Number(m)) })),
    hasFix: stage < 3, fix: FIXES[Math.min(2, stage)], fixBtn: running ? "Showing the example change…" : "Show this example fix", acceptFix: contextSafe(() => { if (running || stage >= 3) return; setRunning(true); if (!reduce && gridWrap.current) gsap.fromTo(gridWrap.current.querySelector("[data-scan]"), { y: 0, opacity: 1 }, { y: gridWrap.current.offsetHeight + 64, duration: .82, ease: "power2.inOut", opacity: 0 }); later(() => { setStage(n => Math.min(3, n + 1)); setRunId(n => n + 1); setRunning(false); }, reduce ? 0 : 820); }),
    allClear: stage >= 3, resetFixes: () => { setStage(0); setRunId(n => n + 1); setSel([11, 8]); },
    flow: FLOW.map(([k, t, b], i) => ({ k, t, b, op: flow > i ? 1 : .95, ty: flow > i ? "0px" : "12px", dot: flow > i ? i >= 2 ? "#1E6B47" : "#1A1916" : "#F6F4EE", tc: i >= 2 ? "#1E6B47" : "#57544C" })), flowW: ["0%", "12.5%", "37.5%", "62.5%", "100%"][flow], replayFlow: () => setFlowRun(n => n + 1),
    outcomes: [{ isBreak: true, isOk: false, isQ: false, t: "Breaks", c: "#B23A2E", b: "We show you the exact case, the timeline and why.", br: "1px solid #DAD6CB", pl: "0px" }, { isBreak: false, isOk: true, isQ: false, t: "Survives", c: "#1E6B47", b: "Nothing failed in our tests. That’s not a promise about the real day.", br: "1px solid #DAD6CB", pl: "28px" }, { isBreak: false, isOk: false, isQ: true, t: "Unknown", c: "#8A6410", b: "Something was unclear, so we say so. It never counts as a pass.", br: "none", pl: "28px" }].map(o => ({ ...o, bg: "transparent", enter: () => {} })),
    text, onText: (event: ChangeEvent<HTMLTextAreaElement>) => { clearInterval(typer.current); loadingId.current++; setLoadingExample(false); props.onTextChange(event.target.value, true); setLoaded(false); }, onTaScroll: (event: UIEvent<HTMLTextAreaElement>) => { if (gutRef.current) gutRef.current.style.transform = `translateY(${-event.currentTarget.scrollTop}px)`; }, edFocus: () => setEdFocused(true), edBlur: () => setEdFocused(false), edBorder: edFocused ? "#1A1916" : "#CFC9BB",
    lineCount, gutter: Array.from({ length: Math.max(17, lineCount) }, (_, i) => ({ n: i + 1, c: "#57544C" })), charText: text.length.toLocaleString("en-US"), charColor: text.length >= 4000 ? "#B23A2E" : text.length >= 3500 ? "#8A6410" : "#57544C", noTextS: noText ? "true" : "false", readBg: noText ? "#E4E0D6" : "#1E6B47", readColor: noText ? "#57544C" : "#F6F4EE", readCursor: noText ? "not-allowed" : "pointer", readOutline: readFocus && !noText ? "2px solid #1A1916" : "none", readPlan: () => { if (!noText) { setReadFocus(false); props.onReadPlan(); } },
    loadExample, exampleLoaded: loaded, exampleLabel: loadingExample ? "Loading example…" : loaded ? "Example plan loaded" : "Load the example plan", toggleKey: () => props.onKeyOpen(!props.keyOpen), keyOpen: props.keyOpen, keyRot: props.keyOpen ? "90deg" : "0deg", apiKey: props.apiKey, onKey: (event: ChangeEvent<HTMLInputElement>) => props.onKeyChange(event.target.value), keyProvider: props.keyProvider, onKeyProvider: (event: ChangeEvent<HTMLSelectElement>) => props.onKeyProviderChange(event.target.value as AIProvider), readingPlan: props.readingPlan, error: props.error,
  };
}
export type LandingValues = ReturnType<typeof useLanding>;
