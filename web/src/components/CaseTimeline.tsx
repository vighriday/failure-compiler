import { routeLabel } from "../lib/labels";
import type { PlanMap, ScenarioResult } from "../types";

export default function CaseTimeline({ plan, result, reasons }: { plan: PlanMap; result: ScenarioResult; reasons: Record<string, string> }) {
  const x = (time: number) => 94 + (time - 540) / 210 * 402;
  const name = (id: string | null) => plan.people.find((person) => person.id === id)?.name ?? "team";
  const summary = (reason: string) => {
    if (reason.includes("Nobody can open")) return "Never leaves: nobody can open the loading area.";
    if (reason.includes("Loading team gone.")) return `Never leaves. ${reason.split("Loading team gone.")[0]}Loading team gone.`;
    return "Never leaves: no listed team can deliver this route.";
  };
  return <div className="case-timeline"><h3>The checker's best schedule</h3>
    <div className="timeline-scroll" role="region" aria-label="Scrollable route timeline" tabIndex={0}>
    <svg className="timeline-svg" viewBox="0 0 520 290" role="img" aria-label="Best schedule from 9:00 to 12:30, one lane per route. Noon is the deadline.">
      {[540, 600, 660, 720, 750].map((time) => <g key={time}><line x1={x(time)} x2={x(time)} y1="45" y2="274" className="time-guide" /><text x={x(time) - (time === 720 ? 4 : 0)} y="36" textAnchor={time >= 720 ? "end" : "middle"} className="timeline-time">{`${Math.floor(time / 60)}:${String(time % 60).padStart(2, "0")}`}</text></g>)}
      {plan.routes.map((route, index) => {
        const y = 51 + index * 73;
        const events = result.timeline.filter((event) => event.route_id === route.id);
        const load = events.find((event) => event.event === "load_start");
        const loadEnd = events.find((event) => event.event === "load_end");
        const drive = events.find((event) => event.event === "drive_start");
        const driveEnd = events.find((event) => event.event === "drive_end");
        const missing = events.some((event) => event.event === "not_delivered");
        const vehicle = plan.vehicles.find((vehicle) => vehicle.id === route.vehicle_id)?.name;
        return <g key={route.id}><text x="0" y={y + 29} className="timeline-route">{routeLabel(route.name)}</text><text x="0" y={y + 47} className="timeline-time">{vehicle}</text><line x1="94" x2="496" y1={y + 60} y2={y + 60} className="lane-rule" />
          {missing ? <><line x1="94" x2="496" y1={y + 29} y2={y + 29} className="missing-lane" /><text x="99" y={y + 48} className="missing-note">{summary(reasons[route.id] ?? "")}</text></> : <>
            {load && loadEnd && <><text x={x(load.time)} y={y + 12} className="load-person">Load: {name(load.person_id)}</text><rect x={x(load.time)} y={y + 19} width={Math.max(2, x(loadEnd.time) - x(load.time))} height="10" className="load-bar" /></>}
            {drive && driveEnd && <><rect x={x(drive.time)} y={y + 33} width={Math.max(2, x(driveEnd.time) - x(drive.time))} height="19" className={driveEnd.time > plan.finish_time ? "drive-bar late-bar" : "drive-bar"} /><text x={(x(drive.time) + x(driveEnd.time)) / 2} y={y + 47} textAnchor="middle" className="drive-person">Drive: {name(drive.person_id)}</text></>}
          </>}
        </g>;
      })}
      <line x1={x(plan.finish_time)} x2={x(plan.finish_time)} y1="44" y2="274" className="deadline-line" /><text x={x(plan.finish_time) - 4} y="15" textAnchor="end" className="deadline-label">Noon: families waiting</text>
    </svg>
    </div>
    <p className="timeline-scroll-hint">Scroll across the timeline to see every route and the noon deadline.</p>
  </div>;
}
