"""Report card PDFs (ReportLab: pure Python, no system libraries).

Four designs, chosen per school in the owner console (agreed with the school):
  classic  – centred letterhead with a double rule, coloured table headings
  modern   – full-width coloured banner with logo and learner photo
  prestige – letterhead with a curved colour sweep and gold accents, crest watermark
  compact  – smaller type, comments side by side; fits long subject lists on one page
Every design uses the school's own colour and logo, frames the page, colours each grade and
shows the learner's subjects as a bar chart beside the summary figures.
"""

import io
import os
from dataclasses import dataclass

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .reports import verify_url

STYLES = getSampleStyleSheet()
GRID = colors.HexColor("#cbd5e1")
TEMPLATES = {
    "classic": "Classic",
    "modern": "Modern banner",
    "prestige": "Prestige letterhead",
    "compact": "Compact",
}
GOLD = colors.HexColor("#c9a227")


def score_color(score):
    """Green for distinction, blue for credit, amber for pass, red for fail."""
    if score is None:
        return colors.HexColor("#94a3b8")
    if score >= 80:
        return colors.HexColor("#15803d")
    if score >= 60:
        return colors.HexColor("#1d4ed8")
    if score >= 40:
        return colors.HexColor("#b45309")
    return colors.HexColor("#b91c1c")


@dataclass
class Design:
    template: str
    brand: colors.Color
    tint: colors.Color
    photo: bool
    size: float  # base font size

    def style(self, name, **kw):
        base = {"fontSize": self.size, "leading": self.size + 3}
        base.update(kw)
        return ParagraphStyle(name, parent=STYLES["Normal"], **base)


def _tint(color, amount=0.88):
    return colors.Color(
        color.red + (1 - color.red) * amount,
        color.green + (1 - color.green) * amount,
        color.blue + (1 - color.blue) * amount,
    )


def design_for(school, template=None, color=None):
    template = template if template in TEMPLATES else (school.report_template or "classic")
    try:
        brand = colors.HexColor(color or school.report_color or "#1d4ed8")
    except ValueError:
        brand = colors.HexColor("#1d4ed8")
    return Design(
        template=template,
        brand=brand,
        tint=_tint(brand),
        photo=school.report_show_photo,
        size=8 if template == "compact" else 9,
    )


class QRFlowable(Flowable):
    def __init__(self, value, size=26 * mm):
        super().__init__()
        self.value, self.size = value, size
        self.width = self.height = size

    def draw(self):
        widget = qr.QrCodeWidget(self.value)
        x1, y1, x2, y2 = widget.getBounds()
        drawing = Drawing(
            self.size, self.size, transform=[self.size / (x2 - x1), 0, 0, self.size / (y2 - y1), 0, 0]
        )
        drawing.add(widget)
        renderPDF.draw(drawing, self.canv, 0, 0)


def _fmt(value, places=1):
    if value is None or value == "":
        return "–"
    if isinstance(value, float):
        return f"{value:.{places}f}".rstrip("0").rstrip(".")
    return str(value)


def _image(path, size):
    return Image(path, size, size) if path and os.path.exists(path) else None


