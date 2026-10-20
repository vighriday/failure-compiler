"""Inspect A4/Letter report text and render every page for visual review.

Run: uv run --with pymupdf -- python scripts/verify_report_pdf.py
"""

import json
import re
import unicodedata
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]


def main():
    reports = []
    for paper, path in [
        ("a4", ROOT / "docs/sample-report.pdf"),
        ("letter", ROOT / "devpost/screens/sample-report-letter.pdf"),
    ]:
        document = pymupdf.open(path)
        output = ROOT / "devpost/screens" / f"report-{paper}"
        output.mkdir(parents=True, exist_ok=True)
        text = unicodedata.normalize("NFKC", "\n".join(page.get_text() for page in document))
        for heading in [
            "The plan",
            "What was tested",
            "What broke before fixes",
            "Fixes",
            "After the fixes",
            "What was NOT tested",
        ]:
            assert heading in text, heading
        for phrase in [
            "All 100 tested scenarios survive.",
            "Fix 1 (AI)",
            "Fix 2 (yours)",
            "Fix 3 (yours)",
            "Couldn't apply",
            "Gemini unavailable",
            "volunteers arriving late",
            "Fingerprint:",
        ]:
            assert phrase in text, phrase
        assert "Back to results" not in text and "Print or save as PDF" not in text
        assert re.search(r"Fingerprint:\s*[a-f0-9]{64}", text)
        pages = []
        for index, page in enumerate(document):
            spans = [
                span
                for block in page.get_text("dict")["blocks"]
                if "lines" in block
                for line in block["lines"]
                for span in line["spans"]
                if span["text"].strip()
            ]
            assert all(pymupdf.Rect(span["bbox"]) in page.rect for span in spans), (
                paper,
                index,
                "clipped text",
            )
            assert all(span["size"] >= 8.8 for span in spans), (
                paper,
                index,
                "text below 12 CSS px",
            )
            assert all(span["color"] == 0 for span in spans), (paper, index, "non-black text")
            assert len(page.get_text().strip()) > 100, (paper, index, "nearly empty page")
            page.get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25), alpha=False).save(
                str(output / f"page-{index + 1}.png")
            )
            pages.append(
                {
                    "page": index + 1,
                    "characters": len(page.get_text()),
                    "width_pt": page.rect.width,
                    "height_pt": page.rect.height,
                }
            )
        reports.append({"paper": paper, "pages": pages})
    (ROOT / "devpost/screens/report-pdf-verification.json").write_text(
        json.dumps(reports, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
