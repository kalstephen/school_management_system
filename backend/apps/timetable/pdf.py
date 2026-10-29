"""Printable timetables (class, teacher or room week) and exam timetables, as PDF."""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DAYS = [(1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"), (5, "Friday")]
STYLES = getSampleStyleSheet()
CELL = ParagraphStyle("cell", parent=STYLES["Normal"], fontSize=8, leading=10, alignment=1)
SMALL = ParagraphStyle(
    "small", parent=STYLES["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#64748b")
)


def _brand(school):
    try:
        return colors.HexColor(school.report_color or "#1d4ed8")
    except ValueError:
        return colors.HexColor("#1d4ed8")


def _header(school, title, subtitle):
    return [
        Paragraph(
            f"<b>{school.name.upper()}</b>",
            ParagraphStyle("h", parent=STYLES["Title"], fontSize=15, spaceAfter=0),
        ),
        Paragraph(
            title, ParagraphStyle("t", parent=STYLES["Heading2"], alignment=1, textColor=_brand(school))
        ),
        Paragraph(subtitle, ParagraphStyle("s", parent=SMALL, alignment=1)),
        Spacer(1, 4 * mm),
    ]


def weekly_timetable_pdf(school, title, subtitle, periods, slots):
    """periods: Period rows in order. slots: TimetableSlot rows for one class, teacher or room.
    Every lesson shows its subject, teacher and class (and room), whichever week is printed."""
    by_cell = {}
    for slot in slots:
        by_cell.setdefault((slot.day, slot.period_id), []).append(slot)
    header = ["Period"] + [name for _, name in DAYS]
    rows = [header]
    break_rows = []
    for period in periods:
        label = Paragraph(f"<b>{period.name}</b><br/>{period.start_time:%H:%M}–{period.end_time:%H:%M}", CELL)
        if period.is_break:
            rows.append([label, Paragraph(f"<i>{period.name}</i>", CELL), "", "", "", ""])
            break_rows.append(len(rows) - 1)
            continue
        row = [label]
        for day, _ in DAYS:
            parts = []
            for slot in by_cell.get((day, period.id), []):
                teacher = slot.teacher.full_name if slot.teacher else "No teacher yet"
                room = f" · {slot.room.name}" if slot.room else ""
                parts.append(
                    f"<b>{slot.subject.name}</b><br/><font size=7>{teacher}<br/>"
                    f"{slot.stream or slot.school_class}{room}</font>"
                )
            row.append(Paragraph("<br/>".join(parts), CELL))
        rows.append(row)
    width = landscape(A4)[0] - 24 * mm
    table = Table(rows, colWidths=[28 * mm] + [(width - 28 * mm) / 5] * 5, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), _brand(school)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f1f5f9")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for index in break_rows:
        style += [
            ("SPAN", (1, index), (-1, index)),
            ("BACKGROUND", (1, index), (-1, index), colors.HexColor("#fef3c7")),
        ]
    table.setStyle(TableStyle(style))
    return _build(school, title, subtitle, [table], landscape(A4))


def exam_timetable_pdf(school, exam, rows):
    """rows: ExamSchedule entries for the exam, any classes."""
    data = [["Date", "Time", "Class", "Paper", "Room", "Invigilator"]]
    for r in rows:
        paper = f"{r.subject.name}{f' P{r.paper.number}' if r.paper else ''}"
        data.append(
            [
                f"{r.date:%a %d %b %Y}",
                f"{r.start_time:%H:%M}–{r.end_time:%H:%M}",
                r.school_class.name,
                paper,
                r.room.name if r.room else "–",
                r.invigilator.full_name if r.invigilator else "–",
            ]
        )
    if len(data) == 1:
        data.append(["No papers scheduled yet", "", "", "", "", ""])
    width = A4[0] - 24 * mm
    table = Table(data, colWidths=[32 * mm, 26 * mm, 18 * mm, None, 24 * mm, 36 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _brand(school)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    table._argW[3] = width - sum(w for i, w in enumerate(table._argW) if i != 3)
    return _build(school, f"Exam timetable — {exam.name}", str(exam.term), [table], A4)


def seating_plan_pdf(school, exam, seats):
    """One page per room and session: seat number, learner and class, ready for the door."""
    from reportlab.platypus import PageBreak

    groups = {}
    for seat in seats:
        groups.setdefault((seat.date, seat.start_time, seat.room.name), []).append(seat)
    body = []
    for index, ((date, start, room), rows) in enumerate(sorted(groups.items())):
        if index:
            body.append(PageBreak())
        classes = ", ".join(sorted({str(s.school_class) for s in rows}))
        body.append(
            Paragraph(
                f"<b>{room}</b> · {date:%A %d %B %Y} · {start:%H:%M} · {len(rows)} learners ({classes})",
                ParagraphStyle("sp", parent=STYLES["Heading3"], alignment=1),
            )
        )
        table = Table(
            [["Seat", "Learner", "Adm. No.", "Class"]]
            + [[s.seat, s.learner.full_name, s.learner.adm_no, str(s.school_class)] for s in rows],
            colWidths=[18 * mm, 80 * mm, 40 * mm, 40 * mm],
            repeatRows=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                    ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                    ("BACKGROUND", (0, 0), (-1, 0), _brand(school)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ]
            )
        )
        body.append(table)
    if not body:
        body = [Paragraph("No seating plan yet.", STYLES["Normal"])]
    return _build(
        school,
        f"Seating plan — {exam.name}",
        "Classes are mixed so neighbours are from different classes",
        body,
        A4,
    )


def _build(school, title, subtitle, body, pagesize):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=title,
    )
    doc.build(_header(school, title, subtitle) + body)
    return buffer.getvalue()
