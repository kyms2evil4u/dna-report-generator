"""
PDF Report Generator using ReportLab.
Produces a professional, multi-section DNA report.
"""

import os
from datetime import datetime
from typing import Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics import renderPDF


# ── Color palette ────────────────────────────────────────────────────────────
COLORS = {
    "primary":    colors.HexColor("#1A73E8"),
    "secondary":  colors.HexColor("#4A90D9"),
    "accent":     colors.HexColor("#5BB5A2"),
    "light_bg":   colors.HexColor("#F8FAFF"),
    "border":     colors.HexColor("#E8EEF7"),
    "text":       colors.HexColor("#1A1A2E"),
    "muted":      colors.HexColor("#6B7280"),
    "pathogenic": colors.HexColor("#DC3545"),
    "warning":    colors.HexColor("#F59E0B"),
    "safe":       colors.HexColor("#10B981"),
    "white":      colors.white,
}


def _build_styles():
    styles = getSampleStyleSheet()
    custom = {
        "Title": ParagraphStyle("Title", fontSize=26, textColor=COLORS["primary"], spaceAfter=8, fontName="Helvetica-Bold", alignment=TA_LEFT),
        "Subtitle": ParagraphStyle("Subtitle", fontSize=12, textColor=COLORS["muted"], spaceAfter=4, fontName="Helvetica"),
        "H2": ParagraphStyle("H2", fontSize=16, textColor=COLORS["primary"], spaceBefore=16, spaceAfter=6, fontName="Helvetica-Bold"),
        "H3": ParagraphStyle("H3", fontSize=12, textColor=COLORS["text"], spaceBefore=8, spaceAfter=4, fontName="Helvetica-Bold"),
        "Body": ParagraphStyle("Body", fontSize=9, textColor=COLORS["text"], spaceAfter=4, fontName="Helvetica", leading=14),
        "Small": ParagraphStyle("Small", fontSize=8, textColor=COLORS["muted"], fontName="Helvetica"),
        "Disclaimer": ParagraphStyle("Disclaimer", fontSize=7.5, textColor=COLORS["muted"], fontName="Helvetica-Oblique", leading=11),
        "Badge_Red": ParagraphStyle("BadgeRed", fontSize=8, textColor=COLORS["white"], fontName="Helvetica-Bold", alignment=TA_CENTER),
        "Badge_Yellow": ParagraphStyle("BadgeYellow", fontSize=8, textColor=COLORS["text"], fontName="Helvetica-Bold", alignment=TA_CENTER),
        "Badge_Green": ParagraphStyle("BadgeGreen", fontSize=8, textColor=COLORS["white"], fontName="Helvetica-Bold", alignment=TA_CENTER),
    }
    return custom


def _header_footer(canvas, doc):
    """Draw header and footer on every page."""
    canvas.saveState()
    w, h = doc.pagesize

    # Header bar
    canvas.setFillColor(COLORS["primary"])
    canvas.rect(0, h - 0.5 * inch, w, 0.5 * inch, fill=True, stroke=False)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(0.5 * inch, h - 0.33 * inch, "DNA Report Generator")
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(w - 0.5 * inch, h - 0.33 * inch, f"Generated {datetime.now().strftime('%B %d, %Y')}")

    # Footer
    canvas.setFillColor(COLORS["muted"])
    canvas.setFont("Helvetica", 8)
    canvas.drawString(0.5 * inch, 0.3 * inch, "FOR INFORMATIONAL PURPOSES ONLY — NOT A MEDICAL DIAGNOSIS")
    canvas.drawRightString(w - 0.5 * inch, 0.3 * inch, f"Page {doc.page}")

    canvas.restoreState()


def _section_header(title: str, styles: Dict) -> list:
    return [
        HRFlowable(width="100%", thickness=2, color=COLORS["primary"], spaceAfter=4),
        Paragraph(title, styles["H2"]),
    ]


def _severity_color(severity: str) -> Any:
    return {"high": COLORS["pathogenic"], "moderate": COLORS["warning"], "low": COLORS["safe"]}.get(severity, COLORS["muted"])


def _risk_tier_color(tier: str) -> Any:
    return {"high": COLORS["pathogenic"], "elevated": COLORS["warning"], "average": COLORS["accent"], "below_average": COLORS["safe"]}.get(tier, COLORS["muted"])


