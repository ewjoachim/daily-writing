from __future__ import annotations

from . import build
from . import settings as settings_module


def main():
    settings = settings_module.Settings()  # pyright: ignore[reportCallIssue]

    match settings.subcommand:
        case settings_module.Build():
            build.build(settings=settings)
        case settings_module.Serve():
            serve_website(settings=settings)


def serve_website(settings: settings_module.Settings):
    try:
        from . import serve
    except ImportError:
        raise Exception(
            "Extra dependencies `server` is required for daily-writing serve (`pip install daily-writing[server]`)"
        )

    serve.serve(settings=settings)


if __name__ == "__main__":
    main()
