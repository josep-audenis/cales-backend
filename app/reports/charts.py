"""Chart generators returning PNG bytes (matplotlib Agg). Editorial styling."""

from __future__ import annotations

import io
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from app.schemas.analyze_response import Driver, PricePath


DAMM_RED = "#E30613"
DAMM_BLACK = "#1A1A1A"
INK = "#2B2B2B"
SUBTLE = "#5C5C5C"
BASE_BLUE = "#1F4E79"
WORST_RED = "#C0392B"
RELIEF_GREEN = "#1E8449"
GREY = "#8C8C8C"
GRID = "#E5E5E5"
PANEL_BG = "#FAFAFA"

_BASE_RC = {
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 9.5,
    "axes.labelcolor": INK,
    "axes.edgecolor": "#CCCCCC",
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.facecolor": "white",
    "figure.facecolor": "white",
    "xtick.color": SUBTLE,
    "ytick.color": SUBTLE,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "legend.frameon": False,
    "legend.fontsize": 8.5,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "grid.linestyle": "-",
}


def _fig_to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _title(ax, text: str, subtitle: str | None = None) -> None:
    ax.set_title(text, color=DAMM_BLACK, loc="left", pad=14, fontsize=12, fontweight="bold")
    if subtitle:
        ax.text(
            0.0, 1.02, subtitle, transform=ax.transAxes,
            color=SUBTLE, fontsize=9, ha="left", va="bottom",
        )


def price_paths_chart(paths: list[PricePath], spot: float | None) -> bytes:
    with plt.rc_context(_BASE_RC):
        fig, ax = plt.subplots(figsize=(8.2, 4.2))
        color_map = {"base_case": BASE_BLUE, "worst_case": WORST_RED, "relief_case": RELIEF_GREEN}
        by_id = {p.id: p for p in paths}
        base = by_id.get("base_case")
        worst = by_id.get("worst_case")
        relief = by_id.get("relief_case")

        if base and worst and relief and len(base.graph_points) == len(worst.graph_points) == len(relief.graph_points):
            xs = [pt.date for pt in base.graph_points]
            lo = [min(w.value, r.value) for w, r in zip(worst.graph_points, relief.graph_points)]
            hi = [max(w.value, r.value) for w, r in zip(worst.graph_points, relief.graph_points)]
            ax.fill_between(xs, lo, hi, color=BASE_BLUE, alpha=0.08, linewidth=0, label="Forecast band")

        for p in paths:
            xs = [pt.date for pt in p.graph_points]
            ys = [pt.value for pt in p.graph_points]
            c = color_map.get(p.id, GREY)
            ax.plot(xs, ys, color=c, linewidth=2.2, label=p.label, marker="o", markersize=4, markeredgecolor="white", markeredgewidth=0.8)
            if ys:
                ax.annotate(
                    f"{ys[-1]:,.0f}",
                    xy=(xs[-1], ys[-1]),
                    xytext=(6, 0), textcoords="offset points",
                    color=c, fontsize=8.5, fontweight="bold", va="center",
                )

        if spot is not None and paths and paths[0].graph_points:
            ax.scatter([paths[0].graph_points[0].date], [spot], color=DAMM_BLACK, zorder=5, s=60, label=f"Spot {spot:,.0f}", edgecolor="white", linewidth=1.2)

        _title(ax, "Forecast corridor", "Base, worst and relief scenarios over the horizon")
        ax.set_ylabel("Price")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.grid(True, axis="y", alpha=0.8)
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
        ax.legend(loc="upper left", ncol=4, bbox_to_anchor=(0.0, -0.12))
        ax.margins(x=0.04)
        fig.tight_layout()
        return _fig_to_png(fig)


