"""An isolated local preview that cannot accidentally make provider requests."""

import socket
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@contextmanager
def local_preview():
    import uvicorn

    from server.main import app

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    with (
        patch(
            "server.ai.adapter.read_plan",
            side_effect=AssertionError("Capture must use saved reading"),
        ),
        patch(
            "server.ai.adapter.suggest_fixes",
            side_effect=AssertionError("Capture must use saved suggestions"),
        ),
    ):
        worker.start()
        try:
            yield f"http://127.0.0.1:{listener.getsockname()[1]}"
        finally:
            server.should_exit = True
            worker.join(timeout=10)
            listener.close()
