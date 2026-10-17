import type { FactControl, ReadingItem } from "../types";

type Props = {
  item: ReadingItem;
  disabled: boolean;
  onCorrect: (field: string, value: unknown) => void;
  onConfirm: () => void;
};

export default function FactEditor({ item, disabled, onCorrect, onConfirm }: Props) {
  function editor(control: FactControl) {
    const label = control.field === item.field ? `Correction for ${item.original_statement ?? item.statement}` : `${control.label} for ${item.entity_id}`;
    if (control.type === "ordered_people") {
      const selected = control.value as string[];
      return <div>
        {selected.map((personId, index) => <div className="choice-row" key={personId}>
          <span>{index + 1}. {control.options?.find((option) => option.value === personId)?.label}</span>
          <button type="button" className="quiet-link" disabled={disabled || index === 0} aria-label={`Move ${personId} earlier in ${control.field}`} onClick={() => {
            const next = [...selected]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; onCorrect(control.field, next);
          }}>↑</button>
          <button type="button" className="quiet-link" disabled={disabled || index === selected.length - 1} aria-label={`Move ${personId} later in ${control.field}`} onClick={() => {
            const next = [...selected]; [next[index], next[index + 1]] = [next[index + 1], next[index]]; onCorrect(control.field, next);
          }}>↓</button>
          <button type="button" className="quiet-link" disabled={disabled} aria-label={`Remove ${personId} from ${control.field}`} onClick={() => onCorrect(control.field, selected.filter((id) => id !== personId))}>Remove</button>
        </div>)}
        <select aria-label={label} disabled={disabled} value="" onChange={(event) => onCorrect(control.field, [...selected, event.target.value])}>
          <option value="">Add a person</option>
          {control.options?.filter((option) => !selected.includes(option.value)).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </div>;
    }
    if (control.type === "time") {
      const minutes = Number(control.value), time = `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
      return <input type="time" aria-label={label} disabled={disabled} value={time} onChange={(event) => {
        if (!event.target.value) return;
        const [hour, minute] = event.target.value.split(":").map(Number); onCorrect(control.field, hour * 60 + minute);
      }} />;
    }
    if (control.type === "number" && control.field === "households") return <input key={String(control.value)} type="number" aria-label={label} disabled={disabled} defaultValue={Number(control.value)} min={control.min} max={control.max} step={control.step} onBlur={(event) => {
      if (event.currentTarget.reportValidity() && event.target.value !== "" && Number(event.target.value) !== control.value) onCorrect(control.field, Number(event.target.value));
    }} />;
    const options = control.type === "boolean" ? [{value: "true", label: "Yes"}, {value: "false", label: "No"}]
      : control.type === "number" ? Array.from({length: 48}, (_, index) => ({value: String((index + 1) * 5), label: `${(index + 1) * 5} minutes`})) : control.options ?? [];
    return <select aria-label={label} disabled={disabled} value={String(control.value)} onChange={(event) => onCorrect(control.field, control.type === "boolean" ? event.target.value === "true" : control.type === "number" ? Number(event.target.value) : event.target.value)}>
      {control.type === "select" && !control.value && <option value="">Choose a value</option>}
      {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>;
  }
  return <div className="inline-editor">
    {item.controls.map((control) => <label key={control.field}>{control.label}{editor(control)}</label>)}
    {item.status === "guessed" && <button type="button" disabled={disabled} className="quiet-link" onClick={onConfirm}>Keep this guess</button>}
  </div>;
}
