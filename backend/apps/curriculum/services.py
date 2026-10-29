"""Who teaches what, suggested from teachers' subject specialisations."""

from collections import defaultdict

from django.db import transaction
from django.db.models import Q, Sum

from apps.schoolsetup.models import SchoolClass

from .models import SubjectAllocation


def periods_for(subject):
    """A starting weekly load: examined core subjects get more periods."""
    if subject.in_aggregate or subject.category in ("principal",):
        return 5
    return 3


def allocate_from_specialisations(school, class_ids=None):
    """For each class (each stream, where the class is streamed) and each approved subject it
    offers with no teacher yet, allocate the specialist with the lightest load who still has
    room under their weekly maximum."""
    from apps.assessment.grading import subjects_offered
    from apps.staff.models import StaffProfile

    classes = SchoolClass.objects.filter(school=school).prefetch_related("streams").order_by("order")
    if class_ids:
        classes = classes.filter(pk__in=class_ids)
    load = defaultdict(int)
    for row in (
        SubjectAllocation.objects.filter(school=school)
        .values("teacher_id")
        .annotate(n=Sum("periods_per_week"))
    ):
        load[row["teacher_id"]] = row["n"] or 0
    specialists = defaultdict(list)
    for teacher in StaffProfile.objects.filter(
        school=school, kind="teaching", status="active"
    ).prefetch_related("subjects"):
        for subject in teacher.subjects.all():
            specialists[subject.id].append(teacher)
    created, unfilled = [], []
    with transaction.atomic():
        for school_class in classes:
            groups = list(school_class.streams.all()) or [None]
            for subject in subjects_offered(school_class):
                for stream in groups:
                    # Taken when the whole class, or this stream, already has a teacher.
                    taken = SubjectAllocation.objects.filter(
                        school=school, subject=subject, school_class=school_class
                    ).filter(Q(stream__isnull=True) | Q(stream=stream) if stream else Q(stream__isnull=True))
                    if taken.exists():
                        continue
                    periods = periods_for(subject)
                    options = [
                        t
                        for t in specialists.get(subject.id, [])
                        if not t.max_periods_per_week or load[t.id] + periods <= t.max_periods_per_week
                    ]
                    label = f"{subject.name} · {stream or school_class}"
                    if not options:
                        unfilled.append(label)
                        continue
                    teacher = min(options, key=lambda t: load[t.id])
                    SubjectAllocation.objects.create(
                        school=school,
                        teacher=teacher,
                        subject=subject,
                        school_class=school_class,
                        stream=stream,
                        periods_per_week=periods,
                    )
                    load[teacher.id] += periods
                    created.append(f"{label} → {teacher.full_name}")
    return {"created": created, "unfilled": unfilled}
