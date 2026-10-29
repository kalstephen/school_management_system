"""Ugandan defaults a new school can load in one click. Everything stays editable.

Grade bands are common school practice, not official UNEB tables: schools should check
them against current UNEB/NCDC guidance and their own policy.
"""

from django.db import transaction

PLE_BANDS = [  # label, min, max, points, descriptor
    ("D1", 90, 100, 1, "Distinction"),
    ("D2", 80, 89.99, 2, "Distinction"),
    ("C3", 70, 79.99, 3, "Credit"),
    ("C4", 60, 69.99, 4, "Credit"),
    ("C5", 55, 59.99, 5, "Credit"),
    ("C6", 50, 54.99, 6, "Credit"),
    ("P7", 45, 49.99, 7, "Pass"),
    ("P8", 40, 44.99, 8, "Pass"),
    ("F9", 0, 39.99, 9, "Fail"),
]
CBC_BANDS = [
    ("A", 80, 100, 5, "Exceptional"),
    ("B", 70, 79.99, 4, "Outstanding"),
    ("C", 50, 69.99, 3, "Satisfactory"),
    ("D", 40, 49.99, 2, "Basic"),
    ("E", 0, 39.99, 1, "Elementary"),
]
UACE_BANDS = [
    ("A", 80, 100, 6, "Principal pass"),
    ("B", 70, 79.99, 5, "Principal pass"),
    ("C", 60, 69.99, 4, "Principal pass"),
    ("D", 50, 59.99, 3, "Principal pass"),
    ("E", 45, 49.99, 2, "Principal pass"),
    ("O", 35, 44.99, 1, "Subsidiary pass"),
    ("F", 0, 34.99, 0, "Fail"),
]

UCE_OLD_BANDS = [
    ("D1", 80, 100, 1, "Distinction"),
    ("D2", 75, 79.99, 2, "Distinction"),
    ("C3", 70, 74.99, 3, "Credit"),
    ("C4", 65, 69.99, 4, "Credit"),
    ("C5", 60, 64.99, 5, "Credit"),
    ("C6", 50, 59.99, 6, "Credit"),
    ("P7", 45, 49.99, 7, "Pass"),
    ("P8", 40, 44.99, 8, "Pass"),
    ("F9", 0, 39.99, 9, "Fail"),
]

# Ready-made scales schools start from. All stay editable by the head teacher, director or DOS.
GRADING_PRESETS = {
    "ple": {
        "name": "Primary (PLE) D1–F9",
        "description": "Nine grades with points 1–9. Four subjects' points add up to the PLE aggregate "
        "(4 = best); Division I is 4–12, II 13–23, III 24–29, IV 30–34.",
        "bands": PLE_BANDS,
    },
    "cbc": {
        "name": "O-Level CBC achievement levels A–E",
        "description": "New lower-secondary curriculum: five achievement levels, no aggregates or divisions. "
        "Activities of integration count for 20% of each subject.",
        "bands": CBC_BANDS,
    },
    "uace": {
        "name": "A-Level (UACE) A–F",
        "description": "Principal subjects earn points A=6, B=5, C=4, D=3, E=2, O=1, F=0. "
        "Subsidiaries earn 1 point for a pass.",
        "bands": UACE_BANDS,
    },
    "uce_old": {
        "name": "O-Level (old curriculum) D1–F9",
        "description": "The nine-grade scale used before the competency-based curriculum.",
        "bands": UCE_OLD_BANDS,
    },
}

SECTIONS = {
    "nursery": ("Nursery", "nursery", None, ["Baby", "Middle", "Top"], None),
    "primary": ("Primary", "ple", "PLE grading (D1–F9)", [f"P{i}" for i in range(1, 8)], "P7"),
    "olevel": ("O-Level", "cbc", "CBC achievement levels (A–E)", [f"S{i}" for i in range(1, 5)], "S4"),
    "alevel": ("A-Level", "uace", "UACE grades (A–F)", ["S5", "S6"], "S6"),
}