def generate_pdf_report(report_data: Dict, output_path: str) -> str:
    """
    Generate a comprehensive PDF DNA report.
    Returns the path to the generated PDF.
    """
    styles = _build_styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.6 * inch,
    )

    story = []
    summary = report_data.get("summary", {})
    ancestry = report_data.get("ancestry", {})
    risk_scores = report_data.get("risk_scores", [])
    pgx = report_data.get("pharmacogenomics", [])
    traits = report_data.get("traits", [])
    categories = report_data.get("categories", {})

    # ── COVER ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("DNA Health &amp; Ancestry Report", styles["Title"]))
    story.append(Paragraph(f"Prepared for: {report_data.get('name', 'User')}", styles["Subtitle"]))
    story.append(Paragraph(f"Analysis date: {datetime.now().strftime('%B %d, %Y')}", styles["Subtitle"]))
    story.append(Spacer(1, 0.2 * inch))

    # Summary stats table
    total_variants = summary.get("total_variants", 0)
    pathogenic_count = summary.get("pathogenic_count", 0)
    format_detected = summary.get("format", "Unknown")

    stat_data = [
        ["Total Variants Analyzed", "Pathogenic Variants", "File Format", "Analysis Mode"],
        [
            str(total_variants),
            str(pathogenic_count),
            format_detected.upper(),
            summary.get("mode", "Fast").title(),
        ],
    ]
    stat_table = Table(stat_data, colWidths=[1.8 * inch] * 4)
    stat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLORS["primary"]),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 9),
        ("BACKGROUND", (0, 1), (-1, 1), COLORS["light_bg"]),
        ("FONTSIZE",   (0, 1), (-1, 1), 14),
        ("FONTNAME",   (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR",  (0, 1), (-1, 1), COLORS["primary"]),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [None]),
        ("GRID",       (0, 0), (-1, -1), 0.5, COLORS["border"]),
        ("ROWHEIGHT",  (0, 0), (-1, 0), 24),
        ("ROWHEIGHT",  (0, 1), (-1, 1), 36),
    ]))
    story.append(stat_table)
    story.append(Spacer(1, 0.3 * inch))

    # Disclaimer
    story.append(Paragraph(
        "⚠️ IMPORTANT DISCLAIMER: This report is for informational and educational purposes only. "
        "It does not constitute medical advice, diagnosis, or treatment. Please consult a qualified "
        "healthcare professional or genetic counselor before making any health decisions based on this report.",
        styles["Disclaimer"]
    ))
    story.append(PageBreak())

    # ── ANCESTRY ──────────────────────────────────────────────────────────────
    story += _section_header("Ancestry Composition", styles)
    if ancestry.get("composition"):
        comp = ancestry["composition"]
        labels = ancestry.get("labels", {})
        story.append(Paragraph(
            f"Based on <b>{ancestry.get('markers_used', 0)}</b> ancestry-informative markers (AIMs), "
            f"your strongest ancestry signal is <b>{ancestry.get('top_population', 'Unknown')}</b>.",
            styles["Body"]
        ))
        story.append(Spacer(1, 0.1 * inch))

        anc_data = [["Population", "Estimated %", "Confidence"]]
        for pop_code, pct in sorted(comp.items(), key=lambda x: x[1], reverse=True):
            label = labels.get(pop_code, pop_code)
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            anc_data.append([label, f"{pct:.1f}%", bar[:20]])

        anc_table = Table(anc_data, colWidths=[2.2 * inch, 1.2 * inch, 3.5 * inch])
        anc_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLORS["primary"]),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLORS["light_bg"]]),
            ("GRID",       (0, 0), (-1, -1), 0.5, COLORS["border"]),
            ("ALIGN",      (1, 0), (-1, -1), "CENTER"),
            ("FONTNAME",   (2, 1), (2, -1), "Courier"),
            ("TEXTCOLOR",  (2, 1), (2, -1), COLORS["primary"]),
        ]))
        story.append(anc_table)
    story.append(Spacer(1, 0.2 * inch))

    # ── DISEASE RISK ──────────────────────────────────────────────────────────
    story += _section_header("Complex Disease Risk", styles)
    if risk_scores:
        for rs in risk_scores[:8]:  # top 8
            row = KeepTogether([
                Paragraph(f"<b>{rs['condition']}</b> — {rs['description']}", styles["H3"]),
                Paragraph(
                    f"Risk Level: <b>{rs['risk_label']}</b> | "
                    f"Your estimated lifetime risk: <b>{rs['adjusted_risk_pct']}%</b> "
                    f"(population baseline: {rs['baseline_risk_pct']}%) | "
                    f"Relative risk: <b>{rs['relative_risk']}x</b>",
                    styles["Body"]
                ),
                Spacer(1, 0.05 * inch),
            ])
            story.append(row)
    story.append(PageBreak())

    # ── PATHOGENIC VARIANTS ───────────────────────────────────────────────────
    story += _section_header("Pathogenic Variants", styles)
    pathogenic = categories.get("pathogenic", [])
    if pathogenic:
        path_data = [["rsID", "Gene", "Chr:Pos", "Genotype", "Significance", "CADD"]]
        for v in pathogenic[:20]:
            path_data.append([
                v.get("rsid", ""),
                v.get("gene") or "—",
                f"{v.get('chromosome', '')}:{v.get('position', '')}",
                v.get("genotype", ""),
                v.get("clinical_significance") or "—",
                str(round(float(v.get("cadd_score") or 0), 1)) if v.get("cadd_score") else "—",
            ])
        path_table = Table(path_data, colWidths=[1.0*inch, 0.9*inch, 1.1*inch, 0.8*inch, 1.5*inch, 0.7*inch])
        path_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLORS["pathogenic"]),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FFF5F5")]),
            ("GRID",       (0, 0), (-1, -1), 0.5, COLORS["border"]),
            ("ALIGN",      (0, 0), (-1, -1), "LEFT"),
        ]))
        story.append(path_table)
    else:
        story.append(Paragraph("No pathogenic variants identified in the analyzed set.", styles["Body"]))
    story.append(Spacer(1, 0.2 * inch))

    # ── PHARMACOGENOMICS ──────────────────────────────────────────────────────
    story += _section_header("Pharmacogenomics", styles)
    if pgx:
        pgx_data = [["Gene", "Variant", "Genotype", "Affected Drugs", "Effect", "Severity"]]
        for p in pgx:
            pgx_data.append([
                p.get("gene", ""),
                p.get("star_allele", ""),
                p.get("your_genotype", ""),
                ", ".join(p.get("drugs_affected", [])[:2]),
                p.get("effect", ""),
                p.get("severity", "").title(),
            ])
        pgx_table = Table(pgx_data, colWidths=[0.7*inch, 0.9*inch, 0.8*inch, 1.4*inch, 2.0*inch, 0.7*inch])
        pgx_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLORS["secondary"]),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLORS["light_bg"]]),
            ("GRID",       (0, 0), (-1, -1), 0.5, COLORS["border"]),
        ]))
        story.append(pgx_table)
    else:
        story.append(Paragraph("No pharmacogenomic variants identified.", styles["Body"]))
    story.append(Spacer(1, 0.2 * inch))

    # ── TRAITS ────────────────────────────────────────────────────────────────
    story += _section_header("Physical &amp; Sensory Traits", styles)
    if traits:
        for t in traits:
            story.append(Paragraph(
                f"<b>{t.get('icon','')} {t['trait']}</b> ({t['gene']}) — {t['interpretation']}",
                styles["Body"]
            ))
    story.append(PageBreak())

    # ── FINAL DISCLAIMER ──────────────────────────────────────────────────────
    story += _section_header("Important Information", styles)
    story.append(Paragraph(
        "This report was generated computationally from raw genetic variant data using publicly available "
        "databases including ClinVar, Ensembl VEP, MyVariant.info, and gnomAD. The analysis is limited to "
        "a curated set of known variants and does not represent a comprehensive genome-wide analysis. "
        "Polygenic risk scores are estimates based on published GWAS studies and should be interpreted "
        "with caution. Individual risk is influenced by many factors including environment, lifestyle, "
        "and gene-gene interactions not captured in this report.",
        styles["Disclaimer"]
    ))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return output_path
