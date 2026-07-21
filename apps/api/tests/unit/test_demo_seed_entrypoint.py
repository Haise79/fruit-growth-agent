import asyncio
import sys
from collections.abc import Coroutine
from typing import Any

from pytest import MonkeyPatch

from fruit_agent.demo import seed


def test_windows_seed_uses_selector_event_loop(monkeypatch: MonkeyPatch) -> None:
    observed: dict[str, object] = {}

    def fake_run(
        coroutine: Coroutine[Any, Any, None],
        *,
        debug: bool | None = None,
        loop_factory: object = None,
    ) -> None:
        del debug
        observed["loop_factory"] = loop_factory
        coroutine.close()

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(asyncio, "run", fake_run)

    seed.run()

    assert observed["loop_factory"] is asyncio.SelectorEventLoop
