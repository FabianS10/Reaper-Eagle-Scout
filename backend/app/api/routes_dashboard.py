from datetime import date, timedelta
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.opportunity import Opportunity
from app.schemas.search_schema import DashboardSummary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

FX_TO_USD = {
    "COP": 1 / 4200, "MXN": 1 / 17, "PEN": 1 / 3.7,
    "CLP": 1 / 900, "USD": 1.0, "EUR": 1.08, "BRL": 1 / 5.1,
}


@router.get("/summary", response_model=DashboardSummary)
def get_summary(db: Session = Depends(get_db)):
    opps = db.query(Opportunity).all()
    today = date.today()

    total_usd = 0.0
    for o in opps:
        if o.budget_amount:
            fx = FX_TO_USD.get(o.budget_currency or "USD", 1.0)
            total_usd += float(o.budget_amount) * fx

    by_sector: dict[str, int] = {}
    by_country: dict[str, int] = {}
    by_type: dict[str, int] = {}
    urgency_map = {"critical": 0, "hot": 0, "open": 0, "unknown": 0}

    conf_sum = 0.0
    conf_count = 0

    for o in opps:
        if o.sector:
            by_sector[o.sector] = by_sector.get(o.sector, 0) + 1
        if o.country:
            by_country[o.country] = by_country.get(o.country, 0) + 1
        if o.opportunity_type:
            by_type[o.opportunity_type] = by_type.get(o.opportunity_type, 0) + 1
        if o.extraction_confidence:
            conf_sum += o.extraction_confidence
            conf_count += 1
        if o.deadline:
            days = (o.deadline - today).days
            if days < 0:
                pass  # closed
            elif days <= 7:
                urgency_map["critical"] += 1
            elif days <= 21:
                urgency_map["hot"] += 1
            else:
                urgency_map["open"] += 1
        else:
            urgency_map["unknown"] += 1

    closing_soon = sum(
        1 for o in opps
        if o.deadline and 0 <= (o.deadline - today).days <= 14
    )
    sources = len(set(o.source_url.split("/")[2] for o in opps if o.source_url))

    return DashboardSummary(
        total_opportunities=len(opps),
        high_priority_count=sum(1 for o in opps if (o.final_score or 0) >= 80),
        closing_soon_count=closing_soon,
        avg_confidence=round(conf_sum / conf_count, 3) if conf_count else 0.0,
        total_pipeline_value_usd=round(total_usd, 2),
        sources_scanned=sources,
        by_sector=by_sector,
        by_country=by_country,
        by_type=by_type,
        urgency_map=urgency_map,
    )