def _header(snap, d):
    school = snap["school"]
    logo = _image(school.get("logo"), 20 * mm)
    photo = _image(snap["learner"].get("photo"), 22 * mm) if d.photo else None
    contact = " · ".join(x for x in [school.get("address"), school.get("phone"), school.get("email")] if x)
    if d.template == "modern":
        white = d.style("w", textColor=colors.white)
        lines = [
            Paragraph(
                f"<b>{school['name'].upper()}</b>",
                d.style("wt", fontSize=17, leading=21, textColor=colors.white),
            ),
            Paragraph(f"<i>{school.get('motto') or ''}</i>", white),
            Paragraph(contact, d.style("wc", fontSize=7.5, textColor=colors.white)),
        ]
        cells = [logo or "", lines, photo or ""]
        band = Table([cells], colWidths=[26 * mm, None, 26 * mm])
        band.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), d.brand),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        title = Table(
            [
                [
                    Paragraph(
                        f"<b>LEARNER'S REPORT · {snap['term'].upper()}</b>",
                        d.style("bt", alignment=1, textColor=d.brand),
                    )
                ]
            ]
        )
        title.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), d.tint),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return [band, title]
    if d.template == "prestige":
        gold = GOLD.hexval()[2:]
        lines = [
            Paragraph(
                f"<b>{school['name'].upper()}</b>",
                d.style("pt", fontName="Times-Bold", fontSize=19, leading=23, alignment=1, textColor=d.brand),
            )
        ]
        if school.get("motto"):
            lines.append(
                Paragraph(
                    f"<font color='#{gold}'><i>“{school['motto']}”</i></font>", d.style("pm", alignment=1)
                )
            )
        if contact:
            lines.append(Paragraph(contact, d.style("pc", fontSize=7.5, alignment=1)))
        if school.get("registration_number"):
            lines.append(
                Paragraph(f"Reg. No. {school['registration_number']}", d.style("pr", fontSize=7, alignment=1))
            )
        head = Table(
            [[logo or "", lines, photo or ""]],
            colWidths=[26 * mm, None, 26 * mm],
            style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6 * mm)],
        )
        ribbon = Table(
            [
                [
                    Paragraph(
                        f"<b>TERMLY REPORT · {snap['term'].upper()}</b>",
                        d.style("prb", alignment=1, textColor=colors.white),
                    )
                ]
            ],
            colWidths=[110 * mm],
        )
        ribbon.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), d.brand),
                    ("LINEABOVE", (0, 0), (-1, 0), 1.5, GOLD),
                    ("LINEBELOW", (0, -1), (-1, -1), 1.5, GOLD),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return [head, Spacer(1, 2 * mm), ribbon]
    if d.template == "compact":
        line = Paragraph(
            f"<font size=13><b>{school['name'].upper()}</b></font>  ·  {contact}<br/>"
            f"<font color='#{d.brand.hexval()[2:]}'><b>LEARNER'S REPORT — {snap['term'].upper()}</b></font>",
            d.style("ch", leading=14),
        )
        return [
            Table(
                [[logo or "", line, photo or ""]],
                colWidths=[22 * mm, None, 24 * mm],
                style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, d.brand)],
            )
        ]
    lines = [
        Paragraph(
            f"<b>{school['name'].upper()}</b>",
            d.style("ct", fontSize=16, leading=20, alignment=1, textColor=d.brand),
        )
    ]
    if school.get("motto"):
        lines.append(Paragraph(f"<i>{school['motto']}</i>", d.style("cm", alignment=1)))
    if contact:
        lines.append(Paragraph(contact, d.style("cc", fontSize=7.5, alignment=1)))
    if school.get("registration_number"):
        lines.append(
            Paragraph(f"Reg. No. {school['registration_number']}", d.style("cr", fontSize=7, alignment=1))
        )
    head = Table(
        [[logo or "", lines, photo or ""]],
        colWidths=[26 * mm, None, 26 * mm],
        style=[
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, 0), 2, d.brand),
        ],
    )
    rule = Table([[""]], colWidths=[None], rowHeights=[1.2 * mm])
    rule.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.6, d.brand)]))
    title = Table(
        [
            [
                Paragraph(
                    f"<b>LEARNER'S REPORT — {snap['term'].upper()}</b>",
                    d.style("crt", alignment=1, textColor=d.brand),
                )
            ]
        ],
        colWidths=[100 * mm],
    )
    title.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, d.brand),
                ("BACKGROUND", (0, 0), (-1, -1), d.tint),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return [head, rule, title]


def _learner_table(snap, d):
    learner = snap["learner"]
    rows = [
        ["Name", learner["name"], "Adm. No.", learner["adm_no"]],
        ["Class", f"{snap['class']} {snap['stream']}".strip(), "LIN", learner["lin"] or "–"],
        ["Sex", learner["sex"], "House", learner["house"] or "–"],
    ]
    table = Table(rows, colWidths=[24 * mm, 67 * mm, 24 * mm, 67 * mm])
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", d.size),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", d.size),
        ("FONT", (2, 0), (2, -1), "Helvetica-Bold", d.size),
        ("BACKGROUND", (0, 0), (0, -1), d.tint),
        ("BACKGROUND", (2, 0), (2, -1), d.tint),
    ]
    style.append(
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRID)
        if d.template == "modern"
        else ("GRID", (0, 0), (-1, -1), 0.4, GRID)
    )
    table.setStyle(TableStyle(style))
    return table


