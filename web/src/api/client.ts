import type { ExampleReading, PlanMap } from "../types";

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

export const validateMap = (plan_map: PlanMap, items: unknown[], questions: unknown[], answers: Record<string, string>) =>
  request<{ valid: boolean; issues: Array<{ item_id: string; message: string }>; unconfirmed_items: number; open_questions: number }>(
    "/api/validate-map",
    { plan_map, items, questions, answers },
  );

export const confirmMap = (plan_map: PlanMap, items: unknown[], questions: unknown[], answers: Record<string, string>) =>
  request<{ confirmed: boolean; fingerprint: string | null }>("/api/confirm-map", { plan_map, items, questions, answers });
