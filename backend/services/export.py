"""
ExportService — generates PDF and EMR text exports from a CarePlan.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

from __future__ import annotations

import html
import io
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    ListFlowable,
    ListItem,
)

if TYPE_CHECKING:
    from backend.schemas import CarePlan


def _esc(text: str) -> str:
    """Escape *text* for safe use inside a reportlab Paragraph (XML context)."""
    return html.escape(str(text), quote=False)


class ExportService:
    """Generates PDF and EMR text exports from a CarePlan object."""

    # ------------------------------------------------------------------
    # PDF export
    # ------------------------------------------------------------------

    def to_pdf(self, care_plan: "CarePlan") -> bytes:
        """Render *care_plan* as a formatted PDF and return the raw bytes.

        The PDF includes:
        - Case ID header
        - Timeline section
        - Findings by specialty
        - Recommendations list
        - Alerts list

        Validates: Requirements 7.1, 7.3
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            "CareFlowTitle",
            parent=styles["Title"],
            fontSize=18,
            spaceAfter=6,
            textColor=colors.HexColor("#1e3a5f"),
        )
        heading1_style = ParagraphStyle(
            "CareFlowH1",
            parent=styles["Heading1"],
            fontSize=13,
            spaceBefore=14,
            spaceAfter=4,
            textColor=colors.HexColor("#1e3a5f"),
            borderPad=2,
        )
        heading2_style = ParagraphStyle(
            "CareFlowH2",
            parent=styles["Heading2"],
            fontSize=11,
            spaceBefore=8,
            spaceAfter=2,
            textColor=colors.HexColor("#2d6a9f"),
        )
        body_style = ParagraphStyle(
            "CareFlowBody",
            parent=styles["Normal"],
            fontSize=9,
            spaceAfter=3,
            leading=13,
        )
        alert_style = ParagraphStyle(
            "CareFlowAlert",
            parent=styles["Normal"],
            fontSize=9,
            spaceAfter=3,
            leading=13,
            textColor=colors.HexColor("#b91c1c"),
        )
        meta_style = ParagraphStyle(
            "CareFlowMeta",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#6b7280"),
            spaceAfter=2,
        )

        story = []

        # ── Header ────────────────────────────────────────────────────
        story.append(Paragraph("CareFlow Orchestrator", title_style))
        story.append(Paragraph("Clinical Care Plan", styles["Heading2"]))
        story.append(Paragraph(f"Case ID: {_esc(care_plan.case_id)}", meta_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1")))
        story.append(Spacer(1, 0.3 * cm))

        # ── Timeline ──────────────────────────────────────────────────
        story.append(Paragraph("Timeline", heading1_style))
        if care_plan.timeline:
            for entry in care_plan.timeline:
                story.append(
                    Paragraph(
                        f"<b>[{_esc(entry.specialty.upper())}]</b> {_esc(entry.timestamp)} — {_esc(entry.description)}",
                        body_style,
                    )
                )
        else:
            story.append(Paragraph("No timeline entries.", body_style))
        story.append(Spacer(1, 0.2 * cm))

        # ── Findings by specialty ─────────────────────────────────────
        story.append(Paragraph("Findings by Specialty", heading1_style))
        if care_plan.findings:
            for specialty, findings in care_plan.findings.items():
                story.append(Paragraph(_esc(specialty.capitalize()), heading2_style))
                story.append(Paragraph(_esc(findings.summary), body_style))
                if findings.action_items:
                    items = [
                        ListItem(Paragraph(_esc(item), body_style), bulletColor=colors.HexColor("#2d6a9f"))
                        for item in findings.action_items
                    ]
                    story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
        else:
            story.append(Paragraph("No specialty findings available.", body_style))
        story.append(Spacer(1, 0.2 * cm))

        # ── Recommendations ───────────────────────────────────────────
        story.append(Paragraph("Recommendations", heading1_style))
        if care_plan.recommendations:
            items = [
                ListItem(Paragraph(_esc(rec), body_style), bulletColor=colors.HexColor("#2d6a9f"))
                for rec in care_plan.recommendations
            ]
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
        else:
            story.append(Paragraph("No recommendations.", body_style))
        story.append(Spacer(1, 0.2 * cm))

        # ── Alerts ────────────────────────────────────────────────────
        story.append(Paragraph("Alerts", heading1_style))
        if care_plan.alerts:
            items = [
                ListItem(Paragraph(_esc(alert), alert_style), bulletColor=colors.HexColor("#b91c1c"))
                for alert in care_plan.alerts
            ]
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
        else:
            story.append(Paragraph("No alerts.", body_style))

        doc.build(story)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # EMR text export
    # ------------------------------------------------------------------

    def to_emr(self, care_plan: "CarePlan") -> str:
        """Render *care_plan* as structured plain text suitable for EMR import.

        The output uses labeled sections separated by blank lines, compatible
        with common EMR import formats.

        Validates: Requirements 7.2, 7.4
        """
        lines: list[str] = []

        def section(title: str) -> None:
            lines.append("")
            lines.append(f"=== {title.upper()} ===")

        # ── Header ────────────────────────────────────────────────────
        lines.append("CAREFLOW ORCHESTRATOR — CLINICAL CARE PLAN")
        lines.append(f"CASE_ID: {care_plan.case_id}")
        lines.append("-" * 60)

        # ── Timeline ──────────────────────────────────────────────────
        section("TIMELINE")
        if care_plan.timeline:
            for entry in care_plan.timeline:
                lines.append(
                    f"  [{entry.specialty.upper()}] {entry.timestamp}: {entry.description}"
                )
        else:
            lines.append("  (no timeline entries)")

        # ── Findings by specialty ─────────────────────────────────────
        section("FINDINGS BY SPECIALTY")
        if care_plan.findings:
            for specialty, findings in care_plan.findings.items():
                lines.append(f"  SPECIALTY: {specialty.upper()}")
                lines.append(f"  SUMMARY: {findings.summary}")
                if findings.action_items:
                    lines.append("  ACTION ITEMS:")
                    for item in findings.action_items:
                        lines.append(f"    - {item}")
                lines.append("")
        else:
            lines.append("  (no specialty findings)")

        # ── Recommendations ───────────────────────────────────────────
        section("RECOMMENDATIONS")
        if care_plan.recommendations:
            for i, rec in enumerate(care_plan.recommendations, start=1):
                lines.append(f"  {i}. {rec}")
        else:
            lines.append("  (no recommendations)")

        # ── Alerts ────────────────────────────────────────────────────
        section("ALERTS")
        if care_plan.alerts:
            for alert in care_plan.alerts:
                lines.append(f"  [ALERT] {alert}")
        else:
            lines.append("  (no alerts)")

        lines.append("")
        lines.append("-" * 60)
        lines.append("END OF CARE PLAN")

        return "\n".join(lines)