def driver_impact_chart(drivers: list[Driver]) -> bytes:
    with plt.rc_context(_BASE_RC):
        n = max(1, len(drivers))
        fig, ax = plt.subplots(figsize=(8.2, max(2.4, 0.48 * n + 1.4)))
        labels: list[str] = []
        values: list[float] = []
        bar_colors: list[str] = []
        for d in sorted(drivers, key=lambda x: x.impact_score):
            sign = 1.0 if d.buyer_impact == "negative" else (-1.0 if d.buyer_impact == "positive" else 0.0)
            v = sign * abs(d.impact_score) if sign != 0.0 else d.impact_score
            labels.append(d.label[:46])
            values.append(v)
            bar_colors.append(WORST_RED if sign > 0 else (RELIEF_GREEN if sign < 0 else GREY))

        bars = ax.barh(labels, values, color=bar_colors, edgecolor="white", linewidth=0.6, height=0.72)
        ax.axvline(0, color=DAMM_BLACK, linewidth=0.8)
        for bar, v in zip(bars, values):
            x = bar.get_width()
            ax.text(
                x + (0.005 if x >= 0 else -0.005),
                bar.get_y() + bar.get_height() / 2,
                f"{v:+.2f}",
                va="center", ha="left" if x >= 0 else "right",
                fontsize=8, color=INK, fontweight="bold",
            )

        _title(ax, "Driver impact (signed)", "Red = pressure against the buyer · Green = relief")
        ax.set_xlabel("Signed impact score")
        ax.grid(True, axis="x", alpha=0.8)
        ax.set_axisbelow(True)
        xmax = max((abs(v) for v in values), default=0.1)
        ax.set_xlim(-xmax * 1.25 - 0.02, xmax * 1.25 + 0.02)
        fig.tight_layout()
        return _fig_to_png(fig)


def coverage_gauge(current: float | None, target: float | None) -> bytes:
    with plt.rc_context(_BASE_RC):
        fig, ax = plt.subplots(figsize=(7.5, 1.6))
        cur = current or 0.0
        tgt = target or max(cur, 1.0)
        span = max(tgt * 1.6, cur * 1.25, 1.0)

        ax.barh([0], [span], color=PANEL_BG, edgecolor="#E0E0E0", linewidth=0.8, height=0.55)
        ax.barh([0], [tgt], color="#D6D6D6", height=0.55, label=f"Target {tgt:.1f} mo")
        ax.barh([0], [cur], color=DAMM_RED, height=0.55, label=f"Current {cur:.1f} mo")
        ax.axvline(tgt, color="#666666", linewidth=1.0, linestyle="--")
        ax.text(tgt, 0.55, f"Target {tgt:.1f}", color=SUBTLE, fontsize=8, ha="center", va="bottom")
        ax.text(cur, -0.55, f"Now {cur:.1f}", color=DAMM_RED, fontsize=9, ha="center", va="top", fontweight="bold")

        ax.set_xlim(0, span)
        ax.set_ylim(-0.9, 0.9)
        ax.set_yticks([])
        ax.set_xlabel("Months of coverage", labelpad=8)
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(left=False, bottom=False)
        _title(ax, "Warehouse coverage", "Current stock vs. target months of demand")
        ax.legend(loc="lower right", bbox_to_anchor=(1.0, -0.55), ncol=2)
        fig.tight_layout()
        return _fig_to_png(fig)


def scenario_sparkline(points: Iterable, color: str = BASE_BLUE) -> bytes:
    pts = list(points)
    with plt.rc_context(_BASE_RC):
        fig, ax = plt.subplots(figsize=(2.6, 0.9))
        if pts:
            xs = [p.date for p in pts]
            ys = [p.value for p in pts]
            ax.plot(xs, ys, color=color, linewidth=1.8)
            ax.fill_between(xs, ys, min(ys), color=color, alpha=0.10, linewidth=0)
            ax.scatter([xs[-1]], [ys[-1]], color=color, s=18, zorder=5, edgecolor="white", linewidth=0.8)
            ax.text(xs[-1], ys[-1], f"  {ys[-1]:,.0f}", color=color, fontsize=7.5, va="center", fontweight="bold")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.margins(x=0.18, y=0.25)
        return _fig_to_png(fig)


