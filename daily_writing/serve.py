import asyncio
import functools
import logging
import pathlib
from typing import Any, override

import fastapi
import fastapi.staticfiles
import uvicorn
import watchfiles
import watchfiles.main
import yarl

from daily_writing import build_context

from . import build
from . import settings as settings_module

logger = logging.getLogger("daily_writing")


class WatchFilter(watchfiles.DefaultFilter):
    """Watchers report resolved paths (``/private/tmp`` for ``/tmp`` on macOS), which a
    string prefix match against ``ignore_paths`` would miss."""

    def __init__(self, *, ignored: list[pathlib.Path]):
        super().__init__()
        self.ignored: list[pathlib.Path] = [p.resolve() for p in ignored]

    @override
    def __call__(self, change: watchfiles.Change, path: str) -> bool:
        resolved = pathlib.Path(path).resolve()
        if any(resolved.is_relative_to(ignored) for ignored in self.ignored):
            return False
        return super().__call__(change, path)


def serve(settings: settings_module.CLISettings):
    asyncio.run(serve_async(settings=settings))


async def serve_async(settings: settings_module.CLISettings):
    if not settings.serve:
        raise NotImplementedError()

    # Captured before model_copy() below, which would erase the narrowing above.
    serve_config = settings.serve

    reload_event = asyncio.Event()
    stop_event = asyncio.Event()

    app = fastapi.FastAPI()
    settings = settings.model_copy(
        update={"site_url": yarl.URL("http://localhost:8000")}
    )

    async def websocket_loop(websocket: fastapi.WebSocket):
        await websocket.accept()
        while True:
            reload_task = asyncio.create_task(reload_event.wait())
            stop_task = asyncio.create_task(stop_event.wait())
            async for task in asyncio.as_completed([reload_task, stop_task]):
                if task is reload_task:
                    break
                else:
                    return
            await asyncio.sleep(2)
            await websocket.send_text(data="reload")
            reload_event.clear()

    async def websocket_endpoint(
        websocket: fastapi.WebSocket,
    ):
        try:
            await websocket_loop(websocket=websocket)
        except fastapi.WebSocketDisconnect:
            pass

    settings.build_dir.mkdir(exist_ok=True, parents=True)
    app.websocket("/ws")(websocket_endpoint)
    app.mount(
        "/",
        fastapi.staticfiles.StaticFiles(directory=settings.build_dir, html=True),
    )

    async def ping_websocket(file_changes: set[watchfiles.main.FileChange]) -> None:
        change_paths = sorted(
            str(pathlib.Path(f[1]).relative_to(pathlib.Path.cwd(), walk_up=True))
            for f in file_changes
        )
        logger.info(f"Reloading ({', '.join(change_paths)})")
        reload_event.set()

    # When the shutdown of the server is requested, we set an event that stops all the
    # websockets
    class ShutdownServer(uvicorn.Server):
        @override
        async def shutdown(self, *args: Any, **kwargs: Any):
            stop_event.set()
            await super().shutdown(*args, **kwargs)

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, workers=1)
    server = ShutdownServer(config)

    context = build_context.BuildContext(inject_hot_reload_js=True)

    try:
        await asyncio.gather(
            server.serve(),
            watchfiles.arun_process(
                ".",
                *serve_config.additional_paths,
                watch_filter=WatchFilter(
                    ignored=[settings.build_dir, settings.cache_dir]
                ),
                target=functools.partial(
                    build.build, settings=settings, context=context
                ),
                target_type="function",
                callback=ping_websocket,
            ),
        )
    except asyncio.exceptions.CancelledError:
        return
