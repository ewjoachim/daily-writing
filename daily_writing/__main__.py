from __future__ import annotations

import logging

from . import build
from . import settings as settings_module


def main():
    logging.basicConfig(level="INFO")
    logging.getLogger("fontTools").setLevel("WARNING")
    settings = settings_module.Settings()  # pyright: ignore[reportCallIssue]

    match settings.subcommand:
        case settings_module.Build():
            build.build(settings=settings)
        case settings_module.Serve():
            serve_website(settings=settings)
        case None:
            raise Exception("No command selected")


def serve_website(settings: settings_module.Settings):
    try:
        from . import serve  # noqa: PLC0415
    except ImportError as exc:
        raise Exception(
            "Extra dependencies `server` is required for daily-writing serve (`pip install daily-writing[server]`)"
        ) from exc

    serve.serve(settings=settings)


if __name__ == "__main__":
    main()
