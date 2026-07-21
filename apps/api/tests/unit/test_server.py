import asyncio
import sys

import uvicorn
from pytest import MonkeyPatch

from fruit_agent import server


def test_windows_server_selects_database_compatible_event_loop(
    monkeypatch: MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        asyncio,
        "set_event_loop_policy",
        lambda policy: observed.update(policy=policy),
    )
    monkeypatch.setattr(
        uvicorn,
        "run",
        lambda app, **kwargs: observed.update(app=app, kwargs=kwargs),
    )

    server.run()

    assert isinstance(observed["policy"], asyncio.WindowsSelectorEventLoopPolicy)
    assert observed["app"] == "fruit_agent.app:app"
    assert observed["kwargs"] == {"host": "127.0.0.1", "port": 8000}
