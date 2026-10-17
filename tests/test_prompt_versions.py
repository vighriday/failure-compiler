"""The revised extraction prompt stays generic and leaves all example outcomes to the checker."""

import re

from server.ai.prompts import READ_PROMPT_VERSION, READ_SYSTEM
from tests.validation_helpers import truth_data


def test_read_v2_is_generic_and_requires_complete_extraction_and_approximation_marks():
    assert READ_PROMPT_VERSION == "read-v2"
    assert "every delivery or" in READ_SYSTEM and "arrival of supplies" in READ_SYSTEM
    assert "plan's own words for names" in READ_SYSTEM
    assert "approximate durations" in READ_SYSTEM and "affected entity guessed" in READ_SYSTEM
    for person in truth_data().people:
        assert person.name not in READ_SYSTEM
    for example_time in ("9:30", "10:30", "10:45", "12:00", "540", "570", "630", "645", "720"):
        assert example_time not in READ_SYSTEM
    assert not re.search(r"\b(?:90|30|45)\b", READ_SYSTEM)
