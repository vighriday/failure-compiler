import examplePlan from "../../../fixtures/example-plan.txt?raw";

export const PLAN = examplePlan.trimEnd().split("\n");
export const EXAMPLE = examplePlan;
export const TABS = [["top", "Overview"], ["plan", "Plan"], ["read", "Read"], ["test", "Crash test"], ["trust", "Trust"], ["start", "Start"]] as const;
export type LandingTab = typeof TABS[number][0];
export const STORY: { k: string; t: string; b: string; hl: number[]; tick: number[]; q: number[]; red: boolean }[] = [
  { k: "Lines 8 to 10", t: "Every job has a person and a backup.", b: "Three routes, 30 households, five volunteers, one car and one van.", hl: [8, 9, 10], tick: [8, 9, 10], q: [], red: false },
  { k: "Lines 5, 9 and 10", t: "Two routes share one van.", b: "The van gets back at 9:30. Route C can only leave after Route B is done with it.", hl: [5, 9, 10], tick: [], q: [], red: false },
  { k: "Line 3", t: "One key opens the loading bay.", b: "Joel has the only key, and he leaves at 10:30.", hl: [3], tick: [], q: [], red: false },
  { k: "Lines 13 and 15", t: "The loaders leave early.", b: "Maya leaves at 10:45. Sam drives but does not load.", hl: [13, 15], tick: [], q: [], red: false },
  { k: "Lines 8 to 10", t: "It looks done. Is it?", b: "You only find out by testing what happens when one thing, or two things, go wrong.", hl: [8, 9, 10], tick: [], q: [8, 9, 10], red: true },
];
export const STATEMENTS: [string, number][] = [["Joel has the only loading-bay key.", 3], ["Joel leaves at 10:30.", 3], ["The van is back at 9:30.", 5], ["Everything is delivered by 12:00.", 6], ["Only one vehicle loads at a time.", 12], ["Loading team: Joel, Anita, Maya.", 13], ["Maya leaves at 10:45.", 15], ["GUESS", 10]];
export const NAMES = ["Ravi absent", "Joel absent", "Anita absent", "Maya absent", "Sam absent", "Ravi leaves 90 min early", "Joel leaves 90 min early", "Anita leaves 90 min early", "Maya leaves 90 min early", "Sam leaves 90 min early", "Van back 30 min late", "Car back 30 min late", "Supply truck 45 min late", "Loading area blocked 30 min"];
const SENTENCES = ["Ravi is absent", "Joel is absent", "Anita is absent", "Maya is absent", "Sam is absent", "Ravi leaves 90 min early", "Joel leaves 90 min early", "Anita leaves 90 min early", "Maya leaves 90 min early", "Sam leaves 90 min early", "the van is back 30 min late", "the car is back 30 min late", "the supply truck is 45 min late", "the loading area is blocked for 30 min"];
const cap = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
export const caseTitle = (r: number, c: number) => r === c ? cap(SENTENCES[r - 1]) + "." : cap(SENTENCES[c - 1]) + ", and " + SENTENCES[r - 1] + ".";
export const FIXES = [{ n: 1, title: "Sam loads Route C", stats: "Fixes 2 cases. Breaks nothing new." }, { n: 2, title: "Sam backs up Route A", stats: "Fixes 1 case. Breaks nothing new." }, { n: 3, title: "Spare keys for Maya and Sam", stats: "Fixes the last case. Breaks nothing new." }];
export type SampleCellType = "hatch" | "fixed" | "cross" | "dash" | "ring" | "ok";
// These illustrate the locked example. Live results always come from the Python checker.
export function sampleCellType(r: number, c: number, stage: number): SampleCellType {
  if (r >= 6 && r <= 10 && c === r - 5) return "hatch";
  if (stage >= 3) return r === 2 && c === 2 ? "fixed" : "ok";
  if (r === 2 && c === 2) return "cross";
  if (r === 2 || c === 2) return "dash";
  if (r === 11 && (c === 3 || c === 8)) return stage >= 1 ? "fixed" : "ring";
  if (r === 13 && c === 1) return stage >= 2 ? "fixed" : "ring";
  return "ok";
}
export const SAMPLE_STATUS = {
  ok: ["Survives. The checker found a schedule.", "#1E6B47"], cross: ["Weak spot. This alone breaks the plan.", "#B23A2E"], ring: ["Hidden pair. Each is fine alone, together they break the plan.", "#B23A2E"], fixed: ["Now survives.", "#1E6B47"], dash: ["Already broken, because Joel absent breaks it alone.", "#57544C"], hatch: ["Can't happen. The same person can't be absent and leave early.", "#57544C"],
};
