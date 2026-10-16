import type { RunCount, ScenarioResult } from "../types";

export function countResults(results: ScenarioResult[], total = results.length): RunCount {
  const weak_spots = results.filter((r) => r.state === "cross" && r.failures.length === 1).length;
  const hidden_pairs = results.filter((r) => r.state === "cross" && r.failures.length === 2).length;
  const dimmed = results.filter((r) => r.state === "dim").length;
  const survived = results.filter((r) => r.state === "tick").length;
  const unknown = results.filter((r) => r.state === "qmark").length;
  const pending = total - results.length;
  let line = `${total} tests: ${weak_spots} single weak spot${weak_spots === 1 ? "" : "s"}, ${hidden_pairs} hidden pair${hidden_pairs === 1 ? "" : "s"}, ${dimmed} already broken by ${weak_spots === 1 ? "the" : "a"} weak spot, ${survived} survived`;
  if (unknown) line += `, ${unknown} unknown`;
  if (pending) line += `, ${pending} to go`;
  return { total, completed: results.length, weak_spots, hidden_pairs, dimmed, survived, unknown, pending, line: line + "." };
}
