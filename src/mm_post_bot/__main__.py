import asyncio
from collections.abc import Mapping
from typing import Any

from mm_post_bot.config import Settings, load_settings
from mm_post_bot.db import DbConn, connect_postgres, init_schema
from mm_post_bot.dispatcher import CommandContextFactory, MessageRouter, handle_event
from mm_post_bot.logging import configure_logging, get_logger
from mm_post_bot.mm_client import MattermostClient
from mm_post_bot.ws_listener import listen_events

logger = get_logger(__name__)


async def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    conn = connect_postgres(settings.db_url)
    manager_mm: MattermostClient | None = None
    try:
        init_schema(conn)
        manager_mm = MattermostClient(
            settings.mm_rest_base,
            settings.mm_bot_token,
            verify_ssl=settings.mm_verify_ssl,
        )
        manager_me = await manager_mm.get_me()
        manager_user_id = str(manager_me["id"])
        manager_username = str(manager_me["username"])

        router = MessageRouter(
            manager_user_id=manager_user_id,
            manager_username=manager_username,
        )
        context_factory = CommandContextFactory(
            conn=conn,
            settings=settings,
            manager_mm=manager_mm,
            manager_user_id=manager_user_id,
        )

        logger.info(
            "runtime_started",
            manager_user_id=manager_user_id,
            manager_username=manager_username,
        )
        await _serve_events(settings, router=router, context_factory=context_factory)
    finally:
        await _close_manager(manager_mm)
        _close_db(conn)


async def _serve_events(
    settings: Settings,
    *,
    router: MessageRouter,
    context_factory: CommandContextFactory,
) -> None:
    tasks: set[asyncio.Task[None]] = set()

    try:
        async for event in listen_events(settings):
            task = asyncio.create_task(
                _handle_event_logged(event, router=router, context_factory=context_factory)
            )
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    except asyncio.CancelledError:
        await _cancel_pending_tasks(tasks)
        raise
    except Exception:
        await _cancel_pending_tasks(tasks)
        raise
    else:
        if tasks:
            await asyncio.gather(*tasks)


async def _handle_event_logged(
    event: Mapping[str, Any],
    *,
    router: MessageRouter,
    context_factory: CommandContextFactory,
) -> None:
    try:
        await handle_event(event, router=router, context_factory=context_factory)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("event_handler_failed", error=str(exc))


async def _cancel_pending_tasks(tasks: set[asyncio.Task[None]]) -> None:
    if not tasks:
        return

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def _close_manager(manager_mm: MattermostClient | None) -> None:
    if manager_mm is None:
        return
    await manager_mm.aclose()


def _close_db(conn: DbConn) -> None:
    conn.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
