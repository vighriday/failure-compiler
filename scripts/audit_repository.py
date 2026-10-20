"""Inspect tracked files and reachable history without printing credential values."""

import json
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "Google API key": rb"AIza[0-9A-Za-z_-]{35}",
    "Groq API key": rb"gsk_[0-9A-Za-z]{40,}",
    "GitHub token": rb"(?:gh[pousr]_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{40,})",
    "private key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "AWS access key": rb"(?:AKIA|ASIA)[0-9A-Z]{16}",
}
# These were deliberately captured for the slice-3 review and later removed
# from the working tree. They contain only the fictional example. The hook
# runs a TypeScript check and has no key, personal path or external command.
REVIEWED_HISTORY = {
    "oxcode.hooks.json",
    "devpost/screens/slice3-screen1-paste.png",
    "devpost/screens/slice3-screen2-load.png",
    "devpost/screens/slice3-screen2-correction.png",
    "devpost/screens/slice3-screen2-ready.png",
}


def git(*args):
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args], cwd=ROOT
    )


def private_path(path):
    name = Path(path).name.lower()
    return (
        name == "learner-profile.md"
        or name.endswith(".zip")
        or (name == ".env" or name.startswith(".env.")) and name != ".env.example"
        or path.startswith("devpost/screens/")
        or name == "oxcode.hooks.json"
    )


def main():
    objects = git("rev-list", "--objects", "--all").decode().splitlines()
    paths, hashes = {}, set()
    for line in objects:
        oid, _, path = line.partition(" ")
        hashes.add(oid)
        if path:
            paths[oid] = path
    staged = git("ls-files", "--stage").decode().splitlines()
    current_paths = set()
    for line in staged:
        metadata, path = line.split("\t", 1)
        current_paths.add(path)
        oid = metadata.split()[1]
        hashes.add(oid)
        paths[oid] = path
    local_keys = [
        value.encode()
        for name, value in dotenv_values(ROOT / ".env").items()
        if name.endswith("_API_KEY") and value and len(value) >= 16
    ]
    findings, reviewed, blobs = [], [], 0
    # One batch avoids thousands of processes; only object identifiers and
    # finding classes are emitted, never matched values or surrounding text.
    process = subprocess.Popen(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "cat-file", "--batch"],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    try:
        for oid in sorted(hashes):
            process.stdin.write((oid + "\n").encode())
            process.stdin.flush()
            header = process.stdout.readline().decode().split()
            data = process.stdout.read(int(header[2]))
            process.stdout.read(1)
            if header[1] != "blob":
                continue
            blobs += 1
            path = paths.get(oid, "(historical blob)")
            if private_path(path):
                if path in REVIEWED_HISTORY and path not in current_paths:
                    reviewed.append(path)
                else:
                    findings.append({"object": oid[:12], "path": path, "kind": "private path"})
            for kind, pattern in PATTERNS.items():
                if re.search(pattern, data):
                    findings.append({"object": oid[:12], "path": path, "kind": kind})
            if any(key in data for key in local_keys):
                findings.append({"object": oid[:12], "path": path, "kind": "local key value"})
    finally:
        process.stdin.close()
        process.wait(timeout=10)
    result = {
        "reachable_and_index_blobs": blobs,
        "reviewed_history_artifacts": sorted(set(reviewed)),
        "findings": findings,
    }
    print(json.dumps(result, indent=2))
    proof = ROOT / "devpost/screens/repository-audit.json"
    proof.parent.mkdir(parents=True, exist_ok=True)
    proof.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
