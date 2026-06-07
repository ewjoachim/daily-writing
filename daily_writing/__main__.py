import logging

from . import build, normalize
from . import settings as settings_module


class NoCommandSelected(Exception):
    pass


class MissingExtraDependency(Exception):
    pass


def main():
    settings = settings_module.CLISettings()  # pyright: ignore[reportCallIssue]
    logging.basicConfig(level=settings.verbosity)
    logging.getLogger("fontTools").setLevel("WARNING")
    logging.getLogger("markdown_it.rules_block").setLevel("INFO")

    match settings.subcommand:
        case settings_module.Build():
            build.build(settings=settings)
        case settings_module.Serve():
            serve_website(settings=settings)
        case settings_module.Normalize():
            normalize.normalize(settings=settings)
        case None:
            raise NoCommandSelected("No command selected")


def serve_website(settings: settings_module.CLISettings):
    try:
        from . import serve  # noqa: PLC0415
    except ImportError as exc:
        raise MissingExtraDependency(
            "Extra dependencies `server` is required for daily-writing serve (`pip install daily-writing[server]`)"
        ) from exc

    serve.serve(settings=settings)


if __name__ == "__main__":
    main()