def _results_table(snap, d):
    rule, exams = snap["rule_set"], snap["exams"]
    small = d.style("rs", fontSize=d.size - 1, leading=d.size + 1)
    if rule == "nursery":
        header = ["Learning area", "Rating", "Remark"]
        body = [
            [r["name"], r["grade"] or "–", Paragraph(r["descriptor"] or "", small)] for r in snap["subjects"]
        ]
        widths = [60 * mm, 40 * mm, None]
    else:
        # Each assessment column shows its share of the term score, e.g. "BOT 20%".
        header = ["Subject"] + [
            Paragraph(
                f"<b>{e['short']}</b><br/>{_fmt(e.get('weight'))}%",
                d.style("eh", fontSize=d.size - 1, leading=d.size, alignment=1, textColor=colors.white),
            )
            for e in exams
        ]
        header += ["Score", "Grade", "Teacher's comment", "Initials"]
        body = []
        for r in snap["subjects"]:
            row = [r["name"]] + [_fmt(r["exams"].get(str(e["id"]))) for e in exams]
            row += [
                _fmt(r["score"]),
                r["grade"] or "–",
                Paragraph(r.get("comment") or r.get("descriptor") or "", small),
                r.get("initials", ""),
            ]
            body.append(row)
        widths = [44 * mm] + [14 * mm] * len(exams) + [17 * mm, 13 * mm, None, 15 * mm]
    table = Table([header] + body, colWidths=widths, repeatRows=1)
    graded = []
    if rule != "nursery":
        score_col, grade_col = 1 + len(exams), 2 + len(exams)
        for index, r in enumerate(snap["subjects"], start=1):
            tone = score_color(r["score"])
            graded += [
                ("TEXTCOLOR", (score_col, index), (grade_col, index), tone),
                ("FONT", (score_col, index), (grade_col, index), "Helvetica-Bold", d.size),
            ]
    style = [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", d.size - 0.5),
        ("FONT", (0, 1), (-1, -1), "Helvetica", d.size),
        ("BACKGROUND", (0, 0), (-1, 0), d.brand),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        (
            "ROWBACKGROUNDS",
            (0, 1),
            (-1, -1),
            [colors.white, d.tint if d.template == "modern" else colors.HexColor("#f8fafc")],
        ),
    ]
    style.append(
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRID)
        if d.template == "modern"
        else ("GRID", (0, 0), (-1, -1), 0.4, GRID)
    )
    if d.template == "compact":
        style += [("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    table.setStyle(TableStyle(style + graded))
    return table


def _chart(snap, d, width, height):
    """Each subject's score as a bar (coloured by band) with the 50% pass line."""
    rows = [r for r in snap["subjects"] if r.get("score") is not None][:12]
    drawing = Drawing(width, height)
    if not rows:
        return drawing
    label_w, top, bottom = 24 * mm, 9, 12
    bar_space = (height - top - bottom) / len(rows)
    bar_h = min(bar_space * 0.62, 9)
    plot_w = width - label_w - 14
    drawing.add(
        String(
            0,
            height - 7,
            "Performance by subject",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            fillColor=d.brand,
        )
    )
    for i, r in enumerate(rows):
        y = height - top - (i + 1) * bar_space + (bar_space - bar_h) / 2
        name = (r.get("short_name") or r["name"])[:14]
        drawing.add(
            String(0, y + 1.5, name, fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor("#334155"))
        )
        drawing.add(Rect(label_w, y, plot_w, bar_h, fillColor=colors.HexColor("#f1f5f9"), strokeColor=None))
        score = max(0.0, min(100.0, float(r["score"])))
        drawing.add(
            Rect(label_w, y, plot_w * score / 100, bar_h, fillColor=score_color(score), strokeColor=None)
        )
        drawing.add(
            String(label_w + plot_w + 2, y + 1.5, f"{score:.0f}", fontName="Helvetica-Bold", fontSize=6.5)
        )
    pass_x = label_w + plot_w * 0.5
    drawing.add(
        Line(
            pass_x,
            bottom - 2,
            pass_x,
            height - top,
            strokeColor=colors.HexColor("#64748b"),
            strokeDashArray=[2, 2],
            strokeWidth=0.6,
        )
    )
    drawing.add(
        String(pass_x - 6, 2, "50%", fontName="Helvetica", fontSize=6, fillColor=colors.HexColor("#64748b"))
    )
    return drawing


def _summary_block(snap, d):
    """Summary tiles beside the subject chart (the chart is left out for nursery reports)."""
    tiles = _summary_table(snap, d)
    if snap["rule_set"] == "nursery" or not any(r.get("score") is not None for r in snap["subjects"]):
        return tiles
    chart_w = 82 * mm
    height = min(70 * mm, len([r for r in snap["subjects"] if r.get("score") is not None][:12]) * 12 + 28)
    block = Table([[tiles, _chart(snap, d, chart_w, height)]], colWidths=[None, chart_w + 4 * mm])
    block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (1, 0), (1, 0), 0.5, GRID),
                ("LEFTPADDING", (1, 0), (1, 0), 6),
            ]
        )
    )
    return block


