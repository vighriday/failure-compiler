import { useState } from "react";
import type { FactControl, PlanMap, ReadingItem, RuleQuestion } from "../types";
import FactEditor from "./FactEditor";

export default function MissingFactQuestion({question, plan, disabled, onAnswer}: {
  question: RuleQuestion; plan: PlanMap; disabled: boolean; onAnswer: (value: unknown) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [arrival, setArrival] = useState("");
  const [place, setPlace] = useState("");
  const minutes = (time: string) => { const [hour, minute] = time.split(":").map(Number); return hour * 60 + minute; };
  if (question.kind === "missing_delivery") return <div>
    <div className="choice-row"><button type="button" className="choice-button" disabled={disabled} onClick={() => onAnswer("No delivery")}>No delivery</button><button type="button" className="choice-button" disabled={disabled} onClick={() => setAdding(true)}>Add a delivery</button></div>
    {adding && <div className="inline-editor">
      <label>Arrival time<input type="time" aria-label="Supply delivery arrival time" value={arrival} onChange={(event) => setArrival(event.target.value)} disabled={disabled} /></label>
      <label>Place<select aria-label="Supply delivery place" value={place} onChange={(event) => setPlace(event.target.value)} disabled={disabled}><option value="">Choose a place</option>{plan.places.map((entity) => <option key={entity.id} value={entity.id}>{entity.name}</option>)}</select></label>
      <button type="button" className="choice-button" disabled={disabled || !arrival || !place} onClick={() => onAnswer({choice: "Add a delivery", arrives_at: minutes(arrival), place_id: place})}>Add supply delivery</button>
    </div>}
  </div>;
  if (question.kind === "missing_finish") return <div className="inline-editor"><label>Finish time<input type="time" aria-label="Missing finish time" value={arrival} onChange={(event) => setArrival(event.target.value)} disabled={disabled} /></label><button type="button" className="choice-button" disabled={disabled || !arrival} onClick={() => onAnswer(minutes(arrival))}>Use finish time</button></div>;
  const route = plan.routes.find((route) => route.id === question.entity_id);
  const field = question.field ?? "vehicle_id";
  const control: FactControl = {
    field, label: field === "vehicle_id" ? "Choose a vehicle" : "Choose people (primary first)",
    type: field === "vehicle_id" ? "select" : "ordered_people", value: route?.[field] ?? "",
    options: (field === "vehicle_id" ? plan.vehicles : plan.people.filter((person) => field === "loader_ids" || person.can_drive)).map((entity) => ({value: entity.id, label: entity.name})),
  };
  const item: ReadingItem = {id: question.id, entity_id: question.entity_id ?? "", entity_type: "route", group: "Routes", field, source_line: null, status: "added", statement: question.question_text, controls: [control]};
  return <FactEditor item={item} disabled={disabled} onCorrect={(_, value) => onAnswer(value)} onConfirm={() => undefined} />;
}
