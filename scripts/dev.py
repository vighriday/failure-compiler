"""Run the FastAPI API and Vite front end together for local development."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from http.client import HTTPConnection, HTTPException
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS = {"API": 8000, "Web": 5173}
STARTUP_TIMEOUT = 90
PROGRESS_INTERVAL = 5


def port_in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def endpoint_ready(name: str, port: int) -> bool:
    """A listening socket alone does not mean the app can serve a request."""
    connection = HTTPConnection("127.0.0.1", port, timeout=0.5)
    try:
        connection.request("GET", "/api/health" if name == "API" else "/")
        response = connection.getresponse()
        if response.status != 200:
            return False
        return name != "API" or json.loads(response.read()) == {"status": "ok"}
    except (OSError, HTTPException, ValueError):
        return False
    finally:
        connection.close()


def wait_for_servers(
    servers: dict[str, subprocess.Popen[bytes]], timeout: float = STARTUP_TIMEOUT
) -> bool:
    started = time.monotonic()
    next_progress = started + PROGRESS_INTERVAL
    while True:
        for name, process in servers.items():
            code = process.poll()
            if code is not None:
                print(
                    f"{name} server exited during startup (exit code {code}). "
                    "Check its output above.",
                    file=sys.stderr,
                    flush=True,
                )
                return False
        pending = [name for name in servers if not endpoint_ready(name, ENDPOINTS[name])]
        if not pending:
            return True
        now = time.monotonic()
        elapsed = now - started
        if elapsed >= timeout:
            print(
                f"Startup timed out after {timeout:g} seconds. "
                f"Still waiting for: {', '.join(pending)}. Check its output above.",
                file=sys.stderr,
                flush=True,
            )
            return False
        if now >= next_progress:
            print(
                f"Still starting: {', '.join(pending)} "
                f"({elapsed:.0f}s elapsed; allowing up to {timeout:g}s).",
                flush=True,
            )
            next_progress = now + PROGRESS_INTERVAL
        time.sleep(0.1)


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
    env["PYTHONUNBUFFERED"] = "1"
    commands = {
        "API": [
            sys.executable,
            "-m",
            "uvicorn",
            "server.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        "Web": [
            "node",
            str(ROOT / "node_modules" / "vite" / "bin" / "vite.js"),
            "--host",
            "127.0.0.1",
            "--port",
            "5173",
            "--strictPort",
        ],
    }
    servers: dict[str, subprocess.Popen[bytes]] = {}
    try:
        print(f"Starting the API and web server (up to {STARTUP_TIMEOUT} seconds)...", flush=True)
        for name, command in commands.items():
            try:
                servers[name] = start_process(command, env)
            except OSError as error:
                print(f"Could not start {name} server: {error}", file=sys.stderr)
                return 1
        if not wait_for_servers(servers):
            return 1
        print("API: http://127.0.0.1:8000 | Web: http://127.0.0.1:5173", flush=True)
        while all(process.poll() is None for process in servers.values()):
            time.sleep(0.25)
        for name, process in servers.items():
            if process.poll() is not None:
                print(f"{name} server stopped (exit code {process.returncode}).", file=sys.stderr)
                return process.returncode or 1
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        stop_processes(list(servers.values()))


if __name__ == "__main__":
    sys.exit(main())
