from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..config import Settings
from ..db import DbConn, connect_postgres, init_schema
from .api import api_router
from .deps import current_session
from .routes import router


def _spa_index(web_dir: Path) -> Path:
    return web_dir / "static" / "spa" / "index.html"


def create_app_from_settings(settings: Settings) -> FastAPI:
    conn = connect_postgres(settings.db_url)
    try:
        init_schema(conn)
    except Exception:
        conn.close()
        raise
    return create_app(settings=settings, conn=conn, owns_conn=True)


def create_app(
    settings: Settings,
    conn: DbConn,
    *,
    owns_conn: bool = False,
    web_dir: Path | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owns_conn:
                app.state.conn.close()

    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.state.conn = conn

    resolved_web_dir = web_dir or Path(__file__).parent
    app.mount("/static", StaticFiles(directory=resolved_web_dir / "static"), name="static")
    spa_dir = resolved_web_dir / "static" / "spa"
    spa_assets_dir = spa_dir / "assets"
    app.include_router(api_router)
    app.include_router(router)

    if _spa_index(resolved_web_dir).is_file() and spa_assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=spa_assets_dir), name="spa-assets")
        app.mount(
            "/app/assets",
            StaticFiles(directory=spa_assets_dir),
            name="spa-preview-assets",
        )

        @app.get("/")
        @app.get("/drafts")
        @app.get("/drafts/{path:path}")
        @app.get("/targets")
        @app.get("/audit")
        @app.get("/app")
        @app.get("/app/{path:path}")
        def react_app(
            _session: Annotated[object, Depends(current_session)],
            path: str = "",
        ) -> FileResponse:
            return FileResponse(_spa_index(resolved_web_dir))

    return app
