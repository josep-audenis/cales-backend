"""Live smoke test for the multi-agent orchestrator."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)

from app.agent.runtime import run_agent


async def main(material: str = "barley") -> None:
    ctx = {"material": material, "priority_profile": "balanced", "horizon_days": 180}
    t0 = time.perf_counter()
    result = await run_agent(f"Recommend an action for {material}", ctx)
    dt = time.perf_counter() - t0

    print("\n========== ANSWER ==========")
    print(result.answer)
    print("\n========== TOOL CALLS ==========")
    for tc in result.tool_calls:
        print(f"  [{tc.get('agent','?')}] {tc.get('tool')} args={str(tc.get('args'))[:120]}")
    print("\n========== TIMINGS ==========")
    timings = (result.raw or {}).get("timings") if isinstance(result.raw, dict) else None
    print(json.dumps(timings, indent=2) if timings else "(none — fell back to single-agent or deterministic)")
    print(f"\nWALL: {dt:.2f}s")

    signals = (result.raw or {}).get("signals") if isinstance(result.raw, dict) else None
    if signals:
        print(f"\n========== SIGNALS ({len(signals)}) ==========")
        for s in signals:
            print(f"  - {s.get('name')} | {s.get('direction')} | score={s.get('score')} | conf={s.get('confidence')}")
    evidence = (result.raw or {}).get("evidence_urls") if isinstance(result.raw, dict) else None
    if evidence:
        print(f"\n========== EVIDENCE URLS ({len(evidence)}) ==========")
        for u in evidence:
            print(f"  - {u}")


if __name__ == "__main__":
    material = sys.argv[1] if len(sys.argv) > 1 else "barley"
    asyncio.run(main(material))
