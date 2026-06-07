import asyncio
import functools
import logging
import pathlib
from typing import Any, override

import fastapi
import fastapi.staticfiles
import pydantic.networks
import uvicorn
import watchfiles
import watchfiles.main

from daily_writing import build_context

from . import build
from . import settings as settings_module

logger = logging.getLogger("daily_writing")


def serve(settings: settings_module.CLISettings):
    asyncio.run(serve_async(settings=settings))


async def serve_async(settings: settings_module.CLISettings):
    if not settings.serve:
        raise NotImplementedError()

    reload_event = asyncio.Event()
    stop_event = asyncio.Event()

    app = fastapi.FastAPI()
    settings.server_url = pydantic.networks.HttpUrl("http://localhost:8000")

    async def websocket_endpoint(
        websocket: fastapi.WebSocket,
    ):
        try:  # noqa: PLW0717
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
                *settings.serve.additional_paths,
                watch_filter=watchfiles.DefaultFilter(
                    ignore_paths=[
                        settings.build_dir.absolute(),
                        settings.cache_dir.absolute(),
                    ]
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
