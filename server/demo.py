"""A clean recording start that discards only the requesting browser's state."""

from threading import RLock

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from server.credentials import CLIENTS, browser_session
from server.fixes import DETAILS, FIX_LOCKS, RAW_FIXES, RETRIED, SCORED
from server.review import REVIEWS
from server.session import OWNED_SESSIONS

router = APIRouter()
STATE_LOCK = RLock()
RESET_MESSAGE = "This demo session was reset. Start again."


def require_active_owner(owner: str) -> None:
    if owner not in CLIENTS:
        raise HTTPException(409, RESET_MESSAGE)


def clear_browser(owner: str) -> None:
    """Invalidate captured revisions before dropping this browser's registries."""
    with STATE_LOCK:
        client = CLIENTS.pop(owner, None)
        if client is not None:
            client.keys.clear()
            client.selected_provider = None
        for reading_id, review in list(REVIEWS.items()):
            if review.owner == owner:
                del REVIEWS[reading_id]
        # A fix finishing while its parent lock is held may install a child before
        # invalidation acquires that lock. Sweep again to include that new child.
        while owned := [
            (key, value) for key, value in list(OWNED_SESSIONS.items()) if key[0] == owner
        ]:
            for key, session in owned:
                with session.lock:
                    session.revision += 1
                    session.results = None
                    session.review_evidence.clear()
                    session.suggestion_batches.clear()
                    session.ancestors.clear()
                    if OWNED_SESSIONS.get(key) is session:
                        del OWNED_SESSIONS[key]

        def scoped(key: tuple) -> bool:
            return len(key) == 4 and key[0] == owner

        for store in (SCORED, DETAILS, RAW_FIXES, FIX_LOCKS):
            for key in list(store):
                if scoped(key):
                    del store[key]
        RETRIED.difference_update(key for key in list(RETRIED) if scoped(key))


def discard_browser(owner: str) -> str:
    with STATE_LOCK:
        clear_browser(owner)
        return browser_session(None)


@router.post("/api/demo/reset")
def reset_demo(request: Request) -> JSONResponse:
    request.state.owner = discard_browser(request.state.owner)
    return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})