SUBJECTS = {
    "nursery": [
        ("Language development", "LANG", "core", False),
        ("Number work", "NUM", "core", False),
        ("Social development", "SOC", "core", False),
        ("Creative arts", "ART", "core", False),
        ("Health habits", "HLTH", "core", False),
    ],
    "primary": [
        ("English", "ENG", "core", True),
        ("Mathematics", "MTC", "core", True),
        ("Science", "SCI", "core", True),
        ("Social Studies", "SST", "core", True),
        ("Religious Education", "RE", "core", False),
        ("Literacy", "LIT", "core", False),
        ("Local Language", "LL", "elective", False),
    ],
    "olevel": [
        ("English Language", "ENG", "core", False),
        ("Mathematics", "MTC", "core", False),
        ("Physics", "PHY", "core", False),
        ("Chemistry", "CHEM", "core", False),
        ("Biology", "BIO", "core", False),
        ("Geography", "GEO", "core", False),
        ("History and Political Education", "HPE", "core", False),
        ("Kiswahili", "KIS", "core", False),
        ("Physical Education", "PE", "core", False),
        ("Religious Education", "RE", "core", False),
        ("Entrepreneurship", "ENT", "core", False),
        ("Agriculture", "AGR", "elective", False),
        ("ICT", "ICT", "elective", False),
        ("Literature in English", "LIT", "elective", False),
        ("Art and Design", "ART", "elective", False),
        ("Performing Arts", "PA", "elective", False),
        ("Technology and Design", "TD", "elective", False),
        ("Nutrition and Food Technology", "NFT", "elective", False),
    ],
    "alevel": [
        ("General Paper", "GP", "subsidiary", False),
        ("Subsidiary Mathematics", "SMTC", "subsidiary", False),
        ("Subsidiary ICT", "SICT", "subsidiary", False),
        ("Mathematics", "MTC", "principal", False),
        ("Physics", "PHY", "principal", False),
        ("Chemistry", "CHEM", "principal", False),
        ("Biology", "BIO", "principal", False),
        ("Economics", "ECON", "principal", False),
        ("Geography", "GEO", "principal", False),
        ("History", "HIST", "principal", False),
        ("Literature in English", "LIT", "principal", False),
        ("Divinity", "DIV", "principal", False),
        ("Entrepreneurship", "ENT", "principal", False),
        ("Agriculture", "AGR", "principal", False),
        ("Fine Art", "ART", "principal", False),
    ],
}
A_LEVEL_PAPERS = {
    "MTC": 2,
    "PHY": 3,
    "CHEM": 3,
    "BIO": 3,
    "ECON": 2,
    "GEO": 3,
    "HIST": 3,
    "LIT": 3,
    "DIV": 3,
    "ENT": 3,
    "AGR": 3,
    "ART": 3,
}
COMBINATIONS = [
    ("PCM", ["PHY", "CHEM", "MTC"], "SICT"),
    ("PCB", ["PHY", "CHEM", "BIO"], "SMTC"),
    ("BCM", ["BIO", "CHEM", "MTC"], "SICT"),
    ("HEG", ["HIST", "ECON", "GEO"], "SMTC"),
    ("HEL", ["HIST", "ECON", "LIT"], "SMTC"),
    ("MEG", ["MTC", "ECON", "GEO"], "SICT"),
    ("BCA", ["BIO", "CHEM", "AGR"], "SMTC"),
    ("DEG", ["DIV", "ECON", "GEO"], "SMTC"),
]

EXPENSE_CATEGORIES = [
    ("Feeding / kitchen", ["Posho", "Beans", "Sugar", "Cooking oil", "Firewood", "Gas", "Milk"], False),
    (
        "Salaries & allowances",
        ["Teaching staff", "Non-teaching staff", "Part-time", "Allowances", "NSSF"],
        False,
    ),
    ("Utilities", ["Electricity (Yaka)", "Water (NWSC)", "Internet", "Airtime"], False),
    (
        "Academics",
        ["Stationery", "Printing", "Exam papers", "UNEB registration", "Textbooks", "Lab chemicals"],
        False,
    ),
    ("Maintenance & repairs", ["Buildings", "Furniture", "Plumbing", "Electrical"], False),
    ("Transport", ["Fuel", "Vehicle service", "Trips", "Hire"], False),
    ("Health & welfare", ["Sickbay drugs", "Sanitary items", "Cleaning materials"], False),
    ("Administration", ["Bank charges", "Licences", "Meetings", "Statutory fees"], False),
    ("Capital purchases", ["Equipment", "Computers", "Furniture"], True),
    ("Co-curricular", ["Sports", "Music", "Drama", "Clubs"], False),
]

COMMENTS = [
    ("class_teacher", 80, 100, "Excellent work. Keep it up."),
    ("class_teacher", 65, 79.99, "Very good effort. Aim higher."),
    ("class_teacher", 50, 64.99, "Fair performance. More effort is needed."),
    ("class_teacher", 0, 49.99, "Needs to work much harder and seek help."),
    ("head", 80, 100, "Outstanding results. Congratulations."),
    ("head", 65, 79.99, "Good results. Keep improving."),
    ("head", 50, 64.99, "Average. Work harder next term."),
    ("head", 0, 49.99, "Below expectations. Parents should follow up."),
]
# Subject teachers' presets, by the learner's mark in that subject.
SUBJECT_COMMENTS = [
    ("subject", 80, 100, "Excellent. Keep it up."),
    ("subject", 70, 79.99, "Very good work."),
    ("subject", 60, 69.99, "Good. Can do better."),
    ("subject", 50, 59.99, "Fair. More practice needed."),
    ("subject", 40, 49.99, "Weak. Needs more effort."),
    ("subject", 0, 39.99, "Poor. Needs extra help and practice."),
]


