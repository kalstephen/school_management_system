"""The Ugandan school calendar: public holidays, standard term dates and school days.

Term dates follow the usual Ministry of Education pattern (Term 1 February–May, Term 2
late May–August, Term 3 September–early December). The owner console generates them in
one step and can adjust any date afterwards; schools see them read-only.

Eid dates depend on the moon sighting and are confirmed by government each year, so the
table below is the expected date. A school closure or a changed holiday is added as a
calendar event of kind "holiday", which the register respects.
"""

import datetime

from django.db import transaction
from django.utils import timezone

FIXED_HOLIDAYS = {
    (1, 1): "New Year's Day",
    (1, 26): "NRM Liberation Day",
    (2, 16): "Archbishop Janani Luwum Day",
    (3, 8): "International Women's Day",
    (5, 1): "Labour Day",
    (6, 3): "Uganda Martyrs' Day",
    (6, 9): "National Heroes' Day",
    (10, 9): "Independence Day",
    (12, 25): "Christmas Day",
    (12, 26): "Boxing Day",
}

EID_AL_FITR = {
    2024: (4, 10),
    2025: (3, 31),
    2026: (3, 20),
    2027: (3, 10),
    2028: (2, 27),
    2029: (2, 15),
    2030: (2, 5),
}
EID_AL_ADHA = {
    2024: (6, 17),
    2025: (6, 6),
    2026: (5, 27),
    2027: (5, 17),
    2028: (5, 6),
    2029: (4, 25),
    2030: (4, 14),
}


def easter_sunday(year):
    """Gregorian Easter (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return datetime.date(year, month, day)


def public_holidays(year):
    """{date: name} for Uganda's public holidays in the year."""
    days = {datetime.date(year, m, d): name for (m, d), name in FIXED_HOLIDAYS.items()}
    easter = easter_sunday(year)
    days[easter - datetime.timedelta(days=2)] = "Good Friday"
    days[easter + datetime.timedelta(days=1)] = "Easter Monday"
    if year in EID_AL_FITR:
        days[datetime.date(year, *EID_AL_FITR[year])] = "Eid al-Fitr"
    if year in EID_AL_ADHA:
        days[datetime.date(year, *EID_AL_ADHA[year])] = "Eid al-Adha"
    return dict(sorted(days.items()))


def _weekday_on_or_after(day, weekday):
    return day + datetime.timedelta(days=(weekday - day.weekday()) % 7)


def _weekday_on_or_before(day, weekday):
    return day - datetime.timedelta(days=(day.weekday() - weekday) % 7)


def standard_terms(year):
    """[(number, opens, closes)] following the usual Ugandan pattern for the year."""
    monday, friday = 0, 4
    return [
        (
            1,
            _weekday_on_or_after(datetime.date(year, 2, 1), monday),
            _weekday_on_or_before(datetime.date(year, 5, 2), friday),
        ),
        (
            2,
            _weekday_on_or_before(datetime.date(year, 5, 31), monday),
            _weekday_on_or_before(datetime.date(year, 8, 22), friday),
        ),
        (
            3,
            _weekday_on_or_after(datetime.date(year, 9, 8), monday),
            _weekday_on_or_before(datetime.date(year, 12, 5), friday),
        ),
    ]


def sync_term_status(school, today=None):
    """Open the term running today (or the last one that started), close earlier ones and
    mark later ones planned; the year holding that term becomes the current year."""
    from .models import AcademicYear, Term

    today = today or timezone.localdate()
    terms = list(Term.objects.filter(school=school).order_by("start_date"))
    started = [t for t in terms if t.start_date <= today]
    running = started[-1] if started else None
    for term in terms:
        if term == running:
            status = Term.Status.OPEN
        elif term.start_date > today:
            status = Term.Status.PLANNED
        else:
            status = Term.Status.CLOSED
        if term.status != status:
            term.status = status
            term.save(update_fields=["status"])
    if running:
        AcademicYear.objects.filter(school=school).exclude(pk=running.academic_year_id).update(
            is_current=False
        )
        AcademicYear.objects.filter(pk=running.academic_year_id).update(is_current=True)
    return running


def generate_year(school, year):
    """Create the academic year and its three terms with the standard dates. Terms that
    already exist are left as they are. Returns (academic_year, terms_created)."""
    from .models import AcademicYear, Term

    plan = standard_terms(year)
    created = 0
    with transaction.atomic():
        academic_year, _ = AcademicYear.objects.get_or_create(
            school=school,
            name=str(year),
            defaults={"start_date": plan[0][1], "end_date": plan[-1][2]},
        )
        following = {1: plan[1][1], 2: plan[2][1], 3: standard_terms(year + 1)[0][1]}
        for number, opens, closes in plan:
            _, made = Term.objects.get_or_create(
                school=school,
                academic_year=academic_year,
                number=number,
                defaults={
                    "start_date": opens,
                    "end_date": closes,
                    "next_term_begins": following[number],
                },
            )
            created += int(made)
        sync_term_status(school)
    return academic_year, created


def calendar_days(school, start, end):
    """Every day from start to end with whether school is in session and why not."""
    from .models import CalendarEvent, Term

    terms = list(Term.objects.filter(school=school, start_date__lte=end, end_date__gte=start))
    closures = list(
        CalendarEvent.objects.filter(school=school, kind=CalendarEvent.Kind.HOLIDAY, start_date__lte=end)
    )
    holidays = {}
    for year in range(start.year, end.year + 1):
        holidays.update(public_holidays(year))
    days, day = [], start
    while day <= end:
        reason = None
        if day.weekday() >= 5:
            reason = "Weekend"
        elif day in holidays:
            reason = holidays[day]
        else:
            closure = next((c for c in closures if c.start_date <= day <= (c.end_date or c.start_date)), None)
            if closure:
                reason = closure.title
            elif not any(t.start_date <= day <= t.end_date for t in terms):
                reason = "School holiday (between terms)"
        days.append({"date": day, "school_day": reason is None, "reason": reason or ""})
        day += datetime.timedelta(days=1)
    return days


def is_school_day(school, day):
    """(True, "") on a school day, else (False, the reason)."""
    info = calendar_days(school, day, day)[0]
    return info["school_day"], info["reason"]
