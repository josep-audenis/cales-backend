"""Executive PDF report builder from AnalyzeResponse."""

from __future__ import annotations

import hashlib
import io
from functools import lru_cache
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.reports import charts
from app.schemas.analyze_response import AnalyzeResponse, ExecutiveNarrative

TEMPLATE_VERSION = "2.0"

DAMM_RED = colors.HexColor("#E30613")
DAMM_BLACK = colors.HexColor("#1A1A1A")
INK = colors.HexColor("#2B2B2B")
SUBTLE = colors.HexColor("#5C5C5C")
LIGHT_GREY = colors.HexColor("#F4F4F4")
PANEL_BG = colors.HexColor("#FAFAFA")
MID_GREY = colors.HexColor("#999999")
DIVIDER = colors.HexColor("#E0E0E0")
ACCENT_BLUE = colors.HexColor("#1F4E79")

ACTION_COLORS = {
    "BUY_NOW": colors.HexColor("#E30613"),
    "HEDGE": colors.HexColor("#E08E1A"),
    "WAIT": colors.HexColor("#1F4E79"),
    "MONITOR": colors.HexColor("#666666"),
}

ACTION_BLURB = {
    "BUY_NOW": "Lock procurement now. The forecast and signal balance favour early action over deferral.",
    "HEDGE": "Partially commit and hedge the residual exposure. Asymmetric risk favours layered execution.",
    "WAIT": "Defer purchasing. Signals do not yet justify locking forward exposure at current levels.",
    "MONITOR": "Maintain coverage and observe. Insufficient signal strength to justify a directional move.",
}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    SERIF = "Times-Roman"
    SERIF_B = "Times-Bold"
    SERIF_I = "Times-Italic"
    SANS_B = "Helvetica-Bold"
    s = {
        "cover_title": ParagraphStyle("ct", parent=base["Title"], fontSize=36, leading=40, textColor=DAMM_BLACK, alignment=TA_LEFT, fontName=SERIF_B),
        "cover_sub": ParagraphStyle("cs", parent=base["BodyText"], fontSize=13, leading=17, textColor=SUBTLE, alignment=TA_LEFT, fontName=SERIF_I),
        "cover_meta": ParagraphStyle("cm", parent=base["BodyText"], fontSize=11, leading=16, textColor=INK, fontName=SERIF),
        "cover_kicker": ParagraphStyle("ck", parent=base["BodyText"], fontSize=9, leading=12, textColor=DAMM_RED, alignment=TA_LEFT, fontName=SANS_B),
        "section_kicker": ParagraphStyle("sk", parent=base["BodyText"], fontSize=8, leading=10, textColor=DAMM_RED, fontName=SANS_B, spaceAfter=2),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=20, leading=24, textColor=DAMM_BLACK, spaceAfter=4, fontName=SERIF_B),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, leading=16, textColor=DAMM_BLACK, spaceAfter=4, fontName=SERIF_B),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=11, leading=14, textColor=DAMM_BLACK, spaceAfter=3, fontName=SERIF_B),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=10.5, leading=15.5, alignment=TA_JUSTIFY, textColor=INK, fontName=SERIF),
        "body_lead": ParagraphStyle("bl", parent=base["BodyText"], fontSize=12, leading=17, alignment=TA_JUSTIFY, textColor=INK, spaceAfter=6, fontName=SERIF_I),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=8, leading=10, textColor=SUBTLE, fontName=SERIF),
        "callout": ParagraphStyle("co", parent=base["BodyText"], fontSize=10.5, leading=15, textColor=INK, alignment=TA_LEFT, fontName=SERIF),
        "chip": ParagraphStyle("chip", parent=base["BodyText"], fontSize=18, leading=22, textColor=colors.white, alignment=TA_CENTER, fontName=SANS_B),
        "chip_sub": ParagraphStyle("cs2", parent=base["BodyText"], fontSize=8.5, leading=10, textColor=colors.white, alignment=TA_CENTER, fontName="Helvetica"),
        "footnote": ParagraphStyle("fn", parent=base["BodyText"], fontSize=8.5, leading=11, textColor=INK, fontName=SERIF),
    }
    return s