@router.get("/report", response_class=HTMLResponse)
def generate_report(db: Session = Depends(get_db)):
    """
    Generate a printable HTML intelligence report.
    Open in browser and use Print → Save as PDF for a clean PDF.
    """
    from datetime import datetime
    opps = db.query(Opportunity).order_by(
        Opportunity.final_score.desc().nulls_last()
    ).all()

    today = date.today()

    def fmt_budget(amount, currency):
        if not amount:
            return "—"
        amount = float(amount)
        if currency == "COP":
            if amount >= 1e9:
                return f"{amount/1e9:.1f}B COP"
            return f"{amount/1e6:.0f}M COP"
        if currency == "USD":
            if amount >= 1e6:
                return f"${amount/1e6:.1f}M USD"
            return f"${amount/1e3:.0f}K USD"
        return f"{amount:,.0f} {currency or ''}"

    def fmt_days(dl):
        if not dl:
            return "—"
        d = (dl - today).days
        if d < 0:
            return f"Closed ({abs(d)}d ago)"
        return f"{d}d remaining"

    rows = ""
    for o in opps:
        score = int(o.final_score or 0)
        score_color = "#2d6a2d" if score >= 80 else "#7a6020" if score >= 65 else "#555"
        dl_color = "#8b1a1a" if o.deadline and (o.deadline - today).days <= 14 else "#1a1a1a"
        rows += f"""
        <tr>
          <td style="font-weight:700;color:{score_color};text-align:center">{score}</td>
          <td>{o.title or '—'}</td>
          <td style="color:#555;font-size:11px">{o.organization or '—'}</td>
          <td style="font-family:monospace;font-size:11px;color:{dl_color}">{fmt_days(o.deadline)}</td>
          <td style="font-family:monospace;font-size:11px">{fmt_budget(o.budget_amount, o.budget_currency)}</td>
          <td style="font-family:monospace;font-size:11px">{int((o.extraction_confidence or 0)*100)}%</td>
        </tr>"""

    cards = ""
    for o in opps:
        score = int(o.final_score or 0)
        evs = "\n".join(
            f'<div class="ev">{e}</div>'
            for e in (o.evidence_snippets or [])
        )
        reqs = "\n".join(
            f"<li>{r}</li>"
            for r in (o.requirements or [])[:5]
        )
        cards += f"""
        <div class="card">
          <div class="card-score">{score}/100</div>
          <div class="card-title">{o.title or '—'}</div>
          <div class="card-org">{o.organization or '—'} &mdash; {o.country or ''}, {o.city or ''}</div>
          <div class="card-why">{o.why_score()}</div>
          <div class="card-section-label">Evidence</div>
          {evs or '<div class="ev">No evidence snippets extracted.</div>'}
          <div class="card-section-label">Requirements</div>
          <ul class="req-list">{reqs or '<li>No requirements extracted.</li>'}</ul>
          <div class="card-meta">
            <span>Deadline: {o.deadline or '—'}</span>
            <span>Budget: {fmt_budget(o.budget_amount, o.budget_currency)}</span>
            <span>Source: {(o.source_url or '—')[:60]}</span>
          </div>
        </div>"""

    total_usd = sum(
        float(o.budget_amount or 0) * FX_TO_USD.get(o.budget_currency or "USD", 1.0)
        for o in opps
    )
    avg_conf = sum((o.extraction_confidence or 0) for o in opps) / max(len(opps), 1)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Eagle Scout — Intelligence Report</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'IBM Plex Sans',sans-serif;background:#fff;color:#1a1a1a;font-size:13px;}}
  .header{{background:#0f0f0f;color:#f0f0f0;padding:28px 40px;}}
  .header h1{{font-size:22px;font-weight:700;letter-spacing:-.5px;}}
  .header .sub{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:#666;margin-top:4px;letter-spacing:1px;}}
  .meta-row{{display:flex;gap:48px;margin-top:16px;border-top:1px solid #2a2a2a;padding-top:16px;}}
  .meta-item .label{{font-family:'IBM Plex Mono',monospace;font-size:9px;color:#555;letter-spacing:1px;}}
  .meta-item .val{{font-size:14px;font-weight:600;color:#e0e0e0;margin-top:2px;}}
  .section{{padding:24px 40px;border-bottom:1px solid #e8e8e8;}}
  .section-title{{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;color:#888;margin-bottom:16px;}}
  .stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;}}
  .stat-box{{background:#f7f7f7;padding:14px 18px;border-left:2px solid #1a1a1a;}}
  .stat-num{{font-size:28px;font-weight:700;font-family:'IBM Plex Mono',monospace;}}
  .stat-lbl{{font-size:11px;color:#666;margin-top:2px;}}
  table{{width:100%;border-collapse:collapse;}}
  thead{{background:#0f0f0f;color:#f0f0f0;}}
  th{{padding:9px 12px;font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:1px;text-align:left;font-weight:400;}}
  td{{padding:9px 12px;border-bottom:1px solid #eee;vertical-align:top;}}
  tr:nth-child(even) td{{background:#fafafa;}}
  .card{{padding:20px 24px;margin-bottom:16px;border:1px solid #e0e0e0;border-left:3px solid #1a1a1a;page-break-inside:avoid;}}
  .card-score{{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:700;color:#888;margin-bottom:6px;}}
  .card-title{{font-size:15px;font-weight:700;}}
  .card-org{{font-size:12px;color:#666;margin-top:3px;margin-bottom:10px;}}
  .card-why{{background:#f7f7f7;padding:10px 14px;font-size:12px;line-height:1.6;margin-bottom:10px;}}
  .card-section-label{{font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:1px;color:#999;margin:10px 0 6px;}}
  .ev{{border-left:2px solid #ccc;padding:6px 10px;font-size:11px;color:#444;font-style:italic;margin-bottom:4px;}}
  .req-list{{padding-left:18px;font-size:11px;color:#444;line-height:1.8;}}
  .card-meta{{display:flex;gap:24px;margin-top:12px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:#888;border-top:1px solid #eee;padding-top:10px;}}
  .footer{{background:#0f0f0f;color:#444;padding:14px 40px;font-family:'IBM Plex Mono',monospace;font-size:10px;text-align:center;}}
  @media print{{.section{{page-break-inside:avoid;}}}}
</style>
</head>
<body>
<div class="header">
  <h1>EAGLE SCOUT</h1>
  <div class="sub">LATAM OPPORTUNITY INTELLIGENCE REPORT</div>
  <div class="meta-row">
    <div class="meta-item"><div class="label">GENERATED</div><div class="val">{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div></div>
    <div class="meta-item"><div class="label">OPPORTUNITIES</div><div class="val">{len(opps)}</div></div>
    <div class="meta-item"><div class="label">PIPELINE VALUE</div><div class="val">${total_usd/1e6:.1f}M USD</div></div>
    <div class="meta-item"><div class="label">AVG CONFIDENCE</div><div class="val">{avg_conf*100:.0f}%</div></div>
  </div>
</div>
<div class="section">
  <div class="section-title">EXECUTIVE SUMMARY</div>
  <div class="stat-grid">
    <div class="stat-box"><div class="stat-num">{len(opps)}</div><div class="stat-lbl">Total Opportunities</div></div>
    <div class="stat-box"><div class="stat-num">{sum(1 for o in opps if (o.final_score or 0) >= 80)}</div><div class="stat-lbl">High Priority (80+)</div></div>
    <div class="stat-box"><div class="stat-num">{sum(1 for o in opps if o.deadline and 0 <= (o.deadline-today).days <= 14)}</div><div class="stat-lbl">Closing Within 14 Days</div></div>
    <div class="stat-box"><div class="stat-num">{avg_conf*100:.0f}%</div><div class="stat-lbl">Avg Extraction Confidence</div></div>
  </div>
</div>
<div class="section">
  <div class="section-title">RANKED OPPORTUNITY TABLE</div>
  <table>
    <thead><tr><th>SCORE</th><th>TITLE</th><th>ENTITY</th><th>DEADLINE</th><th>BUDGET</th><th>CONF</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<div class="section">
  <div class="section-title">DETAILED INTELLIGENCE CARDS</div>
  {cards}
</div>
<div class="footer">EAGLE SCOUT &mdash; CONFIDENTIAL &mdash; NOT FOR PUBLIC DISTRIBUTION &mdash;
Powered by Bright Data Web Intelligence + Anthropic Claude AI</div>
</body>
</html>"""

    return HTMLResponse(content=html)
