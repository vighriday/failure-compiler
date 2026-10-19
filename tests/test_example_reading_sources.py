"""Physical source references are checked on the unedited provider reading."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_source_line_is_a_nonblank_physical_plan_line() -> None:
    reading = json.loads((ROOT / "fixtures/example-reading.json").read_text(encoding="utf-8"))
    plan_lines = (ROOT / "fixtures/example-plan.txt").read_text(encoding="utf-8").splitlines()

    payload = json.loads(reading["raw_text"])
    entities = [
        item
        for collection in ("people", "vehicles", "places", "deliveries", "routes")
        for item in payload[collection]
    ]
    entities.append({"id": "finish_time", "source_line": payload["finish_time_source"]})
    for item in entities:
        source_line = item["source_line"]
        match = re.fullmatch(r"L([1-9][0-9]*)", source_line)
        assert match, f"Invalid source line {source_line!r} in {item['id']}"
        line_number = int(match.group(1))
        assert line_number <= len(plan_lines), f"{source_line} is outside the plan"
        assert plan_lines[line_number - 1].strip(), f"{source_line} is blank"