def _summary_table(snap, d):
    rule = snap["rule_set"]
    cells = []
    if rule != "nursery":
        cells += [("Total", _fmt(snap["total"])), ("Average", _fmt(snap["average"]))]
    if rule == "ple":
        cells += [("Aggregate", _fmt(snap["aggregate"])), ("Division", snap["division"] or "–")]
    if rule == "uace":
        cells.append(("Points", _fmt(snap["points"])))
    if snap["show_positions"] and rule != "nursery" and snap["position"]:
        cells.append(("Position", f"{snap['position']} of {snap['out_of']}"))
    attendance = snap.get("attendance") or {}
    if attendance.get("total"):
        cells.append(("Attendance", f"{attendance['present']}/{attendance['total']} days"))
    if not cells:
        return Spacer(1, 1)
    # Two tiles per row: a small label over a large figure.
    grid = []
    for start in range(0, len(cells), 2):
        pair = cells[start : start + 2] + [("", "")] * (2 - len(cells[start : start + 2]))
        grid += [[c[0] for c in pair], [c[1] for c in pair]]
    table = Table(grid)
    style = [("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for row in range(0, len(grid), 2):
        style += [
            ("FONT", (0, row), (-1, row), "Helvetica-Bold", d.size - 1),
            ("FONT", (0, row + 1), (-1, row + 1), "Helvetica-Bold", d.size + 4),
            ("TEXTCOLOR", (0, row + 1), (-1, row + 1), d.brand),
            ("BOTTOMPADDING", (0, row + 1), (-1, row + 1), 6),
            ("LINEBELOW", (0, row + 1), (-1, row + 1), 3, colors.white),
        ]
    if d.template in ("modern", "prestige"):
        style += [("BACKGROUND", (0, 0), (-1, -1), d.tint), ("LINEAFTER", (0, 0), (0, -1), 3, colors.white)]
        if d.template == "prestige":
            style.append(("BOX", (0, 0), (-1, -1), 0.8, GOLD))
        table.setStyle(TableStyle(style))
        return table
    style += [("BOX", (0, 0), (-1, -1), 0.4, GRID), ("INNERGRID", (0, 0), (-1, -1), 0.25, GRID)]
    table.setStyle(TableStyle(style))
    return table


def _comments(snap, d):
    body = d.style("cb")
    rows = [
        ("Class teacher's comment", Paragraph(snap.get("class_teacher_comment") or "", body)),
        ("Head teacher's comment", Paragraph(snap.get("head_comment") or "", body)),
    ]
    if d.template == "compact":
        table = Table(
            [
                [Paragraph(f"<b>{rows[0][0]}</b>", body), Paragraph(f"<b>{rows[1][0]}</b>", body)],
                [rows[0][1], rows[1][1]],
            ],
            colWidths=[None, None],
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                    ("BACKGROUND", (0, 0), (-1, 0), d.tint),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
                ]
            )
        )
        extra = []
        if snap.get("promotion_note"):
            extra.append(Paragraph(f"<b>Decision:</b> {snap['promotion_note']}", body))
        if snap.get("next_term_begins"):
            extra.append(Paragraph(f"<b>Next term begins:</b> {snap['next_term_begins']}", body))
        return [table, *extra]
    rows = [[Paragraph(f"<b>{label}</b>", body), value] for label, value in rows]
    if snap.get("promotion_note"):
        rows.append([Paragraph("<b>Decision</b>", body), Paragraph(f"<b>{snap['promotion_note']}</b>", body)])
    if snap.get("next_term_begins"):
        rows.append([Paragraph("<b>Next term begins</b>", body), Paragraph(snap["next_term_begins"], body)])
    table = Table(rows, colWidths=[45 * mm, None])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), d.tint),
                ("TOPPADDING", (0, 0), (-1, 1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, 1), 12),
            ]
        )
    )
    return [table]


