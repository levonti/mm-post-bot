import asyncio
import runpy
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import Any, ClassVar, cast

from mm_post_bot import __main__ as entrypoint
from mm_post_bot.config import Settings
from mm_post_bot.dispatcher import CommandContextFactory, MessageRouter


class FakeConn:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeMattermostClient:
    instances: ClassVar[list[FakeMattermostClient]] = []

    def __init__(
        self,
        rest_base: str,
        token: str,
        *,
        verify_ssl: bool = True,
    ) -> None:
        self.rest_base = rest_base
        self.token = token
        self.verify_ssl = verify_ssl
        self.closed = False
        FakeMattermostClient.instances.append(self)

    async def get_me(self) -> dict[str, Any]:
        return {"id": "manager-id", "username": "postbot"}

    async def aclose(self) -> None:
        self.closed = True


def _settings() -> Settings:
    return Settings(
        mm_url="https://mm.internal/i",
        mm_bot_token="manager-token",
        mm_admins="alice",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key="0" * 44,
        mm_verify_ssl=False,
    )


async def test_main_bootstraps_runtime_and_closes_resources(monkeypatch):
    conn = FakeConn()
    calls: list[Any] = []

    async def fake_listen_events(settings: Settings) -> AsyncIterator[dict[str, Any]]:
        calls.append(("listen", settings.db_url))
        yield {"event": "posted", "data": {"post": '{"user_id":"alice-id"}'}}

    async def fake_handle_event(
        event: Mapping[str, Any],
        *,
        router: MessageRouter,
        context_factory: CommandContextFactory,
    ) -> None:
        calls.append(
            (
                "handle",
                event["event"],
                router.extract_command({"user_id": "manager-id", "message": "!status"}, "D"),
                context_factory.from_post({"user_id": "alice-id"}, "D").manager_user_id,
            )
        )

    monkeypatch.setattr(entrypoint, "load_settings", _settings)
    monkeypatch.setattr(entrypoint, "configure_logging", lambda level: calls.append(("log", level)))
    monkeypatch.setattr(
        entrypoint,
        "connect_postgres",
        lambda dsn: calls.append(("connect", dsn)) or conn,
    )
    monkeypatch.setattr(
        entrypoint,
        "init_schema",
        lambda used_conn: calls.append(("schema", used_conn)),
    )
    monkeypatch.setattr(entrypoint, "MattermostClient", FakeMattermostClient)
    monkeypatch.setattr(entrypoint, "listen_events", fake_listen_events)
    monkeypatch.setattr(entrypoint, "handle_event", fake_handle_event)

    await entrypoint.main()

    assert calls == [
        ("log", "INFO"),
        ("connect", "postgresql://mm_post:secret@postgres/mm_post_bot"),
        ("schema", conn),
        ("listen", "postgresql://mm_post:secret@postgres/mm_post_bot"),
        ("handle", "posted", None, "manager-id"),
    ]
    assert FakeMattermostClient.instances[0].rest_base == "https://mm.internal/i/api/v4"
    assert FakeMattermostClient.instances[0].token == "manager-token"
    assert FakeMattermostClient.instances[0].verify_ssl is False
    assert FakeMattermostClient.instances[0].closed is True
    assert conn.closed is True


async def test_event_loop_spawns_handlers_without_blocking_iteration(monkeypatch):
    started_first_handler = asyncio.Event()
    release_first_handler = asyncio.Event()
    handled: list[int] = []

    async def fake_listen_events(settings: Settings) -> AsyncIterator[dict[str, Any]]:
        yield {"id": 1}
        await started_first_handler.wait()
        yield {"id": 2}
        release_first_handler.set()

    async def fake_handle_event(
        event: Mapping[str, Any],
        *,
        router: MessageRouter,
        context_factory: CommandContextFactory,
    ) -> None:
        handled.append(cast(int, event["id"]))
        if event["id"] == 1:
            started_first_handler.set()
            await release_first_handler.wait()

    monkeypatch.setattr(entrypoint, "listen_events", fake_listen_events)
    monkeypatch.setattr(entrypoint, "handle_event", fake_handle_event)

    await asyncio.wait_for(
        entrypoint._serve_events(
            _settings(),
            router=cast(MessageRouter, object()),
            context_factory=cast(CommandContextFactory, object()),
        ),
        timeout=1,
    )

    assert handled == [1, 2]


def test_module_execution_calls_run(monkeypatch):
    called: list[str] = []

    monkeypatch.setattr("asyncio.run", lambda coro: called.append("run") or coro.close())

    runpy.run_path(str(Path(entrypoint.__file__).resolve()), run_name="__main__")

    assert called == ["run"]
