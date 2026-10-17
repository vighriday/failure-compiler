export type Status = "unconfirmed" | "confirmed" | "corrected" | "added" | "guessed" | "stale";

export type ReadingItem = {
  id: string;
  group: "People" | "Vehicles" | "Routes" | "Times";
  entity_type: "person" | "vehicle" | "place" | "delivery" | "route" | "plan";
  entity_id: string;
  field: string;
  statement: string;
  source_line: string | null;
  status: Status;
  guessed?: boolean;
  value?: number | boolean;
  correct_value?: number | boolean;
  choices?: number[];
  original_statement?: string | null;
  changed_by_fix?: number | null;
  controls: FactControl[];
};

export type FactControl = {
  field: string; label: string; value: number | boolean | string | string[];
  type: "time" | "boolean" | "number" | "select" | "ordered_people";
  options?: Array<{value: string; label: string}>;
  min?: number; max?: number; step?: number;
};

export type RuleQuestion = {
  id: string;
  item_id: string;
  question_text: string;
  source_line?: string | null;
  kind?: "missing_delivery" | "missing_assignment" | "missing_finish";
  entity_id?: string;
  field?: string;
  choices: string[];
};

export type PlanMap = {
  fingerprint: string | null;
  ai_meta: { provider: string; model: string; timestamp: string };
  people: Array<Record<string, any>>;
  vehicles: Array<Record<string, any>>;
  places: Array<Record<string, any>>;
  deliveries: Array<Record<string, any>>;
  routes: Array<Record<string, any>>;
  finish_time: number;
  finish_time_source: string;
  finish_time_guessed: boolean;
  problem_sizes: Record<string, number>;
  questions: Array<Record<string, any>>;
  fix_history: AppliedFix[];
};

export type ExampleReading = {
  reading_id: string;
  plan_text: string;
  plan_map: PlanMap;
  items: ReadingItem[];
  questions: RuleQuestion[];
  placeholder: boolean;
  read_by: string;
  problem_types: Record<string, number>;
};

export type ReviewState = Pick<ExampleReading, "reading_id" | "plan_map" | "items" | "questions"> & {
  answers: Record<string, string>;
  issues: Array<{item_id: string; field: string; bad_value: unknown; message: string}>;
  confirmed: boolean; out_of_date: boolean;
};

export type CellState = "tick" | "cross" | "dim" | "qmark";
export type TimelineEvent = { route_id: string; event: string; time: number; person_id: string | null; vehicle_id: string | null };
export type ScenarioResult = {
  scenario_id: string; failures: string[]; state: CellState; dim_cause: string | null;
  lateness_minutes: number | null; timeline: TimelineEvent[]; human_cost: string | null;
  map_fingerprint: string;
};
export type Problem = { id: string; type_id: string; entity_id: string; entity_type: string; size: number | null; label: string };
export type ScenarioRef = { scenario_id: string; failures: string[] };
export type RunMeta = { fingerprint: string; total: number; problems: Problem[]; scenarios: ScenarioRef[] };
export type RunCount = {
  total: number; completed: number; weak_spots: number; hidden_pairs: number;
  dimmed: number; survived: number; unknown: number; pending: number; line: string;
};

export type FixOperation = { op: string; target_id: string; field: string; value: string | number | boolean | string[] };
export type AppliedFix = { fix_id: string; description: string; operations: FixOperation[]; from_fingerprint: string; to_fingerprint: string };
export type FixSuggestion = {
  id: string; description: string; operations: FixOperation[]; scenario_results: ScenarioResult[];
  fixes_n: number; still_broken_n: number; new_crosses_n: number; new_crosses: string[];
  eligible: boolean; rejection_reason: string | null; gate_status: string; gate_reason: string | null;
};
export type CaseDetail = {
  placeholder: boolean; explanation: string | null; result: ScenarioResult;
  route_reasons: Record<string, string>; alone_results: ScenarioResult[]; suggestions: FixSuggestion[];
};
