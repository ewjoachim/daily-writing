import asyncio
import functools
import pathlib
from typing import Any, override

import fastapi
import fastapi.staticfiles
import uvicorn
import watchfiles
import watchfiles.main

from . import build
from . import settings as settings_module


def serve(settings: settings_module.Settings):
    asyncio.run(serve_async(settings=settings))


async def serve_async(settings: settings_module.Settings):
    reload_event = asyncio.Event()
    stop_event = asyncio.Event()

    app = fastapi.FastAPI()

    async def websocket_endpoint(
        websocket: fastapi.WebSocket,
    ):
        try:
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
            str(pathlib.Path(f[1]).relative_to(pathlib.Path.cwd()))
            for f in file_changes
        )
        print(f"Reloading ({', '.join(change_paths)})")
        reload_event.set()

    # When the shutdown of the server is requested, we set an event that stops all the
    # websockets
    class ShutdownServer(uvicorn.Server):
        @override
        async def shutdown(self, *args: Any, **kwargs: Any):
            stop_event.set()
            await super().shutdown(*args, **kwargs)

    config = uvicorn.Config(app, host="0.0.0.0", port=8000, workers=1)
    server = ShutdownServer(config)

    settings.inject_hot_reload_js = True

    try:
        await asyncio.gather(
            server.serve(),
            watchfiles.arun_process(
                ".",
                watch_filter=watchfiles.DefaultFilter(
                    ignore_paths=[settings.build_dir.absolute()]
                ),
                target=functools.partial(build.build, settings=settings),
                target_type="function",
                callback=ping_websocket,
            ),
        )
    except asyncio.exceptions.CancelledError:
        return
