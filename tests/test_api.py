import httpx
from google.genai import types

import main


# ─── Pages & health ───────────────────────────────────────────────────────────

def test_index_and_static(client):
    r = client.get("/")
    assert r.status_code == 200 and "ARIA" in r.text and 'id="auth-form"' in r.text
    assert r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/static/js/dashboard.js").status_code == 200
    assert client.get("/static/css/style.css").status_code == 200


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["database"] == "ok"
    assert body["integrations"]["gemini"] is False   # reports config, never values


def test_healthz_reports_db_outage(client, monkeypatch):
    class Broken:
        def connect(self):
            raise RuntimeError("db down")
    monkeypatch.setattr(main, "engine", Broken())
    r = client.get("/healthz")
    assert r.status_code == 503 and r.json()["database"] == "unreachable"


def test_time(client):
    assert "iso" in client.get("/api/time").json()


# ─── Widgets (external APIs mocked at the HTTP layer) ─────────────────────────

def test_weather_missing_key(client):
    assert client.get("/api/weather?city=Paris").json() == {"error": "OPENWEATHER_API_KEY not set"}


def test_weather_success_and_param_encoding(client, mock_http, monkeypatch):
    monkeypatch.setattr(main, "OPENWEATHER_API_KEY", "k")
    seen = {}

    def handler(req: httpx.Request):
        seen["q"] = req.url.params["q"]
        seen["appid"] = req.url.params["appid"]
        return httpx.Response(200, json={
            "name": "Paris", "sys": {"country": "FR"},
            "main": {"temp": 20.04, "feels_like": 19.5, "humidity": 50},
            "weather": [{"description": "clear sky", "icon": "01d"}], "wind": {"speed": 3.2},
        })
    mock_http(handler)
    r = client.get("/api/weather", params={"city": "Paris&appid=evil"})
    assert r.json()["city"] == "Paris" and r.json()["description"] == "Clear Sky"
    assert seen == {"q": "Paris&appid=evil", "appid": "k"}   # injection stays inside q


def test_weather_city_not_found(client, mock_http, monkeypatch):
    monkeypatch.setattr(main, "OPENWEATHER_API_KEY", "k")
    mock_http(lambda req: httpx.Response(404, json={}))
    assert "not found" in client.get("/api/weather?city=Nowhere").json()["error"]


def test_upstream_network_failure_is_graceful(client, mock_http):
    def handler(req):
        raise httpx.ConnectError("connection refused", request=req)
    mock_http(handler)
    r = client.get("/api/crypto?symbol=bitcoin")
    assert r.status_code == 200
    assert r.json() == {"error": "Crypto price service is unreachable right now"}


def test_crypto(client, mock_http):
    mock_http(lambda req: httpx.Response(200, json={
        "bitcoin": {"usd": 65000.5, "usd_24h_change": -1.234, "usd_market_cap": 1}}))
    assert client.get("/api/crypto?symbol=Bitcoin").json() == {
        "symbol": "bitcoin", "price_usd": 65000.5, "change_24h": -1.23, "market_cap": 1}
    mock_http(lambda req: httpx.Response(200, json={}))
    assert "not found" in client.get("/api/crypto?symbol=nocoin").json()["error"]


def test_news(client, mock_http, monkeypatch):
    monkeypatch.setattr(main, "NEWS_API_KEY", "k")

    def handler(req):
        assert req.headers["x-api-key"] == "k" and "apiKey" not in str(req.url)
        return httpx.Response(200, json={"articles": [
            {"title": "T", "source": {"name": "S"}, "url": "https://x", "publishedAt": "2026-01-02T00:00:00Z",
             "description": None},
            {"title": None, "source": None, "url": None, "publishedAt": None, "description": "d"},
        ]})
    mock_http(handler)
    arts = client.get("/api/news?query=ai&count=50").json()["articles"]
    assert arts[0]["source"] == "S" and arts[0]["published"] == "2026-01-02"
    assert arts[1]["source"] == "Unknown"


def test_github(client, mock_http):
    assert client.get("/api/github").json() == {"error": "No GitHub username provided"}
    assert "not a valid" in client.get("/api/github?username=../../etc").json()["error"]
    mock_http(lambda req: httpx.Response(200, json=[
        {"type": "PushEvent", "repo": {"name": "o/r"}, "created_at": "2026-01-01T00:00:00Z"}]))
    assert client.get("/api/github?username=octocat").json()["events"] == [
        {"type": "Push", "repo": "o/r", "date": "2026-01-01"}]


