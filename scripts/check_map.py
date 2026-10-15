"""Print the crash-test triangle and count line for a truth-map JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.checker.runner import run_checker
from server.models import PlanMapData


def format_counts(results: list) -> str:
    singles = [result for result in results if len(result.failures) == 1]
    pairs = [result for result in results if len(result.failures) == 2]
    single_crosses = sum(result.state == "cross" for result in singles)
    hidden_pairs = sum(result.state == "cross" for result in pairs)
    dimmed = sum(result.state == "dim" for result in pairs)
    survived = sum(result.state == "tick" for result in results)
    unknown = sum(result.state == "qmark" for result in results)
    if unknown:
        return (
            f"{len(results)} tests: {single_crosses} single weak spots, "
            f"{hidden_pairs} hidden pairs, {dimmed} already broken by a single failure, "
            f"{survived} survived, {unknown} unknown."
        )
    return (
        f"{len(results)} tests: {single_crosses} single weak spot, "
        f"{hidden_pairs} hidden pairs, {dimmed} already broken by the weak spot, "
        f"{survived} survived."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map_file", type=Path, help="Path to a PlanMapData JSON file")
    args = parser.parse_args()
    plan = PlanMapData.model_validate_json(args.map_file.read_text(encoding="utf-8"))
    results = run_checker(plan)

    print("Scenario                              Result")
    for result in results:
        print(f"{result.scenario_id:<38} {result.state}")
    print(format_counts(results))


if __name__ == "__main__":
    main()
