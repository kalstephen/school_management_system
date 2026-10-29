"""Import UNEB national results and analyse them by year, division, subject and teacher."""

import csv
import io
from collections import Counter, defaultdict

from apps.curriculum.models import Subject, SubjectAllocation
from apps.learners.models import Learner

from .models import UnebResult

FIXED_COLUMNS = {"index_number", "candidate_name", "sex", "aggregate", "division", "points", "result"}


def import_results(school, year, level, file_obj):
    text = file_obj.read()
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    names = {l.full_name.lower(): l for l in Learner.objects.filter(school=school)}
    names.update({f"{l.last_name} {l.first_name}".lower(): l for l in names.values()})
    created, updated, errors = 0, 0, []
    for line, row in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        if not row.get("index_number") or not row.get("candidate_name"):
            errors.append({"row": line, "error": "index_number and candidate_name are required"})
            continue
        grades = {k.upper(): v.upper() for k, v in row.items() if k not in FIXED_COLUMNS and v}
        try:
            aggregate = int(row["aggregate"]) if row.get("aggregate") else None
            points = float(row["points"]) if row.get("points") else None
        except ValueError:
            errors.append({"row": line, "error": "aggregate and points must be numbers"})
            continue
        _, made = UnebResult.objects.update_or_create(
            school=school,
            year=year,
            level=level,
            index_number=row["index_number"],
            defaults={
                "candidate_name": row["candidate_name"],
                "sex": row.get("sex", "")[:1].upper(),
                "learner": names.get(row["candidate_name"].lower()),
                "subject_grades": grades,
                "aggregate": aggregate,
                "division": row.get("division") or row.get("result", ""),
                "points": points,
            },
        )
        created += int(made)
        updated += int(not made)
    return {"created": created, "updated": updated, "errors": errors}


def analyse(school, level):
    rows = list(UnebResult.objects.filter(school=school, level=level))
    by_year = defaultdict(list)
    for r in rows:
        by_year[r.year].append(r)
    years = []
    for year in sorted(by_year):
        group = by_year[year]
        aggregates = [r.aggregate for r in group if r.aggregate is not None]
        points = [float(r.points) for r in group if r.points is not None]
        years.append(
            {
                "year": year,
                "candidates": len(group),
                "divisions": dict(Counter(r.division or "–" for r in group)),
                "average_aggregate": round(sum(aggregates) / len(aggregates), 1) if aggregates else None,
                "average_points": round(sum(points) / len(points), 1) if points else None,
                "by_sex": dict(Counter(r.sex or "–" for r in group)),
            }
        )
    latest = max(by_year) if by_year else None
    subjects = []
    if latest:
        codes = defaultdict(Counter)
        for r in by_year[latest]:
            for code, grade in r.subject_grades.items():
                codes[code][grade] += 1
        teacher_by_code = _teachers_by_code(school, level)
        for code, grades in sorted(codes.items()):
            subjects.append({"code": code, "grades": dict(grades), "teachers": teacher_by_code.get(code, [])})
    return {"level": level, "years": years, "latest_year": latest, "subjects": subjects}


def _teachers_by_code(school, level):
    level_map = {"PLE": "primary", "UCE": "olevel", "UACE": "alevel"}
    result = defaultdict(list)
    subjects = Subject.objects.filter(school=school, level=level_map.get(level), status="approved")
    for subject in subjects:
        names = sorted(
            {
                a.teacher.full_name
                for a in SubjectAllocation.objects.filter(
                    subject=subject, school_class__is_candidate_class=True
                ).select_related("teacher")
            }
        )
        for key in {subject.short_name.upper(), subject.uneb_code.upper()} - {""}:
            result[key] = names
    return result