def _cover_page(canvas, doc, material: str, horizon_label: str, generated_at: str) -> None:
    canvas.saveState()
    # Top brand mark — black wordmark, no background
    canvas.setFillColor(DAMM_BLACK)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(2 * cm, A4[1] - 1.8 * cm, "DAMM")
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(SUBTLE)
    canvas.drawString(2 * cm + 1.4 * cm, A4[1] - 1.8 * cm, "Procurement Intelligence")
    # Thin red accent rule under mark
    canvas.setStrokeColor(DAMM_RED)
    canvas.setLineWidth(0.8)
    canvas.line(2 * cm, A4[1] - 2.1 * cm, 4.6 * cm, A4[1] - 2.1 * cm)
    # Footer
    canvas.setStrokeColor(DIVIDER)
    canvas.setLineWidth(0.4)
    canvas.line(2 * cm, 1.55 * cm, A4[0] - 2 * cm, 1.55 * cm)
    canvas.setFillColor(SUBTLE)
    canvas.setFont("Times-Italic", 8.5)
    canvas.drawString(2 * cm, 1.15 * cm, "Powered by Cala & cales.ai")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 2 * cm, 1.15 * cm, "Confidential")
    canvas.restoreState()


def _header_footer(canvas, doc, material: str, horizon_label: str, generated_at: str) -> None:
    canvas.saveState()
    # Top: material name only (left), report title (right) — no background, no timestamp
    canvas.setFillColor(DAMM_BLACK)
    canvas.setFont("Times-Bold", 9)
    canvas.drawString(2 * cm, A4[1] - 1.1 * cm, material.capitalize())
    canvas.setFont("Times-Italic", 8.5)
    canvas.setFillColor(SUBTLE)
    canvas.drawString(2 * cm + 2.8 * cm, A4[1] - 1.1 * cm, horizon_label)
    canvas.setFont("Times-Italic", 8.5)
    canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 1.1 * cm, "Executive Procurement Report")
    # Thin divider under header
    canvas.setStrokeColor(DIVIDER)
    canvas.setLineWidth(0.4)
    canvas.line(2 * cm, A4[1] - 1.35 * cm, A4[0] - 2 * cm, A4[1] - 1.35 * cm)
    # Footer
    canvas.line(2 * cm, 1.4 * cm, A4[0] - 2 * cm, 1.4 * cm)
    canvas.setFont("Times-Italic", 8)
    canvas.setFillColor(SUBTLE)
    canvas.drawString(2 * cm, 1.0 * cm, "Powered by Cala & cales.ai")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 2 * cm, 1.0 * cm, f"Page {doc.page}")
    canvas.restoreState()


def _section_header(title: str, kicker: str, styles) -> list[Any]:
    out: list[Any] = []
    out.append(Paragraph(kicker.upper(), styles["section_kicker"]))
    out.append(Paragraph(title, styles["h1"]))
    out.append(_divider())
    out.append(Spacer(1, 0.25 * cm))
    return out


def _divider() -> Table:
    t = Table([[""]], colWidths=[17 * cm], rowHeights=[0.05 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), DAMM_RED)]))
    return t


def _action_banner(action: str, confidence: float, horizon_days: int, headline: str, styles) -> Table:
    color = ACTION_COLORS.get(action.upper(), DAMM_BLACK)
    chip_inner = Table(
        [
            [Paragraph(f"<b>{action}</b>", styles["chip"])],
            [Paragraph(f"{confidence * 100:.0f}% confidence · {horizon_days}d", styles["chip_sub"])],
        ],
        colWidths=[5.5 * cm],
        rowHeights=[1.4 * cm, 0.6 * cm],
    )
    chip_inner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    blurb_text = headline or ACTION_BLURB.get(action.upper(), "")
    right = Paragraph(f"<b>Recommendation.</b> {blurb_text}", styles["callout"])
    wrap = Table([[chip_inner, right]], colWidths=[6 * cm, 11 * cm])
    wrap.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (1, 0), (1, 0), PANEL_BG),
                ("LEFTPADDING", (1, 0), (1, 0), 14),
                ("RIGHTPADDING", (1, 0), (1, 0), 14),
                ("TOPPADDING", (1, 0), (1, 0), 12),
                ("BOTTOMPADDING", (1, 0), (1, 0), 12),
                ("LINEABOVE", (1, 0), (1, 0), 0.6, DAMM_RED),
                ("LINEBELOW", (1, 0), (1, 0), 0.6, DAMM_RED),
            ]
        )
    )
    return wrap


