"""List actual fact citations for human support review, without editing a provider capture."""

import argparse
import json
import re
from pathlib import Path


def audit_sources(payload: dict, text: str) -> dict:
    lines, rows, invalid = text.splitlines(), [], []
    for collection in ("people", "vehicles", "places", "deliveries", "routes"):
        for entity in payload[collection]:
            for field, source in entity.get("fact_sources", {}).items():
                row = {
                    "entity": entity["name"],
                    "field": field,
                    "value": entity[field],
                    "source_line": source,
                    "text": None,
                }
                if source is not None:
                    match = re.fullmatch(r"L([1-9][0-9]*)", source)
                    if match and int(match[1]) <= len(lines) and lines[int(match[1]) - 1].strip():
                        row["text"] = lines[int(match[1]) - 1]
                    else:
                        invalid.append(row)
                rows.append(row)
    source = payload.get("finish_time_source")
    if source:
        match = re.fullmatch(r"L([1-9][0-9]*)", source)
        row = {
            "entity": "Plan",
            "field": "finish_time",
            "value": payload["finish_time"],
            "source_line": source,
            "text": None,
        }
        if match and int(match[1]) <= len(lines) and lines[int(match[1]) - 1].strip():
            row["text"] = lines[int(match[1]) - 1]
        else:
            invalid.append(row)
        rows.append(row)
    return {
        "facts": rows,
        "invalid": invalid,
        "uncited": [row for row in rows if row["source_line"] is None],
        "semantic_support": "Requires human review; valid line numbers alone do not prove support.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reading", type=Path)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    capture = json.loads(args.reading.read_text(encoding="utf-8"))
    payload = json.loads(capture["raw_text"]) if "raw_text" in capture else capture
    result = audit_sources(payload, args.plan.read_text(encoding="utf-8"))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["invalid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
