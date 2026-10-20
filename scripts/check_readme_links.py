"""Check README file paths, heading anchors and optionally public web targets."""

import argparse
import concurrent.futures
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def targets(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return sorted(
        set(re.findall(r"\]\(([^)\s]+)\)", text) + re.findall(r'(?:src|href)="([^"]+)"', text))
    )


def anchors(text):
    ids, counts = set(), {}
    for heading in re.findall(r"^#{1,6} (.+)$", text, flags=re.M):
        heading = re.sub(r"<[^>]+>", "", heading)
        heading = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", heading)
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        ids.add(slug + (f"-{count}" if count else ""))
        counts[slug] = count + 1
    return ids


def check_local(text):
    failures = []
    for target in targets(text):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        path = ROOT / unquote(parsed.path or "README.md")
        if not path.exists():
            failures.append({"target": target, "reason": "missing local file"})
        elif (
            parsed.fragment
            and path.suffix.lower() == ".md"
            and unquote(parsed.fragment) not in anchors(path.read_text(encoding="utf-8"))
        ):
            failures.append({"target": target, "reason": "missing heading anchor"})
    return failures


def check_web(target):
    try:
        request = Request(target, headers={"User-Agent": "Mozilla/5.0 (README link check)"})
        with urlopen(request, timeout=20) as response:
            return {"target": target, "status": response.status}
    except (HTTPError, URLError, TimeoutError) as error:
        return {
            "target": target,
            "status": getattr(error, "code", "unverified"),
            "reason": str(error),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external", action="store_true")
    args = parser.parse_args()
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    result = {"local_failures": check_local(text), "external": []}
    if args.external:
        urls = [target for target in targets(text) if target.startswith("https://")]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            result["external"] = list(pool.map(check_web, urls))
    print(json.dumps(result, indent=2))
    proof = ROOT / "devpost/screens/readme-links.json"
    proof.parent.mkdir(parents=True, exist_ok=True)
    proof.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if result["local_failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
