"""get_current_user must not block the event loop.

Its DB lookup is synchronous. Declared `async def`, it ran on the event loop, so
a slow checkout (e.g. an exhausted connection pool waiting out its 30s timeout)
froze every request in the process, /health included.
"""

import asyncio
import time
from unittest.mock import MagicMock

import httpx
from fastapi import Depends, FastAPI

from app.database import get_db
from app.models.user import User, UserRole
from app.utils.security import create_access_token, get_current_user

DB_STALL_SECONDS = 1.0


def _stalling_session() -> MagicMock:
    """A session whose query blocks, like waiting on a drained pool."""
    user = User(username="stalled", role=UserRole.VOTER, is_active=True)

    def stall(*args, **kwargs):
        time.sleep(DB_STALL_SECONDS)
        query = MagicMock()
        query.filter.return_value.first.return_value = user
        return query

    session = MagicMock()
    session.query.side_effect = stall
    return session


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    @app.get("/whoami")
    def whoami(user: User = Depends(get_current_user)):
        return {"username": user.username}

    app.dependency_overrides[get_db] = lambda: _stalling_session()
    return app


def test_slow_auth_lookup_does_not_block_other_requests():
    app = _build_app()
    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'stalled'})}"}

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Timed from before the stalled request is scheduled: a blocked loop
            # also delays the sleep below, so timing only /ping would miss it.
            start = time.monotonic()
            slow = asyncio.create_task(client.get("/whoami", headers=headers))
            await asyncio.sleep(0.1)  # let the auth lookup start and stall

            pong = await client.get("/ping")
            ping_seconds = time.monotonic() - start

            me = await slow
            return pong, ping_seconds, me

    # A private loop, not asyncio.run(): that would clear the main thread's
    # current loop and break later tests that call asyncio.get_event_loop().
    loop = asyncio.new_event_loop()
    try:
        pong, ping_seconds, me = loop.run_until_complete(scenario())
    finally:
        loop.close()

    assert pong.status_code == 200
    assert me.status_code == 200 and me.json() == {"username": "stalled"}
    # With the lookup on the event loop, /ping cannot answer until the stall ends.
    assert ping_seconds < DB_STALL_SECONDS / 2, ping_seconds
