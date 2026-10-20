"""Copy installed browser-runtime licence notices without changing their text."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    sections = [
        "Third-party notices for Failure Compiler\n"
        "The project MIT licence does not replace these dependency licences.\n"
        "Python dependencies retain their licence files in their installed distributions.\n",
    ]
    for package in ("react", "react-dom", "@fontsource/ibm-plex-sans", "@fontsource/ibm-plex-mono"):
        licence = (ROOT / "node_modules" / package / "LICENSE").read_text(encoding="utf-8")
        sections.append(f"=== {package} ===\n\n{licence}")
    for package, source in (("gsap", "gsap-core.js"), ("@gsap/react", "src/index.js")):
        text = (ROOT / "node_modules" / package / source).read_text(encoding="utf-8")
        notice = text.split("/*!", 1)[1].split("*/", 1)[0]
        sections.append(f"=== {package} ===\n\n/*!{notice}*/\n")
    target = ROOT / "web/public/third-party-notices.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n\n".join(sections), encoding="utf-8")
    print("Saved browser-runtime and font notices.")


if __name__ == "__main__":
    main()
