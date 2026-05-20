import pytest

from mm_post_bot.channel_links import ChannelLink, ChannelLinkError, parse_channel_link


def test_parse_channel_link_with_subpath():
    parsed = parse_channel_link(
        "https://mm.internal/i/team-name/channels/channel-name",
        mm_url="https://mm.internal/i",
    )

    assert parsed == ChannelLink(team_name="team-name", channel_name="channel-name")


def test_parse_channel_link_rejects_other_host():
    with pytest.raises(ChannelLinkError):
        parse_channel_link(
            "https://evil.internal/i/team-name/channels/channel-name",
            mm_url="https://mm.internal/i",
        )


def test_parse_channel_link_rejects_non_channel_path():
    with pytest.raises(ChannelLinkError):
        parse_channel_link("https://mm.internal/i/team-name/pl/channel-name", mm_url="https://mm.internal/i")
