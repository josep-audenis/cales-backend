from typing import Any

from fastapi.testclient import TestClient

from app.agent.runtime import AgentRunResult
from app.api.routes import agent as agent_route
from app.main import app


client = TestClient(app)


def test_analyze_accepts_report_generation_payload(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_run_agent(message: str, context: dict[str, Any] | None = None) -> AgentRunResult:
        captured["message"] = message
        captured["context"] = context
        return AgentRunResult(answer="ok", tool_calls=[])

    monkeypatch.setattr(agent_route, "run_agent", fake_run_agent)

    payload = {
        "material": "aluminium",
        "horizon_days": 90,
        "horizon_label": "3M",
        "priority_profile": "balanced",
        "requested_at": "2026-05-23T00:00:00+02:00",
        "context": {
            "current_date": True,
            "spot_price": True,
            "warehouse_fill_pct": 82,
            "related_news": True,
            "source_reliability": True,
        },
        "include_market_drivers": True,
        "analysis_type": "base_case",
    }

    r = client.post("/agent/analyze", json=payload)

    assert r.status_code == 200
    assert r.json() == {"answer": "ok", "tool_calls": []}
    assert captured["context"]["context"]["warehouse_fill_pct"] == 82
    assert "what_if_scenarios" not in captured["message"]
    assert "selected_news_ids" not in captured["message"]
