"""Run the FastAPI API and Vite front end together for local development."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS = {"API": 8000, "Web": 5173}


def port_in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def start_process(command: list[str], env: dict[str, str]) -> subprocess.Popen[bytes]:
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    return subprocess.Popen(command, cwd=ROOT, env=env, **options)


def stop_processes(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            try:
                if os.name == "nt":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(process.pid, signal.SIGTERM)
            except OSError:
                pass  # The process may have exited between poll and signal.
    for process in processes:
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)


def main() -> int:
    busy = [(name, port) for name, port in ENDPOINTS.items() if port_in_use(port)]
    if busy:
        for name, port in busy:
            print(f"{name} port {port} is already in use.", file=sys.stderr)
        print(
            "If the app is already running, open http://127.0.0.1:5173/. "
            "Otherwise stop the other server and try again.",
            file=sys.stderr,
        )
        return 1
    if os.name == "nt":
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(ROOT / ".uv-cache"))
    commands = [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        [
            "node",
            str(ROOT / "node_modules" / "vite" / "bin" / "vite.js"),
            "--host",
            "127.0.0.1",
            "--port",
            "5173",
            "--strictPort",
        ],
    ]
    processes: list[subprocess.Popen[bytes]] = []
    try:
        for command in commands:
            processes.append(start_process(command, env))
        print("Starting the API and web server...", flush=True)
        deadline = time.monotonic() + 20
        while all(process.poll() is None for process in processes):
            if all(port_in_use(port) for port in ENDPOINTS.values()):
                print("API: http://127.0.0.1:8000  ·  Web: http://127.0.0.1:5173", flush=True)
                break
            if time.monotonic() >= deadline:
                print("The servers did not become ready within 20 seconds.", file=sys.stderr)
                return 1
            time.sleep(0.1)
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
        return next(
            (process.returncode or 1 for process in processes if process.poll() is not None), 0
        )
    except KeyboardInterrupt:
        return 0
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    sys.exit(main())
