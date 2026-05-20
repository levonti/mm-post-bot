from types import TracebackType
from typing import Any, Self, cast
from urllib.parse import quote

import httpx


class MattermostError(RuntimeError):
    def __init__(self, status: int, message: str, payload: Any = None) -> None:
        super().__init__(f"Mattermost API error {status}: {message}")
        self.status = status
        self.payload = payload


class MattermostClient:
    def __init__(
        self,
        rest_base: str,
        token: str,
        *,
        timeout: float = 15.0,
        verify_ssl: bool = True,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=rest_base,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            verify=verify_ssl,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, *, json: Any | None = None) -> Any:
        response = await self._client.request(method, path, json=json)
        if response.status_code >= 400:
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    message = str(payload.get("message") or response.text)
                else:
                    message = response.text
            except ValueError:
                payload = None
                message = response.text
            raise MattermostError(response.status_code, message, payload)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def get_me(self) -> dict[str, Any]:
        return cast(dict[str, Any], await self._request("GET", "/users/me"))

    async def create_direct_channel(self, user_id_a: str, user_id_b: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._request("POST", "/channels/direct", json=[user_id_a, user_id_b]),
        )

    async def get_channel_by_team_and_name(
        self,
        team_name: str,
        channel_name: str,
    ) -> dict[str, Any]:
        encoded_team_name = quote(team_name, safe="")
        encoded_channel_name = quote(channel_name, safe="")
        return cast(
            dict[str, Any],
            await self._request(
                "GET",
                f"/teams/name/{encoded_team_name}/channels/name/{encoded_channel_name}",
            ),
        )

    async def create_post(self, channel_id: str, message: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._request(
                "POST",
                "/posts",
                json={"channel_id": channel_id, "message": message},
            ),
        )
