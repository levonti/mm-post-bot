import asyncio
import json
import ssl
from collections.abc import AsyncIterator
from typing import Any, cast

from websockets.asyncio.client import connect

from .config import Settings
from .logging import get_logger

logger = get_logger(__name__)


def _ssl_context(settings: Settings) -> ssl.SSLContext | None:
    if not settings.mm_ws_url.startswith("wss://"):
        return None
    if settings.mm_verify_ssl:
        return ssl.create_default_context()
    return ssl._create_unverified_context()


async def listen_events(settings: Settings) -> AsyncIterator[dict[str, Any]]:
    backoff_seconds = 1

    while True:
        try:
            async with connect(settings.mm_ws_url, ssl=_ssl_context(settings)) as websocket:
                await websocket.send(
                    json.dumps(
                        {
                            "seq": 1,
                            "action": "authentication_challenge",
                            "data": {"token": settings.mm_bot_token},
                        }
                    )
                )
                logger.info("mattermost_ws_connected")
                backoff_seconds = 1

                async for raw_message in websocket:
                    try:
                        payload = json.loads(cast(str, raw_message))
                    except json.JSONDecodeError as exc:
                        logger.warning("mattermost_ws_malformed_frame_ignored", error=str(exc))
                        continue
                    if isinstance(payload, dict):
                        yield cast(dict[str, Any], payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "mattermost_ws_reconnect_scheduled",
                error=str(exc),
                backoff_seconds=backoff_seconds,
            )
            await asyncio.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30)
