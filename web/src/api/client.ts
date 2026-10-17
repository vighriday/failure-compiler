import type { AppliedFix, CaseDetail, ExampleReading, PlanMap, ReviewState, RunCount, RunMeta, ScenarioResult } from "../types";

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail));
  }
  return payload as T;
}

export const readExample = (text: string) =>
  request<ExampleReading>("/api/read-plan", { text, example: true });

export const updateMap = (reading_id: string, action: string, values: Record<string, unknown> = {}) =>
  request<ReviewState>("/api/update-map", { reading_id, action, ...values });

export const confirmMap = (reading_id: string) =>
  request<ReviewState>("/api/confirm-map", { reading_id });

type RunEvent = ({ type: "start" } & RunMeta) | { type: "result"; result: ScenarioResult; count: RunCount } | { type: "complete"; count: RunCount };

export async function streamTests(fingerprint: string, reducedMotion: boolean, onEvent: (event: RunEvent) => void, signal: AbortSignal) {
  const response = await fetch(`/api/run-tests?map=${encodeURIComponent(fingerprint)}&reduced_motion=${reducedMotion}`, { signal });
  if (!response.ok || !response.body) throw new Error("Could not start the crash test. Confirm the map and try again.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const line = block.split("\n").find((entry) => entry.startsWith("data: "));
        if (line) onEvent(JSON.parse(line.slice(6)) as RunEvent);
      }
      if (done) break;
    }
  } finally { reader.releaseLock(); }
}

export const suggestFixes = (fingerprint: string, scenario_id: string) =>
  request<CaseDetail>("/api/suggest-fixes", { fingerprint, scenario_id });

export const applyFix = (fingerprint: string, scenario_id: string, fix_id: string) =>
  request<{ fingerprint: string; plan_map: PlanMap; applied_fix: AppliedFix }>("/api/apply-fix", { fingerprint, scenario_id, fix_id });
