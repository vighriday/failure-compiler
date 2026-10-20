import { useState } from "react";
import type { FixOperation, PlanMap } from "../types";

const operations = [
  ["add_driver", "Add a driver to a route"], ["add_loader", "Add a loader to a route"],
  ["give_spare_key", "Give a spare key"], ["set_person_availability", "Change someone's hours"],
  ["move_route", "Move a route to another vehicle"],
];
const time = (n: number) => `${Math.floor(n / 60).toString().padStart(2, "0")}:${(n % 60).toString().padStart(2, "0")}`;
const routeName = (name: string) => /^route\b/i.test(name) ? name : `Route ${name}`;

export default function ChangeBuilder({ plan, disabled, onTest }: {
  plan: PlanMap; disabled: boolean; onTest: (operations: FixOperation[]) => Promise<void>;
}) {
  const blank = (op = "add_driver"): FixOperation => {
    if (op === "give_spare_key") return {op, target_id: plan.people[0].id, field: "holds_key", value: true};
    if (op === "set_person_availability") return {op, target_id: plan.people[0].id, field: "available_until", value: plan.people[0].available_until};
    return {op, target_id: plan.routes[0].id, field: op === "move_route" ? "vehicle_id" : op === "add_loader" ? "loader_ids" : "driver_ids", value: op === "move_route" ? plan.vehicles[0].id : plan.people[0].id};
  };
  const [rows, setRows] = useState<FixOperation[]>([blank()]);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const update = (index: number, patch: Partial<FixOperation>) => setRows((current) => current.map((row, i) => i === index ? {...row, ...patch} : row));
  async function submit() {
    setTesting(true); setError("");
    try { await onTest(rows); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not test this change. Try again."); }
    finally { setTesting(false); }
  }
  return <section className="change-builder" aria-label="Test your own change">
    <div className="section-kicker">YOUR TURN</div><h3>Test your own change</h3>
    <p>Pick up to three changes. The checker tests the whole plan before you can accept them.</p>
    <fieldset disabled={disabled || testing}>
      {rows.map((row, i) => <div className="change-operation" key={i}>
        <label>Change {i + 1}<select aria-label={`Operation ${i + 1}`} value={row.op} onChange={(event) => update(i, blank(event.target.value))}>{operations.map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></label>
        {["give_spare_key", "set_person_availability"].includes(row.op) ? <label>Person<select aria-label={`Person ${i + 1}`} value={row.target_id} onChange={(event) => { const person = plan.people.find((p) => p.id === event.target.value)!; update(i, {target_id: person.id, ...(row.op === "set_person_availability" ? {value: person[row.field]} : {})}); }}>{plan.people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label> : <>
          <label>Route<select aria-label={`Route ${i + 1}`} value={row.target_id} onChange={(event) => update(i, {target_id: event.target.value})}>{plan.routes.map((r) => <option key={r.id} value={r.id}>{routeName(r.name)}</option>)}</select></label>
          {row.op === "move_route" ? <label>Vehicle<select aria-label={`Vehicle ${i + 1}`} value={String(row.value)} onChange={(event) => update(i, {value: event.target.value})}>{plan.vehicles.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}</select></label> : <label>Person<select aria-label={`Person ${i + 1}`} value={String(row.value)} onChange={(event) => update(i, {value: event.target.value})}>{plan.people.filter((p) => row.op !== "add_driver" || p.can_drive).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>}
        </>}
        {row.op === "set_person_availability" && <><label>Hours<select aria-label={`Hours ${i + 1}`} value={row.field} onChange={(event) => update(i, {field: event.target.value, value: plan.people.find((p) => p.id === row.target_id)![event.target.value]})}><option value="available_from">Starts at</option><option value="available_until">Finishes at</option></select></label><label>Time<input type="time" required aria-label={`Time ${i + 1}`} value={time(row.value as number)} onChange={(event) => { if (event.target.value) { const [h, m] = event.target.value.split(":").map(Number); update(i, {value: h * 60 + m}); } }} /></label></>}
        {rows.length > 1 && <button className="quiet-link remove-operation" type="button" aria-label={`Remove change ${i + 1}`} onClick={() => setRows((current) => current.filter((_, index) => index !== i))}>Remove</button>}
      </div>)}
      <div className="choice-row">{rows.length < 3 && <button className="button button-text" type="button" onClick={() => setRows((current) => [...current, blank()])}>Add another operation</button>}<span className="mono">{rows.length} / 3 operations</span></div>
      <button type="button" className="button button-primary" onClick={submit}>{testing ? "Checking every scenario…" : "Test this change"}</button>
    </fieldset>
    {error && <p className="inline-error" role="alert">{error}</p>}
  </section>;
}
