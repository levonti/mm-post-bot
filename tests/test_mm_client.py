import json

import httpx
import pytest
import respx

from mm_post_bot.mm_client import MattermostClient, MattermostError


@pytest.fixture()
def client():
    return MattermostClient("https://mm.example/api/v4", "test-token")


@respx.mock
async def test_get_me(client):
    respx.get("https://mm.example/api/v4/users/me").mock(
        return_value=httpx.Response(200, json={"id": "u1", "username": "bot", "is_bot": True})
    )

    me = await client.get_me()
    assert me["username"] == "bot"
    await client.aclose()


@respx.mock
async def test_get_channel_by_team_and_name(client):
    route = respx.get(
        "https://mm.example/api/v4/teams/name/team/channels/name/town-square"
    ).mock(return_value=httpx.Response(200, json={"id": "channel-id", "name": "town-square"}))

    channel = await client.get_channel_by_team_and_name("team", "town-square")
    assert channel["id"] == "channel-id"
    assert route.calls.last.request.headers["authorization"] == "Bearer test-token"
    await client.aclose()


@respx.mock
async def test_create_post(client):
    route = respx.post("https://mm.example/api/v4/posts").mock(
        return_value=httpx.Response(201, json={"id": "post-id", "channel_id": "channel-id"})
    )

    post = await client.create_post("channel-id", "hello")
    assert post["id"] == "post-id"
    assert json.loads(route.calls.last.request.content) == {
        "channel_id": "channel-id",
        "message": "hello",
    }
    await client.aclose()


@respx.mock
async def test_create_direct_channel(client):
    route = respx.post("https://mm.example/api/v4/channels/direct").mock(
        return_value=httpx.Response(201, json={"id": "dm-channel-id"})
    )

    channel = await client.create_direct_channel("user-a", "user-b")
    assert channel["id"] == "dm-channel-id"
    assert json.loads(route.calls.last.request.content) == ["user-a", "user-b"]
    await client.aclose()


@respx.mock
async def test_error_surface(client):
    respx.get("https://mm.example/api/v4/users/me").mock(
        return_value=httpx.Response(401, json={"message": "Invalid token"})
    )

    with pytest.raises(MattermostError) as exc:
        await client.get_me()

    assert exc.value.status == 401
    assert "Invalid token" in str(exc.value)
    await client.aclose()


@respx.mock
async def test_error_surface_with_non_dict_json(client):
    respx.get("https://mm.example/api/v4/users/me").mock(
        return_value=httpx.Response(500, json=["bad"])
    )

    with pytest.raises(MattermostError) as exc:
        await client.get_me()

    assert exc.value.status == 500
    assert "Mattermost API error 500" in str(exc.value)
    assert exc.value.payload == ["bad"]
    await client.aclose()


@respx.mock
async def test_error_surface_with_plain_text_body(client):
    respx.get("https://mm.example/api/v4/users/me").mock(
        return_value=httpx.Response(502, text="upstream unavailable")
    )

    with pytest.raises(MattermostError) as exc:
        await client.get_me()

    assert exc.value.status == 502
    assert "upstream unavailable" in str(exc.value)
    assert exc.value.payload is None
    await client.aclose()


@respx.mock
async def test_get_channel_by_team_and_name_url_encodes(client):
    route = respx.get(
        "https://mm.example/api/v4/teams/name/team%20space/channels/name/channel%2Fslash"
    ).mock(return_value=httpx.Response(200, json={"id": "channel-id"}))

    channel = await client.get_channel_by_team_and_name("team space", "channel/slash")
    assert channel["id"] == "channel-id"
    assert route.called
    await client.aclose()
