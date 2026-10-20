import { useEffect, useRef, useState } from "react";
import { NAMES, SAMPLE_STATUS, caseTitle, sampleCellType } from "./data";
import SampleGridView from "./SampleGridView";

type Flag = boolean | "true" | "false";
type GridProps = { cell?: number | string; labels?: string; callout?: Flag; stage?: number | string; animate?: Flag; count?: Flag; legend?: Flag; readout?: Flag; selR?: number; selC?: number; onSelect?: (r: number, c: number) => void; runId?: number };
const enabled = (flag: Flag | undefined, fallback: boolean) => flag === undefined ? fallback : flag === true || flag === "true";
const COUNTS = [{ w: 1, wl: "weak spot", p: 3, pl: "hidden pairs", o: 84 }, { w: 1, wl: "weak spot", p: 1, pl: "hidden pair", o: 86 }, { w: 1, wl: "weak spot", p: 0, pl: "hidden pairs", o: 87 }, { w: 0, wl: "weak spots", p: 0, pl: "hidden pairs", o: 100 }];
function useSampleGrid(props: GridProps) {
  const root = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  const [checked, setChecked] = useState(0);
  const [hov, setHover] = useState<[number, number] | null>(null);
  const [run, setRun] = useState(0);
  const [instant, setInstant] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    let timer: ReturnType<typeof setInterval> | undefined;
    let frame = 0;
    let started = false;
    const start = () => {
      if (started) return;
      started = true;
      const skip = media.matches || !enabled(props.animate, true);
      setInstant(skip); setShown(false); setChecked(skip ? 100 : 0);
      frame = requestAnimationFrame(() => setShown(true));
      if (!skip) timer = setInterval(() => setChecked(n => { const next = Math.min(100, n + 3); if (next === 100) clearInterval(timer); return next; }), 30);
    };
    const observer = new IntersectionObserver(entries => { if (entries.some(entry => entry.isIntersecting)) { start(); observer.disconnect(); } }, { threshold: 0.15 });
    if (root.current) observer.observe(root.current);
    const update = () => { if (media.matches) { clearInterval(timer); setInstant(true); setShown(true); setChecked(100); } };
    media.addEventListener("change", update);
    return () => { observer.disconnect(); clearInterval(timer); cancelAnimationFrame(frame); media.removeEventListener("change", update); };
  }, [props.runId, props.animate, run]);
  const requestedCell = Number(props.cell ?? 34);
  const s = Number.isFinite(requestedCell) ? Math.max(16, Math.min(44, requestedCell)) : 34;
  const names = props.labels === "names", st = Number(props.stage ?? 0);
  const L = names ? 176 : 30, T = names ? 168 : 0;
  const sel = [props.selR ?? 0, props.selC ?? 0];
  const cells = [], diag = [];
  let i = 0;
  for (let r = 1; r <= 14; r++) {
    diag.push({ x: L + (r - 1) * s, y: T + (r - 1) * s });
    for (let c = 1; c <= r; c++) {
      const type = sampleCellType(r, c, st), ringIdx = ["11-3", "11-8", "13-1"].indexOf(`${r}-${c}`);
      const d = i * 9, rd = 1200 + Math.max(0, ringIdx) * 180;
      const anim = shown && !instant;
      cells.push({ r, c, type, x: L + (c - 1) * s, y: T + (r - 1) * s, aria: caseTitle(r, c) + " " + SAMPLE_STATUS[type][0], ol: sel[0] === r && sel[1] === c ? "2px solid #1A1916" : hov?.[0] === r && hov[1] === c ? "1px solid #1A1916" : "none",
        isHatch: type === "hatch", isTick: type === "ok" || type === "fixed", isCross: type === "cross" || type === "ring", isDash: type === "dash", isRing: type === "ring", isBox: type === "fixed",
        off22: shown ? 0 : 22, off32: shown ? 0 : 32, off12: shown ? 0 : 12, off79: shown ? 0 : 79, off104: shown ? 0 : 104, hop: shown ? 1 : 0,
        tr: anim ? `stroke-dashoffset 280ms cubic-bezier(.4,0,.2,1) ${d}ms` : "none", htr: anim ? `opacity 300ms ease ${d}ms` : "none", rtr: anim ? `stroke-dashoffset 620ms cubic-bezier(.6,0,.2,1) ${rd}ms` : "none",
        enter: () => setHover([r, c]), click: () => props.onSelect?.(r, c) });
      i++;
    }
  }
  const act = (n: number) => hov?.includes(n);
  const rows = Array.from({ length: 14 }, (_, index) => { const n = index + 1; return { y: T + index * s, w: names ? L - 14 : 22, j: names ? "flex-start" : "flex-end", label: names ? NAMES[index] : String(n).padStart(2, "0"), font: names ? `${act(n) ? 500 : 400} 13px 'IBM Plex Sans',sans-serif` : `${act(n) ? 500 : 400} 12px 'IBM Plex Mono',monospace`, color: act(n) ? "#1A1916" : "#57544C" }; });
  const cols = rows.map((row, index) => names ? { x: L + index * s + s * .42, y: T - 26, w: 200, a: "left", tf: "rotate(-52deg)", label: row.label, font: `400 12px 'IBM Plex Sans',sans-serif`, color: row.color } : { x: L + index * s, y: 14 * s + 6, w: s, a: "center", tf: "none", label: row.label, font: `400 12px 'IBM Plex Mono',monospace`, color: row.color });
  const seps = [{ y: T, w: L + s, c: "#1A1916" }, ...[5, 10, 12, 13].map(r => ({ y: T + r * s, w: L + r * s, c: "#DAD6CB" }))];
  const target = hov ?? (sel[0] ? sel : [11, 8]), status = SAMPLE_STATUS[sampleCellType(target[0], target[1], st)];
  const ro = { pair: caseTitle(target[0], target[1]), status: status[0], color: status[1] };
  const x = L + 7.5 * s, bw = Math.max(196, Math.round(6.4 * s)), bh = 124, bx = L + 14 * s - bw, by = 0, y1 = T + 10.5 * s, y2 = bh, len = Math.max(1, y1 - y2), cd = 2040;
  const anim = shown && !instant;
  const co = { x, y1, y2, len, off: shown ? 0 : len, bx, by, bw, bh, op: shown ? 1 : 0, ty: shown ? 0 : 8, ltr: anim ? `stroke-dashoffset 500ms ease ${cd}ms` : "none", dtr: anim ? `opacity 200ms ease ${cd}ms` : "none", btr: anim ? `opacity 360ms ease ${cd + 420}ms, transform 360ms ease ${cd + 420}ms` : "none" };
  return { root, cells, diag, rows, cols, seps, s, L, T, W: names ? L + 14 * s + 130 : L + 14 * s, H: names ? T + 14 * s : 14 * s + 26, gridH: 14 * s, k32: `scale(${s / 32})`, names, diagLabelY: T - 52,
    bandOp: hov ? 1 : 0, bandRowY: hov ? T + (hov[0] - 1) * s : T, bandRowW: hov ? L + hov[0] * s : 0, bandColX: hov ? L + (hov[1] - 1) * s : L, bandColH: hov ? 14 * s : 0,
    showCount: enabled(props.count, true), showLegend: enabled(props.legend, true), showReadout: enabled(props.readout, true), showCallout: enabled(props.callout, false) && st === 0,
    cnt: COUNTS[Math.max(0, Math.min(3, st))], checked, sentOp: checked >= 100 ? 1 : .25, ro, co, replay: () => setRun(n => n + 1), leave: () => setHover(null) };
}
export type SampleGridValues = ReturnType<typeof useSampleGrid>;
export default function SampleGrid(props: GridProps) {
  const values = useSampleGrid(props);
  return <div className="sample-grid" role="group" aria-label="Illustration of the locked example results"><SampleGridView v={values} /></div>;
}
