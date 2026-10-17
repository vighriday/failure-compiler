"""Configuration: AI model names, problem type definitions, size presets, cap."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# AI providers; ranked by complete checker equivalence, fields, consistency, tokens.
# ---------------------------------------------------------------------------
PROVIDER_MODELS = {"groq": "openai/gpt-oss-120b", "gemini": "gemini-3.8-flash"}
PRIMARY_PROVIDER = "gemini"
PRIMARY_MODEL = PROVIDER_MODELS[PRIMARY_PROVIDER]
FALLBACK_PROVIDER = "groq"
FALLBACK_MODEL = PROVIDER_MODELS[FALLBACK_PROVIDER]
BAKEOFF_DATE = "2026-10-17"
BAKEOFF_WINNER = PRIMARY_PROVIDER
# read-v3, three runs each: Gemini 43/100 exact results, 90.57% fields;
# Groq 12/100, 82%. Full results include schedules. devpost/bakeoff-read-v3.json.
BAKEOFF_SCORES = {
    "gemini": {"checker_mean": 43.0, "aligned_field_mean": 90.57, "total_tokens": 7470},
    "groq": {"checker_mean": 12.0, "aligned_field_mean": 82.0, "total_tokens": 10775},
}

# ---------------------------------------------------------------------------
# Problem-type taxonomy (fixed list)
# ---------------------------------------------------------------------------
# Each problem type applies to a category of entity.  Sizes are in minutes
# (or None for "absent").

PROBLEM_TYPES: list[dict] = [
    {"id": "volunteer_absent", "label": "{name} absent", "applies_to": "person", "has_size": False},
    {
        "id": "volunteer_leaves_early",
        "label": "{name} leaves early ({size}m)",
        "applies_to": "person",
        "has_size": True,
        "default_size": 90,
    },
    {
        "id": "vehicle_returns_late",
        "label": "{name} returns late ({size}m)",
        "applies_to": "vehicle",
        "has_size": True,
        "default_size": 30,
    },
    {
        "id": "supply_delivery_late",
        "label": "{name} arrives late ({size}m)",
        "applies_to": "delivery",
        "has_size": True,
        "default_size": 45,
    },
    {
        "id": "place_blocked",
        "label": "{name} blocked ({size}m)",
        "applies_to": "place",
        "has_size": True,
        "default_size": 30,
    },
]

SIZE_PRESETS = [15, 30, 45, 60, 90]

# Cap: maximum number of problems before the app refuses to run.
PROBLEM_CAP = 24  # -> 300 tests max

# Checker
SOLVER_MAX_DETERMINISTIC_TIME = 30.0  # CP-SAT deterministic-time limit per scenario
SOLVER_SEED = 42

# Not-delivered penalty: households * (finish_time + 180) minutes.
NOT_DELIVERED_HORIZON_PADDING = 180  # minutes added to finish_time for penalty calc
