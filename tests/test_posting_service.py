import pytest
from test_commands import CommandFixture
from test_commands import ctx as _commands_ctx
from test_commands import pg_conn as _commands_pg_conn

from mm_post_bot.repository import UserBot, UserChannel
from mm_post_bot.security import encrypt_token, hash_message
from mm_post_bot.services.posting import (
    DraftMessageEmpty,
    PublishDraftRequest,
    PublishError,
    TargetRequest,
    create_draft,
    list_target_options,
    publish_draft,
    update_draft_message,
)

ctx = _commands_ctx
pg_conn = _commands_pg_conn


def _approved(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    return ctx.make("alice-id", "alice")


def _bot_and_channel(ctx: CommandFixture) -> tuple[UserBot, UserChannel]:
    command_ctx = ctx.make("alice-id", "alice")
    bot = ctx.user_bots.add(
        owner_user_id="alice-id",
        alias="news",
        bot_user_id="bot-id",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext=encrypt_token("secret-token", command_ctx.token_encryption_key),
        token_fingerprint="secret-token-fp",
    )
    channel = ctx.user_channels.add(
        owner_user_id="alice-id",
        alias="town",
        channel_id="channel-id",
    )
    ctx.user_post_defaults.set_for_owner(
        "alice-id",
        bot_alias="news",
        channel_alias="town",
    )
    return bot, channel


def test_create_draft_strips_empty_messages(ctx: CommandFixture):
    command_ctx = _approved(ctx)

    with pytest.raises(DraftMessageEmpty):
        create_draft(command_ctx, "   \n  ")


def test_create_and_update_draft_hashes_messages(ctx: CommandFixture):
    command_ctx = _approved(ctx)

    draft = create_draft(command_ctx, "  hello newsroom  \n")
    updated = update_draft_message(command_ctx, draft.id, "\nrevised body  ")

    assert draft.message == "hello newsroom"
    assert draft.message_sha256 == hash_message("hello newsroom")
    assert updated.id == draft.id
    assert updated.message == "revised body"
    assert updated.message_sha256 == hash_message("revised body")


def test_list_target_options_marks_default(ctx: CommandFixture):
    command_ctx = _approved(ctx)
    bot, channel = _bot_and_channel(ctx)

    options = list_target_options(command_ctx)

    assert options.bots == [bot]
    assert options.channels == [channel]
    assert options.default is not None
    assert options.default.bot.alias == "news"
    assert options.default.channel.alias == "town"
    assert options.has_stale_default is False


async def test_publish_draft_uses_default_target_and_records_audit(ctx: CommandFixture):
    command_ctx = _approved(ctx)
    bot, _channel = _bot_and_channel(ctx)
    draft = create_draft(command_ctx, "Default target post")

    result = await publish_draft(
        command_ctx,
        PublishDraftRequest(
            draft_id=draft.id,
            target=TargetRequest(bot_alias=None, channel_alias=None),
        ),
    )

    assert result.draft_id == draft.id
    assert result.mattermost_post_id == "post-1"
    assert result.bot == bot
    assert result.channel.alias == "town"
    assert ctx.created_posts == [
        {
            "id": "post-1",
            "channel_id": "channel-id",
            "message": "Default target post",
            "token": "secret-token",
        }
    ]

    sent = ctx.post_drafts.get_for_owner("alice-id", draft.id)
    assert sent.status == "sent"
    assert sent.sent_by_user_bot_id == bot.id
    assert sent.sent_channel_id == "channel-id"
    assert sent.mattermost_post_id == "post-1"

    audits = ctx.audits.list_for_user("alice-id")
    assert len(audits) == 1
    assert audits[0].status == "success"
    assert audits[0].draft_id == draft.id
    assert audits[0].user_bot_id == bot.id
    assert audits[0].channel_link == "town"
    assert audits[0].resolved_channel_id == "channel-id"
    assert audits[0].message_sha256 == hash_message("Default target post")
    assert audits[0].mattermost_post_id == "post-1"
    assert audits[0].error_code is None
    assert audits[0].error_message is None


async def test_publish_draft_returns_error_when_channel_alias_missing(ctx: CommandFixture):
    command_ctx = _approved(ctx)
    bot, _channel = _bot_and_channel(ctx)
    draft = create_draft(command_ctx, "Missing channel post")

    with pytest.raises(PublishError) as exc_info:
        await publish_draft(
            command_ctx,
            PublishDraftRequest(
                draft_id=draft.id,
                target=TargetRequest(bot_alias="news", channel_alias="missing"),
            ),
        )

    assert exc_info.value.code == "channel_not_found"
    assert exc_info.value.message_key == "send.channel_not_found"
    assert ctx.created_posts == []
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "draft"

    audits = ctx.audits.list_for_user("alice-id")
    assert len(audits) == 1
    assert audits[0].status == "failed"
    assert audits[0].draft_id == draft.id
    assert audits[0].user_bot_id == bot.id
    assert audits[0].channel_link == "missing"
    assert audits[0].resolved_channel_id is None
    assert audits[0].message_sha256 == hash_message("Missing channel post")
    assert audits[0].mattermost_post_id is None
    assert audits[0].error_code == "channel_alias"
    assert audits[0].error_message is not None
