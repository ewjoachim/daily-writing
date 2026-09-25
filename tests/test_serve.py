import asyncio
import types

import pytest
import watchfiles

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


def test_watch_filter__ignores_resolved_paths(tmp_path):
    real = tmp_path / "real"
    (real / "_build").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real)
    watch_filter = serve.WatchFilter(ignored=[link / "_build"])

    assert not watch_filter(watchfiles.Change.added, str(real / "_build" / "a.html"))
    assert watch_filter(watchfiles.Change.added, str(real / "source.md"))


def test_watch_filter__keeps_default_filtering(tmp_path):
    watch_filter = serve.WatchFilter(ignored=[])

    assert not watch_filter(watchfiles.Change.added, str(tmp_path / ".git" / "HEAD"))
