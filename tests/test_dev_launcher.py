"""Check startup readiness, slow starts, diagnostics and child-server cleanup."""

import os
import socket
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

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


@pytest.mark.parametrize(("name", "status", "body", "expected"), [
    ("API", 200, b'{"status":"ok"}', True),
    ("API", 503, b'{"status":"ok"}', False),
    ("API", 200, b'{"status":"starting"}', False),
    ("API", 200, b'not JSON', False),
    ("Web", 200, b'<html></html>', True),
    ("Web", 503, b'<html></html>', False),
])
def test_readiness_requires_a_successful_http_response(
    monkeypatch, name, status, body, expected
) -> None:
    connection = Mock()
    response = connection.getresponse.return_value
    response.status = status
    response.read.return_value = body
    factory = Mock(return_value=connection)
    monkeypatch.setattr(dev, "HTTPConnection", factory)

    assert dev.endpoint_ready(name, dev.ENDPOINTS[name]) is expected
    factory.assert_called_once_with("127.0.0.1", dev.ENDPOINTS[name], timeout=0.5)
    connection.request.assert_called_once_with("GET", "/api/health" if name == "API" else "/")
    connection.close.assert_called_once()


def test_readiness_retries_a_server_that_is_not_accepting_requests(monkeypatch) -> None:
    connection = Mock()
    connection.request.side_effect = ConnectionRefusedError()
    monkeypatch.setattr(dev, "HTTPConnection", Mock(return_value=connection))
    assert not dev.endpoint_ready("API", 8000)
    connection.close.assert_called_once()


@pytest.fixture
def startup_clock(monkeypatch):
    clock = SimpleNamespace(now=0.0)

    def sleep(seconds):
        clock.now += seconds

    monkeypatch.setattr(dev, "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep))
    return clock


def test_slow_api_is_allowed_to_start_after_twenty_seconds(
    monkeypatch, capsys, startup_clock
) -> None:
    servers = {name: SimpleNamespace(poll=lambda: None) for name in dev.ENDPOINTS}
    monkeypatch.setattr(
        dev, "endpoint_ready", lambda name, _port: name == "Web" or startup_clock.now >= 25
    )
    assert dev.wait_for_servers(servers)
    assert startup_clock.now >= 25
    output = capsys.readouterr()
    assert "Still starting: API" in output.out
    assert "Still starting: Web" not in output.out
    assert not output.err


def test_timeout_names_the_server_still_pending(monkeypatch, capsys, startup_clock) -> None:
    servers = {name: SimpleNamespace(poll=lambda: None) for name in dev.ENDPOINTS}
    monkeypatch.setattr(dev, "endpoint_ready", lambda name, _port: name == "Web")
    assert not dev.wait_for_servers(servers, timeout=2)
    assert "Startup timed out after 2 seconds. Still waiting for: API." in capsys.readouterr().err


def test_early_exit_names_the_server_and_exit_code(capsys) -> None:
    assert not dev.wait_for_servers({"API": SimpleNamespace(poll=lambda: 7)})
    assert "API server exited during startup (exit code 7)." in capsys.readouterr().err


def test_failed_startup_stops_both_servers(monkeypatch) -> None:
    processes = [Mock(), Mock()]
    start = Mock(side_effect=processes)
    stop = Mock()
    monkeypatch.setattr(dev, "port_in_use", lambda _port: False)
    monkeypatch.setattr(dev, "start_process", start)
    monkeypatch.setattr(dev, "wait_for_servers", lambda _servers: False)
    monkeypatch.setattr(dev, "stop_processes", stop)
    monkeypatch.setattr(dev.signal, "signal", Mock())

    assert dev.main() == 1
    stop.assert_called_once_with(processes)


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