def forecast_corridor_pct(low_pct: float, base_pct: float, high_pct: float) -> bytes:
    """Horizontal corridor bar showing expected % move plus band."""
    with plt.rc_context(_BASE_RC):
        fig, ax = plt.subplots(figsize=(8.0, 1.5))
        lo, hi = min(low_pct, high_pct), max(low_pct, high_pct)
        span = max(abs(lo), abs(hi), 1.0) * 1.4
        ax.axvspan(lo, hi, color=BASE_BLUE, alpha=0.12)
        ax.axvline(base_pct, color=BASE_BLUE, linewidth=2.4)
        ax.axvline(0, color="#999999", linewidth=0.8, linestyle="--")
        ax.text(base_pct, 0.55, f"Base {base_pct:+.1f}%", color=BASE_BLUE, ha="center", fontsize=9, fontweight="bold")
        ax.text(lo, -0.55, f"{lo:+.1f}%", color=RELIEF_GREEN, ha="center", fontsize=8.5, va="top", fontweight="bold")
        ax.text(hi, -0.55, f"{hi:+.1f}%", color=WORST_RED, ha="center", fontsize=8.5, va="top", fontweight="bold")
        ax.set_xlim(-span, span)
        ax.set_ylim(-1.1, 1.1)
        ax.set_yticks([])
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f}%"))
        ax.tick_params(left=False)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.spines["bottom"].set_visible(True)
        ax.spines["bottom"].set_color("#CCCCCC")
        _title(ax, "Forecast corridor (% change)", "Expected move and full range over horizon")
        fig.tight_layout()
        return _fig_to_png(fig)


def confidence_dial(confidence: float) -> bytes:
    """Half-donut confidence dial 0–100%."""
    with plt.rc_context(_BASE_RC):
        fig, ax = plt.subplots(figsize=(3.6, 2.2), subplot_kw={"projection": "polar"})
        pct = max(0.0, min(1.0, confidence))
        import numpy as np
        theta = np.linspace(np.pi, 0, 200)
        ax.plot(theta, [1] * len(theta), color=PANEL_BG, linewidth=14, solid_capstyle="round")
        filled = np.linspace(np.pi, np.pi - np.pi * pct, max(2, int(200 * pct)))
        color = RELIEF_GREEN if pct >= 0.66 else (WORST_RED if pct < 0.33 else "#E08E1A")
        ax.plot(filled, [1] * len(filled), color=color, linewidth=14, solid_capstyle="round")
        ax.set_ylim(0, 1.15)
        ax.set_yticks([])
        ax.set_xticks([])
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.text(0, -0.15, f"{pct * 100:.0f}%", ha="center", va="center", fontsize=22, fontweight="bold", color=DAMM_BLACK, transform=ax.transAxes)
        ax.text(0, -0.32, "Confidence", ha="center", va="center", fontsize=9, color=SUBTLE, transform=ax.transAxes)
        return _fig_to_png(fig)


def risk_opportunity_chart(risk: float, opportunity: float) -> bytes:
    """Two stacked horizontal bars: risk vs opportunity 0–10."""
    with plt.rc_context(_BASE_RC):
        fig, ax = plt.subplots(figsize=(7.0, 1.8))
        labels = ["Opportunity", "Risk"]
        vals = [max(0.0, min(10.0, opportunity)), max(0.0, min(10.0, risk))]
        colors_ = [RELIEF_GREEN, WORST_RED]
        bars = ax.barh(labels, vals, color=colors_, height=0.55, edgecolor="white", linewidth=0.6)
        ax.barh(labels, [10, 10], color=PANEL_BG, height=0.55, zorder=0)
        for bar, v in zip(bars, vals):
            ax.text(v + 0.15, bar.get_y() + bar.get_height() / 2, f"{v:.1f} / 10", va="center", fontsize=9, fontweight="bold", color=INK)
        ax.set_xlim(0, 10.8)
        ax.set_xticks([0, 2.5, 5, 7.5, 10])
        ax.grid(True, axis="x", alpha=0.6)
        ax.set_axisbelow(True)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(left=False)
        _title(ax, "Risk vs. Opportunity", "0 = low · 10 = high")
        fig.tight_layout()
        return _fig_to_png(fig)
