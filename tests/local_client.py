from fastapi.testclient import TestClient as BaseTestClient


class LocalTestClient(BaseTestClient):
    def __init__(self, app, **kwargs):
        super().__init__(app, base_url="http://127.0.0.1", **kwargs)
        token = self.get("/api/local-session").json()["token"]
        self.headers["X-Local-Session"] = token
