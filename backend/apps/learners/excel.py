"""Bulk enrolment from Excel.

The school downloads a template, fills one row per learner (names, residence, parents and
guardians, health), then uploads it while choosing the term, class and stream the learners
join. Rows are checked one by one; a preview (dry run) shows problems before anything is saved.
"""

import datetime
import io

from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from .models import Enrolment, Guardian, Learner, LearnerGuardian

# key, header, required, width, help text
COLUMNS = [
    ("first_name", "First name", True, 16, "Required"),
    ("last_name", "Surname", True, 16, "Required"),
    ("other_names", "Other names", False, 16, ""),
    ("sex", "Sex (M/F)", True, 10, "M or F"),
    ("date_of_birth", "Date of birth", False, 14, "e.g. 2018-03-21"),
    ("lin", "LIN", False, 16, "Learner Identification Number"),
    ("adm_no", "Admission number", False, 16, "Leave empty to generate"),
    ("residence", "Day/Boarding", False, 13, "Day or Boarding"),
    ("religion", "Religion", False, 14, ""),
    ("nationality", "Nationality", False, 13, "Default Ugandan"),
    ("district", "District", False, 14, ""),
    ("address", "Village / address", False, 22, ""),
    ("previous_school", "Previous school", False, 22, ""),
    ("father_name", "Father's name", False, 20, ""),
    ("father_phone", "Father's phone", False, 15, ""),
    ("father_occupation", "Father's occupation", False, 16, ""),
    ("mother_name", "Mother's name", False, 20, ""),
    ("mother_phone", "Mother's phone", False, 15, ""),
    ("mother_occupation", "Mother's occupation", False, 16, ""),
    ("guardian_name", "Guardian's name", False, 20, "If not a parent"),
    ("guardian_relationship", "Guardian relationship", False, 16, "e.g. Aunt, Uncle"),
    ("guardian_phone", "Guardian's phone", False, 15, ""),
    ("guardian_email", "Guardian's email", False, 22, "For emailed report cards"),
    ("allergies", "Allergies", False, 18, "e.g. Penicillin, peanuts"),
    ("medical_conditions", "Illness / medical conditions", False, 26, "e.g. Asthma, sickle cell"),
    ("special_needs", "Special needs", False, 18, ""),
    ("notes", "Other notes", False, 22, ""),
]
HEADERS = {header.lower(): key for key, header, *_ in COLUMNS}
EXAMPLE = {
    "first_name": "Aisha",
    "last_name": "Namubiru",
    "sex": "F",
    "date_of_birth": "2019-05-14",
    "residence": "Day",
    "religion": "Catholic",
    "district": "Wakiso",
    "address": "Kazo, Nansana",
    "father_name": "John Namubiru",
    "father_phone": "0772123456",
    "mother_name": "Sarah Nakato",
    "mother_phone": "0701234567",
    "allergies": "",
    "medical_conditions": "Asthma (has inhaler)",
}


def build_template(school_name=""):
    """An .xlsx file with the learner columns, an example row and an instructions sheet."""
    book = Workbook()
    sheet = book.active
    sheet.title = "Learners"
    header_fill = PatternFill("solid", fgColor="1D4ED8")
    required_fill = PatternFill("solid", fgColor="1E3A8A")
    for column, (key, header, required, width, _help) in enumerate(COLUMNS, start=1):
        cell = sheet.cell(row=1, column=column, value=header + (" *" if required else ""))
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = required_fill if required else header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        sheet.column_dimensions[cell.column_letter].width = width
        example = sheet.cell(row=2, column=column, value=EXAMPLE.get(key, ""))
        example.font = Font(italic=True, color="64748B")
    sheet.row_dimensions[1].height = 32
    sheet.freeze_panes = "C2"
    sex = DataValidation(type="list", formula1='"M,F"', allow_blank=True)
    residence = DataValidation(type="list", formula1='"Day,Boarding"', allow_blank=True)
    sheet.add_data_validation(sex)
    sheet.add_data_validation(residence)
    sex.add("D2:D2000")
    residence.add("H2:H2000")

    guide = book.create_sheet("How to fill")
    lines = [
        f"Learner import template{f' — {school_name}' if school_name else ''}",
        "",
        "1. Fill one row per learner on the 'Learners' sheet. Delete the grey example row (row 2).",
        "2. Columns marked * are required: first name, surname and sex (M or F).",
        "3. Dates: write them as YYYY-MM-DD, e.g. 2018-03-21 (DD/MM/YYYY also works).",
        "4. Parents and guardians: fill any you have. Siblings with the same parent phone number share one",
        "   parent record, so a parent is never entered twice.",
        "5. Health: allergies and illnesses are visible only to the nurse and head teacher.",
        "6. Leave the admission number empty: the system gives each learner the next number.",
        "7. In the system: Learners → Import from Excel. Choose the academic year, class and (optionally)",
        "   stream, press Check file to see any problems, then Import.",
    ]
    for row, text in enumerate(lines, start=1):
        cell = guide.cell(row=row, column=1, value=text)
        if row == 1:
            cell.font = Font(bold=True, size=14)
    guide.column_dimensions["A"].width = 110
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = _text(value)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"date of birth '{text}' should look like 2018-03-21")


