from types import SimpleNamespace
from typing import Any, cast

import pytest

from mm_post_bot.commands import CommandContext, dispatch
from mm_post_bot.config import Settings
from mm_post_bot.dispatcher import (
    CommandContextFactory,
    MessageRouter,
    handle_draft_body,
    handle_event,
    redact_command_for_log,
)
from mm_post_bot.security import hash_message

VALID_FERNET_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="


class _UnusedContextFactory:
    def from_post(self, post, channel_type):
        raise AssertionError("context factory should not be called")


class _UserRepo:
    def __init__(self, status: str | None) -> None:
        self.status = status

    def get(self, user_id: str):
        if self.status is None:
            raise LookupError(user_id)
        return SimpleNamespace(status=self.status)


class _PreferenceConn:
    def execute(self, sql: str, params: Any = ()) -> SimpleNamespace:
        return SimpleNamespace(fetchone=lambda: None)


class _DraftCaptureRepo:
    def __init__(self, active: bool) -> None:
        self.active = active
        self.cleared: list[str] = []

    def get_active(self, owner_user_id: str, *, now):
        if not self.active:
            return None
        return SimpleNamespace(owner_user_id=owner_user_id)

    def clear(self, owner_user_id: str) -> None:
        self.cleared.append(owner_user_id)
        self.active = False


class _PostDraftRepo:
    def __init__(self) -> None:
        self.created: list[dict[str, str]] = []

    def create(self, *, owner_user_id: str, message: str, message_sha256: str):
        self.created.append(
            {
                "owner_user_id": owner_user_id,
                "message": message,
                "message_sha256": message_sha256,
            }
        )
        return SimpleNamespace(id=42)


def _draft_body_ctx(
    *,
    user_status: str | None = "approved",
    active_capture: bool = True,
    locale: str = "en",
):
    return CommandContext(
        caller_user_id="alice-id",
        caller_username="alice",
        channel_id="dm-channel",
        channel_type="D",
        user_repo=cast(Any, _UserRepo(user_status)),
        user_preference_repo=cast(Any, object()),
        user_bot_repo=cast(Any, object()),
        user_channel_repo=cast(Any, object()),
        user_post_default_repo=cast(Any, object()),
        draft_capture_repo=cast(Any, _DraftCaptureRepo(active_capture)),
        post_draft_repo=cast(Any, _PostDraftRepo()),
        audit_repo=cast(Any, object()),
        manager_mm=cast(Any, object()),
        manager_user_id="manager-id",
        admin_usernames=frozenset(),
        mm_rest_base="https://mm.internal/api/v4",
        mm_url="https://mm.internal",
        token_encryption_key="key",
        mm_verify_ssl=True,
        default_locale="en",
        locale=locale,
    )


def test_dm_is_command():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "u1", "message": "!help"}, "D") == "!help"


def test_channel_mention_is_command():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    post = {"user_id": "u1", "message": "@postbot !status"}
    assert router.extract_command(post, "O") == "!status"


def test_channel_without_mention_is_ignored():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "u1", "message": "!status"}, "O") is None


def test_self_message_is_ignored():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "mgr", "message": "!help"}, "D") is None


def test_non_command_dm_can_be_draft_body():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "u1", "message": "draft body"}, "D") is None
    post = {"user_id": "u1", "message": "draft body"}
    assert router.extract_draft_body(post, "D") == "draft body"


def test_draft_body_only_in_dm():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_draft_body({"user_id": "u1", "message": "draft body"}, "O") is None


def test_context_factory_normalizes_sender_name_username():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="levonti",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
    )
    factory = CommandContextFactory(
        conn=cast(Any, _PreferenceConn()),
        settings=settings,
        manager_mm=cast(Any, object()),
        manager_user_id="mgr",
    )

    ctx = factory.from_post({"user_id": "u1", "sender_name": "@levonti"}, "D")

    assert ctx.caller_username == "levonti"


def test_redacts_bot_add_token():
    assert redact_command_for_log("!bot add news secret-token") == "!bot add news [REDACTED]"


async def test_malformed_post_json_is_ignored():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    event = {"event": "posted", "data": {"post": "{bad", "channel_type": "D"}}

    response = await handle_event(
        event,
        router=router,
        context_factory=cast(CommandContextFactory, _UnusedContextFactory()),
    )

    assert response is None


async def test_dispatch_returns_parse_error_for_malformed_shell_syntax():
    response = await dispatch(_draft_body_ctx(), '!help "unterminated')

    assert response == "Could not parse command: No closing quotation"


async def test_handle_draft_body_saves_active_capture():
    ctx = _draft_body_ctx()

    response = await handle_draft_body(ctx, "hello from the draft")

    assert response is not None
    assert "Draft #42 saved" in response
    assert "!send 42" in response
    assert "!send 42 --bot <alias> --channel <channel_alias>" in response
    post_draft_repo = cast(_PostDraftRepo, ctx.post_draft_repo)
    assert post_draft_repo.created == [
        {
            "owner_user_id": "alice-id",
            "message": "hello from the draft",
            "message_sha256": hash_message("hello from the draft"),
        }
    ]
    assert cast(_DraftCaptureRepo, ctx.draft_capture_repo).cleared == ["alice-id"]


async def test_handle_draft_body_uses_selected_locale():
    ctx = _draft_body_ctx(locale="ru")

    response = await handle_draft_body(ctx, "текст черновика")

    assert response is not None
    assert response.startswith("Черновик #42 сохранён.")
    assert "!send 42" in response
    assert "!send 42 --bot <alias> --channel <channel_alias>" in response


async def test_handle_draft_body_ignores_dm_without_active_capture():
    ctx = _draft_body_ctx(active_capture=False)

    response = await handle_draft_body(ctx, "hello from the draft")

    assert response is None
    assert cast(_PostDraftRepo, ctx.post_draft_repo).created == []
    assert cast(_DraftCaptureRepo, ctx.draft_capture_repo).cleared == []


@pytest.mark.parametrize(
    ("user_status", "expected"),
    [
        ("pending", "pending approval"),
        ("blocked", "blocked"),
        (None, "!register"),
    ],
)
async def test_handle_draft_body_requires_approved_user(user_status: str | None, expected: str):
    ctx = _draft_body_ctx(user_status=user_status)

    response = await handle_draft_body(ctx, "pending user draft")

    assert response is not None
    assert expected in response.lower()
    assert cast(_PostDraftRepo, ctx.post_draft_repo).created == []
    assert cast(_DraftCaptureRepo, ctx.draft_capture_repo).cleared == []
