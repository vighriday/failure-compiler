"""The README gallery has the promised dimensions and no missing local targets."""

import struct
from pathlib import Path

from scripts.check_readme_links import check_local

ROOT = Path(__file__).resolve().parents[1]


def test_readme_files_and_heading_anchors_resolve():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert not check_local(readme)
    assert "https://youtu.be/VIDEO_ID" not in readme


def test_gallery_is_six_real_three_to_two_png_files():
    for name in [
        "01-paste-plan",
        "02-plan-map",
        "03-crash-test-grid",
        "04-broken-case",
        "05-fix-turned-down",
        "06-report",
    ]:
        data = (ROOT / "docs/images" / f"{name}.png").read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", data[16:24]) == (1500, 1000)


def test_sample_report_is_a_real_nonempty_pdf():
    data = (ROOT / "docs/sample-report.pdf").read_bytes()
    assert data.startswith(b"%PDF-") and len(data) > 10000


def test_recording_candidates_have_their_requested_aspect_ratios():
    for name, size in (("youtube-thumbnail.png", (1280, 720)),
                       ("devpost-thumbnail.png", (1500, 1000))):
        data = (ROOT / "docs/images" / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", data[16:24]) == size


def test_bundled_font_and_browser_runtime_notices_are_present():
    notice = (ROOT / "web/public/third-party-notices.txt").read_text(encoding="utf-8")
    for package in ("react", "react-dom", "@fontsource/ibm-plex-sans", "@fontsource/ibm-plex-mono"):
        assert f"=== {package} ===" in notice
    assert notice.count("SIL OPEN FONT LICENSE Version 1.1") == 2
    assert "https://gsap.com/standard-license" in notice
