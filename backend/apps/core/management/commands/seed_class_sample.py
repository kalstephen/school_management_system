"""Fill one class of a real school with sample data so the screens can be tried out:
learners with parents and health notes (loaded through the Excel import), a class teacher
with a login and weekly planner, a published timetable, exams with marks, and attendance.

    python manage.py seed_class_sample --school NewHope-002 --class P1 --stream East --count 50

Running it again adds nothing that is already there.
"""

import datetime
import io
import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook

from apps.accounts.models import Membership, RoleAssignment, User
from apps.accounts.services import sync_class_teacher_role
from apps.assessment.models import Exam, ExamSchedule, Mark, MarkSheet
from apps.assessment.services import prepare_sheets
from apps.attendance.services import save_roll_call
from apps.core.context import acting_as
from apps.core.models import School
from apps.curriculum.models import Subject, SubjectAllocation
from apps.learners.excel import COLUMNS, build_template, import_learners
from apps.learners.models import Enrolment
from apps.schoolsetup.defaults import seed_school_defaults
from apps.schoolsetup.models import AcademicYear, SchoolClass, Stream, Term
from apps.staff.models import PlannerTask, StaffProfile
from apps.timetable.models import Period, TimetableSlot
from apps.timetable.services import generate_timetable

from .seed_demo import FIRST, LAST

TEACHER = ("p1east", "Agnes", "Nakimuli", "Teacher@2026")
DOS = ("nhdos", "Paul", "Ssebunya", "Studies@2026")
DISTRICTS = [
    ("Wakiso", ["Nansana", "Kira", "Entebbe", "Kasangati", "Gayaza"]),
    ("Kampala", ["Ntinda", "Kawempe", "Makindye", "Nakawa", "Rubaga"]),
    ("Mukono", ["Seeta", "Namilyango", "Goma"]),
]
RELIGIONS = ["Catholic", "Anglican", "Muslim", "Pentecostal", "Seventh-day Adventist"]
OCCUPATIONS = [
    "Teacher",
    "Trader",
    "Farmer",
    "Nurse",
    "Boda boda rider",
    "Mechanic",
    "Accountant",
    "Tailor",
    "Driver",
    "",
]
HEALTH = [
    ("", "Asthma (keeps an inhaler in the bag)"),
    ("Penicillin", ""),
    ("Peanuts", ""),
    ("", "Sickle cell — needs plenty of water"),
    ("", "Epilepsy — on daily medication"),
    ("Dust", "Allergic rhinitis"),
]
PLANNER = [
    (1, "Check homework books for P1 East", "high"),
    (1, "Roll call and follow up on absentees", "normal"),
    (2, "Prepare Literacy I lesson notes for the week", "normal"),
    (3, "Mark Mathematics class exercise", "high"),
    (4, "Meet parents of learners who missed school", "normal"),
    (5, "Update class register and send weekly report to the DOS", "high"),
    (None, "Arrange the reading corner", "low"),
]