def card_story(card, d):
    snap = card.snapshot
    gap = (2 if d.template == "compact" else 4) * mm
    story = [
        *_header(snap, d),
        Spacer(1, gap),
        _learner_table(snap, d),
        Spacer(1, gap),
        _results_table(snap, d),
        Spacer(1, gap),
        _summary_block(snap, d),
        Spacer(1, gap),
    ]
    if not snap.get("is_complete", True):
        story.append(Paragraph("<i>Some results are missing for this term.</i>", d.style("mi", fontSize=8)))
    story += _comments(snap, d)
    signatures = Table(
        [
            [
                "Class teacher's signature: ____________________",
                "Head teacher's signature: ____________________",
            ]
        ],
        colWidths=[None, None],
    )
    signatures.setStyle(
        TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", d.size), ("TOPPADDING", (0, 0), (-1, -1), 14)])
    )
    story += [signatures, Spacer(1, gap)]
    status = "" if card.status == "published" else f" ({card.get_status_display().upper()})"
    small = d.style("fs", fontSize=7.5)
    footer = Table(
        [
            [
                [
                    Paragraph(f"Serial: <b>{card.serial}</b>{status}", d.style("fn")),
                    Paragraph("Scan the code to check this report is genuine.", small),
                    Paragraph(snap["school"].get("footer") or "", small),
                ],
                QRFlowable(verify_url(card), size=(22 if d.template == "compact" else 26) * mm),
            ]
        ],
        colWidths=[None, 30 * mm],
    )
    footer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    story.append(footer)
    return story


def _decorate(d, school_name):
    """Page furniture drawn behind every page: a frame in the school colour, a faint
    watermark of the school's name and each design's own letterhead shapes."""

    def draw(canvas, doc):
        width, height = A4
        canvas.saveState()
        # Watermark
        canvas.setFillColor(d.brand)
        canvas.setFillAlpha(0.045)
        canvas.setFont("Helvetica-Bold", 46)
        canvas.translate(width / 2, height / 2)
        canvas.rotate(35)
        canvas.drawCentredString(0, 0, (school_name or "")[:28].upper())
        canvas.restoreState()

        canvas.saveState()
        inset = 7 * mm
        if d.template == "prestige":
            # A sweep of colour across the top with a gold edge, and a band at the foot.
            path = canvas.beginPath()
            path.moveTo(0, height)
            path.lineTo(width, height)
            path.lineTo(width, height - 16 * mm)
            path.curveTo(width * 0.65, height - 4 * mm, width * 0.35, height - 26 * mm, 0, height - 12 * mm)
            path.close()
            canvas.setFillColor(d.brand)
            canvas.drawPath(path, stroke=0, fill=1)
            canvas.setStrokeColor(GOLD)
            canvas.setLineWidth(1.4)
            edge = canvas.beginPath()
            edge.moveTo(width, height - 17.5 * mm)
            edge.curveTo(
                width * 0.65, height - 5.5 * mm, width * 0.35, height - 27.5 * mm, 0, height - 13.5 * mm
            )
            canvas.drawPath(edge, stroke=1, fill=0)
            canvas.setFillColor(d.brand)
            canvas.rect(0, 0, width, 5 * mm, stroke=0, fill=1)
            canvas.setFillColor(GOLD)
            canvas.rect(0, 5 * mm, width, 0.8 * mm, stroke=0, fill=1)
            canvas.setStrokeColor(GOLD)
            canvas.setLineWidth(0.6)
            canvas.roundRect(inset, inset, width - 2 * inset, height - 2 * inset, 4 * mm, stroke=1, fill=0)
        elif d.template == "modern":
            canvas.setFillColor(d.tint)
            for x, y, flip in ((0, height, -1), (width, 0, 1)):
                p = canvas.beginPath()
                p.moveTo(x, y)
                p.lineTo(x - flip * 40 * mm, y)
                p.lineTo(x, y + flip * 40 * mm)
                p.close()
                canvas.drawPath(p, stroke=0, fill=1)
            canvas.setStrokeColor(d.brand)
            canvas.setLineWidth(0.8)
            canvas.rect(inset, inset, width - 2 * inset, height - 2 * inset, stroke=1, fill=0)
        else:
            # Double rule frame (classic) or a single hairline (compact).
            canvas.setStrokeColor(d.brand)
            canvas.setLineWidth(1.6 if d.template == "classic" else 0.6)
            canvas.rect(inset, inset, width - 2 * inset, height - 2 * inset, stroke=1, fill=0)
            if d.template == "classic":
                canvas.setLineWidth(0.4)
                gap = 1.6 * mm
                canvas.rect(
                    inset + gap,
                    inset + gap,
                    width - 2 * (inset + gap),
                    height - 2 * (inset + gap),
                    stroke=1,
                    fill=0,
                )
        canvas.restoreState()

    return draw