def read_rows(file_obj):
    """Rows from an .xlsx (or .csv) upload as dicts keyed by column key."""
    name = getattr(file_obj, "name", "").lower()
    if name.endswith(".csv"):
        import csv

        text = file_obj.read().decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        table = list(reader)
    else:
        book = load_workbook(file_obj, read_only=True, data_only=True)
        sheet = book["Learners"] if "Learners" in book.sheetnames else book.active
        table = [list(row) for row in sheet.iter_rows(values_only=True)]
    if not table:
        return []
    keys = []
    for header in table[0]:
        clean = _text(header).replace("*", "").strip().lower()
        keys.append(HEADERS.get(clean) or clean.replace(" ", "_"))
    rows = []
    for number, values in enumerate(table[1:], start=2):
        row = {key: values[i] if i < len(values) else None for i, key in enumerate(keys)}
        if all(_text(v) == "" for v in row.values()):
            continue
        row["_row"] = number
        rows.append(row)
    return rows


def _guardian(school, name, phone, email="", occupation=""):
    name, phone = _text(name), _text(phone)
    if not name and not phone:
        return None
    guardian = Guardian.objects.filter(school=school, phone=phone).first() if phone else None
    if guardian is None and name and not phone:
        guardian = Guardian.objects.filter(school=school, full_name__iexact=name, phone="").first()
    if guardian is None:
        guardian = Guardian.objects.create(
            school=school,
            full_name=name or phone,
            phone=phone,
            email=_text(email),
            occupation=_text(occupation),
        )
    return guardian


def validate_row(school, row, seen_adm):
    first, last = _text(row.get("first_name")), _text(row.get("last_name"))
    if not first or not last:
        raise ValueError("first name and surname are required")
    sex = _text(row.get("sex")).upper()[:1]
    if sex not in ("M", "F"):
        raise ValueError("sex must be M or F")
    adm_no = _text(row.get("adm_no"))
    if adm_no:
        if (
            adm_no.lower() in seen_adm
            or Learner.objects.filter(school=school, adm_no__iexact=adm_no).exists()
        ):
            raise ValueError(f"admission number {adm_no} is already used")
        seen_adm.add(adm_no.lower())
    return {
        "first_name": first,
        "last_name": last,
        "other_names": _text(row.get("other_names")),
        "sex": sex,
        "date_of_birth": _date(row.get("date_of_birth")),
        "lin": _text(row.get("lin")),
        "adm_no": adm_no,
        "residence": "boarding" if _text(row.get("residence")).lower().startswith("b") else "day",
        "religion": _text(row.get("religion")),
        "nationality": _text(row.get("nationality")) or "Ugandan",
        "district": _text(row.get("district")),
        "address": _text(row.get("address")),
        "previous_school": _text(row.get("previous_school")),
        "allergies": _text(row.get("allergies")),
        "medical_notes": _text(row.get("medical_conditions")),
        "special_needs": _text(row.get("special_needs")),
        "notes": _text(row.get("notes")),
    }


def create_learner(school, data, row, term, school_class, stream, year):
    """Save one checked row (see validate_row): the learner with the next admission number
    when none is given, their enrolment, and their father, mother and guardian."""
    with transaction.atomic():
        if not data["adm_no"]:
            data["adm_no"] = school.next_admission_number(year)
        learner = Learner.objects.create(
            school=school,
            admitted_on=datetime.date.today(),
            year_of_entry=datetime.date.today().year,
            has_medical_alert=bool(data["allergies"] or data["medical_notes"]),
            **data,
        )
        if school_class:
            Enrolment.objects.create(
                school=school,
                learner=learner,
                term=term,
                school_class=school_class,
                stream=stream,
                residence=learner.residence,
            )
        links = [
            (
                _guardian(
                    school, row.get("father_name"), row.get("father_phone"), "", row.get("father_occupation")
                ),
                "Father",
            ),
            (
                _guardian(
                    school, row.get("mother_name"), row.get("mother_phone"), "", row.get("mother_occupation")
                ),
                "Mother",
            ),
            (
                _guardian(
                    school, row.get("guardian_name"), row.get("guardian_phone"), row.get("guardian_email")
                ),
                _text(row.get("guardian_relationship")) or "Guardian",
            ),
        ]
        primary_set = False
        for guardian, relationship in links:
            if guardian is None:
                continue
            _, made = LearnerGuardian.objects.get_or_create(
                school=school,
                learner=learner,
                guardian=guardian,
                defaults={"relationship": relationship, "is_primary": not primary_set},
            )
            primary_set = primary_set or made
    return learner


def import_learners(school, file_obj, term, school_class, stream=None, dry_run=False):
    """Check (dry_run) or import learners into the chosen term, class and stream."""
    rows = read_rows(file_obj)
    errors, preview, created = [], [], 0
    seen_adm = set()
    year = term.academic_year.name
    for row in rows:
        try:
            data = validate_row(school, row, seen_adm)
        except ValueError as exc:
            errors.append(
                {
                    "row": row["_row"],
                    "name": f"{_text(row.get('first_name'))} {_text(row.get('last_name'))}".strip(),
                    "error": str(exc),
                }
            )
            continue
        preview.append(
            {
                "row": row["_row"],
                "name": f"{data['first_name']} {data['last_name']}",
                "sex": data["sex"],
                "residence": data["residence"],
                "medical": bool(data["allergies"] or data["medical_notes"]),
            }
        )
        if dry_run:
            continue
        create_learner(school, data, row, term, school_class, stream, year)
        created += 1
    return {
        "rows": len(rows),
        "valid": len(preview),
        "created": created,
        "errors": errors,
        "preview": preview[:200],
        "dry_run": dry_run,
        "target": f"{stream or school_class} · {term}",
    }
