import csv
import datetime
import io

from django.db import transaction

from apps.schoolsetup.models import SchoolClass, Stream, current_term

from .models import Enrolment, Guardian, Learner, LearnerGuardian

IMPORT_COLUMNS = [
    "adm_no",
    "lin",
    "first_name",
    "last_name",
    "other_names",
    "sex",
    "date_of_birth",
    "class",
    "stream",
    "residence",
    "guardian_name",
    "guardian_phone",
    "guardian_relationship",
    "guardian_email",
]


def _parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date '{value}' is not in YYYY-MM-DD or DD/MM/YYYY format")


def find_or_create_guardian(school, name, phone, email="", relationship=""):
    name, phone = (name or "").strip(), (phone or "").strip()
    if not name and not phone:
        return None
    guardian = Guardian.objects.filter(school=school, phone=phone).first() if phone else None
    if guardian is None:
        guardian = Guardian.objects.create(
            school=school, full_name=name or phone, phone=phone, email=email or ""
        )
    return guardian


def admit_learner(school, data, term=None, school_class=None, stream=None, guardian=None, relationship=""):
    """Create a learner with an admission number, enrol them and link a guardian."""
    term = term or current_term(school)
    with transaction.atomic():
        if not data.get("adm_no"):
            year = term.academic_year.name if term else datetime.date.today().year
            data["adm_no"] = school.next_admission_number(year)
        learner = Learner.objects.create(school=school, **data)
        if term and school_class:
            Enrolment.objects.create(
                school=school,
                learner=learner,
                term=term,
                school_class=school_class,
                stream=stream,
                residence=learner.residence,
            )
        if guardian:
            LearnerGuardian.objects.create(
                school=school, learner=learner, guardian=guardian, relationship=relationship, is_primary=True
            )
    return learner


def import_learners_csv(school, file_obj):
    """Bulk import from CSV. Each row is validated on its own; good rows are saved and
    errors are reported by row number."""
    text = file_obj.read()
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    term = current_term(school)
    classes = {c.name.strip().lower(): c for c in SchoolClass.objects.filter(school=school)}
    created, errors = 0, []
    for line, row in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        try:
            if not row.get("first_name") or not row.get("last_name"):
                raise ValueError("first_name and last_name are required")
            sex = row.get("sex", "").upper()[:1]
            if sex not in ("M", "F"):
                raise ValueError("sex must be M or F")
            school_class = classes.get(row.get("class", "").lower())
            if row.get("class") and school_class is None:
                raise ValueError(f"class '{row['class']}' does not exist")
            stream = None
            if school_class and row.get("stream"):
                stream = Stream.objects.filter(school_class=school_class, name__iexact=row["stream"]).first()
                if stream is None:
                    raise ValueError(f"stream '{row['stream']}' does not exist in {school_class}")
            if row.get("adm_no") and Learner.objects.filter(school=school, adm_no=row["adm_no"]).exists():
                raise ValueError(f"admission number {row['adm_no']} already exists")
            guardian = find_or_create_guardian(
                school, row.get("guardian_name"), row.get("guardian_phone"), row.get("guardian_email")
            )
            admit_learner(
                school,
                {
                    "adm_no": row.get("adm_no", ""),
                    "lin": row.get("lin", ""),
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "other_names": row.get("other_names", ""),
                    "sex": sex,
                    "date_of_birth": _parse_date(row.get("date_of_birth")),
                    "residence": "boarding" if row.get("residence", "").lower().startswith("b") else "day",
                    "admitted_on": datetime.date.today(),
                },
                term=term,
                school_class=school_class,
                stream=stream,
                guardian=guardian,
                relationship=row.get("guardian_relationship", ""),
            )
            created += 1
        except ValueError as exc:
            errors.append({"row": line, "error": str(exc)})
    return {"created": created, "errors": errors}


def learners_in(school, term, school_class=None, stream=None):
    enrolments = Enrolment.objects.filter(school=school, term=term, learner__status=Learner.Status.ACTIVE)
    if school_class:
        enrolments = enrolments.filter(school_class=school_class)
    if stream:
        enrolments = enrolments.filter(stream=stream)
    return Learner.objects.filter(pk__in=enrolments.values("learner_id"))
