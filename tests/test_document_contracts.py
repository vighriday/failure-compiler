"""Keep the corrected documentation facts aligned with the example and session lifetime."""

from html import unescape
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
    assert '<span class="score-fix">Fixes 2</span>' in prd
    assert '<span class="score-broken">Still broken 2</span>' in prd
    for document in (prd, spec):
        assert "Test your own change" in document or "ChangeBuilder.tsx" in document
        assert "Joel absent + Ravi absent" in document or "Joel + Ravi absent" in document
        assert "Suggested by Groq / openai/gpt-oss-120b (fallback: Gemini unavailable)" in document


def test_readme_describes_server_memory_and_review_actions():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Closing the tab does not clear server memory" in readme
    assert "POST /api/update-map" in readme
    assert "Closing the tab ends the session" not in readme


def test_report_and_history_contracts_match_in_markdown_and_html():
    for name in ("prd.md", "prd.html", "spec.md", "spec.html"):
        document = (ROOT / "devpost" / name).read_text(encoding="utf-8").lower()
        for fact in (
            "before/after",
            "read-only",
            "32 ai items",
            "30",
            "volunteers arriving late",
            "window.print()",
            "a4",
            "letter",
            "4.5:1",
            "12px",
            "gemini",
            "natural schedules",
        ):
            assert fact in document, (name, fact)


def test_spec_file_trees_match_the_implemented_report_and_builder():
    markdown = (ROOT / "devpost/spec.md").read_text(encoding="utf-8")
    tree = markdown.split("## File Structure\n", 1)[1].split("```", 2)[1].strip()
    companion = (ROOT / "devpost/spec.html").read_text(encoding="utf-8")
    html_tree = companion.split('<section id="files">', 1)[1].split("<pre>", 1)[1]
    assert unescape(html_tree.split("</pre>", 1)[0]).strip() == tree
    for path in (
        "server/report.py",
        "web/src/screens/Report.tsx",
        "web/src/screens/report.css",
        "web/src/components/ChangeBuilder.tsx",
        "scripts/verify_accessibility.py",
        "docs/sample-report.pdf",
    ):
        assert (ROOT / path).is_file()
        assert Path(path).name in tree
    assert "ReportPage.tsx" not in tree
    assert "gen-types.ts" not in tree
