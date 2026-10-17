"""Do not start a duplicate app or leave child servers behind after stopping."""

import os
import socket
import subprocess
import sys
import time

from scripts import dev


def test_api_can_start_without_loading_the_solver() -> None:
    probe = subprocess.run(
        [sys.executable, "-c", """
import sys
from server.main import health
assert health() == {"status": "ok"}
assert "server.checker.solver" not in sys.modules
assert not {"ortools", "numpy", "pandas"}.intersection(sys.modules)
"""],
        cwd=dev.ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert probe.returncode == 0, probe.stderr


def test_busy_port_rejects_start_without_spawning(monkeypatch, capsys) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        monkeypatch.setattr(dev, "ENDPOINTS", {"API": port})

        def must_not_spawn(*_args):
            raise AssertionError("A duplicate run must not start another server")

        monkeypatch.setattr(dev, "start_process", must_not_spawn)
        assert dev.main() == 1
        assert f"API port {port} is already in use." in capsys.readouterr().err


def test_shutdown_stops_the_child_server_as_well_as_its_parent(tmp_path) -> None:
    ready = tmp_path / "ready-port.txt"
    child = f"""
import os, signal, socket, time
from pathlib import Path
if os.name == 'nt':
    signal.signal(signal.SIGBREAK, signal.default_int_handler)
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    Path({str(ready)!r}).write_text(str(listener.getsockname()[1]))
    try:
        time.sleep(60)
    except KeyboardInterrupt:
        pass
"""
    parent = f"""
import os, signal, subprocess, sys, time
if os.name == 'nt':
    signal.signal(signal.SIGBREAK, signal.default_int_handler)
subprocess.Popen([sys.executable, '-c', {child!r}])
try:
    time.sleep(60)
except KeyboardInterrupt:
    pass
"""
    process = dev.start_process([sys.executable, "-c", parent], os.environ.copy())
    try:
        deadline = time.monotonic() + 8
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists(), "Child server did not start"
        port = int(ready.read_text())
        assert dev.port_in_use(port)
    finally:
        dev.stop_processes([process])
    deadline = time.monotonic() + 3
    while dev.port_in_use(port) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert process.poll() is not None
    assert not dev.port_in_use(port), "The child server was left running"
