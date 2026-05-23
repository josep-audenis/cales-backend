"""Executive PDF report builder from AnalyzeResponse."""

from __future__ import annotations

import hashlib
import io
from functools import lru_cache
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
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
from app.schemas.analyze_response import AnalyzeResponse

TEMPLATE_VERSION = "1.0"

DAMM_RED = colors.HexColor("#E30613")
DAMM_BLACK = colors.HexColor("#1A1A1A")
LIGHT_GREY = colors.HexColor("#F2F2F2")
MID_GREY = colors.HexColor("#999999")

ACTION_COLORS = {
    "BUY_NOW": colors.HexColor("#E30613"),
    "HEDGE": colors.HexColor("#E08E1A"),
    "WAIT": colors.HexColor("#1F77B4"),
    "MONITOR": colors.HexColor("#666666"),
}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    s = {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=22, leading=26, textColor=DAMM_BLACK),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=15, leading=18, textColor=DAMM_RED, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12, leading=14, textColor=DAMM_BLACK, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=9.5, leading=13, alignment=TA_LEFT),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=8, leading=10, textColor=MID_GREY),
        "chip": ParagraphStyle("chip", parent=base["BodyText"], fontSize=14, leading=16, textColor=colors.white, alignment=TA_CENTER),
        "cover_meta": ParagraphStyle("cm", parent=base["BodyText"], fontSize=11, leading=15, textColor=DAMM_BLACK),
        "footnote": ParagraphStyle("fn", parent=base["BodyText"], fontSize=8, leading=10),
    }
    return s


def _header_footer(canvas, doc, material: str, horizon_label: str, generated_at: str) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MID_GREY)
    canvas.drawString(2 * cm, A4[1] - 1.2 * cm, f"{material}  ·  {horizon_label}  ·  {generated_at}")
    canvas.setStrokeColor(MID_GREY)
    canvas.setLineWidth(0.3)
    canvas.line(2 * cm, A4[1] - 1.35 * cm, A4[0] - 2 * cm, A4[1] - 1.35 * cm)
    canvas.drawString(2 * cm, 1.0 * cm, "Procurement decision aid — not financial advice")
    canvas.drawRightString(A4[0] - 2 * cm, 1.0 * cm, f"Page {doc.page}")
    canvas.restoreState()


def _action_chip(action: str, confidence: float, horizon_days: int, styles) -> Table:
    color = ACTION_COLORS.get(action.upper(), DAMM_BLACK)
    tbl = Table(
        [[Paragraph(f"<b>{action}</b>", styles["chip"])]],
        colWidths=[6 * cm],
        rowHeights=[1.4 * cm],
    )
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 0.5, color),
                ("ROUNDEDCORNERS", [6, 6, 6, 6]),
            ]
        )
    )
    meta = Paragraph(
        f"Confidence: <b>{confidence * 100:.0f}%</b> · Recommended horizon: <b>{horizon_days}d</b>",
        styles["body"],
    )
    wrap = Table([[tbl, meta]], colWidths=[6.5 * cm, 10.5 * cm])
    wrap.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return wrap


