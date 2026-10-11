import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from querylab.web.local_boundary import LocalOnlyMiddleware


@pytest.fixture
def boundary():
    app = FastAPI()
    calls = []
    app.add_middleware(LocalOnlyMiddleware)

    @app.api_route("/history", methods=["GET", "POST", "DELETE"])
    async def operation():
        calls.append("handler")
        return {"ok": True}

    @app.websocket("/ws")
    async def socket(websocket: WebSocket):
        await websocket.accept()
        calls.append("socket")
        await websocket.send_text("ok")
        await websocket.close()

    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        yield client, calls


@pytest.mark.parametrize(
    "headers",
    [
        {"host": "attacker.example"},
        {"host": "localhost:" + "1" * 5000},
        {"host": "localhost.attacker.example"},
        {"host": "127.0.0.1:8000@attacker.example"},
        {"host": "localhost:0"},
        {"host": "localhost:65536"},
        {"host": "localhost:8001"},
        {"forwarded": "for=127.0.0.1"},
        {"x-real-ip": "127.0.0.1"},
        {"x-forwarded-host": "127.0.0.1:8000"},
        {"origin": "null"},
        {"origin": "http://127.0.0.1:8001"},
        {"origin": "https://attacker.example"},
        {"sec-fetch-site": "cross-site"},
        {"sec-fetch-site": "same-site"},
        {"host": "attacker.example", "x-forwarded-host": "127.0.0.1:8000"},
    ],
)
def test_hostile_reads_bootstrap_and_mutations_never_reach_handlers(boundary, headers):
    client, calls = boundary
    token = client.get("/api/local-session").json()["token"]
    for path in ["/history", "/api/local-session"]:
        assert client.get(path, headers=headers).status_code == 403
    assert (
        client.post(
            "/history",
            content=b"invalid body",
            headers={"x-local-session": token, **headers},
        ).status_code
        == 403
    )
    assert calls == []


def test_token_required_and_local_flow(boundary):
    client, calls = boundary
    assert client.post("/history").status_code == 403
    assert (
        client.delete("/history", headers={"x-local-session": "wrong"}).status_code
        == 403
    )
    assert calls == []
    bootstrap = client.get("/api/local-session")
    assert bootstrap.headers["cache-control"] == "no-store"
    token = bootstrap.json()["token"]
    assert (
        client.post(
            "/history",
            headers={
                "x-local-session": token,
                "origin": "http://127.0.0.1:8000",
                "sec-fetch-site": "same-origin",
            },
        ).status_code
        == 200
    )
    assert calls == ["handler"]


@pytest.mark.parametrize(
    "origin,token_kind",
    [
        (None, "valid"),
        ("null", "valid"),
        ("https://attacker.example", "valid"),
        ("http://127.0.0.1:8001", "valid"),
        ("http://127.0.0.1:8000", "wrong"),
    ],
)
def test_websocket_handshake_rejected_before_accept(boundary, origin, token_kind):
    client, calls = boundary
    token = (
        client.get("/api/local-session").json()["token"]
        if token_kind == "valid"
        else "wrong"
    )
    headers = {"origin": origin} if origin is not None else {}
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "ws://127.0.0.1:8000/ws",
            headers=headers,
            subprotocols=["local-session." + token],
        ):
            pass
    assert calls == []


def test_local_websocket_flow(boundary):
    client, calls = boundary
    token = client.get("/api/local-session").json()["token"]
    with client.websocket_connect(
        "ws://127.0.0.1:8000/ws",
        headers={"origin": "http://127.0.0.1:8000"},
        subprotocols=["local-session." + token],
    ) as ws:
        assert ws.receive_text() == "ok"
    assert calls == ["socket"]


def test_duplicate_security_headers_rejected(boundary):
    client, calls = boundary
    for name, value in [
        ("host", "127.0.0.1:8000"),
        ("origin", "http://127.0.0.1:8000"),
        ("sec-fetch-site", "same-origin"),
        ("x-local-session", "wrong"),
    ]:
        assert (
            client.get("/history", headers=[(name, value), (name, value)]).status_code
            == 403
        )
    assert calls == []


def test_restart_rotates_token():
    first = LocalOnlyMiddleware(None)
    second = LocalOnlyMiddleware(None)
    assert first.token != second.token
