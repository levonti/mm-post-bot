from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..config import Settings
from ..db import DbConn, connect_postgres, init_schema
from .api import api_router
from .routes import router


def create_app_from_settings(settings: Settings) -> FastAPI:
    conn = connect_postgres(settings.db_url)
    try:
        init_schema(conn)
    except Exception:
        conn.close()
        raise
    return create_app(settings=settings, conn=conn, owns_conn=True)


def create_app(settings: Settings, conn: DbConn, *, owns_conn: bool = False) -> FastAPI:
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

    web_dir = Path(__file__).parent
    app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")
    app.include_router(api_router)
    app.include_router(router)
    return app
