"""Keep the corrected documentation facts aligned with the example and session lifetime."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_html_companions_keep_the_current_example_counts():
    for name in ("scope.html", "prd.html", "spec.html"):
        document = (ROOT / "devpost" / name).read_text(encoding="utf-8")
        assert "3 hidden pairs" in document
        assert "84 survived" in document
        for stale in ("89 survived", "88 survived", "2 hidden pairs", "40 minutes late", "12:40"):
            assert stale not in document


def test_html_keys_are_additive_and_fix_card_counts_match_four_crosses():
    spec = (ROOT / "devpost/spec.html").read_text(encoding="utf-8")
    assert "existing holders keep their keys" in spec
    assert "false</code> on the current holder" not in spec
    prd = (ROOT / "devpost/prd.html").read_text(encoding="utf-8")
    assert '<span class="score-broken">Still broken 4</span>' in prd
    assert '<span class="score-fix">Fixes 3</span>' in prd
    assert '<span class="score-broken">Still broken 1</span>' in prd


def test_readme_describes_server_memory_and_review_actions():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Closing the tab does not clear server memory" in readme
    assert "POST /api/update-map" in readme
    assert "Closing the tab ends the session" not in readme
