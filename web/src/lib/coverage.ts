import type { PlanMap } from "../types";

/** Listed cover is a roster check, not a guarantee that the schedule works. */
export function routeCoverage(plan: PlanMap) {
  const people = new Map(plan.people.map((person) => [person.id, person]));
  return plan.routes.map((route) => {
    const vehicle = plan.vehicles.find((candidate) => candidate.id === route.vehicle_id)?.name;
    const drivers = [...new Set(route.driver_ids as string[])]
      .map((id) => people.get(id)).filter((person) => person?.can_drive)
      .map((person) => String(person!.name));
    const hasLoader = (route.loader_ids as string[]).some((id) => people.has(id));
    return {id: route.id, name: route.name, vehicle, drivers, hasLoader,
      complete: Boolean(vehicle && drivers.length > 1 && hasLoader)};
  });
}
