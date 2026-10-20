"""Run saved-example browser checks on isolated local servers, with no AI calls."""

import argparse
import os
import runpy
from pathlib import Path

from local_preview import local_preview

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", action="store_true", help="Run only the full example story")
    args = parser.parse_args()
    if not (ROOT / "web/dist/index.html").is_file():
        parser.error("Build the frontend first: npm run build")
    previous = os.environ.get("FAILURE_COMPILER_URL")
    try:
        with local_preview() as base:
            os.environ["FAILURE_COMPILER_URL"] = base
            names = ["story"] if args.story else ["story", "review", "landing", "accessibility"]
            for name in names:
                print(f"Running {name} browser checks", flush=True)
                runpy.run_path(str(ROOT / "scripts" / f"verify_{name}.py"), run_name="__main__")
    finally:
        if previous is None:
            os.environ.pop("FAILURE_COMPILER_URL", None)
        else:
            os.environ["FAILURE_COMPILER_URL"] = previous


if __name__ == "__main__":
    main()
