"""Saved bake-offs can be rescored without fresh calls or losing original evidence."""

import copy
import json

from scripts import bakeoff
from server.evaluation import MEASUREMENT_VERSION
from tests.validation_helpers import ROOT


def test_rescore_is_offline_preserves_raw_errors_and_prior_measurements(monkeypatch):
    saved = json.loads((ROOT / "devpost/bakeoff-read-v3.json").read_text(encoding="utf-8"))
    saved.pop("measurement_version", None)
    saved.pop("measurement_history", None)
    original = copy.deepcopy(saved)
    saved["readings"].append(
        {"provider": "other", "reading": 1, "error": "server_error", "attempts": []}
    )

    def no_provider(*args, **kwargs):
        raise AssertionError("Offline scoring must never call a provider")

    monkeypatch.setattr(bakeoff, "read_plan", no_provider)
    monkeypatch.setattr(
        bakeoff,
        "compare",
        lambda _: {
            "measurement_version": MEASUREMENT_VERSION,
            "checker_matches": 100,
            "checker_total": 100,
            "aligned_field_match_percent": 100,
        },
    )
    report = bakeoff.rescore_saved_report(saved)
    assert report["measurement_version"] == MEASUREMENT_VERSION
    assert len(report["measurement_history"]) == 1
    assert report["measurement_history"][0]["ranking"] == original["ranking"]
    assert report["readings"][-1] == saved["readings"][-1]
    for before, after in zip(original["readings"], report["readings"]):
        assert before["raw"] == after["raw"]
        assert before["attempts"] == after["attempts"]
        assert before.get("previous_attempts") == after.get("previous_attempts")
    assert len(bakeoff.rescore_saved_report(report)["measurement_history"]) == 1
