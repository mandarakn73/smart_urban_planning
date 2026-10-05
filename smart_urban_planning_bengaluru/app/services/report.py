from __future__ import annotations

from io import BytesIO
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def _p(text: Any, style):
    return Paragraph(str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)


def build_report_pdf(payload: Dict[str, Any]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="Smart Urban Planning Assistant – Bengaluru Planning Report",
        author="Smart Urban Planning Assistant",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8.5, leading=11))
    styles.add(ParagraphStyle(name="Heading", parent=styles["Heading2"], spaceBefore=8, spaceAfter=6))

    story = []
    story.append(_p("Smart Urban Planning Assistant – Bengaluru", styles["TitleCenter"]))
    story.append(_p("Conceptual planning report generated from the local Digital Twin/GIS context, planning-knowledge retrieval and scenario analysis.", styles["Small"]))
    story.append(Spacer(1, 6 * mm))

    scenario = payload.get("scenario") or {}
    loc = scenario.get("location") or {}
    dev = scenario.get("development") or {}
    spatial = payload.get("spatial") or {}
    impact = payload.get("impact_analysis") or {}
    rag = payload.get("planning_knowledge") or {}
    alternatives = payload.get("alternatives") or {}

    site_rows = [
        ["Latitude", loc.get("latitude", "—")],
        ["Longitude", loc.get("longitude", "—")],
        ["Radius (m)", scenario.get("radius_m", "—")],
        ["Development", dev.get("type", "—")],
        ["Units", dev.get("units", "—")],
    ]
    story.append(_p("1. Site & Scenario", styles["Heading"]))
    t = Table(site_rows, colWidths=[45 * mm, 120 * mm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d5dd")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f4f7")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)

    story.append(_p("2. Spatial Findings", styles["Heading"]))
    findings = (spatial.get("findings") or {})
    spatial_rows = [["Layer", "Count in radius", "Nearest (m)"]]
    for key in ["roads", "schools", "hospitals", "police", "fire_stations", "bus_stops", "parks", "water_bodies", "buildings", "landuse", "traffic_events"]:
        d = findings.get(key) or {}
        spatial_rows.append([key.replace("_", " ").title(), d.get("count_within_radius", "—"), d.get("nearest_m", "—")])
    t = Table(spatial_rows, colWidths=[75 * mm, 45 * mm, 45 * mm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d0d5dd")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2ff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ]))
    story.append(t)

    story.append(_p("3. Impact Analysis", styles["Heading"]))
    for domain in ["mobility", "social_infrastructure", "environment", "built_context", "utilities", "regulatory"]:
        d = impact.get(domain) or {}
        story.append(_p(f"<b>{domain.replace('_', ' ').title()}</b>: {d.get('interpretation', 'No narrative returned.')}", styles["Small"]))
        story.append(Spacer(1, 2 * mm))

    story.append(_p("4. Planning Knowledge (RAG)", styles["Heading"]))
    story.append(_p(f"Provider: {rag.get('provider', 'unknown')} • Evidence items: {len(rag.get('results') or [])}", styles["Small"]))
    for i, item in enumerate((rag.get("results") or [])[:8], start=1):
        text = item.get("text", "")
        page = f" p.{item['page']}" if item.get("page") else ""
        story.append(_p(f"{i}. {item.get('document', 'Planning source')}{page}: {text}", styles["Small"]))
        story.append(Spacer(1, 1.5 * mm))

    story.append(PageBreak())
    story.append(_p("5. Conceptual Planning Alternatives", styles["Heading"]))
    for key, option in alternatives.items():
        s = option.get("summary") or {}
        story.append(_p(f"{option.get('strategy_label', key.title())}", styles["Heading"]))
        rows = [
            ["Site area (m²)", s.get("site_area_m2", "—")],
            ["Actual parcel", "Yes" if s.get("actual_parcel") else "No"],
            ["Building blocks", s.get("building_blocks", "—")],
            ["Indicative units/block", s.get("indicative_units_per_block", "—")],
            ["Target green share", f"{round(float(s.get('target_green_share', 0)) * 100)}%"],
            ["RAG evidence items", s.get("rag_evidence_items", "—")],
        ]
        tt = Table(rows, colWidths=[65 * mm, 100 * mm])
        tt.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d0d5dd")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f4f7")),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ]))
        story.append(tt)
        story.append(Spacer(1, 3 * mm))
        for decision in option.get("decision_log") or []:
            story.append(_p(f"<b>{decision.get('decision', '').replace('_', ' ').title()}</b>: {decision.get('reason', '')} [{decision.get('evidence', '')}]", styles["Small"]))
        story.append(Spacer(1, 5 * mm))

    story.append(_p("6. Limitations", styles["Heading"]))
    limitations = [
        "This output is conceptual and not construction-ready or a regulatory approval.",
        "OSM-derived context is indicative and depends on the completeness and currency of the local extract.",
        "Utilities and demand-capacity calculations are not performed unless validated local utility datasets are loaded.",
        "Numeric regulatory values are not inferred unless directly supported by the retrieved planning evidence and verified for the site/jurisdiction.",
        "For approval or professional design work, use an authoritative parcel, survey, applicable zoning regulations and licensed planning/architectural review.",
    ]
    for x in limitations:
        story.append(_p("• " + x, styles["Small"]))
        story.append(Spacer(1, 1.5 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(_p("Generated by the Smart Urban Planning Assistant prototype. Spatial design is a research visualization, not a legal or construction deliverable.", styles["Small"]))
    doc.build(story)
    return buf.getvalue()


def build_report_html(payload: Dict[str, Any]) -> str:
    import html

    scenario = payload.get("scenario") or {}
    spatial = payload.get("spatial") or {}
    impact = payload.get("impact_analysis") or {}
    alternatives = payload.get("alternatives") or {}
    rag = payload.get("planning_knowledge") or {}

    loc = scenario.get("location") or {}
    dev = scenario.get("development") or {}

    rows = []
    for key, option in alternatives.items():
        s = option.get("summary") or {}
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(option.get('strategy_label', key.title())))}</td>"
            f"<td>{html.escape(str(s.get('building_blocks', '—')))}</td>"
            f"<td>{html.escape(str(s.get('indicative_units_per_block', '—')))}</td>"
            f"<td>{round(float(s.get('target_green_share', 0)) * 100)}%</td>"
            f"<td>{html.escape(str(s.get('target_parking_share', 0) * 100))}%</td>"
            "</tr>"
        )

    finding_rows = []
    for key in [
        "roads", "schools", "hospitals", "police", "fire_stations",
        "bus_stops", "parks", "water_bodies", "buildings", "landuse",
        "traffic_events"
    ]:
        d = (spatial.get("findings") or {}).get(key) or {}
        nearest = d.get("nearest_m")
        nearest_text = "—" if nearest is None else f"{float(nearest):.1f}"
        finding_rows.append(
            "<tr>"
            f"<td>{html.escape(key.replace('_', ' ').title())}</td>"
            f"<td>{html.escape(str(d.get('count_within_radius', '—')))}</td>"
            f"<td>{nearest_text}</td>"
            "</tr>"
        )

    context_cards = []
    summary_ctx = (scenario.get("observed_context_summary") or {})
    for key in ["roads", "schools", "hospitals", "bus_stops", "parks", "water_bodies"]:
        d = summary_ctx.get(key) or {}
        context_cards.append(
            f"<div class='card'><div class='card-title'>{html.escape(key.replace('_', ' ').title())}</div>"
            f"<div class='card-value'>{html.escape(str(d.get('count', '—')))}</div>"
            "</div>"
        )

    decision_blocks = []
    for key, option in alternatives.items():
        label = option.get("strategy_label", key.title())
        decisions = option.get("decision_log") or []
        if not decisions:
            continue
        items = []
        for decision in decisions:
            items.append(
                "<li>"
                f"<b>{html.escape(str(decision.get('decision', '').replace('_', ' ').title()))}</b>: "
                f"{html.escape(str(decision.get('reason', '')))} "
                f"<span class='evidence'>[{html.escape(str(decision.get('evidence', '')))}]</span>"
                "</li>"
            )
        decision_blocks.append(
            f"<div class='decision-block'><h3>{html.escape(str(label))}</h3><ul>{''.join(items)}</ul></div>"
        )

    impact_blocks = []
    for domain in ["mobility", "social_infrastructure", "environment", "built_context", "utilities", "regulatory"]:
        d = impact.get(domain) or {}
        impact_blocks.append(
            "<div class='impact'>"
            f"<div class='impact-head'><b>{html.escape(domain.replace('_', ' ').title())}</b>"
            f"<span class='tag'>{html.escape(str(d.get('status', 'not_available')))}</span></div>"
            f"<p>{html.escape(str(d.get('interpretation', 'No narrative returned.')))}</p>"
            "</div>"
        )

    rag_items = []
    for i, item in enumerate((rag.get("results") or [])[:8], start=1):
        page = f" • p.{html.escape(str(item['page']))}" if item.get("page") else ""
        rag_items.append(
            "<div class='rag-item'>"
            f"<div class='rag-title'>{i}. {html.escape(str(item.get('document', 'Planning source')))}{page}</div>"
            f"<div>{html.escape(str(item.get('text', '')))}</div>"
            "</div>"
        )

    return f"""<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<title>Bengaluru Planning Report</title>
<style>
body{{font-family:Arial,sans-serif;max-width:1050px;margin:40px auto;padding:0 28px;color:#172b4d;line-height:1.5}}
h1{{margin-bottom:4px;font-size:30px}}
h2{{margin-top:30px;border-bottom:2px solid #d9e2ec;padding-bottom:7px}}
h3{{margin-bottom:8px}}
.meta{{color:#667085;margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:16px 0 24px}}
.card{{border:1px solid #d9e2ec;border-radius:10px;padding:14px;background:#f8fafc}}
.card-title{{font-size:12px;color:#667085}}
.card-value{{font-size:22px;font-weight:700;margin-top:4px}}
table{{border-collapse:collapse;width:100%;margin:12px 0 20px}}
td,th{{border:1px solid #d9dee7;padding:9px;text-align:left;vertical-align:top}}
th{{background:#eef4fb}}
.note{{background:#fff8e7;padding:13px;margin:10px 0;border-radius:8px;border-left:4px solid #e5a100}}
.impact{{border:1px solid #d9e2ec;border-radius:10px;padding:12px;margin:10px 0;background:#fff}}
.impact-head{{display:flex;justify-content:space-between;align-items:center}}
.tag{{font-size:12px;background:#eef4fb;padding:4px 8px;border-radius:999px;color:#315b85}}
.decision-block{{border:1px solid #d9e2ec;border-radius:10px;padding:10px 14px;margin:10px 0}}
.evidence{{color:#667085}}
.rag-item{{border:1px solid #d9e2ec;border-radius:8px;padding:12px;margin:8px 0;background:#fafcff}}
.rag-title{{font-weight:700;margin-bottom:6px}}
ul{{margin-top:6px}}
.small{{color:#667085;font-size:13px}}
@media(max-width:800px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style>
</head>
<body>
<h1>Smart Urban Planning Assistant – Bengaluru</h1>
<div class='meta'>Conceptual planning report based on the Digital Twin/GIS context, spatial analysis, planning-knowledge retrieval and scenario alternatives.</div>

<h2>1. Site & Scenario</h2>
<table>
<tr><th>Latitude</th><td>{html.escape(str(loc.get('latitude','—')))}</td></tr>
<tr><th>Longitude</th><td>{html.escape(str(loc.get('longitude','—')))}</td></tr>
<tr><th>Analysis radius</th><td>{html.escape(str(scenario.get('radius_m','—')))} m</td></tr>
<tr><th>Development type</th><td>{html.escape(str(dev.get('type','—')))}</td></tr>
<tr><th>Units</th><td>{html.escape(str(dev.get('units','—')))}</td></tr>
</table>

<h2>2. Observed Urban Context</h2>
<div class='grid'>{''.join(context_cards)}</div>
<p class='small'>These are observed features in the processed Bengaluru dataset within the requested analysis radius. A zero count does not imply city-wide absence.</p>

<h2>3. Spatial Findings</h2>
<table>
<tr><th>Layer</th><th>Count within radius</th><th>Nearest feature (m)</th></tr>
{''.join(finding_rows)}
</table>

<h2>4. Impact Analysis</h2>
{''.join(impact_blocks)}

<h2>5. Planning Knowledge (RAG)</h2>
<p>Provider: <b>{html.escape(str(rag.get('provider','unknown')))}</b> • Evidence items: <b>{len(rag.get('results') or [])}</b></p>
{''.join(rag_items)}

<h2>6. Planning Alternatives</h2>
<table>
<tr><th>Option</th><th>Blocks</th><th>Indicative units/block</th><th>Target green share</th><th>Target parking share</th></tr>
{''.join(rows)}
</table>

<h2>7. Design Decisions & Explainability</h2>
{''.join(decision_blocks)}

<h2>8. Data & Limitations</h2>
<div class='note'>Conceptual only; not construction-ready and not a regulatory approval. Regulatory values, setbacks, FAR, parking and fire-access requirements require parcel-specific validation.</div>
<div class='note'>An actual parcel boundary should be supplied for site-specific validation. Without one, the conceptual site envelope is only a planning visualization.</div>
<p>Utilities and demand-capacity calculations are not performed unless validated local utility datasets and assumptions are supplied. OSM-derived context depends on the completeness and currency of the processed extract.</p>

<p class='small'>Generated by the Smart Urban Planning Assistant prototype.</p>
</body>
</html>"""
