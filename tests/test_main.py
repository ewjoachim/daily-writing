import types

import pytest

from daily_writing import __main__ as main_module
from daily_writing import settings as settings_module


def test_main__parses_then_dispatches(monkeypatch):
    fake_settings = types.SimpleNamespace(verbosity="INFO", subcommand=None)
    seen = {}
    monkeypatch.setattr(
        main_module.settings_module, "CLISettings", lambda: fake_settings
    )
    monkeypatch.setattr(
        main_module, "run", lambda settings: seen.setdefault("s", settings)
    )

    main_module.main()

    assert seen["s"] is fake_settings


def test_run__build(monkeypatch):
    called = {}
    monkeypatch.setattr(
        main_module.build,
        "build",
        lambda settings: called.setdefault("build", settings),
    )

    main_module.run(types.SimpleNamespace(subcommand=settings_module.Build()))

    assert "build" in called


def test_run__serve(monkeypatch):
    called = {}
    monkeypatch.setattr(
        main_module, "serve_website", lambda settings: called.setdefault("serve", True)
    )

    main_module.run(types.SimpleNamespace(subcommand=settings_module.Serve()))

    assert called == {"serve": True}


def test_run__normalize(monkeypatch):
    called = {}
    monkeypatch.setattr(
        main_module.normalize,
        "normalize",
        lambda settings: called.setdefault("normalize", True),
    )

    main_module.run(types.SimpleNamespace(subcommand=settings_module.Normalize()))

    assert called == {"normalize": True}


def test_run__no_command():
    with pytest.raises(main_module.NoCommandSelected):
        main_module.run(types.SimpleNamespace(subcommand=None))


def test_serve_website__delegates(monkeypatch):
    called = {}
    monkeypatch.setattr(
        "daily_writing.serve.serve",
        lambda settings: called.setdefault("serve", settings),
    )

    main_module.serve_website(settings="SENTINEL")

    assert called["serve"] == "SENTINEL"