def _kv_table(rows: list[tuple[str, str]], col_widths=(5 * cm, 11 * cm)) -> Table:
    data = [[k, v] for k, v in rows]
    t = Table(data, colWidths=col_widths)
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), DAMM_BLACK),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT_GREY]),
                ("BOX", (0, 0), (-1, -1), 0.25, MID_GREY),
                ("INNERGRID", (0, 0), (-1, -1), 0.15, MID_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _striped_table(header: list[str], rows: list[list[Any]], col_widths: list[float]) -> Table:
    data = [header] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DAMM_BLACK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
                ("BOX", (0, 0), (-1, -1), 0.25, MID_GREY),
                ("INNERGRID", (0, 0), (-1, -1), 0.15, MID_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
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
    """Render PDF bytes. Cached by response hash + template version."""
    h = _hash_response(resp)
    return _cached_render(h, resp.model_dump_json())


def _render(resp: AnalyzeResponse) -> bytes:
    buf = io.BytesIO()
    styles = _styles()
    material = resp.material.value if hasattr(resp.material, "value") else str(resp.material)
    generated = resp.generated_at.strftime("%Y-%m-%d %H:%M UTC")

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=1.6 * cm,
        title=f"Executive report — {material}",
        author="Damm Procurement",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")

    def _hf(c, d):
        _header_footer(c, d, material, resp.horizon_label, generated)

    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame]),
        PageTemplate(id="body", frames=[frame], onPage=_hf),
    ])

    story: list[Any] = []

    # Footnote map: evidence_id -> [N]
    fn_map = {ev.id: i + 1 for i, ev in enumerate(resp.evidence)}

    def fn_refs(ids: list[str]) -> str:
        nums = [str(fn_map[i]) for i in ids if i in fn_map]
        return f"[{','.join(nums)}]" if nums else ""

    # ---------- COVER ----------
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("Executive Procurement Report", styles["title"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(f"<b>Material:</b> {material}", styles["cover_meta"]))
    story.append(Paragraph(f"<b>Horizon:</b> {resp.horizon_label} ({resp.horizon_days} days)", styles["cover_meta"]))
    story.append(Paragraph(f"<b>Analysis type:</b> {resp.analysis_type}", styles["cover_meta"]))
    story.append(Paragraph(f"<b>Generated:</b> {generated}", styles["cover_meta"]))
    story.append(Spacer(1, 10 * cm))
    story.append(Paragraph("Damm · Procurement Intelligence", styles["small"]))
    story.append(PageBreak())

    # ---------- EXECUTIVE SUMMARY ----------
    story.append(Paragraph("Executive Summary", styles["h1"]))
    rec = resp.recommendation
    story.append(_action_chip(rec.action, rec.confidence, rec.recommended_horizon_days, styles))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(rec.summary, styles["body"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(f"<b>Decision rationale.</b> {rec.decision_rationale}", styles["body"]))
    story.append(Spacer(1, 0.3 * cm))

    spot = resp.market_context.spot_price
    kv = [
        ("Spot price", f"{spot.value:.2f} {spot.unit} (as of {spot.as_of})" if spot else "—"),
        ("Warehouse fill", f"{resp.market_context.warehouse_fill_pct:.1f}%" if resp.market_context.warehouse_fill_pct is not None else "—"),
        ("Months to buy", str(rec.months_to_buy) if rec.months_to_buy is not None else "—"),
        ("Current coverage", f"{rec.current_coverage_months:.1f} mo" if rec.current_coverage_months is not None else "—"),
        ("Target coverage", f"{rec.target_coverage_months:.1f} mo" if rec.target_coverage_months is not None else "—"),
        ("Risk / opportunity", f"{rec.risk_score:.2f} / {rec.opportunity_score:.2f}"),
    ]
    story.append(_kv_table(kv))
    story.append(PageBreak())

    # ---------- MARKET CONTEXT ----------
    story.append(Paragraph("Market Context", styles["h1"]))
    if spot:
        story.append(Paragraph(
            f"<b>Spot:</b> {spot.value:.2f} {spot.unit} · source <i>{spot.source_id}</i> · as of {spot.as_of}",
            styles["body"],
        ))
    fc = resp.forecast
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        f"<b>Forecast:</b> {fc.direction}, expected {fc.expected_change_pct:+.1f}% "
        f"(range {fc.range_low_pct:+.1f}% to {fc.range_high_pct:+.1f}%).",
        styles["body"],
    ))
    story.append(Paragraph(fc.interpretation, styles["body"]))
    story.append(Spacer(1, 0.3 * cm))

    if rec.current_coverage_months is not None or rec.target_coverage_months is not None:
        story.append(_png_image(
            charts.coverage_gauge(rec.current_coverage_months, rec.target_coverage_months),
            width=10 * cm,
        ))
        story.append(Spacer(1, 0.2 * cm))

    if resp.price_paths:
        spot_val = spot.value if spot else None
        story.append(_png_image(charts.price_paths_chart(resp.price_paths, spot_val), width=16 * cm))
    story.append(PageBreak())

    # ---------- DRIVERS ----------
    story.append(Paragraph("Drivers", styles["h1"]))
    if resp.drivers:
        header = ["Driver", "Dir.", "Buyer", "Impact", "Score", "Conf.", "Refs"]
        rows = []
        for d in resp.drivers:
            rows.append([
                Paragraph(d.label, styles["body"]),
                d.direction.replace("_price_pressure", "").replace("_", " "),
                d.buyer_impact,
                d.impact,
                f"{d.impact_score:.2f}",
                f"{d.confidence * 100:.0f}%",
                fn_refs(d.evidence_ids),
            ])
        story.append(_striped_table(header, rows, [4.5 * cm, 2.4 * cm, 1.6 * cm, 1.4 * cm, 1.3 * cm, 1.3 * cm, 2.5 * cm]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(_png_image(charts.driver_impact_chart(resp.drivers), width=16 * cm))
    else:
        story.append(Paragraph("No drivers identified.", styles["body"]))
    story.append(PageBreak())

    # ---------- REASONING ----------
    story.append(Paragraph("Reasoning Chain", styles["h1"]))
    for step in resp.reasoning_chain:
        refs = fn_refs(step.evidence_ids)
        story.append(Paragraph(
            f"<b>{step.step}. [{step.type}]</b> {step.text} {refs}",
            styles["body"],
        ))
        story.append(Spacer(1, 0.15 * cm))
    story.append(PageBreak())

    # ---------- SCENARIOS ----------
    story.append(Paragraph("Scenarios", styles["h1"]))
    color_map = {"base_case": charts.BASE_BLUE, "worst_case": charts.WORST_RED, "relief_case": charts.RELIEF_GREEN}
    for p in resp.price_paths:
        block: list[Any] = []
        block.append(Paragraph(f"<b>{p.label}</b> — {p.direction.replace('_', ' ')}", styles["h2"]))
        block.append(Paragraph(p.summary, styles["body"]))
        block.append(Paragraph(
            f"Expected change: <b>{p.expected_change_pct:+.1f}%</b> "
            f"(range {p.range_low_pct:+.1f}% to {p.range_high_pct:+.1f}%) {fn_refs(p.evidence_ids)}",
            styles["body"],
        ))
        block.append(Paragraph(f"<i>{p.explainability.plain_language}</i>", styles["small"]))
        if p.graph_points:
            block.append(_png_image(charts.scenario_sparkline(p.graph_points, color_map.get(p.id, charts.BASE_BLUE)), width=6 * cm))
        block.append(Spacer(1, 0.3 * cm))
        story.append(KeepTogether(block))
    story.append(PageBreak())

    # ---------- WHAT CHANGES / WHAT TO MONITOR ----------
    story.append(Paragraph("What Would Change the Call", styles["h1"]))
    for c in resp.what_would_change_the_recommendation:
        story.append(Paragraph(
            f"<b>If:</b> {c.condition} → <b>shift:</b> {c.likely_shift}. <i>{c.reason}</i>",
            styles["body"],
        ))
        story.append(Spacer(1, 0.15 * cm))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("What to Monitor", styles["h1"]))
    for w in resp.what_to_monitor:
        story.append(Paragraph(f"<b>{w.item}.</b> {w.why} {fn_refs(w.evidence_source_ids)}", styles["body"]))
        story.append(Spacer(1, 0.15 * cm))
    story.append(PageBreak())

    # ---------- EVIDENCE ----------
    story.append(Paragraph("Evidence & Sources", styles["h1"]))
    for i, ev in enumerate(resp.evidence, start=1):
        dt = f" ({ev.date})" if ev.date else ""
        url = f" — <link href='{ev.url}'>{ev.url}</link>" if ev.url else ""
        used = f" · used for: {', '.join(ev.used_for)}" if ev.used_for else ""
        story.append(Paragraph(
            f"<b>[{i}]</b> {ev.source} — {ev.title}{dt} — reliability: {ev.reliability}{url}<br/>"
            f"<i>{ev.signal_extracted}</i>{used}",
            styles["footnote"],
        ))
        story.append(Spacer(1, 0.1 * cm))
    story.append(PageBreak())

    # ---------- LIMITATIONS / AUDIT ----------
    story.append(Paragraph("Limitations & Audit Trail", styles["h1"]))
    if resp.limitations:
        for l in resp.limitations:
            story.append(Paragraph(f"• {l}", styles["body"]))
    dq = resp.audit_trail.data_quality
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("<b>Data quality</b>", styles["h2"]))
    story.append(_kv_table([
        ("Price data", "✓" if dq.price_data_available else "✗"),
        ("Warehouse data", "✓" if dq.warehouse_data_available else "✗"),
        ("External news", "✓" if dq.external_news_available else "✗"),
        ("Source URLs", "✓" if dq.source_urls_available else "✗"),
    ], col_widths=(5 * cm, 11 * cm)))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("<b>Tools called</b>", styles["h2"]))
    story.append(Paragraph(", ".join(resp.audit_trail.tools_called) or "—", styles["body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"Schema {resp.schema_version} · Template {TEMPLATE_VERSION} · Generated {generated}",
        styles["small"],
    ))

    doc.build(story)
    return buf.getvalue()
