import asyncio
import types

import pytest

from daily_writing import serve


def test_serve_async__not_implemented_without_subcommand():
    settings = types.SimpleNamespace(serve=None)

    with pytest.raises(NotImplementedError):
        asyncio.run(serve.serve_async(settings=settings))


def test_serve_delegates_to_serve_async(monkeypatch):
    received = {}

    async def fake_serve_async(settings):
        received["settings"] = settings

    monkeypatch.setattr(serve, "serve_async", fake_serve_async)

    serve.serve(settings="SENTINEL")

    assert received["settings"] == "SENTINEL"
