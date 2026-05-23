"""Chart generators returning PNG bytes (matplotlib Agg)."""

from __future__ import annotations

import io
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.schemas.analyze_response import Driver, PricePath


DAMM_RED = "#E30613"
DAMM_BLACK = "#1A1A1A"
BASE_BLUE = "#1F77B4"
WORST_RED = "#D62728"
RELIEF_GREEN = "#2CA02C"
GREY = "#888888"


def _fig_to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def price_paths_chart(paths: list[PricePath], spot: float | None) -> bytes:
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    color_map = {
        "base_case": BASE_BLUE,
        "worst_case": WORST_RED,
        "relief_case": RELIEF_GREEN,
    }
    by_id = {p.id: p for p in paths}
    base = by_id.get("base_case")
    worst = by_id.get("worst_case")
    relief = by_id.get("relief_case")

    if base and worst and relief and len(base.graph_points) == len(worst.graph_points) == len(relief.graph_points):
        xs = [pt.date for pt in base.graph_points]
        lo = [min(w.value, r.value) for w, r in zip(worst.graph_points, relief.graph_points)]
        hi = [max(w.value, r.value) for w, r in zip(worst.graph_points, relief.graph_points)]
        ax.fill_between(xs, lo, hi, color=BASE_BLUE, alpha=0.10, label="Uncertainty band")

    for p in paths:
        xs = [pt.date for pt in p.graph_points]
        ys = [pt.value for pt in p.graph_points]
        ax.plot(xs, ys, color=color_map.get(p.id, GREY), linewidth=1.8, label=p.label)

    if spot is not None and paths and paths[0].graph_points:
        ax.scatter([paths[0].graph_points[0].date], [spot], color=DAMM_BLACK, zorder=5, s=40, label="Spot")

    ax.set_title("Price paths (base / worst / relief)", fontsize=11, color=DAMM_BLACK)
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend(loc="best", fontsize=8, frameon=False)
    fig.autofmt_xdate()
    return _fig_to_png(fig)


def driver_impact_chart(drivers: list[Driver]) -> bytes:
    fig, ax = plt.subplots(figsize=(7.5, max(2.0, 0.4 * len(drivers) + 1)))
    labels: list[str] = []
    values: list[float] = []
    colors: list[str] = []
    for d in sorted(drivers, key=lambda x: x.impact_score):
        sign = 1.0 if d.buyer_impact == "negative" else (-1.0 if d.buyer_impact == "positive" else 0.0)
        v = sign * d.impact_score if sign != 0.0 else d.impact_score
        labels.append(d.label[:42])
        values.append(v)
        colors.append(WORST_RED if sign > 0 else (RELIEF_GREEN if sign < 0 else GREY))
    ax.barh(labels, values, color=colors)
    ax.axvline(0, color=DAMM_BLACK, linewidth=0.6)
    ax.set_title("Driver impact (signed by buyer impact)", fontsize=11, color=DAMM_BLACK)
    ax.set_xlabel("Impact score (negative = good for buyer)")
    ax.grid(True, axis="x", linestyle=":", alpha=0.4)
    return _fig_to_png(fig)


def coverage_gauge(current: float | None, target: float | None) -> bytes:
    fig, ax = plt.subplots(figsize=(4.0, 1.2))
    cur = current or 0.0
    tgt = target or max(cur, 1.0)
    span = max(tgt * 1.5, cur * 1.2, 1.0)
    ax.barh([0], [span], color="#EEEEEE")
    ax.barh([0], [tgt], color="#BBBBBB", label=f"Target {tgt:.1f}m")
    ax.barh([0], [cur], color=DAMM_RED, label=f"Current {cur:.1f}m")
    ax.set_xlim(0, span)
    ax.set_yticks([])
    ax.set_title("Warehouse coverage (months)", fontsize=10, color=DAMM_BLACK)
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    return _fig_to_png(fig)


def scenario_sparkline(points: Iterable, color: str = BASE_BLUE) -> bytes:
    pts = list(points)
    fig, ax = plt.subplots(figsize=(2.2, 0.7))
    if pts:
        ax.plot([p.date for p in pts], [p.value for p in pts], color=color, linewidth=1.4)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _fig_to_png(fig)
