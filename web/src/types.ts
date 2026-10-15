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