# ─── Agent chat ───────────────────────────────────────────────────────────────

def test_chat_task_shortcuts(client, auth):
    r = client.post("/api/agent/chat", headers=auth, json={"message": "add buy 100% milk"})
    assert r.json()["todo_updated"] is True
    r = client.post("/api/agent/chat", headers=auth, json={"message": "show my tasks"})
    assert "buy 100% milk" in r.json()["reply"]
    # LIKE wildcards in the task name are matched literally
    r = client.post("/api/agent/chat", headers=auth, json={"message": "complete 1_0%"})
    assert "not found" in r.json()["reply"]
    r = client.post("/api/agent/chat", headers=auth, json={"message": "complete 100% milk"})
    assert "completed" in r.json()["reply"]
    assert client.get("/api/todos", headers=auth).json()[0]["done"] is True


def test_chat_validation_and_rate_limit(client, auth, monkeypatch):
    monkeypatch.setattr(main, "CHAT_RATE_LIMIT", 3)
    assert client.post("/api/agent/chat", headers=auth, json={"message": "   "}).status_code == 400
    assert client.post("/api/agent/chat", headers=auth, json={"message": "x" * 2001}).status_code == 422
    codes = [client.post("/api/agent/chat", headers=auth, json={"message": "list tasks"}).status_code
             for _ in range(4)]
    assert codes == [200, 200, 200, 429]   


def test_chat_without_gemini_key(client, auth):
    r = client.post("/api/agent/chat", headers=auth, json={"message": "hello"})
    assert r.status_code == 503 and "not configured" in r.json()["error"]


class _FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def generate_content(self, model, contents, config):
        self.calls.append(list(contents))
        return self.responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.aio = type("Aio", (), {})()
        self.aio.models = _FakeModels(responses)


def _resp(*parts, finish=types.FinishReason.STOP):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=list(parts)), finish_reason=finish)])


def test_chat_gemini_tool_loop(client, auth, monkeypatch):
    fake = _FakeClient([
        _resp(types.Part(function_call=types.FunctionCall(name="get_crypto_price", args={"symbol": "bitcoin"}))),
        _resp(types.Part(text="Bitcoin is at $1.00.")),
    ])
    monkeypatch.setattr(main, "_get_gemini_client", lambda: fake)

    async def fake_price(symbol="bitcoin"):
        return {"symbol": symbol, "price_usd": 1.0, "change_24h": 2.0, "market_cap": 0}
    monkeypatch.setitem(main.TOOL_MAP, "get_crypto_price", fake_price)

    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}, "junk", 5]
    r = client.post("/api/agent/chat", headers=auth, json={"message": "btc?", "history": history})
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == "Bitcoin is at $1.00."
    # Second Gemini call received the formatted tool result
    fn_resp = fake.aio.models.calls[1][-1].parts[0].function_response
    assert fn_resp.name == "get_crypto_price" and "$1.00" in fn_resp.response["result"]
    assert client.get("/my-chats", headers=auth).json()[0]["ai_response"] == "Bitcoin is at $1.00."


def test_chat_gemini_safety_block(client, auth, monkeypatch):
    fake = _FakeClient([_resp(types.Part(text="x"), finish=types.FinishReason.SAFETY)])
    monkeypatch.setattr(main, "_get_gemini_client", lambda: fake)
    r = client.post("/api/agent/chat", headers=auth, json={"message": "bad"})
    assert r.status_code == 422 and "safety" in r.json()["error"]


def test_chat_tool_call_without_args(client, auth, monkeypatch):
    fake = _FakeClient([
        _resp(types.Part(function_call=types.FunctionCall(name="get_github_activity"))),
        _resp(types.Part(text="done")),
    ])
    monkeypatch.setattr(main, "_get_gemini_client", lambda: fake)
    r = client.post("/api/agent/chat", headers=auth, json={"message": "my github"})
    assert r.status_code == 200 and r.json()["reply"] == "done"


def test_api_keys_not_logged(client, mock_http, monkeypatch, caplog):
    monkeypatch.setattr(main, "OPENWEATHER_API_KEY", "super-secret-weather-key")
    mock_http(lambda req: httpx.Response(500, json={}))
    with caplog.at_level("DEBUG"):
        client.get("/api/weather?city=Paris")
    assert "super-secret-weather-key" not in caplog.text