class Command(BaseCommand):
    help = "Add sample learners, a class teacher, timetable, exams, marks and attendance to one class."

    def add_arguments(self, parser):
        parser.add_argument("--school", required=True, help="School ID, e.g. NewHope-002")
        parser.add_argument("--class", dest="class_name", default="P1")
        parser.add_argument("--stream", default="East")
        parser.add_argument("--count", type=int, default=50)

    def handle(self, *args, **opts):
        school = School.objects.filter(code__iexact=opts["school"]).first()
        if school is None:
            raise CommandError(f"No school with ID {opts['school']}.")
        random.seed(f"{school.code}-{opts['class_name']}-{opts['stream']}")
        actor = (
            User.objects.filter(memberships__school=school, memberships__roles__role="director").first()
            or User.objects.filter(is_superuser=True).first()
        )
        with acting_as(actor, school), transaction.atomic():
            self.populate(school, actor, opts)

    def say(self, text):
        self.stdout.write(f"  {text}")

    def populate(self, school, actor, opts):
        today = timezone.localdate()
        if not SchoolClass.objects.filter(school=school).exists():
            seed_school_defaults(school, ["nursery", "primary"])
            self.say("loaded the Ugandan primary defaults (sections, classes, subjects, grading)")
        school_class = SchoolClass.objects.filter(school=school, name__iexact=opts["class_name"]).first()
        if school_class is None:
            raise CommandError(f"{school} has no class {opts['class_name']}.")
        stream, _ = Stream.objects.get_or_create(
            school=school, school_class=school_class, name=opts["stream"]
        )
        term = self.current_term(school, today)

        teacher = self.class_teacher(school, school_class, actor)
        self.learners(school, term, school_class, stream, opts["count"])
        learners = [
            e.learner for e in Enrolment.objects.filter(term=term, stream=stream).select_related("learner")
        ]
        self.timetable(school, term, school_class, teacher, actor)
        self.exams(school, term, school_class, learners, teacher, actor, today)
        self.attendance(school, term, school_class, stream, learners, teacher.user, today)
        self.planner(school, teacher.user, school_class, today)
        self.stdout.write(self.style.SUCCESS(f"{stream}: {len(learners)} learners, term {term}."))
        self.account(school, DOS, "dos", "Director of Studies")
        for (username, *_, password), who in ((TEACHER, "Class teacher"), (DOS, "Director of Studies")):
            self.stdout.write(
                f"{who} sign-in: School ID {school.code}, username {username}, password {password}"
            )

    def current_term(self, school, today):
        term = Term.objects.filter(school=school, start_date__lte=today, end_date__gte=today).first()
        if term is None:
            year = AcademicYear.objects.filter(
                school=school, start_date__lte=today, end_date__gte=today
            ).first()
            if year is None:
                year = AcademicYear.objects.create(
                    school=school,
                    name=str(today.year),
                    start_date=datetime.date(today.year, 2, 2),
                    end_date=datetime.date(today.year, 12, 4),
                )
            term = Term.objects.create(
                school=school,
                academic_year=year,
                number=3,
                start_date=today - datetime.timedelta(days=40),
                end_date=today + datetime.timedelta(days=35),
            )
        AcademicYear.objects.filter(school=school).exclude(pk=term.academic_year_id).update(is_current=False)
        if not term.academic_year.is_current:
            term.academic_year.is_current = True
            term.academic_year.save()
        if term.status != "open":
            term.status = "open"
            term.save()
            self.say(f"opened {term} so it is the current term")
        return term

    def account(self, school, spec, role, designation):
        """A staff member with a sign-in and one school-wide role."""
        username, first, last, password = spec
        user = User.objects.filter(username=username).first()
        if user is None:
            user = User(username=username, first_name=first, last_name=last, phone="0772 000 101")
            user.set_password(password)
            user.save()
            self.say(f"created the sign-in {username} ({designation})")
        membership, _ = Membership.objects.get_or_create(
            school=school, user=user, defaults={"title": designation}
        )
        RoleAssignment.objects.get_or_create(
            school=school, membership=membership, role=role, scope_type="school", scope_id=None
        )
        staff, _ = StaffProfile.objects.get_or_create(
            school=school,
            user=user,
            defaults={
                "first_name": first,
                "last_name": last,
                "kind": "teaching",
                "designation": designation,
                "phone": user.phone,
                "registration_number": f"TR{random.randint(10000, 99999)}",
                "max_periods_per_week": 40,
            },
        )
        return staff

    def class_teacher(self, school, school_class, actor):
        staff = self.account(school, TEACHER, "subject_teacher", "Class teacher")
        if school_class.class_teacher_id != staff.id:
            previous = school_class.class_teacher
            school_class.class_teacher = staff
            school_class.save()
            sync_class_teacher_role(school_class, previous, staff)
        # In lower primary one teacher usually teaches the class every subject.
        for subject in self.subjects(school, school_class):
            SubjectAllocation.objects.get_or_create(
                school=school,
                subject=subject,
                school_class=school_class,
                defaults={"teacher": staff, "periods_per_week": 6 if subject.category == "core" else 3},
            )
        return staff

    def subjects(self, school, school_class):
        rows = Subject.objects.filter(school=school, level="primary")
        limited = rows.filter(classes=school_class)
        return list(limited if limited.exists() else rows.filter(classes__isnull=True, category="core"))

    def learners(self, school, term, school_class, stream, count):
        have = Enrolment.objects.filter(term=term, stream=stream).count()
        if have >= count:
            self.say(f"{stream} already has {have} learners")
            return
        book = load_workbook(io.BytesIO(build_template(school.name)))
        sheet = book["Learners"]
        sheet.delete_rows(2)
        keys = [key for key, *_ in COLUMNS]
        birth_year = term.start_date.year - 6
        for index in range(count - have):
            last = random.choice(LAST)
            sex = random.choice("MF")
            district, places = random.choice(DISTRICTS)
            father = f"{random.choice(FIRST)} {last}"
            mother = f"{random.choice(FIRST)} {random.choice(LAST)}"
            allergies, illness = random.choice(HEALTH) if index % 8 == 3 else ("", "")
            row = {
                "first_name": random.choice(FIRST),
                "last_name": last,
                "other_names": random.choice(["", "", "Grace", "Joel", "Mary", "Peter"]),
                "sex": sex,
                "date_of_birth": datetime.date(
                    birth_year - random.choice([0, 0, 1]), random.randint(1, 12), random.randint(1, 28)
                ),
                "lin": f"LIN{random.randint(10_000_000, 99_999_999)}",
                "residence": "Day",
                "religion": random.choice(RELIGIONS),
                "nationality": "Ugandan",
                "district": district,
                "address": f"{random.choice(places)}, {district}",
                "previous_school": random.choice(["", "", "Little Angels Nursery", "Bright Kids Day Care"]),
                "father_name": father,
                "father_phone": f"07{random.choice('0578')}{random.randint(1_000_000, 9_999_999)}",
                "father_occupation": random.choice(OCCUPATIONS),
                "mother_name": mother,
                "mother_phone": f"07{random.choice('0578')}{random.randint(1_000_000, 9_999_999)}",
                "mother_occupation": random.choice(OCCUPATIONS),
                "guardian_name": f"{random.choice(FIRST)} {random.choice(LAST)}" if index % 10 == 7 else "",
                "guardian_relationship": "Aunt" if index % 10 == 7 else "",
                "guardian_phone": f"0756{random.randint(100_000, 999_999)}" if index % 10 == 7 else "",
                "allergies": allergies,
                "medical_conditions": illness,
                "special_needs": "Wears glasses — sit near the board" if index == 11 else "",
            }
            sheet.append([row.get(key, "") for key in keys])
        upload = io.BytesIO()
        book.save(upload)
        upload.seek(0)
        upload.name = "sample-learners.xlsx"
        result = import_learners(school, upload, term, school_class, stream)
        self.say(
            f"enrolled {result['created']} learners via the Excel import ({len(result['errors'])} skipped)"
        )

    def timetable(self, school, term, school_class, teacher, actor):
        if not Period.objects.filter(school=school).exists():
            times = [
                ("08:00", "08:40"),
                ("08:40", "09:20"),
                ("09:20", "10:00"),
                ("10:00", "10:30", "Break"),
                ("10:30", "11:10"),
                ("11:10", "11:50"),
                ("11:50", "12:30"),
                ("12:30", "14:00", "Lunch"),
                ("14:00", "14:40"),
                ("14:40", "15:20"),
            ]
            number = 0
            for order, row in enumerate(times):
                is_break = len(row) == 3
                number += 0 if is_break else 1
                Period.objects.create(
                    school=school,
                    name=row[2] if is_break else f"Period {number}",
                    order=order,
                    start_time=datetime.time.fromisoformat(row[0]),
                    end_time=datetime.time.fromisoformat(row[1]),
                    is_break=is_break,
                )
        if not TimetableSlot.objects.filter(term=term, school_class=school_class).exists():
            generate_timetable(school, term, [school_class.id])
            self.say("generated the class timetable")
        if term.timetable_published_at is None:
            term.timetable_published_at, term.timetable_published_by = timezone.now(), actor
            term.save()
            self.say("published the timetable")

    def exams(self, school, term, school_class, learners, teacher, actor, today):
        plan = [
            ("bot", "Beginning of Term 3", 20, term.start_date + datetime.timedelta(days=7)),
            ("mot", "Mid-term 3", 30, today - datetime.timedelta(days=12)),
            ("eot", "End of Term 3", 50, term.end_date - datetime.timedelta(days=10)),
        ]
        exams = {}
        for kind, name, weight, start in plan:
            exam = Exam.objects.filter(term=term, kind=kind).first()
            if exam is None:
                exam = Exam.objects.create(
                    school=school,
                    term=term,
                    name=name,
                    kind=kind,
                    weight=weight,
                    start_date=start,
                    end_date=start + datetime.timedelta(days=3),
                )
            exam.classes.add(school_class)
            prepare_sheets(exam, school_class)
            exams[kind] = exam
        ability = {learner.id: random.gauss(66, 12) for learner in learners}
        for kind in ("bot", "mot"):
            for sheet in MarkSheet.objects.filter(exam=exams[kind], school_class=school_class):
                if sheet.marks.exists():
                    continue
                for learner in learners:
                    score = max(8, min(100, round(ability[learner.id] + random.gauss(0, 8))))
                    Mark.objects.create(school=school, mark_sheet=sheet, learner=learner, score=score)
                sheet.status = "approved" if kind == "bot" else "submitted"
                sheet.submitted_by = teacher.user
                sheet.submitted_at = timezone.now()
                sheet.save()
        eot = exams["eot"]
        if not eot.schedule.exists():
            day = eot.start_date
            for index, subject in enumerate(self.subjects(school, school_class)):
                while day.weekday() >= 5:
                    day += datetime.timedelta(days=1)
                morning = index % 2 == 0
                ExamSchedule.objects.create(
                    school=school,
                    exam=eot,
                    subject=subject,
                    school_class=school_class,
                    date=day,
                    start_time=datetime.time(9 if morning else 11, 0),
                    end_time=datetime.time(10 if morning else 12, 30),
                    invigilator=teacher,
                )
                if not morning:
                    day += datetime.timedelta(days=1)
            eot.schedule_published_at = timezone.now()
            eot.save()
            self.say("set and published the end-of-term exam timetable")

    def attendance(self, school, term, school_class, stream, learners, user, today):
        for days_ago in range(14, -1, -1):
            date = today - datetime.timedelta(days=days_ago)
            if date.weekday() >= 5 or date < term.start_date:
                continue
            records = [
                {"learner": l.id, "status": "absent" if random.random() < 0.05 else "present"}
                for l in learners
            ]
            save_roll_call(school, user, term, date, school_class, stream, records)

    def planner(self, school, user, school_class, today):
        monday = today - datetime.timedelta(days=today.weekday())
        if PlannerTask.objects.filter(user=user, week_start=monday).exists():
            return
        for week, done_until in ((monday - datetime.timedelta(days=7), 7), (monday, today.weekday())):
            for day, title, priority in PLANNER:
                PlannerTask.objects.create(
                    school=school,
                    user=user,
                    week_start=week,
                    day=day,
                    title=title,
                    priority=priority,
                    school_class=school_class,
                    done=day is not None and day <= done_until and random.random() < 0.85,
                    done_at=timezone.now() if day is not None and day <= done_until else None,
                )
        self.say("added planner items for last week and this week")