def render_cards(cards, template=None, color=None):
    """One PDF for the given cards in the school's design (or a design being previewed)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=13 * mm,
        title="Report cards",
    )
    story = []
    for index, card in enumerate(cards):
        if index:
            story.append(PageBreak())
        story += card_story(card, design_for(card.school, template, color))
    if not story:
        story = [Paragraph("No report cards.", STYLES["Normal"])]
    if cards:
        decorate = _decorate(design_for(cards[0].school, template, color), cards[0].school.name)
        doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    else:
        doc.build(story)
    return buffer.getvalue()


def sample_card(school):
    """An unsaved report card with made-up results, for previewing a design."""
    from .models import ReportCard

    subjects = [
        ("English", 78, "D2"),
        ("Mathematics", 84, "D2"),
        ("Science", 69, "C3"),
        ("Social Studies", 73, "C3"),
        ("Religious Education", 88, "D1"),
        ("Literacy", 65, "C4"),
    ]
    exams = [
        {"id": 1, "short": "BOT", "weight": 20.0},
        {"id": 2, "short": "MOT", "weight": 30.0},
        {"id": 3, "short": "EOT", "weight": 50.0},
    ]
    snapshot = {
        "school": {
            "name": school.name,
            "motto": school.motto,
            "address": school.address or school.location,
            "phone": school.phone,
            "email": school.email,
            "logo": school.logo.path if school.logo else None,
            "footer": school.report_card_footer,
            "registration_number": school.registration_number,
        },
        "learner": {
            "name": "Sample Learner",
            "adm_no": "2026/0001",
            "lin": "LIN0000000",
            "sex": "Female",
            "house": "Red",
            "photo": None,
        },
        "class": "P5",
        "stream": "East",
        "term": "Term 1 2026",
        "next_term_begins": "Monday 26 May 2026",
        "rule_set": "ple",
        "show_positions": True,
        "exams": exams,
        "subjects": [
            {
                "subject_id": i,
                "name": n,
                "score": float(s),
                "grade": g,
                "descriptor": "Credit" if g.startswith("C") else "Distinction",
                "comment": "Excellent. Keep it up."
                if s >= 80
                else "Very good work."
                if s >= 70
                else "Good. Can do better.",
                "exams": {"1": s - 4, "2": s + 2, "3": s},
                "initials": "AB",
            }
            for i, (n, s, g) in enumerate(subjects)
        ],
        "total": 457.0,
        "average": 76.2,
        "aggregate": 10,
        "division": "I",
        "points": None,
        "position": 3,
        "out_of": 42,
        "is_complete": True,
        "attendance": {"present": 58, "total": 60},
        "class_teacher_comment": "A hard-working learner. Keep it up.",
        "head_comment": "Good results. Aim higher.",
        "promotion_note": "",
    }
    card = ReportCard(school=school, serial="SAMPLE-0001", status="draft", snapshot=snapshot)
    card.verify_token = "sample"
    return card