def _scale(school, name, bands):
    from .models import GradeBand, GradingScale

    scale, created = GradingScale.objects.get_or_create(school=school, name=name)
    if created:
        for label, low, high, points, descriptor in bands:
            GradeBand.objects.create(
                school=school,
                scale=scale,
                label=label,
                min_score=low,
                max_score=high,
                points=points,
                descriptor=descriptor,
            )
    return scale


@transaction.atomic
def seed_school_defaults(school, levels=("nursery", "primary", "olevel", "alevel")):
    from apps.assessment.models import CommentBank
    from apps.curriculum.models import Combination, Paper, Subject
    from apps.finance.models import ExpenseCategory, ExpenseSubCategory

    from .models import Department, SchoolClass, Section

    created = {"sections": 0, "classes": 0, "subjects": 0, "categories": 0}
    scales = {
        "ple": ("PLE grading (D1–F9)", PLE_BANDS),
        "cbc": ("CBC achievement levels (A–E)", CBC_BANDS),
        "uace": ("UACE grades (A–F)", UACE_BANDS),
    }
    for order, level in enumerate(["nursery", "primary", "olevel", "alevel"]):
        if level not in levels:
            continue
        name, rule, _, classes, _candidate = SECTIONS[level]
        scale = _scale(school, *scales[rule]) if rule in scales else None
        section, made = Section.objects.get_or_create(
            school=school,
            name=name,
            defaults={
                "level": level,
                "grading_rule_set": rule,
                "grading_scale": scale,
                "order": order,
                "show_positions": rule not in ("cbc", "nursery"),
            },
        )
        created["sections"] += int(made)
        previous = None
        for index, class_name in enumerate(classes):
            school_class, made = SchoolClass.objects.get_or_create(
                school=school,
                name=class_name,
                defaults={
                    "section": section,
                    "order": order * 10 + index,
                    "is_candidate_class": class_name in ("P7", "S4", "S6"),
                },
            )
            created["classes"] += int(made)
            if previous is not None and previous.next_class_id is None and not previous.is_candidate_class:
                previous.next_class = school_class
                previous.save()
            previous = school_class
        for idx, (subject_name, short, category, in_aggregate) in enumerate(SUBJECTS[level]):
            subject, made = Subject.objects.get_or_create(
                school=school,
                level=level,
                short_name=short,
                defaults={
                    "name": subject_name,
                    "category": category,
                    "in_aggregate": in_aggregate,
                    "order": idx,
                },
            )
            created["subjects"] += int(made)
            if level == "alevel" and made and short in A_LEVEL_PAPERS:
                for number in range(1, A_LEVEL_PAPERS[short] + 1):
                    Paper.objects.create(school=school, subject=subject, number=number)
        if level == "primary":
            lower = list(SchoolClass.objects.filter(school=school, name__in=["P1", "P2", "P3"]))
            # Lower primary is reported with marks and grades but no PLE aggregate.
            if lower:
                lower_section, _ = Section.objects.get_or_create(
                    school=school,
                    level="primary",
                    name="Lower primary",
                    defaults={
                        "grading_rule_set": "generic",
                        "grading_scale": section.grading_scale,
                        "order": order,
                    },
                )
                for school_class in lower:
                    school_class.section = lower_section
                    school_class.save()
        if level == "alevel":
            subjects = {s.short_name: s for s in Subject.objects.filter(school=school, level="alevel")}
            for code, principals, subsidiary in COMBINATIONS:
                combo, made = Combination.objects.get_or_create(
                    school=school, code=code, defaults={"subsidiary": subjects.get(subsidiary)}
                )
                if made:
                    combo.principals.set([subjects[p] for p in principals if p in subjects])
    for name in ["Languages", "Mathematics", "Sciences", "Humanities", "Technical & vocational"]:
        Department.objects.get_or_create(school=school, name=name)
    for order, (name, subs, capital) in enumerate(EXPENSE_CATEGORIES):
        category, made = ExpenseCategory.objects.get_or_create(
            school=school, name=name, defaults={"is_capital": capital, "order": order}
        )
        created["categories"] += int(made)
        if made:
            for sub in subs:
                ExpenseSubCategory.objects.create(school=school, category=category, name=sub)
    if not CommentBank.objects.filter(school=school).exclude(role="subject").exists():
        for role, low, high, text in COMMENTS:
            CommentBank.objects.create(school=school, role=role, min_average=low, max_average=high, text=text)
    if not CommentBank.objects.filter(school=school, role="subject").exists():
        for role, low, high, text in SUBJECT_COMMENTS:
            CommentBank.objects.create(school=school, role=role, min_average=low, max_average=high, text=text)
    return created
