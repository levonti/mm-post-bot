from dataclasses import dataclass
from urllib.parse import urlparse


class ChannelLinkError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ChannelLink:
    team_name: str
    channel_name: str


def parse_channel_link(link: str, *, mm_url: str) -> ChannelLink:
    base = urlparse(mm_url.rstrip("/"))
    parsed = urlparse(link.strip())
    if parsed.scheme != base.scheme or parsed.netloc != base.netloc:
        raise ChannelLinkError("Channel link must use the configured Mattermost host")

    base_parts = [p for p in base.path.split("/") if p]
    link_parts = [p for p in parsed.path.split("/") if p]
    if base_parts and link_parts[: len(base_parts)] != base_parts:
        raise ChannelLinkError("Channel link must use the configured Mattermost base path")

    parts = link_parts[len(base_parts) :]
    if len(parts) != 3 or parts[1] != "channels":
        raise ChannelLinkError(
            "Expected channel link like https://mm.internal/team/channels/channel"
        )

    return ChannelLink(team_name=parts[0], channel_name=parts[2])