def _kpi_strip(kpis: list[tuple[str, str]], styles) -> Table:
    cells = []
    for label, value in kpis:
        block = Table(
            [
                [Paragraph(label.upper(), ParagraphStyle("kl", fontSize=7.5, leading=9, textColor=SUBTLE, fontName="Helvetica-Bold"))],
                [Paragraph(f"<b>{value}</b>", ParagraphStyle("kv", fontSize=13, leading=15, textColor=DAMM_BLACK))],
            ],
            colWidths=[(17 / max(len(kpis), 1)) * cm],
            rowHeights=[0.5 * cm, 0.9 * cm],
        )
        block.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PANEL_BG),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.3, DIVIDER),
                ]
            )
        )
        cells.append(block)
    strip = Table([cells], colWidths=[(17 / max(len(cells), 1)) * cm] * len(cells))
    strip.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    return strip


def _striped_table(header: list[str], rows: list[list[Any]], col_widths: list[float]) -> Table:
    data = [header] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DAMM_BLACK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 8.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, DAMM_BLACK),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, DAMM_BLACK),
                ("LINEBELOW", (0, -1), (-1, -1), 0.4, DIVIDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def _png_image(data: bytes, width: float) -> Image:
    img = Image(io.BytesIO(data))
    iw, ih = img.imageWidth, img.imageHeight
    img.drawWidth = width
    img.drawHeight = width * (ih / iw)
    return img


def _hash_response(resp: AnalyzeResponse) -> str:
    payload = resp.model_dump_json().encode("utf-8")
    return hashlib.sha256(payload + TEMPLATE_VERSION.encode()).hexdigest()


@lru_cache(maxsize=32)
def _cached_render(resp_hash: str, payload_json: str) -> bytes:
    resp = AnalyzeResponse.model_validate_json(payload_json)
    return _render(resp)


def render_executive_pdf(resp: AnalyzeResponse) -> bytes:
    h = _hash_response(resp)
    return _cached_render(h, resp.model_dump_json())


# ---------------------------------------------------------------------------
# Narrative fallbacks — keep PDF text-rich even when LLM narrative is thin
# ---------------------------------------------------------------------------

def _fallback_narrative(resp: AnalyzeResponse) -> ExecutiveNarrative:
    rec = resp.recommendation
    fc = resp.forecast
    spot = resp.market_context.spot_price
    material = resp.material.value if hasattr(resp.material, "value") else str(resp.material)
    horizon = f"{resp.horizon_days}-day"
    top_drivers = sorted(resp.drivers, key=lambda d: abs(d.impact_score), reverse=True)[:3]
    drv_phrase = ", ".join(d.label.lower() for d in top_drivers) or "the current signal mix"

    spot_phrase = (
        f"The reference {material} spot sits at {spot.value:,.2f} {spot.unit} as of {spot.as_of}. "
        if spot else
        f"A reference spot price was not available for {material} at generation time. "
    )

    market_overview = (
        f"{spot_phrase}"
        f"Over the {horizon} horizon, the corridor points {fc.direction} with an expected move of "
        f"{fc.expected_change_pct:+.1f}% and a full range of {fc.range_low_pct:+.1f}% to {fc.range_high_pct:+.1f}%. "
        f"The dominant tone of the signal stack is set by {drv_phrase}, which together explain most of the "
        f"directional pressure embedded in the base path. {fc.interpretation} Liquidity and exchange dynamics for "
        f"{material} keep the spot anchor representative of physical clearing levels, so the corridor can be read "
        f"as a credible distribution of outcomes rather than a single point estimate. Buyers should treat the base "
        f"path as the working assumption and the worst and relief cases as the range against which to stress-test "
        f"upcoming procurement decisions."
    )

    bullish = [d for d in resp.drivers if d.buyer_impact == "negative"]
    bearish = [d for d in resp.drivers if d.buyer_impact == "positive"]
    supply_demand_landscape = (
        f"The supply side currently shows "
        f"{len(bullish)} pressure driver(s) — "
        f"{', '.join(d.label.lower() for d in bullish[:3]) or 'no acute pressure points'} — "
        f"against {len(bearish)} relief driver(s) — "
        f"{', '.join(d.label.lower() for d in bearish[:3]) or 'no material relief channels'}. "
        f"Warehouse coverage stands at {rec.current_coverage_months or 0:.1f} months versus a target of "
        f"{rec.target_coverage_months or 0:.1f} months, framing the operational urgency of any near-term commitment. "
        f"Producer concentration, freight cost dynamics, and regional inventory flows interact with end-use demand "
        f"to set the equilibrium that the forecast corridor reflects. Structural factors such as energy intensity, "
        f"feedstock dependency and currency exposure remain the slow-moving backdrop, while disruption events and "
        f"weather shocks act as the fast-moving overlay. The net of these forces is summarised by the driver impact "
        f"chart on the following page."
    )

    recommendation_rationale = (
        f"The recommended action is {rec.action} over a {rec.recommended_horizon_days}-day horizon at a confidence "
        f"of {rec.confidence * 100:.0f}%. {rec.decision_rationale} "
        f"The decision weighs the asymmetry of the corridor (risk score {rec.risk_score:.1f}, opportunity score "
        f"{rec.opportunity_score:.1f}) against the current coverage position and the priority profile in force. "
        f"Where bullish drivers dominate, the policy preference is to accelerate coverage; where bearish drivers "
        f"dominate, it is to defer. Confidence is calibrated against data completeness and source reliability "
        f"rather than against historical model accuracy, and should be read as a degree of conviction rather than a "
        f"probability of outcome. The action holds until one of the conditions in the 'what would change the call' "
        f"section is triggered."
    )

    risk_assessment = (
        f"The upside tail of the corridor is driven by escalation in "
        f"{', '.join(d.label.lower() for d in bullish[:2]) or 'the current bullish factors'} and would materialise "
        f"if these signals compound rather than offset. The downside relief tail depends on "
        f"{', '.join(d.label.lower() for d in bearish[:2]) or 'demand softening or supply resumption'} taking hold "
        f"within the horizon. Corridor asymmetry — {fc.range_high_pct - fc.range_low_pct:.1f} percentage points "
        f"wide — quantifies how much room the market is pricing for surprises in either direction. "
        f"Residual unknowns include data latency on the most recent disruption signals, the precision of warehouse "
        f"coverage estimates, and possible un-modelled cross-material spillovers. None of these invalidate the "
        f"recommendation, but they justify keeping the watch list active rather than treating the call as final."
    )

    outlook = (
        f"Over the next 30 days, the base path should anchor expectations near a {fc.expected_change_pct:+.1f}% "
        f"drift versus spot, with the band widening as the horizon lengthens. The 60-to-90-day window is where the "
        f"worst and relief cases earn their weight: traders typically re-price the corridor as new evidence on "
        f"{drv_phrase} arrives. The buyer's positioning should aim to be inside coverage target before the band "
        f"widens further, while retaining optionality for the relief case. Re-evaluation should happen on a "
        f"monthly cadence at minimum, and immediately if any of the watch items breach their stated thresholds. "
        f"The strategic objective is not to time the absolute bottom but to keep weighted-average cost inside the "
        f"corridor's lower half."
    )

    methodology_note = (
        f"This report aggregates internal price-derived signals (momentum, seasonality, warehouse pressure) with "
        f"external market-intelligence signals sourced via Cala (producer concentration, disruption scan, dynamic "
        f"drivers). Signals are scored on direction, magnitude and confidence, combined with the forecast corridor, "
        f"and weighed against the active priority profile to produce the action. Sources are graded for reliability "
        f"and listed in the Evidence section. The output is a procurement decision aid, not financial advice."
    )

    headline = (
        f"{rec.action} {material} over {resp.horizon_days}d at {rec.confidence * 100:.0f}% confidence — "
        f"forecast {fc.expected_change_pct:+.1f}%."
    )

    return ExecutiveNarrative(
        headline=headline,
        market_overview=market_overview,
        supply_demand_landscape=supply_demand_landscape,
        recommendation_rationale=recommendation_rationale,
        risk_assessment=risk_assessment,
        outlook=outlook,
        methodology_note=methodology_note,
    )


def _merge_narrative(resp: AnalyzeResponse) -> ExecutiveNarrative:
    fb = _fallback_narrative(resp)
    en = resp.executive_narrative
    if not en:
        return fb
    return ExecutiveNarrative(
        headline=en.headline or fb.headline,
        market_overview=en.market_overview or fb.market_overview,
        supply_demand_landscape=en.supply_demand_landscape or fb.supply_demand_landscape,
        recommendation_rationale=en.recommendation_rationale or fb.recommendation_rationale,
        risk_assessment=en.risk_assessment or fb.risk_assessment,
        outlook=en.outlook or fb.outlook,
        methodology_note=en.methodology_note or fb.methodology_note,
    )


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def _render(resp: AnalyzeResponse) -> bytes:
    buf = io.BytesIO()
    styles = _styles()
    material = resp.material.value if hasattr(resp.material, "value") else str(resp.material)
    generated = resp.generated_at.strftime("%d/%m/%Y")
    narr = _merge_narrative(resp)

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=1.8 * cm,
        title=f"Executive report — {material}",
        author="Damm Procurement",
    )
    body_frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    cover_frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="cover")

    def _cover(c, d): _cover_page(c, d, material, resp.horizon_label, generated)
    def _hf(c, d): _header_footer(c, d, material, resp.horizon_label, generated)

    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[cover_frame], onPage=_cover),
        PageTemplate(id="body", frames=[body_frame], onPage=_hf),
    ])

    story: list[Any] = []

    fn_map = {ev.id: i + 1 for i, ev in enumerate(resp.evidence)}

    def fn_refs(ids: list[str]) -> str:
        nums = [str(fn_map[i]) for i in ids if i in fn_map]
        return f" <font color='#999999'>[{','.join(nums)}]</font>" if nums else ""

    # ---------- COVER ----------
    story.append(Spacer(1, 5.5 * cm))
    story.append(Paragraph("EXECUTIVE PROCUREMENT REPORT", styles["cover_kicker"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(material.capitalize(), styles["cover_title"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"{resp.horizon_label} outlook · {resp.analysis_type.replace('_', ' ').title()}",
        styles["cover_sub"],
    ))
    story.append(Spacer(1, 4.0 * cm))

    # Cover info card
    rec = resp.recommendation
    spot = resp.market_context.spot_price
    spot_str = f"{spot.value:,.2f} {spot.unit}" if spot else "—"
    coverage_str = f"{rec.current_coverage_months:.1f} mo" if rec.current_coverage_months is not None else "—"
    mtb_str = f"{rec.months_to_buy} mo" if rec.months_to_buy is not None else "—"
    forecast_str = f"{resp.forecast.expected_change_pct:+.1f}%"
    info_rows = [
        ["Recommendation", rec.action, "Horizon", f"{rec.recommended_horizon_days} days"],
        ["Spot price", spot_str, "Forecast", forecast_str],
        ["Coverage", coverage_str, "Months to buy", mtb_str],
        ["Material", material.capitalize(), "Date", generated],
    ]
    info = Table(info_rows, colWidths=[3.5 * cm, 4.5 * cm, 3.5 * cm, 4.5 * cm])
    info.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL_BG),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), SUBTLE),
                ("TEXTCOLOR", (2, 0), (2, -1), SUBTLE),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, DIVIDER),
                ("LINEABOVE", (0, 0), (-1, 0), 1.5, DAMM_RED),
            ]
        )
    )
    story.append(info)
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(narr.headline, styles["body_lead"]))
    story.append(PageBreak())

    # ---------- EXECUTIVE SUMMARY ----------
    story.extend(_section_header("Executive Summary", "01 · Recommendation", styles))
    story.append(_action_banner(rec.action, rec.confidence, rec.recommended_horizon_days, narr.headline, styles))
    story.append(Spacer(1, 0.4 * cm))

    # KPI strip
    kpis = [
        ("Spot", f"{spot.value:,.0f}" if spot else "—"),
        ("Forecast", f"{resp.forecast.expected_change_pct:+.1f}%"),
        ("Risk", f"{rec.risk_score:.1f}"),
        ("Opportunity", f"{rec.opportunity_score:.1f}"),
        ("Coverage", f"{rec.current_coverage_months or 0:.1f}m" if rec.current_coverage_months is not None else "—"),
        ("Months to buy", str(rec.months_to_buy) if rec.months_to_buy is not None else "—"),
    ]
    story.append(_kpi_strip(kpis, styles))
    story.append(Spacer(1, 0.5 * cm))

    # Confidence + risk/opp visuals
    story.append(KeepTogether([
        Table(
            [[
                _png_image(charts.confidence_dial(rec.confidence), width=6.5 * cm),
                _png_image(charts.risk_opportunity_chart(rec.risk_score, rec.opportunity_score), width=10 * cm),
            ]],
            colWidths=[7 * cm, 10 * cm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]),
        )
    ]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Market overview", styles["h3"]))
    story.append(Paragraph(narr.market_overview, styles["body"]))
    story.append(PageBreak())

    # ---------- MARKET CONTEXT ----------
    story.extend(_section_header("Market Context", "02 · Spot, forecast and coverage", styles))
    if spot:
        story.append(Paragraph(
            f"<b>Spot:</b> {spot.value:,.2f} {spot.unit} · source <i>{spot.source_id}</i> · as of {spot.as_of}",
            styles["body"],
        ))
    fc = resp.forecast
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(
        f"<b>Forecast:</b> {fc.direction}, expected {fc.expected_change_pct:+.1f}% "
        f"(range {fc.range_low_pct:+.1f}% to {fc.range_high_pct:+.1f}%). {fc.interpretation}",
        styles["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    story.append(_png_image(charts.forecast_corridor_pct(fc.range_low_pct, fc.expected_change_pct, fc.range_high_pct), width=17 * cm))
    story.append(Spacer(1, 0.3 * cm))

    if rec.current_coverage_months is not None or rec.target_coverage_months is not None:
        story.append(_png_image(charts.coverage_gauge(rec.current_coverage_months, rec.target_coverage_months), width=17 * cm))
        story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph("Supply and demand landscape", styles["h3"]))
    story.append(Paragraph(narr.supply_demand_landscape, styles["body"]))

    if resp.price_paths:
        story.append(Spacer(1, 0.4 * cm))
        spot_val = spot.value if spot else None
        story.append(_png_image(charts.price_paths_chart(resp.price_paths, spot_val), width=17 * cm))
    story.append(PageBreak())

    # ---------- DRIVERS ----------
    story.extend(_section_header("Drivers", "03 · What is moving the price", styles))
    if resp.drivers:
        header = ["Driver", "Direction", "Buyer", "Impact", "Score", "Conf.", "Refs"]
        rows = []
        for d in resp.drivers:
            rows.append([
                Paragraph(f"<b>{d.label}</b>", styles["body"]),
                d.direction.replace("_price_pressure", "").replace("_", " "),
                d.buyer_impact,
                d.impact,
                f"{d.impact_score:+.2f}",
                f"{d.confidence * 100:.0f}%",
                fn_refs(d.evidence_ids).replace(" <font color='#999999'>", "").replace("</font>", ""),
            ])
        story.append(_striped_table(header, rows, [4.8 * cm, 2.6 * cm, 1.5 * cm, 1.4 * cm, 1.4 * cm, 1.3 * cm, 2.0 * cm]))
        story.append(Spacer(1, 0.4 * cm))
        story.append(_png_image(charts.driver_impact_chart(resp.drivers), width=17 * cm))
        story.append(Spacer(1, 0.4 * cm))

        # Per-driver expanded explanations
        story.append(Paragraph("Driver detail", styles["h2"]))
        for d in resp.drivers:
            block = [
                Paragraph(f"<b>{d.label}</b> — {d.direction.replace('_', ' ')} · {d.impact} impact · {d.confidence * 100:.0f}% conf.{fn_refs(d.evidence_ids)}", styles["h3"]),
                Paragraph(d.explanation, styles["body"]),
                Spacer(1, 0.2 * cm),
            ]
            story.append(KeepTogether(block))
    else:
        story.append(Paragraph("No drivers identified.", styles["body"]))
    story.append(PageBreak())

    # ---------- RECOMMENDATION RATIONALE ----------
    story.extend(_section_header("Recommendation Rationale", "04 · Why this call", styles))
    story.append(Paragraph(narr.recommendation_rationale, styles["body"]))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Reasoning chain", styles["h2"]))
    for step in resp.reasoning_chain:
        refs = fn_refs(step.evidence_ids)
        story.append(Paragraph(
            f"<b>{step.step}. [{step.type}]</b> {step.text}{refs}",
            styles["body"],
        ))
        story.append(Spacer(1, 0.12 * cm))
    story.append(PageBreak())

    # ---------- RISK & SCENARIOS ----------
    story.extend(_section_header("Risk & Scenarios", "05 · How the corridor could move", styles))
    story.append(Paragraph(narr.risk_assessment, styles["body"]))
    story.append(Spacer(1, 0.3 * cm))

    color_map = {"base_case": charts.BASE_BLUE, "worst_case": charts.WORST_RED, "relief_case": charts.RELIEF_GREEN}
    for p in resp.price_paths:
        block: list[Any] = []
        block.append(Paragraph(f"{p.label} — {p.direction.replace('_', ' ')}", styles["h3"]))
        block.append(Paragraph(p.summary, styles["body"]))
        block.append(Paragraph(
            f"<b>Expected:</b> {p.expected_change_pct:+.1f}% "
            f"(range {p.range_low_pct:+.1f}% to {p.range_high_pct:+.1f}%){fn_refs(p.evidence_ids)}",
            styles["body"],
        ))
        block.append(Paragraph(f"<i>{p.explainability.plain_language}</i>", styles["small"]))
        if p.graph_points:
            block.append(Spacer(1, 0.15 * cm))
            block.append(_png_image(charts.scenario_sparkline(p.graph_points, color_map.get(p.id, charts.BASE_BLUE)), width=7 * cm))
        block.append(Spacer(1, 0.3 * cm))
        story.append(KeepTogether(block))
    story.append(PageBreak())

    # ---------- OUTLOOK / WATCH ----------
    story.extend(_section_header("Outlook & What to Monitor", "06 · The next 30–90 days", styles))
    story.append(Paragraph(narr.outlook, styles["body"]))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("What would change the call", styles["h2"]))
    for c in resp.what_would_change_the_recommendation:
        story.append(Paragraph(
            f"<b>If:</b> {c.condition} → <b>shift:</b> {c.likely_shift}. <i>{c.reason}</i>",
            styles["body"],
        ))
        story.append(Spacer(1, 0.12 * cm))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("What to monitor", styles["h2"]))
    for w in resp.what_to_monitor:
        story.append(Paragraph(f"<b>{w.item}.</b> {w.why}{fn_refs(w.evidence_source_ids)}", styles["body"]))
        story.append(Spacer(1, 0.15 * cm))
    story.append(PageBreak())

    # ---------- EVIDENCE ----------
    story.extend(_section_header("Evidence & Sources", "07 · Citations", styles))
    for i, ev in enumerate(resp.evidence, start=1):
        dt = f" ({ev.date})" if ev.date else ""
        url = f" — <link href='{ev.url}'><font color='#1F4E79'>{ev.url}</font></link>" if ev.url else ""
        used = f" · used for: {', '.join(ev.used_for)}" if ev.used_for else ""
        story.append(Paragraph(
            f"<b>[{i}]</b> {ev.source} — {ev.title}{dt} — <i>reliability: {ev.reliability}</i>{url}<br/>"
            f"<font color='#5C5C5C'>{ev.signal_extracted}</font>{used}",
            styles["footnote"],
        ))
        story.append(Spacer(1, 0.12 * cm))
    story.append(PageBreak())

    # ---------- METHODOLOGY / AUDIT ----------
    story.extend(_section_header("Methodology & Audit", "08 · How this report was built", styles))
    story.append(Paragraph(narr.methodology_note, styles["body"]))
    story.append(Spacer(1, 0.3 * cm))

    if resp.limitations:
        story.append(Paragraph("Limitations", styles["h2"]))
        for l in resp.limitations:
            story.append(Paragraph(f"• {l}", styles["body"]))
        story.append(Spacer(1, 0.25 * cm))

    dq = resp.audit_trail.data_quality
    story.append(Paragraph("Data quality", styles["h2"]))
    dq_rows = [
        ["Price data", "Available" if dq.price_data_available else "Missing"],
        ["Warehouse data", "Available" if dq.warehouse_data_available else "Missing"],
        ["External news", "Available" if dq.external_news_available else "Missing"],
        ["Source URLs", "Available" if dq.source_urls_available else "Missing"],
    ]
    dq_table = Table(dq_rows, colWidths=[5 * cm, 12 * cm])
    dq_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT_GREY]),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, DIVIDER),
            ]
        )
    )
    story.append(dq_table)
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Tools called", styles["h2"]))
    story.append(Paragraph(", ".join(resp.audit_trail.tools_called) or "—", styles["body"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        f"Schema {resp.schema_version} · Template {TEMPLATE_VERSION} · Generated {generated}",
        styles["small"],
    ))

    doc.build(story)
    return buf.getvalue()
