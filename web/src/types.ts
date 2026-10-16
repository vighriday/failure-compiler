export type Status = "unconfirmed" | "confirmed" | "corrected" | "added" | "guessed" | "stale";

export type ReadingItem = {
  id: string;
  group: "People" | "Vehicles" | "Routes" | "Times";
  entity_type: "person" | "vehicle" | "place" | "delivery" | "route" | "plan";
  entity_id: string;
  field: string;
  statement: string;
  source_line: string;
  status: Status;
  guessed?: boolean;
  value?: number | boolean;
  correct_value?: number | boolean;
  choices?: number[];
};

export type RuleQuestion = {
  id: string;
  item_id: string;
  question_text: string;
  source_line?: string;
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
};

export type ExampleReading = {
  plan_text: string;
  plan_map: PlanMap;
  items: ReadingItem[];
  questions: RuleQuestion[];
  placeholder: boolean;
  read_by: string;
  problem_types: Record<string, number>;
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
