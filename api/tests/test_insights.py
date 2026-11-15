import json


def test_insight_requires_gateway_auth(client, box, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    response = client.post("/insights", json={"aoi": box(104, -2, 108, 2)})
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_insight_uses_server_stats_and_limits_output(client, box, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, *_):
            return b'{"choices":[{"message":{"content":"The latest count is provisional."}}]}'

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data))
        assert timeout == 20
        assert request.get_header("Authorization") == "Bearer test-key"
        return FakeResponse()

    monkeypatch.setattr("app.routers.insights.urlopen", fake_urlopen)
    response = client.post(
        "/insights",
        json={"aoi": box(104, -2, 108, 2), "region_name": "Test area", "end": "2020-12"},
        headers={"x-vercel-oidc-token": "test-key"},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "The latest count is provisional."
    facts = json.loads(captured["messages"][1]["content"])
    assert facts["area"] == "Test area"
    assert facts["summary"]["total"] is not None
    assert facts["top_annual_totals"][0]["rank"] == 1
    assert captured["max_tokens"] == 250


def test_insight_prefers_gemini_free_tier(client, box, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, *_):
            return b'{"candidates":[{"content":{"parts":[{"text":"A grounded insight."}]}}]}'

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data))
        assert "gemini-3.5-flash-lite:generateContent" in request.full_url
        assert request.get_header("X-goog-api-key") == "gemini-test-key"
        return FakeResponse()

    monkeypatch.setattr("app.routers.insights.urlopen", fake_urlopen)
    response = client.post("/insights", json={"aoi": box(104, -2, 108, 2)})
    assert response.status_code == 200
    assert response.json()["model"] == "gemini-3.5-flash-lite"
    assert "summary" in captured["contents"][0]["parts"][0]["text"]


def test_insight_passes_a_bounded_question_as_data(client, box, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, *_):
            return b'{"choices":[{"message":{"content":"Data belum cukup."}}]}'

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setattr("app.routers.insights.urlopen", fake_urlopen)
    body = {"aoi": box(104, -2, 108, 2), "question": "  Apa penyebab kebakaran?  "}
    response = client.post("/insights", json=body, headers={"x-vercel-oidc-token": "test-key"})
    assert response.status_code == 200
    facts = json.loads(captured["messages"][1]["content"])
    assert facts["question"] == "Apa penyebab kebakaran?"
    assert facts["summary"]["total"] is not None
    body["question"] = "x" * 501
    assert client.post("/insights", json=body).status_code == 422
